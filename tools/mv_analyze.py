#!/usr/bin/env python3
"""Analyze a song for the music-video template (numpy + ffmpeg only).

Writes <project>/data/analysis.json:
  fps (30), duration, bpm, beats [s], downbeats [s], energy/low/mid/high [one value per video frame, 0..1]
and, with --draft (or when data/mv.json has no sections), drafts beat-aligned sections into data/mv.json.

Usage: python tools/mv_analyze.py projects/<name> [--bpm 120] [--draft] [--bars 8]
"""
import argparse, json, os, subprocess

import numpy as np

SR = 22050
HOP = 256            # analysis hop (~86 fps) for tempo; features are resampled to the video fps
WIN = 2048
VFPS = 30


def decode(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def stft_features(x):
    n = 1 + max(0, (len(x) - WIN) // HOP)
    win = np.hanning(WIN)
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    bands = {"low": (freqs >= 20) & (freqs < 250), "mid": (freqs >= 250) & (freqs < 2000), "high": (freqs >= 2000) & (freqs < 8000)}
    out = {k: np.zeros(n) for k in ["rms", "flux", "low", "mid", "high"]}
    prev = None
    for a in range(0, n, 2048):  # chunked to keep memory small
        b = min(n, a + 2048)
        idx = np.arange(a, b)[:, None] * HOP + np.arange(WIN)[None, :]
        frames = x[idx] * win
        mag = np.abs(np.fft.rfft(frames, axis=1))
        out["rms"][a:b] = np.sqrt((frames ** 2).mean(1))
        for k, m in bands.items():
            out[k][a:b] = np.log1p(mag[:, m].sum(1))
        lm = np.log1p(mag)
        d = np.diff(np.vstack([lm[:1] if prev is None else prev[None, :], lm]), axis=0)
        out["flux"][a:b] = np.maximum(d, 0).sum(1)
        prev = lm[-1]
    return out


def norm(v, p=95):
    v = v - np.percentile(v, 5)
    top = np.percentile(v, p) + 1e-9
    return np.clip(v / top, 0, 1)


def tempo_and_beats(flux, afps, bpm_hint=None):
    env = flux - np.convolve(flux, np.ones(16) / 16, mode="same")
    env = np.maximum(env, 0)
    env /= env.max() + 1e-9
    if bpm_hint:
        bpm = float(bpm_hint)
    else:
        e = env - env.mean()
        n = len(e)
        nfft = 1 << int(np.ceil(np.log2(2 * n)))
        spec = np.fft.rfft(e, nfft)
        ac = np.fft.irfft(spec * np.conj(spec), nfft)[:n]
        ac /= ac[0] + 1e-9
        lags = np.arange(n)
        # comb score: the true beat period also lines up at 2x, 3x and 4x its lag, a 2:3 or 3:2 "ghost" tempo does not
        cands = np.arange(70.0, 180.01, 0.25)
        scores = []
        for b in cands:
            p = 60 * afps / b
            s = sum(np.interp(k * p, lags, ac) / k ** 0.5 for k in range(1, 5) if k * p < n - 1)
            scores.append(s * np.exp(-0.5 * (np.log2(b / 115) / 1.2) ** 2))  # mild prior toward common tempi
        bpm = float(cands[int(np.argmax(scores))])
    period = 60 * afps / bpm
    # best phase on the beat grid
    phases = np.arange(0, period, 0.5)
    best, best_s = 0.0, -1
    for ph in phases:
        pos = np.arange(ph, len(env) - 1, period).astype(int)
        s = env[pos].sum()
        if s > best_s:
            best, best_s = ph, s
    beats = np.arange(best, len(env) - 1, period) / afps
    # downbeat: which of the 4 beat offsets carries the most low-end onset energy
    return round(bpm, 2), beats


def draft_sections(duration, beats, energy, bars=8):
    """Beat-aligned blocks of `bars` bars, labeled by energy. First block: title, last: credits."""
    if len(beats) < 8:
        edges = list(np.arange(0, duration, 12.0)) + [duration]
    else:
        step = 4 * bars
        edges = [0.0] + [float(beats[i]) for i in range(step, len(beats), step)]
        if duration - edges[-1] < 6 and len(edges) > 1:
            edges.pop()
        edges.append(duration)
    secs = []
    cycle = ["visualizer", "pulse", "lyrics", "visualizer"]
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        e = float(np.mean(energy[int(a * VFPS):max(int(a * VFPS) + 1, int(b * VFPS))]))
        if i == 0:
            kind = "title"
        elif i == len(edges) - 2:
            kind = "credits"
        elif e > 0.62:
            kind = "visualizer"
        else:
            kind = cycle[i % len(cycle)]
        secs.append({"start": round(a, 3), "end": round(b, 3), "kind": kind, "energy": round(e, 3)})
    return secs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project")
    ap.add_argument("--bpm", type=float, default=None, help="known tempo (skips detection)")
    ap.add_argument("--draft", action="store_true", help="rewrite sections in data/mv.json")
    ap.add_argument("--bars", type=int, default=8, help="bars per drafted section")
    a = ap.parse_args()

    proj = os.path.abspath(a.project)
    song = os.path.join(proj, "public", "song.wav")
    x = decode(song)
    duration = len(x) / SR
    f = stft_features(x)
    afps = SR / HOP
    bpm, beats = tempo_and_beats(f["flux"], afps, a.bpm)

    # resample features to one value per video frame
    n_v = int(np.ceil(duration * VFPS))
    ta = np.arange(len(f["rms"])) / afps + WIN / 2 / SR
    tv = np.arange(n_v) / VFPS
    feat = {k: norm(np.interp(tv, ta, f[k])) for k in ["rms", "low", "mid", "high"]}
    energy = np.convolve(feat["rms"], np.ones(5) / 5, mode="same")

    analysis = {
        "fps": VFPS, "duration": round(duration, 3), "bpm": bpm,
        "beats": [round(float(b), 3) for b in beats],
        "downbeats": [round(float(b), 3) for b in beats[::4]],
        "energy": [round(float(v), 3) for v in energy],
        "low": [round(float(v), 3) for v in feat["low"]],
        "mid": [round(float(v), 3) for v in feat["mid"]],
        "high": [round(float(v), 3) for v in feat["high"]],
    }
    os.makedirs(os.path.join(proj, "data"), exist_ok=True)
    json.dump(analysis, open(os.path.join(proj, "data", "analysis.json"), "w"), separators=(",", ":"))

    mv_path = os.path.join(proj, "data", "mv.json")
    mv = json.load(open(mv_path, encoding="utf-8")) if os.path.exists(mv_path) else {}
    if a.draft or not mv.get("sections"):
        mv["sections"] = draft_sections(duration, beats, energy, a.bars)
        mv.setdefault("title", "Untitled")
        mv.setdefault("artist", "")
        mv.setdefault("theme", "neon")
        mv.setdefault("lyrics", [])
        json.dump(mv, open(mv_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"drafted {len(mv['sections'])} sections into data/mv.json")
    print(f"analysis: {duration:.1f} s, {bpm} BPM, {len(beats)} beats")


if __name__ == "__main__":
    main()
