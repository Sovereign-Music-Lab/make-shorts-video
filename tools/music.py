#!/usr/bin/env python3
"""Synthesize an original background score for a Short and mix it under the narration.

Reads   <project>/voice/lines.json and <project>/voice/voice.wav
Writes  <project>/public/mix.wav  (48 kHz stereo, loudness-normalized to -14 LUFS)

Moods:
  sacred   slow organ-like pad (Dm-Bb-F-C) and a soft bell on every line. Reverent documentary tone.
  march    108 BPM driving march (Am-F-C-G): drums, bass, brass stabs on scene cuts, flute motif, A-major landing.
  calm     80 BPM warm pad with plucked arpeggios (C-G-Am-F). Gentle explainer tone.
  tension  90 BPM low drone, pulse and ticking hats (Dm-Bb-Gm-A). Investigations, conflicts, disasters.
  none     narration only.

Usage: python tools/music.py projects/<name> --mood sacred
Everything is generated from code: no samples, no copyrighted material.
"""
import argparse, json, os, subprocess, wave

import numpy as np

SR = 48000


def mtof(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


class Score:
    def __init__(self, total, seed=11):
        self.total = total
        self.n = int(round(total * SR))
        self.buf = np.zeros(self.n)
        self.rng = np.random.default_rng(seed)

    def add(self, start, sig, gain=1.0):
        i0 = int(round(start * SR))
        if i0 < 0 or i0 >= self.n:
            return
        k = min(len(sig), self.n - i0)
        self.buf[i0:i0 + k] += gain * sig[:k]

    # ---- instruments
    def kick(self, v):
        tt = np.arange(int(0.45 * SR)) / SR
        f = 42 + 90 * np.exp(-tt / 0.035)
        return v * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / 0.12)

    def snare(self, v):
        tt = np.arange(int(0.25 * SR)) / SR
        nz = np.diff(self.rng.standard_normal(len(tt)), prepend=0.0)
        return v * (0.6 * nz * np.exp(-tt / 0.085) + 0.5 * np.sin(2 * np.pi * 185 * tt) * np.exp(-tt / 0.06))

    def hat(self, v):
        tt = np.arange(int(0.07 * SR)) / SR
        return v * np.diff(self.rng.standard_normal(len(tt)), prepend=0.0) * np.exp(-tt / 0.018)

    def crash(self, v, dur=2.6):
        tt = np.arange(int(dur * SR)) / SR
        nz = np.diff(np.diff(self.rng.standard_normal(len(tt)), prepend=0.0), prepend=0.0)
        return v * nz * np.exp(-tt / 0.75) * np.clip(tt / 0.004, 0, 1)

    def bass(self, m, v, dur=0.2):
        tt = np.arange(int(dur * SR)) / SR
        f = mtof(m)
        return v * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt / 0.1) * np.clip(tt / 0.005, 0, 1)

    def brass(self, midis, v, dur, attack=0.05, release=0.3):
        tt = np.arange(int(dur * SR)) / SR
        s = np.zeros_like(tt)
        for m in midis:
            f = mtof(m)
            for k in range(1, 11):
                s += np.sin(2 * np.pi * f * k * tt) / (k ** 1.3)
        s /= np.abs(s).max() + 1e-9
        return v * s * np.clip(tt / attack, 0, 1) * np.clip((dur - tt) / release, 0, 1)

    def pad(self, midis, v, dur, swell=0.8):
        tt = np.arange(int(dur * SR)) / SR
        s = np.zeros_like(tt)
        for m in midis:
            f = mtof(m)
            vib = 1 + 0.003 * np.sin(2 * np.pi * 5.0 * tt)
            s += np.sin(2 * np.pi * f * vib * tt) + 0.5 * np.sin(2 * np.pi * f * 1.005 * tt)
        return v * s * np.clip(tt / swell, 0, 1) * np.clip((dur - tt) / swell, 0, 1) / len(midis)

    def organ(self, midis, v, dur, fade=2.0):
        tt = np.arange(int(dur * SR)) / SR
        s = np.zeros_like(tt)
        for m in midis:
            f = mtof(m)
            s += np.sin(2 * np.pi * f * tt) + 0.6 * np.sin(4 * np.pi * f * tt) + 0.25 * np.sin(6 * np.pi * f * tt)
            s += 0.5 * np.sin(2 * np.pi * f * 1.003 * tt)
        return v * s * np.clip(tt / fade, 0, 1) * np.clip((dur - tt) / fade, 0, 1)

    def bell(self, v, base=523.25):
        tt = np.arange(int(4.0 * SR)) / SR
        s = np.zeros_like(tt)
        for ratio, amp, dec in [(1.0, 1.0, 1.6), (2.76, 0.45, 1.1), (5.4, 0.2, 0.7)]:
            s += amp * np.sin(2 * np.pi * base * ratio * tt) * np.exp(-dec * tt)
        return v * s

    def pluck(self, m, v, dur=0.9):
        tt = np.arange(int(dur * SR)) / SR
        f = mtof(m)
        s = np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(4 * np.pi * f * tt) + 0.15 * np.sin(6 * np.pi * f * tt)
        return v * s * np.exp(-tt / 0.35) * np.clip(tt / 0.004, 0, 1)

    def flute(self, m, v, dur):
        tt = np.arange(int(dur * SR)) / SR
        f = mtof(m)
        s = np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt) + 0.08 * np.sin(6 * np.pi * f * tt)
        return v * s * np.clip(tt / 0.06, 0, 1) * np.exp(-tt / (dur * 0.7))

    def drone(self, m, v, dur):
        tt = np.arange(int(dur * SR)) / SR
        f = mtof(m)
        s = np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.5 * tt) + 0.3 * np.sin(2 * np.pi * f * 2.003 * tt)
        return v * s * (0.8 + 0.2 * np.sin(2 * np.pi * 0.15 * tt)) * np.clip(tt / 2.0, 0, 1) * np.clip((dur - tt) / 2.0, 0, 1)


