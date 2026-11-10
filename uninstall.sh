#!/usr/bin/env bash
# make-shorts-video uninstaller.
# Removes what install.sh created inside this folder (node_modules/, .venv/, caches).
# Your videos in projects/ are kept unless you pass --projects (asks first).
#
# Usage:
#   ./uninstall.sh                          # remove node_modules/ and .venv/
#   ./uninstall.sh --projects               # also delete projects/ (your videos)
#   ./uninstall.sh --ollama-model <name>    # also `ollama rm <name>`
#   ./uninstall.sh --yes                    # no questions
# To remove everything afterwards:  cd .. && rm -rf make-shorts-video
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

YES=0
PROJ=0
OLLAMA_MODEL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1 ;;
    --projects) PROJ=1 ;;
    --ollama-model) OLLAMA_MODEL="${2:?model name}"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
  esac
  shift
done
ask() { [ "$YES" = 1 ] && return 0; read -r -p "$1 [y/N] " a; [ "$a" = y ] || [ "$a" = Y ]; }

echo "삭제 대상:"
for d in node_modules .venv; do [ -e "$d" ] && echo "  $d/ ($(du -sh "$d" 2>/dev/null | cut -f1))"; done
[ "$PROJ" = 1 ] && [ -d projects ] && echo "  projects/ ($(du -sh projects 2>/dev/null | cut -f1)) — 만든 영상 포함, 되돌릴 수 없음"
[ -n "$OLLAMA_MODEL" ] && echo "  Ollama 모델 $OLLAMA_MODEL"

ask "진행할까요?" || { echo "취소했습니다."; exit 0; }

rm -rf node_modules .venv
find tools -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "✓ node_modules/, .venv/ 삭제"

if [ "$PROJ" = 1 ] && [ -d projects ]; then
  find projects -mindepth 1 -maxdepth 1 ! -name .gitkeep -exec rm -rf {} +
  echo "✓ projects/ 비움"
fi

if [ -n "$OLLAMA_MODEL" ]; then
  if command -v ollama >/dev/null 2>&1; then ollama rm "$OLLAMA_MODEL" && echo "✓ ollama rm $OLLAMA_MODEL"; else echo "ollama 없음, 건너뜀"; fi
fi

# Remotion leaves bundle folders in the system temp folder
TMPD="${TMPDIR:-/tmp}"
n=$(find "$TMPD" -maxdepth 1 -name 'remotion-webpack-bundle-*' 2>/dev/null | wc -l | tr -d ' ')
if [ "$n" -gt 0 ] && ask "임시 폴더의 Remotion 번들 ${n}개도 지울까요?"; then
  find "$TMPD" -maxdepth 1 -name 'remotion-webpack-bundle-*' -exec rm -rf {} +
  echo "✓ Remotion 임시 번들 삭제"
fi

echo
echo "완전히 지우려면 이 폴더를 삭제하세요:  cd .. && rm -rf \"$(basename "$PWD")\""
