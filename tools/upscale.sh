#!/usr/bin/env bash
# Upscale a 720p-class clip (e.g. 1280x704 from the AI engine) to 1920x1080 FHD, locally with ffmpeg.
# Lanczos resize + light sharpen; keeps aspect by scaling to 1080 high and center-cropping to 1920 wide.
# Usage: tools/upscale.sh <in.mp4> <out.mp4> [fps]
set -euo pipefail
IN="${1:?input clip}"
OUT="${2:?output path}"
FPS="${3:-30}"
mkdir -p "$(dirname "$OUT")"
ffmpeg -y -loglevel error -i "$IN" \
  -vf "fps=${FPS},scale=-2:1080:flags=lanczos,crop=1920:1080,unsharp=5:5:0.6" \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -an "$OUT"
echo "upscaled → $OUT"
