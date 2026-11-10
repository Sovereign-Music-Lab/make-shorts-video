# make-shorts-video

한국어 **팩트 쇼츠**(세로 1080×1920)와 **뮤직비디오**(가로 1920×1080)를 내 컴퓨터에서 만드는 도구입니다.
대본 → 남성 나레이션 → 배경음악 → 모션그래픽 렌더까지 명령 하나로 끝납니다. (`./mkshort`)
뮤직비디오는 내 곡을 분석해 비트에 맞춘 모션그래픽 + 로컬 AI 실사 클립(720p → 1080p 업스케일)으로 만듭니다. (`./mkmv`)

- 대본은 **Claude Code** 또는 **Ollama(로컬 LLM)** 가 쓰거나, 직접 쓸 수 있습니다.
- 나레이션: edge-tts 신경망 음성 (기본 남성 `ko-KR-InJoonNeural`, 무료·API 키 없음, 인터넷 필요)
- 음악: 코드로 합성한 오리지널 곡 (sacred / march / calm / tension), 나레이션 아래로 자동 덕킹
- 영상: Remotion. 장면은 `scenes.json`(JSON)으로 정의 → LLM이 JSON만 쓰면 영상이 됩니다.

```
주제 ──▶ lines.txt + scenes.json ──▶ voice.wav ──▶ mix.wav ──▶ out/<name>.mp4
        (Ollama / Claude / 직접)     (edge-tts)    (music.py)    (Remotion)
```

---

## 1. 설치

필요한 것: macOS 또는 Linux, Node.js 18+, Python 3.10+, ffmpeg, git
(macOS는 Homebrew가 있으면 없는 도구를 `install.sh`가 설치해 줍니다.)

```bash
git clone https://github.com/Sovereign-Music-Lab/make-shorts-video.git
cd make-shorts-video
./install.sh
```

`install.sh` 가 하는 일 (모두 이 폴더 안에만 설치):
1. Node / Python / ffmpeg 확인 (macOS: 없으면 `brew install`)
2. `npm ci` → `node_modules/` (Remotion)
3. `.venv/` 파이썬 가상환경 + `edge-tts`, `numpy`
4. Ollama가 있으면 안내 (모델 받기: `./install.sh --ollama-model gemma4:e4b-mlx`)
5. `./mkshort doctor` 로 점검

> 비공개 저장소라면 먼저 `gh auth login` 으로 GitHub 로그인하세요.
> Linux는 한글 폰트가 필요합니다: `sudo apt install -y fonts-noto-cjk`

설치 확인:

```bash
./mkshort doctor
./mkmv doctor
```

### (선택) 뮤직비디오용 로컬 AI 실사 영상 엔진 — Apple Silicon 전용

```bash
./install_ai.sh                # FastVideo(MLX) + 모델 FastMetal-5B-QAD (~20 GB, 이어받기 가능)
./install_ai.sh --skip-model   # 코드·환경만 먼저, 모델은 나중에
```

- 모두 `ai/` 폴더에 설치됩니다 (git 제외). 디스크 여유가 모자라면 받기 전에 멈춥니다.
- 1280×704 실사 클립(5초)을 만들고 `ffmpeg`로 1920×1080 업스케일합니다.
- 공개 자료 기준 720p 생성 피크 메모리 약 9 GB, 5초 클립 수 분 (기기마다 다름). 24 GB Mac에서는 큰 Ollama 모델을 `ollama stop` 으로 내리고 생성하세요.
- 이 엔진 없이도 뮤직비디오(모션그래픽)는 만들 수 있습니다.

---

## 2. 루틴 사용법

### 가장 빠른 확인 (예제 대본)

```bash
./mkshort make demo --from templeos
```

`projects/demo/out/demo.mp4` (약 75초)가 만들어집니다.

### A. Ollama로 대본까지 자동 (완전 로컬)

```bash
./mkshort make eiffel --topic "에펠탑에 대한 놀라운 사실" --seconds 60
./mkshort make eiffel --topic "..." --model gemma4:12b-mlx --stills   # 모델 지정 + 스틸 시트
```

- 기본 모델: `gemma4:e4b-mlx` (`export MKSHORT_OLLAMA_MODEL=<모델>` 로 변경)
- Ollama는 구조화 출력(JSON 스키마)으로 대본+장면을 만듭니다.
- **로컬 LLM은 사실을 틀릴 수 있습니다.** `projects/<name>/FACTS.md` 를 보고 직접 확인한 뒤 게시하세요.