def sacred(sc, lines):
    chords = [(50, 57, 62, 65), (46, 53, 58, 62), (41, 48, 53, 57), (48, 55, 60, 64)]  # Dm Bb F C
    seg = 8.0
    k = 0
    while k * seg < sc.total:
        sc.add(k * seg, sc.organ(chords[k % 4], 0.08, seg + 2.0))
        k += 1
    for l in lines:
        sc.add(l["s"], sc.bell(0.07))
    trem = 0.85 + 0.15 * np.sin(2 * np.pi * 0.25 * np.arange(sc.n) / SR)
    sc.buf *= trem


def march(sc, lines):
    bpm = 108
    beat = 60.0 / bpm
    bar = beat * 4
    chords = [
        {"brass": [57, 60, 64], "bass": 45, "pad": [45, 52, 57, 60]},
        {"brass": [53, 57, 60], "bass": 41, "pad": [41, 48, 53, 57]},
        {"brass": [60, 64, 67], "bass": 48, "pad": [48, 55, 60, 64]},
        {"brass": [55, 59, 62], "bass": 43, "pad": [43, 50, 55, 59]},
    ]
    n_bars = int(sc.total / bar) + 1
    for m in range(n_bars):
        sc.add(m * bar, sc.pad(chords[m % 4]["pad"], 0.05, bar * 1.02))
    sc.add(0.0, sc.brass(chords[0]["brass"] + [69], 0.16, 2.6))
    sc.add(0.0, sc.crash(0.25))
    for k, line in enumerate(lines):
        cut = max(0.0, line["s"] - 0.25)
        sc.add(cut, sc.brass(chords[k % 4]["brass"], 0.12, 1.6))
        if k % 2 == 0 and k > 0:
            sc.add(cut, sc.crash(0.2))
    for m in range(1, n_bars):
        t0 = m * bar
        c = chords[m % 4]
        for b in range(4):
            tb = t0 + b * beat
            if b in (0, 2):
                sc.add(tb, sc.kick(0.62))
            if b in (1, 3):
                sc.add(tb, sc.snare(0.42))
            sc.add(tb, sc.hat(0.09))
            sc.add(tb + beat / 2, sc.hat(0.07))
            sc.add(tb, sc.bass(c["bass"], 0.14))
            sc.add(tb + beat / 2, sc.bass(c["bass"], 0.1))
        sc.add(t0, sc.brass(c["brass"], 0.085, bar * 0.85))
        sc.add(t0 + 2 * beat, sc.brass(c["brass"], 0.06, beat * 0.8, attack=0.02, release=0.1))
    for m in range(4, n_bars, 4):
        if m * bar >= sc.total - 4:
            break
        for i, note in enumerate([76, 81, 84, 86]):
            sc.add(m * bar + i * beat, sc.flute(note, 0.07, beat * 1.4))
    t_end = max(0.0, lines[-1]["s"] - 0.25)
    sc.add(t_end, sc.brass([57, 61, 64, 69], 0.2, sc.total - t_end + 0.5, release=0.8))
    sc.add(t_end, sc.crash(0.3, dur=4.0))


