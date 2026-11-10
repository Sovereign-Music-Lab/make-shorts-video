# AGENTS.md — rules for any coding agent in this repo

This file is read by Claude Code (through `CLAUDE.md`), by Claude Code running on a local Ollama model
(`ollama launch claude`), and by other agents. Humans: see `README.md`.

## What this repo does
Korean fact Shorts (1080x1920, 30 fps), fully local:
script (`voice/lines.txt` + `data/scenes.json`) → male narration (edge-tts) → synthesized music → Remotion render.
One command runs the whole routine: `./mkshort make <name> --topic "..."`.

## Layout
| Path | Purpose |
|---|---|
| `mkshort`, `tools/mkshort.py` | CLI. Run `./mkshort -h` and `./mkshort <cmd> -h`. |
| `tools/llm.py` | Script writers: `ollama` (local, JSON schema) and `claude` (`claude -p`). |
| `tools/build_voice.py` | Narration builder. Run by `./mkshort voice`. |
| `tools/music.py` | Original score + ducking + loudness. Moods: sacred, march, calm, tension, none. |
| `tools/stills.mjs` | Fast still frames for look checks. |
| `template/short/` | Project skeleton copied by `./mkshort new`. `src/Short.tsx` renders scenes from JSON. |
| `examples/<name>/` | Ready scripts: `lines.txt`, `scenes.json`, `FACTS.md`. |
| `projects/<name>/` | The user's videos. Git-ignored. Each has its own `src/` you may customize. |

## Workflow for an agent
1. Run `./mkshort doctor`. If anything is ✗, run `./install.sh` (or tell the user what is missing).
2. **Facts first.** Research the topic. Put every claim with its source in `projects/<name>/FACTS.md`.
   Leave out anything you cannot verify; note open items at the bottom.
3. Create the project: `./mkshort new <name>`. Write `voice/lines.txt` (one narration line per row, 40 chars or so,
   strong hook first, closing line last) and `data/scenes.json` (schema below).
   Or let a local model draft it: `./mkshort write <name> --topic "..." --llm ollama`, then fact-check and edit the result.
4. `./mkshort voice <name>` → `./mkshort music <name>` → `./mkshort stills <name>`. Look at
   `projects/<name>/out/stills/sheet.jpg` and fix overlaps or empty scenes before rendering.
5. `./mkshort render <name>` (add `--2k` for 1440x2560). Report the mp4 path and duration.

## Hard rules
- **Narration voice:** edge-tts neural voices only. Default male `ko-KR-InJoonNeural`; female `ko-KR-SunHiNeural`.
  **Never use macOS `say`** (Yuna, Eddy, Reed, …). Rate `+10%` keeps a 13-line script near 75 s.
- **Facts:** no invented numbers, dates or quotes. Present claims by people as their claims ("그는 …라고 말했다").
  For deaths, keep to date and place unless the cause is the topic.
- **Layout:** graphics stay above y = 1450 (design space 1080x1920). Captions use y 1470-1790. Source line at y 1868.
- **After any change to `voice/lines.txt`:** rerun `voice`, then `music` (timings change), then render.
- Edit `projects/<name>/src/` for one-off visuals. Edit `template/short/src/` only to improve every future project,
  and keep `tsc` clean: `npx tsc --noEmit -p tsconfig.json`.
- Never commit `projects/`, media files, `node_modules/` or `.venv/` (see `.gitignore`).
- Music is generated from code in `tools/music.py`. Do not add copyrighted audio.

## data/scenes.json
```json
{
  "title": "TempleOS", "theme": "sacred", "mood": "sacred", "captions": true,
  "scenes": [
    { "type": "title", "line": 1, "kicker": "신의 계시?", "title": "TempleOS", "subtitle": "…", "icon": "temple" },
    { "type": "number", "line": 11, "value": 100000, "suffix": "+", "label": "코드 줄 수", "source": "Wikipedia" }
  ]
}
```
- `line` = 1-based narration line where the scene starts (0.25 s before that line). A scene lasts until the next one.
- `theme`: sacred | tech | news | warm. `mood` (music): sacred | march | calm | tension | none.
- Scene types and fields:
  - `title` {kicker, title, subtitle, icon: none|temple|star|globe}
  - `person` {role, name, years, note}
  - `timeline` {title, points: [{year, label}] up to 5}
  - `number` {kicker, value, prefix, suffix, label} (counts up)
  - `statement` {text, sub}
  - `chips` {title, items: [up to 6 short words]}
  - `compare` {title, left: {title, text}, right: {title, text}}
  - `code` {code, caption}
  - `image` {src (file in public/), caption}
  - `ending` {title, subtitle, icon}
  - any scene: `source` (short source name shown at the bottom)
- On-screen text stays short (about 12 characters per row). The narration carries the detail.

## Music videos (`./mkmv`, 1920x1080)
| Path | Purpose |
|---|---|
| `mkmv`, `tools/mkmv.py` | CLI: new, analyze, lyrics, plan, clips, stills, render, studio, make, doctor |
| `tools/mv_analyze.py` | BPM (comb autocorrelation), beat grid, energy + low/mid/high per video frame, beat-aligned section draft |
| `tools/upscale.sh` | 720p-class → 1920x1080 (ffmpeg Lanczos + sharpen, center crop) |
| `tools/demo_song.py` | Code-synthesized 120 BPM demo song for tests |
| `template/mv/` | Remotion project: `src/MV.tsx` renders `data/mv.json` + `data/analysis.json`, audio `public/song.wav` |
| `install_ai.sh`, `ai/` | Optional local AI clips (FastMetal-5B-QAD on MLX, Apple Silicon). `ai/` is git-ignored. |

Workflow: `./mkmv new <n> --song <file>` → (`lyrics`) → `plan` → (`clips`) → `stills` → `render --draft` → `render`.

`data/mv.json`:
```json
{ "title": "…", "artist": "…", "theme": "neon", "credits": ["Music: …"],
  "lyrics": [{ "t": 12.5, "end": 15.0, "text": "…" }],
  "sections": [{ "start": 0, "end": 8.5, "kind": "title" },
               { "start": 8.5, "end": 16.4, "kind": "clip", "prompt": "photorealistic, cinematic …", "clip": "clips/s1.mp4", "clipSeconds": 5.04 }] }
```
- Section kinds: title | visualizer | pulse | lyrics | text {text, sub} | clip {prompt, clip, clipSeconds} | credits.
- Themes: neon | gold | mono | sunset. Keep section start/end on the beat grid (they come from the analysis).
- A `clip` section without a `clip` file renders as `pulse`, so a video always renders.
- AI clip prompts: English, one 5 s shot, no real people, celebrities, logos, violence or sexual content.
- Before `./mkmv clips` on a 24 GB Mac, unload big Ollama models (`ollama ps`, `ollama stop <model>`).
- Never use a song the user has no rights to; the user supplies their own audio.
