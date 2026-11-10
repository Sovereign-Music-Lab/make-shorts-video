# Third-party notices

## tools/build_voice.py
Adapted from `templates/voice/build_voice.py` of **claude-animated-shorts**
(https://github.com/work-core/claude-animated-shorts). Changes: the default edge-tts voice is the male
`ko-KR-InJoonNeural`.

```
MIT License

Copyright (c) 2026 Mr omi

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files
(the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR
IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

## Runtime dependencies (installed by install.sh, not bundled)
- Remotion (https://www.remotion.dev) — check the Remotion license; companies may need a paid company license.
- edge-tts (https://github.com/rany2/edge-tts) — uses Microsoft Edge's online neural voices (needs internet).
- Ollama (https://ollama.com) — optional, for local script drafting.
