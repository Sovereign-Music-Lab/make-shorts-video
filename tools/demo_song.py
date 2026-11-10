#!/usr/bin/env python3
"""Generate an original demo song (code-synthesized, no samples) to try the music-video routine.

Structure at 120 BPM: intro (pad) -> verse (drums + bass) -> chorus (full + lead) -> outro.
Usage: python tools/demo_song.py out.wav [--seconds 48]
"""
import argparse, os, subprocess, sys, wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from music import SR, Score, mtof  # noqa: E402,F401


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=48.0)
    a = ap.parse_args()

    bpm, beat = 120, 0.5
    bar = beat * 4
    sc = Score(a.seconds, seed=3)
    chords = [(45, 52, 57, 60), (41, 48, 53, 57), (48, 55, 60, 64), (43, 50, 55, 59)]  # Am F C G
    n_bars = int(a.seconds / bar)
    for m in range(n_bars):
        t0 = m * bar
        c = chords[m % 4]
        part = "intro" if m < 4 else "verse" if m < 12 else "chorus" if m < n_bars - 2 else "outro"
        sc.add(t0, sc.pad(c, 0.06 if part != "chorus" else 0.08, bar * 1.02))
        if part in ("verse", "chorus"):
            for b in range(4):
                tb = t0 + b * beat
                sc.add(tb, sc.kick(0.7 if part == "chorus" else 0.55))
                if b in (1, 3):
                    sc.add(tb, sc.snare(0.45))
                sc.add(tb + beat / 2, sc.hat(0.08))
                sc.add(tb, sc.bass(c[0] - 12, 0.16))
                sc.add(tb + beat / 2, sc.bass(c[0] - 12, 0.1))
        if part == "chorus":
            sc.add(t0, sc.brass([n + 12 for n in c[1:]], 0.07, bar * 0.9))
            for i, note in enumerate([72, 76, 79, 76, 74, 72, 74, 76]):
                sc.add(t0 + i * beat / 2, sc.flute(note + (c[0] - 45), 0.06, beat * 0.6))
            if m % 4 == 0:
                sc.add(t0, sc.crash(0.25))
    y = sc.buf / (np.abs(sc.buf).max() + 1e-9) * 0.9
    y *= np.clip((a.seconds - np.arange(sc.n) / SR) / 2.0, 0, 1)
    tmp = a.out + ".raw.wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-af", "loudnorm=I=-14:TP=-1.5", "-ac", "2", "-ar", str(SR), a.out], check=True)
    os.remove(tmp)
    print(f"demo song: {a.out} ({a.seconds:.0f} s, {bpm} BPM)")


if __name__ == "__main__":
    main()
