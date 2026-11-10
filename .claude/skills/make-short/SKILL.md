---
name: make-short
description: Make a Korean fact Short (vertical 1080x1920 video, 45-100 s) with verified facts, male edge-tts narration, synthesized music and Remotion motion graphics, using this repo's mkshort CLI. Use when the user asks for a 쇼츠/Shorts/short video about a topic, "사실 영상", "팩트 쇼츠", or names a topic to turn into a short.
---

# make-short

Everything runs locally from the repo root. Rules live in `AGENTS.md` (voice, facts, layout): follow them.

## Steps
1. **Check setup:** `./mkshort doctor`. If Remotion or `.venv` is missing, run `./install.sh --yes`.
2. **Facts:** search the web for the topic. Write `projects/<name>/FACTS.md` as a table: claim | source.
   Drop anything you cannot confirm. Note disputed points under "보류 항목".
3. **Project:** `./mkshort new <name>` (ASCII name, e.g. `templeos-male`).
4. **Script:** write `projects/<name>/voice/lines.txt`, 10-15 lines, one or two sentences each.
   - Line 1 is the hook. The last line is a short reflective close.
   - Match the tone the user asked for (e.g. "성스럽게" → calm, reverent wording, theme `sacred`, mood `sacred`).
   - Write numbers the way they are read ("10만 줄", "640 곱하기 480").
5. **Scenes:** write `projects/<name>/data/scenes.json` (schema in AGENTS.md). One scene per 1-2 lines.
   Pick the type that shows the line: years → `timeline`, a figure → `number`, a person → `person`, a list → `chips`.
6. **Build:**
   ```bash
   ./mkshort voice <name>            # male ko-KR-InJoonNeural, rate +10%
   ./mkshort music <name>            # mood from scenes.json
   ./mkshort stills <name>           # then Read projects/<name>/out/stills/sheet.jpg
   ./mkshort render <name>           # add --2k for 1440x2560
   ```
7. **Check and deliver:** look at the sheet for overlaps, empty scenes or cut text and fix them before the render.
   Report the mp4 path, its duration and any facts left open.

## Custom visuals
The default renderer covers most topics. For a bespoke scene, add a component in
`projects/<name>/src/Short.tsx`, register it in `SCENE_TYPES`, and use its type in scenes.json.
Keep graphics above y = 1450 and run `npx tsc --noEmit -p tsconfig.json`.

## Draft with a local model (optional)
`./mkshort write <name> --topic "..." --llm ollama --model <model>` drafts lines.txt, scenes.json and FACTS.md.
Treat the draft as unverified: check every fact before rendering.