### B. Claude Code로 (사실 검증 포함, 권장)

이 폴더에서 Claude Code를 열고 말하면 됩니다:

```bash
claude
> TempleOS에 대한 팩트 쇼츠 만들어줘. 남자 나레이션으로 성스럽게
```

`.claude/skills/make-short` 스킬과 `CLAUDE.md`/`AGENTS.md` 규칙에 따라 Claude가
웹 검색으로 사실 확인 → 대본 → 장면 → 음성 → 음악 → 스틸 점검 → 렌더까지 진행합니다.

터미널 한 줄로 Claude에게 대본만 맡길 수도 있습니다:

```bash
./mkshort make tos --topic "TempleOS" --llm claude
```

### C. Claude Code를 Ollama 모델로 실행

Ollama(v0.15+)는 Anthropic 호환 API를 제공해서, Claude Code를 로컬 모델로 돌릴 수 있습니다.
같은 스킬과 규칙이 그대로 적용됩니다.

```bash
ollama launch claude                      # 모델 선택 후 Claude Code 실행
# 또는 직접:
ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_API_KEY="" ANTHROPIC_BASE_URL=http://localhost:11434 claude --model gemma4:12b-mlx
```

(작은 모델은 긴 작업에서 실수가 잦습니다. 64k 이상 컨텍스트의 큰 모델을 권장합니다.)

### D. 한 단계씩 (직접 수정하며)

```bash
./mkshort new myshort                     # projects/myshort 생성
#  projects/myshort/voice/lines.txt   ← 나레이션 (한 줄 = 한 문장 묶음)
#  projects/myshort/data/scenes.json  ← 화면 장면
./mkshort write myshort --topic "..."     # (선택) LLM 초안
./mkshort voice myshort                   # 남성 나레이션 (--voice ko-KR-SunHiNeural 여성, --rate +0%)
./mkshort music myshort --mood sacred     # sacred | march | calm | tension | none
./mkshort stills myshort                  # out/stills/sheet.jpg 로 장면 확인
./mkshort studio myshort                  # 브라우저에서 미리보기/수정 (Remotion Studio)
./mkshort render myshort                  # out/myshort.mp4  (--2k 로 1440x2560)
```

`lines.txt` 를 고치면 `voice → music → render` 순서로 다시 실행하세요 (타이밍이 바뀝니다).

### E. 뮤직비디오 (가로 1920×1080, `./mkmv`)

```bash
./mkmv make demo --demo-song                                   # 데모 곡으로 바로 확인
./mkmv make mysong --song ~/Music/mysong.wav --title "제목" --artist "이름"   # 내 곡 → 모션그래픽 MV
./mkmv make mysong --song ~/Music/mysong.wav --plan --concept "새벽 도시, 네온"  # + Ollama 연출 계획
./mkmv make mysong --song ~/Music/mysong.wav --plan --clips    # + 로컬 AI 실사 클립 (install_ai.sh 필요)
```

한 단계씩:

```bash
./mkmv new mysong --song mysong.wav --title "제목" --artist "이름"   # 음원 복사 + BPM/비트/에너지 분석 + 구간 초안
./mkmv analyze mysong --bpm 128 --draft --bars 4    # BPM을 알면 지정, 구간을 4마디 단위로 다시
./mkmv lyrics mysong --file lyrics.lrc              # 가사: LRC([01:23.45] 가사) 또는 일반 텍스트(균등 배치)
./mkmv plan mysong --llm ollama --concept "바다, 일출" --max-clips 6   # 구간별 연출 + AI 클립 프롬프트
./mkmv clips mysong                                 # AI 720p 생성 → 1080p 업스케일 → 구간에 연결
./mkmv stills mysong                                # 구간별 스틸 시트
./mkmv render mysong --draft                        # 960x540 빠른 확인
./mkmv render mysong                                # 최종 1920x1080 → projects/mysong/out/mysong.mp4
```

- 연출 계획은 `projects/<n>/data/mv.json` 에 저장됩니다. 직접 고쳐도 됩니다.
- 구간 종류: `title` `visualizer`(스펙트럼) `pulse`(비트 링) `lyrics`(가사 크게) `text`(비트마다 단어) `clip`(실사 영상) `credits`
- 테마: `neon` `gold` `mono` `sunset`
- `clip` 구간에 내가 찍은 영상을 쓰려면 `public/clips/` 에 넣고 `"clip": "clips/파일.mp4", "clipSeconds": 길이` 를 적으세요.
- AI 클립 프롬프트는 실존 인물·로고를 피하도록 계획 단계에서 제한합니다.

