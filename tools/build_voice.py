#!/usr/bin/env python3
"""Human-sounding narration for a short.

Reads lines.txt (one narration line per row), synthesizes each line with a neural TTS,
trims the silence, and lays the lines on one timeline with fixed gaps. Writes, in the folder you run it from:

  lines/NN.wav   one clip per line (cached; re-synthesized only when text or voice settings change)
  voice.wav      the full narration, 48 kHz mono, for the mix (gain only, no EQ or compression)
  lines.json     start/end per line, plus the speech segments inside each line
  words.json     word start/end times, {"w", "s", "e"} per word, in seconds on the voice timeline

Backends:
  edge        Microsoft neural voices. Free, no key. Default. Gives exact word times.
  elevenlabs  Most natural. Needs ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID. Gives word times.
  openai      gpt-4o-mini-tts. Needs OPENAI_API_KEY. Steerable with --style. No word times.
  say         macOS built-in voice (the old pipeline). No word times.

When a backend gives no word times, words.json is estimated from each line's length.
Those timings are rough, so hand-fix them if the mix ducking or the shot timing depends on them.

Usage (inside the project's voice/ folder, next to lines.txt):
  python3 build_voice.py
  python3 build_voice.py --voice ko-KR-InJoonNeural --rate "-5%"
  python3 build_voice.py --backend elevenlabs
  python3 build_voice.py --backend openai --voice coral --style "차분하고 따뜻한 다큐 내레이터 톤으로"
  python3 build_voice.py --gaps 0.5,0.4,0.6,0      # per-line gaps in seconds (last value unused)
"""
import argparse, asyncio, base64, json, os, subprocess, sys, urllib.error, urllib.request, wave

import numpy as np

SR = 48000
START, TAIL = 0.4, 1.6          # silence before the first line and after the last line
DEFAULT_GAP = 0.4               # seconds between lines
PAD_IN, PAD_OUT = 0.02, 0.06    # keep this much around each trimmed line
EDGE_VOICE = "ko-KR-InJoonNeural"  # male default; also: ko-KR-SunHiNeural (female), ko-KR-HyunsuMultilingualNeural
OPENAI_VOICE = "coral"
SAY_VOICE = "Yuna"


# ---------------------------------------------------------------- audio helpers
def to_wav48(src, dst):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-ac", "1", "-ar", str(SR), dst], check=True)


def read_pcm(path):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64) / 32768


def env(x, win=0.02):
    n = int(win * SR)
    k = len(x) // n
    return np.sqrt((x[: k * n].reshape(k, n) ** 2).mean(1)), n


# ---------------------------------------------------------------- backends
# Each backend writes its own file (base + extension) and returns (path, words or None).
# words are in seconds from the start of that file.

async def _edge_stream(text, voice, rate, pitch, path):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    words = []
    with open(path, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7              # edge-tts counts 100 ns ticks
                words.append({"w": ch["text"], "s": s, "e": s + ch["duration"] / 1e7})
    return words


def synth_edge(text, base, args):
    path = base + ".mp3"
    words = asyncio.run(_edge_stream(text, args.voice, args.rate, args.pitch, path))
    return path, (words or None)


def _post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} from {url}: {e.read().decode('utf-8', 'replace')[:300]}")


def words_from_chars(al):
    """Group ElevenLabs character timings into words (split on whitespace)."""
    words, cur, s, e = [], "", None, None
    for c, a, b in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if c.isspace():
            if cur:
                words.append({"w": cur, "s": s, "e": e})
                cur = ""
        else:
            if not cur:
                s = a
            cur += c
            e = b
    if cur:
        words.append({"w": cur, "s": s, "e": e})
    return words


