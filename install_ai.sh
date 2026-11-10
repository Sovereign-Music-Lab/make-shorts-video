#!/usr/bin/env bash
# Optional: local AI video engine for realistic music-video clips (Apple Silicon only).
# FastMetal-5B-QAD (Wan2.2 TI2V-5B distilled, INT8, MLX) generates 1280x704 clips, 5 s each;
# `./mkmv clips` then upscales them to 1920x1080 with ffmpeg.
# Everything goes into ./ai/ (git-ignored): FastVideo code (pinned), ai/.venv, ai/models (~19.5 GB).
#
# Usage:
#   ./install_ai.sh                # interactive (asks before the 19.5 GB download)
#   ./install_ai.sh --yes          # no questions
#   ./install_ai.sh --skip-model   # code + Python env only, download the model later (rerun without the flag)
# Remove with: ./uninstall.sh --ai
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FASTVIDEO_REPO="https://github.com/hao-ai-lab/FastVideo.git"
FASTVIDEO_SHA="fcbe895b5591123449e64cf0528a83e1532280d4"   # tested with this commit
MODEL_ID="FastVideo/FastMetal-5B-QAD"
MODEL_DIR="ai/models/FastMetal-5B-QAD"
MODEL_GB=20

YES=0
SKIP_MODEL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1 ;;
    --skip-model) SKIP_MODEL=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
  esac
  shift
done
say() { printf '\033[1;35m▶ %s\033[0m\n' "$*"; }
has() { command -v "$1" >/dev/null 2>&1; }
ask() { [ "$YES" = 1 ] && return 0; read -r -p "$1 [y/N] " a; [ "$a" = y ] || [ "$a" = Y ]; }

if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo "이 AI 엔진은 Apple Silicon Mac(MLX) 전용입니다. 다른 환경에서는 모션그래픽만 사용하세요." >&2
  exit 1
fi
[ -d node_modules ] || { echo "먼저 ./install.sh 를 실행하세요." >&2; exit 1; }

# ---------------------------------------------------------------- 1. uv (Python 3.12 for torch/mlx wheels)
say "1/3 uv 확인"
if ! has uv; then
  if has brew && ask "  uv가 없습니다. brew install uv 할까요?"; then brew install uv; else
    echo "  uv 설치: https://docs.astral.sh/uv/  (curl -LsSf https://astral.sh/uv/install.sh | sh)" >&2; exit 1; fi
fi

# ---------------------------------------------------------------- 2. FastVideo code + venv
say "2/3 FastVideo (MLX 런타임) 설치 → ai/"
mkdir -p ai/models
if [ ! -d ai/FastVideo/.git ]; then
  git init -q ai/FastVideo
  git -C ai/FastVideo remote add origin "$FASTVIDEO_REPO"
  git -C ai/FastVideo fetch -q --depth 1 origin "$FASTVIDEO_SHA"
  git -C ai/FastVideo checkout -q FETCH_HEAD
fi
[ -x ai/.venv/bin/python ] || uv venv -q --python 3.12 ai/.venv
VIRTUAL_ENV="$PWD/ai/.venv" uv pip install -q -e "ai/FastVideo[mlx]"
ai/.venv/bin/python -c "import mlx.core, torch, fastvideo; print('  ✓ mlx / torch / fastvideo OK')" 2>/dev/null | tail -1

# ---------------------------------------------------------------- 3. model weights
say "3/3 모델 FastMetal-5B-QAD (~${MODEL_GB} GB)"
if [ "$SKIP_MODEL" = 1 ]; then
  echo "  --skip-model: 모델은 나중에 ./install_ai.sh 로 받으세요."
else
  have_gb=$(du -sg "$MODEL_DIR" 2>/dev/null | cut -f1 || echo 0)
  free_gb=$(df -g . | awk 'NR==2 {print $4}')
  need_gb=$(( MODEL_GB - ${have_gb:-0} + 3 ))
  echo "  받은 양: ${have_gb:-0} GB, 남은 디스크: ${free_gb} GB, 필요: 약 ${need_gb} GB (여유 3 GB 포함)"
  if [ "$free_gb" -lt "$need_gb" ]; then
    echo "  ✗ 디스크가 부족합니다. 공간을 비운 뒤 다시 실행하세요 (이어받기 됩니다)." >&2
    exit 1
  fi
  if ask "  Hugging Face에서 $MODEL_ID 를 받을까요? (중단해도 이어받기 됩니다)"; then
    ai/.venv/bin/python - "$MODEL_ID" "$MODEL_DIR" <<'PY'
import sys
from huggingface_hub import snapshot_download
snapshot_download(sys.argv[1], local_dir=sys.argv[2])
print("  ✓ 모델 준비 완료:", sys.argv[2])
PY
  fi
fi

echo
./mkmv doctor
