#!/usr/bin/env bash
# make-shorts-video installer (macOS / Linux).
# Installs everything inside this folder: node_modules/ (Remotion) and .venv/ (edge-tts, numpy).
# System tools (Node 18+, Python 3.10+, ffmpeg) are installed with Homebrew on macOS when missing.
#
# Usage:
#   ./install.sh                         # interactive
#   ./install.sh --yes                   # no questions (installs missing Homebrew packages)
#   ./install.sh --ollama-model gemma4:e4b-mlx   # also pull an Ollama model for script writing
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

YES=0
OLLAMA_MODEL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1 ;;
    --ollama-model) OLLAMA_MODEL="${2:?model name}"; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
  esac
  shift
done

say() { printf '\033[1;36m▶ %s\033[0m\n' "$*"; }
has() { command -v "$1" >/dev/null 2>&1; }
ask() { [ "$YES" = 1 ] && return 0; read -r -p "$1 [Y/n] " a; [ -z "$a" ] || [ "$a" = y ] || [ "$a" = Y ]; }

OS="$(uname -s)"

# ---------------------------------------------------------------- 1. system tools
say "1/4 시스템 도구 확인 (Node, Python, ffmpeg)"
missing=()
if has node; then
  v="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$v" -ge 18 ] || missing+=(node)
else
  missing+=(node)
fi
has ffmpeg && has ffprobe || missing+=(ffmpeg)
if has python3 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then :; else missing+=(python3); fi

if [ ${#missing[@]} -gt 0 ]; then
  echo "  없는 도구: ${missing[*]}"
  if [ "$OS" = Darwin ] && has brew; then
    pkgs=()
    for m in "${missing[@]}"; do case "$m" in python3) pkgs+=(python) ;; *) pkgs+=("$m") ;; esac; done
    if ask "  Homebrew로 설치할까요? (brew install ${pkgs[*]})"; then brew install "${pkgs[@]}"; else exit 1; fi
  elif [ "$OS" = Darwin ]; then
    echo "  Homebrew가 없습니다. https://brew.sh 설치 후 다시 실행하거나, 위 도구를 직접 설치하세요." >&2; exit 1
  else
    echo "  Linux 예시: sudo apt install -y nodejs npm python3 python3-venv ffmpeg fonts-noto-cjk" >&2
    echo "  (Node는 18 이상 필요. 설치 후 다시 실행하세요.)" >&2; exit 1
  fi
else
  echo "  ✓ node $(node --version), $(python3 --version), ffmpeg"
fi
if [ "$OS" = Linux ] && ! fc-list 2>/dev/null | grep -qi "noto.*cjk\|nanum"; then
  echo "  ! 한글 폰트가 없으면 글자가 깨집니다: sudo apt install -y fonts-noto-cjk"
fi

# ---------------------------------------------------------------- 2. Remotion
say "2/4 Remotion 설치 (node_modules/)"
if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi

# ---------------------------------------------------------------- 3. Python venv
say "3/4 Python 가상환경 (.venv/)"
if [ ! -x .venv/bin/python ]; then
  if has uv; then uv venv .venv -q; else python3 -m venv .venv; fi
fi
if has uv; then
  VIRTUAL_ENV="$PWD/.venv" uv pip install -q -r requirements.txt
else
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -r requirements.txt
fi
chmod +x mkshort uninstall.sh 2>/dev/null || true

# ---------------------------------------------------------------- 4. Ollama (optional)
say "4/4 Ollama (선택: 로컬 LLM으로 대본 자동 작성)"
if has ollama; then
  if [ -n "$OLLAMA_MODEL" ]; then
    ollama pull "$OLLAMA_MODEL"
    echo "  기본 모델로 쓰려면: export MKSHORT_OLLAMA_MODEL=$OLLAMA_MODEL"
  else
    echo "  ✓ ollama 있음. 모델이 없다면: ollama pull gemma4:e4b-mlx (또는 ./install.sh --ollama-model <모델>)"
  fi
else
  echo "  - ollama 없음 (선택). 설치: https://ollama.com/download  — 없어도 Claude Code나 손으로 대본을 쓰면 됩니다."
fi

echo
./mkshort doctor || true
cat <<'EOF'

설치 끝. 바로 해보기:
  ./mkshort make demo --from templeos          # 예제 대본으로 영상 만들기
  ./mkshort make my1 --topic "주제를 한 줄로"     # Ollama가 대본 작성
EOF