def synth_elevenlabs(text, base, args):
    key, vid = os.environ.get("ELEVENLABS_API_KEY"), os.environ.get("ELEVENLABS_VOICE_ID")
    if not key or not vid:
        sys.exit("elevenlabs needs ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in the environment")
    body = {"text": text, "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.2, "use_speaker_boost": True}}
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_128"
    data = json.loads(_post(url, body, {"xi-api-key": key, "Content-Type": "application/json"}))
    path = base + ".mp3"
    with open(path, "wb") as f:
        f.write(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment")
    return path, (words_from_chars(al) if al else None)


def synth_openai(text, base, args):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("openai needs OPENAI_API_KEY in the environment")
    body = {"model": "gpt-4o-mini-tts", "voice": args.voice, "input": text, "response_format": "wav"}
    if args.style:
        body["instructions"] = args.style
    audio = _post("https://api.openai.com/v1/audio/speech", body,
                  {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    path = base + ".wav"
    with open(path, "wb") as f:
        f.write(audio)
    return path, None


def synth_say(text, base, args):
    path = base + ".aiff"
    cmd = ["say", "-v", args.voice, "-o", path]
    if args.say_rate:
        cmd += ["-r", str(args.say_rate)]  # words per minute (macOS say default is about 175)
    subprocess.run(cmd + [text], check=True)  # to_wav48() resamples afterwards
    return path, None


SYNTH = {"edge": synth_edge, "elevenlabs": synth_elevenlabs, "openai": synth_openai, "say": synth_say}
DEFAULT_VOICE = {"edge": EDGE_VOICE, "elevenlabs": None, "openai": OPENAI_VOICE, "say": SAY_VOICE}


def estimate_words(text, dur):
    """No word times from the backend: split the clip evenly by word length."""
    ws = text.split()
    tot = sum(len(w) for w in ws) or 1
    out, t = [], 0.0
    for w in ws:
        d = dur * len(w) / tot
        out.append({"w": w, "s": t, "e": t + d})
        t += d
    return out


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", default="edge", choices=list(SYNTH))
    ap.add_argument("--voice", default=None, help="voice name for the backend (default depends on backend)")
    ap.add_argument("--rate", default="+0%", help="edge only: speaking rate, e.g. -5%% slower, +5%% faster")
    ap.add_argument("--pitch", default="+0Hz", help="edge only: pitch shift, e.g. -20Hz")
    ap.add_argument("--style", default=None, help="openai only: free-text delivery instructions")
    ap.add_argument("--gap", type=float, default=DEFAULT_GAP, help="seconds between lines")
    ap.add_argument("--gaps", default=None, help="comma-separated per-line gaps (overrides --gap)")
    ap.add_argument("--force", action="store_true", help="re-synthesize every line")
    ap.add_argument("--say-rate", type=int, default=None, help="say only: words per minute, e.g. 240")
    args = ap.parse_args()
    if args.voice is None:
        args.voice = DEFAULT_VOICE[args.backend]
    if args.backend == "elevenlabs" and not args.voice:
        args.voice = os.environ.get("ELEVENLABS_VOICE_ID", "")

    texts = [t.strip() for t in open("lines.txt", encoding="utf-8").read().split("\n") if t.strip()]
    gaps = [float(g) for g in args.gaps.split(",")] if args.gaps else [args.gap] * len(texts)
    if len(gaps) < len(texts):
        sys.exit(f"--gaps has {len(gaps)} values for {len(texts)} lines")
    os.makedirs("lines", exist_ok=True)

    out, lines, all_words, t = [], [], [], START
    for i, text in enumerate(texts):
        base = f"lines/{i + 1:02d}"
        cache = base + ".json"
        key = {"backend": args.backend, "voice": args.voice, "rate": args.rate, "pitch": args.pitch,
               "style": args.style, "text": text}
        cached = None
        if not args.force and os.path.exists(cache) and os.path.exists(base + ".wav"):
            cached = json.load(open(cache, encoding="utf-8"))
        if cached and cached.get("key") == key:
            words = cached["words"]
            print(f"line {i + 1}: cached")
        else:
            raw_path, words = SYNTH[args.backend](text, base, args)
            to_wav48(raw_path, base + ".wav")
            json.dump({"key": key, "words": words}, open(cache, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"line {i + 1}: synthesized ({args.backend})")

        x = read_pcm(base + ".wav")
        e, n = env(x)
        on = np.where(e > 0.01)[0]
        if len(on) == 0:
            sys.exit(f"line {i + 1} came out silent: {base}.wav")
        a, b = on[0] * n, (on[-1] + 1) * n
        a0 = max(0, a - int(PAD_IN * SR))
        off = a0 / SR
        x = x[a0: b + int(PAD_OUT * SR)]
        d = len(x) / SR

        if words:
            lw = [{"w": w["w"], "s": min(max(w["s"] - off, 0.0), d), "e": min(max(w["e"] - off, 0.0), d)} for w in words]
            estimated = False
        else:
            lw = estimate_words(text, d)
            estimated = True
        for w in lw:
            all_words.append({"w": w["w"], "s": round(t + w["s"], 3), "e": round(t + w["e"], 3)})

        # phrase segments: speech runs separated by >= 0.12 s of silence
        e2, n2 = env(x)
        sp = e2 > 0.008
        segs, j = [], 0
        while j < len(sp):
            if sp[j]:
                k = j
                while k < len(sp) and (sp[k] or (k + 6 < len(sp) and sp[k:k + 6].any())):
                    k += 1
                segs.append([round(t + j * n2 / SR, 3), round(t + k * n2 / SR, 3)])
                j = k
            else:
                j += 1

        lines.append({"i": i + 1, "text": text, "s": round(t, 3), "e": round(t + d, 3),
                      "segs": segs, "words_estimated": estimated})
        out.append((t, x))
        t += d + gaps[i]

    total = t - gaps[len(texts) - 1] + TAIL
    buf = np.zeros(int(total * SR))
    for s, x in out:
        buf[int(s * SR): int(s * SR) + len(x)] += x
    buf *= 0.89 / np.abs(buf).max()
    with wave.open("voice.wav", "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((buf * 32767).astype(np.int16).tobytes())
    json.dump({"total": round(total, 3), "lines": lines}, open("lines.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump(all_words, open("words.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    est = sum(1 for l in lines if l["words_estimated"])
    print(f"voice.wav {total:.2f} s ({int(round(total * 30))} frames at 30 fps), {len(lines)} lines, "
          f"{len(all_words)} words" + (f", {est} line(s) with estimated word times" if est else ""))


if __name__ == "__main__":
    main()