### 명령어 요약

| 명령 | 설명 |
|---|---|
| `./mkshort doctor` | 설치 점검 |
| `./mkshort make <n> --topic ".."` | 전체 루틴 (write → voice → music → render) |
| `./mkshort make <n> --from <예제>` | `examples/` 대본으로 전체 루틴 |
| `./mkshort new <n>` | 빈 프로젝트 |
| `./mkshort write <n> --topic ".." [--llm ollama\|claude] [--model M] [--seconds 60]` | 대본+장면 초안 |
| `./mkshort voice <n> [--voice V] [--rate +10%]` | 나레이션 |
| `./mkshort music <n> [--mood M]` | 음악+믹스 |
| `./mkshort stills <n>` | 장면별 스틸 시트 |
| `./mkshort render <n> [--2k]` | MP4 렌더 |
| `./mkshort studio <n>` | Remotion Studio 미리보기 |
| `./mkshort list` / `./mkshort rm <n>` | 목록 / 삭제 |
| `./mkmv make <n> --song F [--plan] [--clips]` | 뮤직비디오 전체 루틴 |
| `./mkmv new / analyze / lyrics / plan / clips / stills / render / studio` | 뮤직비디오 단계별 |

### 장면(scenes.json) 형식

```json
{
  "title": "TempleOS", "theme": "sacred", "mood": "sacred", "captions": true,
  "scenes": [
    { "type": "title", "line": 1, "kicker": "신의 계시?", "title": "TempleOS", "icon": "temple" },
    { "type": "timeline", "line": 4, "title": "이름의 역사",
      "points": [{ "year": "2005", "label": "J 운영체제" }, { "year": "2013", "label": "TempleOS" }] },
    { "type": "number", "line": 11, "value": 100000, "suffix": "+", "label": "코드 줄 수", "source": "Wikipedia" },
    { "type": "ending", "line": 13, "title": "TempleOS", "subtitle": "1969–2018" }
  ]
}
```

- `line`: 그 장면이 시작되는 나레이션 줄 번호 (1부터)
- 장면 종류: `title` `person` `timeline` `number` `statement` `chips` `compare` `code` `image` `ending`
- 테마: `sacred`(경건) `tech`(기술) `news`(시사) `warm`(사람/문화)
- 전체 필드 설명: [AGENTS.md](AGENTS.md)

---

## 3. 삭제법

```bash
./uninstall.sh                         # node_modules/, .venv/ 삭제 (만든 영상 projects/ 는 유지)
./uninstall.sh --projects              # 만든 영상까지 삭제 (확인 질문)
./uninstall.sh --ollama-model gemma4:e4b-mlx   # 받은 Ollama 모델도 삭제
./uninstall.sh --ai                    # 로컬 AI 영상 엔진(ai/, 약 22 GB)과 프롬프트 캐시 삭제
cd .. && rm -rf make-shorts-video      # 폴더째 완전 삭제
```

`install.sh` 는 이 폴더 밖에 아무것도 설치하지 않습니다 (Homebrew로 설치한 Node/ffmpeg/Python 제외 —
필요 없으면 `brew uninstall node ffmpeg` 로 직접 지우세요).

---

## 문제 해결

| 증상 | 해결 |
|---|---|
| `delayRender ... timeout` | 메모리 부족. 큰 Ollama 모델이 올라가 있으면 `ollama stop <모델>` 후 다시 렌더 |
| 나레이션 합성 실패 | edge-tts는 인터넷이 필요합니다. 네트워크 확인 후 `./mkshort voice <n>` |
| `Ollama 모델 '…'이 없습니다` | `ollama pull <모델>` 또는 `--model` 로 설치된 모델 지정 (`ollama list`) |
| 한글이 네모로 보임 (Linux) | `sudo apt install -y fonts-noto-cjk` |
| 글자가 겹침 | `./mkshort stills <n>` 로 확인 → `scenes.json` 글자를 줄이거나 장면을 나누기 |

## 고지
- `tools/build_voice.py` 는 MIT 라이선스 코드를 수정한 것입니다 → [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
- Remotion은 회사 사용 시 유료 라이선스가 필요할 수 있습니다. edge-tts는 Microsoft 온라인 음성을 사용합니다.