def calm(sc, lines):
    bpm = 80
    beat = 60.0 / bpm
    bar = beat * 4
    chords = [(48, 52, 55, 60), (43, 47, 50, 55), (45, 48, 52, 57), (41, 45, 48, 53)]  # C G Am F
    n_bars = int(sc.total / bar) + 1
    for m in range(n_bars):
        c = chords[m % 4]
        sc.add(m * bar, sc.pad(c, 0.06, bar * 1.05, swell=1.2))
        arp = [c[0] + 12, c[1] + 12, c[2] + 12, c[3] + 12, c[2] + 12, c[1] + 12, c[2] + 12, c[3] + 12]
        for i, note in enumerate(arp):
            sc.add(m * bar + i * beat / 2, sc.pluck(note, 0.05))
        sc.add(m * bar, sc.bass(c[0] - 12, 0.08, dur=bar * 0.9))


def tension(sc, lines):
    bpm = 90
    beat = 60.0 / bpm
    bar = beat * 4
    roots = [38, 34, 31, 33]  # D Bb G A
    n_bars = int(sc.total / bar) + 1
    sc.add(0.0, sc.drone(26, 0.09, sc.total))
    for m in range(n_bars):
        r = roots[m % 4]
        for b in range(8):
            sc.add(m * bar + b * beat / 2, sc.bass(r, 0.09, dur=0.16))
        for b in range(16):
            sc.add(m * bar + b * beat / 4, sc.hat(0.035 if b % 4 else 0.06))
        if m % 2 == 1:
            sc.add(m * bar, sc.kick(0.45))
    for k, line in enumerate(lines):
        if k > 0:
            sc.add(max(0.0, line["s"] - 0.25), sc.kick(0.5))


MOODS = {"sacred": sacred, "march": march, "calm": calm, "tension": tension}


def read_wav(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32768


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("project", help="project folder, e.g. projects/my-short")
    ap.add_argument("--mood", default="sacred", choices=list(MOODS) + ["none"])
    ap.add_argument("--music-db", type=float, default=0.0, help="music level change in dB (e.g. -3 quieter)")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    proj = os.path.abspath(args.project)
    meta = json.load(open(os.path.join(proj, "voice", "lines.json"), encoding="utf-8"))
    total, lines = meta["total"], meta["lines"]
    sc = Score(total, seed=args.seed)
    voice = read_wav(os.path.join(proj, "voice", "voice.wav"))
    vn = np.zeros(sc.n)
    vn[: min(sc.n, len(voice))] = voice[: min(sc.n, len(voice))]

    t = np.arange(sc.n) / SR
    if args.mood == "none":
        mix = vn
    else:
        MOODS[args.mood](sc, lines)
        music = sc.buf / (np.abs(sc.buf).max() + 1e-9) * 0.35 * 10 ** (args.music_db / 20)
        win = int(0.06 * SR)
        env = np.sqrt(np.convolve(vn ** 2, np.ones(win) / win, mode="same"))
        env /= env.max() + 1e-9
        duck = 1.0 - 0.5 * np.clip(env * 3.0, 0, 1)   # about -6 dB under speech
        mix = music * duck * np.clip(t / 1.0, 0, 1) + vn
    mix *= np.clip((total - t) / 2.0, 0, 1)
    mix *= 0.9 / (np.abs(mix).max() + 1e-9)

    os.makedirs(os.path.join(proj, "out"), exist_ok=True)
    os.makedirs(os.path.join(proj, "public"), exist_ok=True)
    raw = os.path.join(proj, "out", "mix_raw.wav")
    with wave.open(raw, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())
    out = os.path.join(proj, "public", "mix.wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-ac", "2", "-ar", str(SR), out], check=True)
    print(f"music: {args.mood}, wrote {out} ({total:.2f} s)")


if __name__ == "__main__":
    main()
