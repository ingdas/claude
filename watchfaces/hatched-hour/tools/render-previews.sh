#!/usr/bin/env bash
# Regenerate the preview images (watch picker preview + README media).
# Needs: python3, node + playwright, ImageMagick, ffmpeg. Not needed to build the APK.
set -euo pipefail
cd "$(dirname "$0")/.."
B=docs/build
rm -rf "$B" && mkdir -p "$B/frames"

# Time-lapse: 10:00 -> 10:59 in 12 seconds (one frame per 30 s of watch time).
specs=()
for i in $(seq 0 119); do
  specs+=("$(python3 -c "t=$i*30+15; print(f'10:{t//60:02d}:{t%60:04.1f}')")")
done
python3 tools/generate.py --out-dir "$B/frames" --svg "${specs[@]}" > /dev/null
args=(); i=0
for t in "${specs[@]}"; do
  args+=("$B/frames/preview-${t//:/-}.svg" "$B/frames/f$(printf %03d $i).png"); i=$((i+1))
done
node tools/rasterize.js "${args[@]}"
ffmpeg -loglevel error -y -framerate 10 -i "$B/frames/f%03d.png" \
  -vf "scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=none" \
  -loop 0 docs/timelapse.gif

python3 tools/generate.py --out-dir "$B" --svg 10:38:20 10:38:20@1 10:38:20@2 10:38:20~aod > /dev/null
node tools/rasterize.js "$B/preview-10-38-20.svg" app/src/main/res/drawable/preview.png \
  "$B/preview-10-38-20.svg" "$B/p0.png" "$B/preview-10-38-20-1.svg" "$B/p1.png" \
  "$B/preview-10-38-20-2.svg" "$B/p2.png" "$B/preview-10-38-20-aod.svg" "$B/aod.png"
convert "$B/p0.png" "$B/p1.png" "$B/p2.png" -background none -splice 20x0 +append -chop 20x0 -resize 50% docs/palettes.png
convert "$B/aod.png" -resize 50% docs/aod.png
rm -rf "$B"
echo "previews written"
