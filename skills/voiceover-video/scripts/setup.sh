#!/usr/bin/env bash
# setup.sh [brand.json] — one-time setup for voiceover-video. Safe to re-run.
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPTS_DIR")"
ASSETS_DIR="$SKILL_DIR/assets"
GSAP_VERSION="3.12.5"
missing=()

command -v ffmpeg >/dev/null || missing+=("ffmpeg (apt install ffmpeg · brew install ffmpeg)")
command -v node >/dev/null || missing+=("node >= 18")
command -v python3 >/dev/null || missing+=("python3 >= 3.10")
python3 -c "import faster_whisper" 2>/dev/null || missing+=("faster-whisper (pip install faster-whisper)")
python3 -c "import numpy" 2>/dev/null || missing+=("numpy (pip install numpy)")

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "setup incomplete — missing ${#missing[@]}:"
  printf '  %s\n' "${missing[@]}"
  echo "Next: install the above, then re-run setup.sh"
  exit 1
fi

BRAND="${1:-}"
for candidate in "$BRAND" "./brand.json" "$HOME/.config/voiceover-video/brand.json" "$SKILL_DIR/brand.example.json"; do
  if [[ -n "$candidate" && -f "$candidate" ]]; then BRAND="$candidate"; break; fi
done
FONTS_URL=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['fonts']['googleFontsUrl'])" "$BRAND")

if [[ ! -d "$SCRIPTS_DIR/node_modules/playwright-core" ]]; then
  (cd "$SCRIPTS_DIR" && npm install --silent)
fi

# Each playwright-core release pins its own browser build; install is a no-op when the matching one is cached
(cd "$SCRIPTS_DIR" && node node_modules/playwright-core/cli.js install chromium-headless-shell >/dev/null)

mkdir -p "$ASSETS_DIR"
if [[ ! -f "$ASSETS_DIR/gsap.min.js" ]]; then
  curl -sfL -o "$ASSETS_DIR/gsap.min.js" "https://cdnjs.cloudflare.com/ajax/libs/gsap/$GSAP_VERSION/gsap.min.js"
fi

# Re-fetch whenever the brand's font URL changes, so switching brands never renders stale type
if [[ ! -f "$ASSETS_DIR/fonts.css" || "$(cat "$ASSETS_DIR/fonts.url" 2>/dev/null)" != "$FONTS_URL" ]]; then
  rm -f "$ASSETS_DIR"/*.woff2
  # A desktop UA makes Google Fonts serve woff2
  curl -sf -A "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36" "$FONTS_URL" > "$ASSETS_DIR/fonts.css"
  grep -o 'https://fonts.gstatic.com[^)]*' "$ASSETS_DIR/fonts.css" | sort -u | while read -r url; do
    file="$(echo "$url" | sed 's#https://fonts.gstatic.com/s/##; s#/#-#g')"
    curl -sf -o "$ASSETS_DIR/$file" "$url"
    sed -i.bak "s#$url#$file#g" "$ASSETS_DIR/fonts.css" && rm -f "$ASSETS_DIR/fonts.css.bak"
  done
  echo "$FONTS_URL" > "$ASSETS_DIR/fonts.url"
fi

echo "ready · brand $BRAND"
