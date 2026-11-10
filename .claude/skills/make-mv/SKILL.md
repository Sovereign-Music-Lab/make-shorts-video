---
name: make-mv
description: Make a landscape 1920x1080 music video from the user's own song with this repo's mkmv CLI - beat-synced Remotion motion graphics (visualizer, pulse rings, lyrics, text), optional local AI realistic clips (FastMetal 720p upscaled to 1080p) and an LLM shot plan. Use when the user asks for a 뮤직비디오/뮤비/music video, a lyric video or a visualizer for a song.
---

# make-mv

Rules: `AGENTS.md` (section "Music videos"). Everything runs locally from the repo root.

## Steps
1. `./mkmv doctor`. Remotion missing → `./install.sh --yes`. AI engine is optional (`./install_ai.sh`, Apple Silicon, ~20 GB).
2. Ask for the song file if you don't have it (wav/mp3/m4a/flac), plus title, artist, lyrics and a visual concept.
   Only use audio the user owns or has rights to.
3. `./mkmv new <name> --song <file> --title "…" --artist "…" [--theme neon|gold|mono|sunset] [--bpm N]`
   - Check the detected BPM in the output. If it is half/double or 2:3 off, rerun `./mkmv analyze <name> --bpm <true> --draft`.
4. Lyrics (optional): write an LRC file (`[mm:ss.xx] line`) when times are known, otherwise plain lines; `./mkmv lyrics <name> --file <f>`.
5. Plan: `./mkmv plan <name> --concept "…" [--llm claude]`, or edit `projects/<name>/data/mv.json` yourself:
   title first, credits last, `clip` on the strongest sections, `pulse`/`lyrics` on calm ones, `visualizer` on high energy.
6. AI clips (only if the engine is ready): `ollama ps` → stop big models → `./mkmv clips <name>`.
7. `./mkmv stills <name>` → Read `projects/<name>/out/stills/sheet.jpg` → fix overlaps → `./mkmv render <name> --draft` → `./mkmv render <name>`.
8. Report the mp4 path, duration, BPM, and which sections use AI clips.
