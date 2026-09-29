#!/usr/bin/env bash
# setup.sh [--voices] [brand.json] — one-time setup for voiceover-video. Safe to re-run.
# --voices also fetches script mode's voice model (~350 MB) and word-alignment model (~145 MB), once.
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPTS_DIR")"
ASSETS_DIR="$SKILL_DIR/assets"
GSAP_VERSION="3.12.5"
KOKORO_DIR="${VV_KOKORO_DIR:-$HOME/.cache/voiceover-video/kokoro}"
KOKORO_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
VOICES=0
if [[ "${1:-}" == "--voices" ]]; then VOICES=1; shift; fi
missing=()

command -v ffmpeg >/dev/null || missing+=("ffmpeg (apt install ffmpeg · brew install ffmpeg)")
command -v node >/dev/null || missing+=("node >= 18")
command -v npm >/dev/null || missing+=("npm (needed to install playwright-core)")
command -v python3 >/dev/null || missing+=("python3 >= 3.10")
python3 -c "import faster_whisper" 2>/dev/null || missing+=("faster-whisper (pip install faster-whisper)")
python3 -c "import numpy" 2>/dev/null || missing+=("numpy (pip install numpy)")
if (( VOICES )); then
  python3 -c "import kokoro_onnx" 2>/dev/null || missing+=("kokoro-onnx, for script-mode voices (pip install kokoro-onnx)")
fi

node_major=$(node -v 2>/dev/null | sed 's/v\([0-9]*\).*/\1/') || node_major=0
(( node_major >= 18 )) || missing+=("node >= 18 (got $(node -v 2>/dev/null || echo none))")

python_minor=$(python3 --version 2>/dev/null | sed 's/.* 3\.\([0-9]*\).*/\1/') || python_minor=0
(( python_minor >= 10 )) || missing+=("python3 >= 3.10 (got $(python3 --version 2>/dev/null || echo none))")

# speak.py aligns word times with this model; fetch it now so script mode never downloads mid-run
if (( VOICES )) && python3 -c "import faster_whisper" 2>/dev/null; then
  echo "checking the alignment model (faster-whisper base, ~145 MB on first run)"
  if ! fetch_error=$(python3 -c 'from faster_whisper import download_model; download_model("base")' 2>&1 >/dev/null); then
    echo "could not fetch the faster-whisper base model (speak.py word alignment): ${fetch_error##*$'\n'}"
    echo "Next: check the connection, then re-run setup.sh --voices"
    exit 1
  fi
  echo "alignment model ready · faster-whisper base"
fi

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

FONTS_URL=$(python3 - "$BRAND" "$SKILL_DIR/templates/templates.json" <<'PY'
import json, sys
path = sys.argv[1]
try:
    brand = json.load(open(path, encoding="utf-8"))
except (json.JSONDecodeError, OSError) as e:
    print(f"cannot read brand file {path}: {e}", file=sys.stderr)
    print("Next: fix the JSON, or run init_brand.py to create a brand file", file=sys.stderr)
    sys.exit(1)
for key in ("handle", "fonts", "colors"):
    if key not in brand:
        print(f"brand file missing key: {key}", file=sys.stderr)
        print("Next: add it, or run init_brand.py to create a brand file", file=sys.stderr)
        sys.exit(1)
if "googleFontsUrl" not in brand.get("fonts", {}):
    print("brand file missing fonts.googleFontsUrl", file=sys.stderr)
    print("Next: add it, or run init_brand.py to create a brand file", file=sys.stderr)
    sys.exit(1)
# Themes with their own typefaces add families to the brand's request, so one download covers every theme
url = brand["fonts"]["googleFontsUrl"]
manifest = sys.argv[2]
try:
    themes = json.load(open(manifest, encoding="utf-8")).get("templates", [])
except (json.JSONDecodeError, OSError) as e:
    print(f"cannot read theme catalogue {manifest}: {e}", file=sys.stderr)
    print("Next: restore templates/templates.json from git", file=sys.stderr)
    sys.exit(1)
extra = [t["fonts"] for t in themes if t.get("fonts")]
if extra:
    base, _, query = url.partition("?")
    params = [p for p in query.split("&") if p and not p.startswith("display=")]
    params += ["family=" + f for f in extra if "family=" + f not in params]
    url = base + "?" + "&".join(params + ["display=swap"])
print(url)
PY
)

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

if (( VOICES )); then
  mkdir -p "$KOKORO_DIR"
  for file in kokoro-v1.0.onnx voices-v1.0.bin; do
    # Download to a temp name so an interrupted fetch never leaves a truncated model behind
    if [[ ! -s "$KOKORO_DIR/$file" ]]; then
      echo "downloading $file → $KOKORO_DIR"
      if ! curl -sfL -o "$KOKORO_DIR/$file.part" "$KOKORO_URL/$file"; then
        echo "could not download $KOKORO_URL/$file"
        echo "Next: check the connection, or download it by hand into $KOKORO_DIR"
        exit 1
      fi
      mv "$KOKORO_DIR/$file.part" "$KOKORO_DIR/$file"
    fi
  done
  echo "voices ready · $KOKORO_DIR"
fi

# YouTube clips are optional; everything else works without them
if ! command -v yt-dlp >/dev/null; then
  echo "optional: yt-dlp not found — YouTube clips disabled (pipx install yt-dlp)"
fi

echo "ready · brand $BRAND"
if (( VOICES )); then
  echo "Next: write the script, then run speak.py (script mode) — or transcribe.py on a recording"
else
  echo "Next: run transcribe.py on your audio file"
fi
