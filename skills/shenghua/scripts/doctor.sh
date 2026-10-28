#!/usr/bin/env bash
# doctor.sh [kit] — check a shenghua install without downloading or launching anything.
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPTS_DIR")"
ASSETS_DIR="$SKILL_DIR/assets"
KOKORO_DIR="${VV_KOKORO_DIR:-$HOME/.cache/shenghua/kokoro}"
YUNET_DIR="${VV_YUNET_DIR:-$HOME/.cache/shenghua/yunet}"
YUNET_MODEL="face_detection_yunet_2023mar.onnx"
KIT_ARG="${1:-}"
SETUP="bash $SCRIPTS_DIR/setup.sh"
OK=0
WARNINGS=0
MISSING=0

if (( $# > 1 )); then
  echo "doctor: expected at most one kit, got $# arguments"
  echo "Next: run bash $SCRIPTS_DIR/doctor.sh [kit]"
  exit 2
fi

ok() {
  printf '[ok] %s\n' "$1"
  OK=$((OK + 1))
}

warn() {
  printf '[warn] %s\n' "$1"
  WARNINGS=$((WARNINGS + 1))
}

missing() {
  printf '[missing] %s\n' "$1"
  MISSING=$((MISSING + 1))
}

report() {
  case "$1" in
    ok) ok "$2" ;;
    warn) warn "$2" ;;
    missing) missing "$2" ;;
  esac
}

PYTHON_AVAILABLE=0
PYTHON_OK=0
if command -v python3 >/dev/null 2>&1; then
  PYTHON_AVAILABLE=1
  if PYTHON_VERSION=$(python3 -c 'import sys
if sys.version_info < (3, 10):
    sys.exit(1)
print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null); then
    PYTHON_OK=1
    ok "python3 $PYTHON_VERSION"
  else
    PYTHON_VERSION=$(python3 --version 2>&1) || PYTHON_VERSION="unknown version"
    missing "python3 >= 3.10 (got $PYTHON_VERSION) — install Python 3.10 or newer"
  fi
else
  missing "python3 >= 3.10 — install Python 3.10 or newer"
fi

if (( PYTHON_AVAILABLE )) && python3 -c "import numpy" 2>/dev/null; then
  ok "numpy importable"
else
  missing "numpy — run: python3 -m pip install numpy"
fi

if (( PYTHON_AVAILABLE )) && python3 -c "import faster_whisper" 2>/dev/null; then
  ok "faster_whisper importable"
else
  missing "faster-whisper — run: python3 -m pip install faster-whisper 'av<19'"
fi

if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg · $(command -v ffmpeg)"
else
  missing "ffmpeg — install it (apt install ffmpeg · brew install ffmpeg)"
fi

if command -v ffprobe >/dev/null 2>&1; then
  ok "ffprobe · $(command -v ffprobe)"
else
  missing "ffprobe — install ffmpeg (apt install ffmpeg · brew install ffmpeg)"
fi

NODE_OK=0
if command -v node >/dev/null 2>&1; then
  if NODE_VERSION=$(node -e 'const major = Number(process.versions.node.split(".")[0]); if (major < 18) process.exit(1); console.log(process.versions.node);' 2>/dev/null); then
    NODE_OK=1
    ok "node $NODE_VERSION"
  else
    NODE_VERSION=$(node -v 2>/dev/null) || NODE_VERSION="unknown version"
    missing "node >= 18 (got $NODE_VERSION) — install Node.js 18 or newer"
  fi
else
  missing "node >= 18 — install Node.js 18 or newer"
fi

if [[ -d "$SCRIPTS_DIR/node_modules/playwright-core" ]]; then
  ok "playwright-core · scripts/node_modules/playwright-core"
else
  missing "playwright-core — run: $SETUP"
fi

if (( NODE_OK )) && [[ -d "$SCRIPTS_DIR/node_modules/playwright-core" ]]; then
  if CHROMIUM_PATH=$(node - "$SCRIPTS_DIR/node_modules/playwright-core" <<'JS'
const fs = require('fs');
const path = require('path');
// Playwright launches the headless shell when the full chromium build is absent, so either
// binary satisfies the renderer; executablePath() alone reports a false missing
function shellBinary(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) { const found = shellBinary(p); if (found) return found; }
    else if (/^chrome-headless-shell(\.exe)?$/.test(entry.name)) return p;
  }
  return null;
}
try {
  const { chromium } = require(process.argv[2]);
  const executable = chromium.executablePath();
  try {
    fs.accessSync(executable, fs.constants.X_OK);
    if (fs.statSync(executable).isFile()) { console.log(executable); process.exit(0); }
  } catch { /* fall through to the headless shell */ }
  const match = executable.match(/^(.*)[/\\]chromium-(\d+)[/\\]/);
  if (match) {
    const shell = shellBinary(path.join(match[1], `chromium_headless_shell-${match[2]}`));
    if (shell) { console.log(shell); process.exit(0); }
  }
  process.exit(1);
} catch {
  process.exit(1);
}
JS
  ); then
    ok "Chromium · $CHROMIUM_PATH"
  else
    missing "Chromium — run: $SETUP"
  fi
else
  missing "Chromium — install node >= 18 and playwright-core, then run: $SETUP"
fi

if [[ -s "$ASSETS_DIR/gsap.min.js" ]]; then
  ok "GSAP · assets/gsap.min.js"
else
  missing "GSAP — run: $SETUP"
fi

if (( PYTHON_AVAILABLE )); then
  if ! FONT_REPORT=$(python3 - "$SKILL_DIR" "$SCRIPTS_DIR" "$ASSETS_DIR" "$KIT_ARG" <<'PY'
import json
import re
import shlex
import sys
from pathlib import Path

skill = Path(sys.argv[1])
scripts = Path(sys.argv[2])
assets = Path(sys.argv[3])
kit_arg = sys.argv[4]
setup = f"bash {scripts}/setup.sh"


def emit(status, message):
    print(f"{status}\t{message}")


def check_fonts(css_path, families, label, fix):
    try:
        css = css_path.read_text(encoding="utf-8")
    except OSError:
        emit("missing", f"{label} fonts — {css_path} not installed; run: {fix}")
        return
    blocks = css.split("@font-face")
    for role, family in families:
        pattern = re.compile(r"font-family\s*:\s*['\"]?" + re.escape(family) + r"['\"]?\s*;")
        faces = [block for block in blocks if pattern.search(block)]
        if not faces:
            emit("missing", f"{label} font {family} ({role}) — absent from {css_path}; run: {fix}")
            continue
        sources = [source for face in faces for source in re.findall(r"url\(\s*['\"]?([^)'\"]+)", face)]
        unavailable = [source for source in sources
                       if source.startswith(("http://", "https://"))
                       or not (css_path.parent / source).is_file()
                       or (css_path.parent / source).stat().st_size == 0]
        if not sources or unavailable:
            detail = ", ".join(unavailable) if unavailable else "no local font files"
            emit("missing", f"{label} font {family} ({role}) — {detail}; run: {fix}")
        else:
            emit("ok", f"{label} font {family} ({role}) · {len(sources)} files")


try:
    catalogue = json.loads((skill / "templates/templates.json").read_text(encoding="utf-8"))
    themes = catalogue.get("templates", [])
    families = sorted({(theme["id"], theme["fonts"].split(":", 1)[0])
                       for theme in themes if theme.get("fonts")})
    check_fonts(assets / "fonts.css", families, "theme", setup)
except (OSError, ValueError, KeyError, TypeError) as error:
    emit("missing", f"theme fonts — cannot read templates/templates.json ({error}); restore it from git, then run: {setup}")

if kit_arg:
    fix = f"{setup} {shlex.quote(kit_arg)}"
    try:
        sys.path.insert(0, str(scripts))
        import brand_kit
        kit, root = brand_kit.load(brand_kit.resolve(kit_arg))
        target = assets / "kits" / brand_kit.kit_id(kit, root)
        try:
            manifest = json.loads((target / "kit.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}
        if manifest.get("digest") != brand_kit.digest(kit, root):
            emit("missing", f"kit {target.name} fonts — not installed or stale; run: {fix}")
            emit("missing", f"kit {target.name} logos — not installed or stale; run: {fix}")
        else:
            families = [(role, family) for role, family in manifest.get("families", {}).items()]
            check_fonts(target / "fonts.css", families, f"kit {target.name}", fix)
            logos = list(brand_kit.flatten_logos(kit.get("logos", {})))
            absent = [name for name, source in logos
                      if not (target / "logos" / Path(source).name).is_file()
                      or (target / "logos" / Path(source).name).stat().st_size == 0]
            if absent:
                emit("missing", f"kit {target.name} logos {', '.join(absent)} — run: {fix}")
            else:
                emit("ok", f"kit {target.name} logos · {len(logos)} files")
    except brand_kit.KitError as error:
        emit("missing", f"kit {kit_arg} — {error.problem}; {error.fix}")
    except (OSError, ValueError, KeyError, TypeError) as error:
        emit("missing", f"kit {kit_arg} — cannot inspect installed assets ({error}); run: {fix}")
PY
  ); then
    FONT_REPORT="missing	theme fonts — could not inspect templates/templates.json; run: $SETUP"
  fi
  while IFS=$'\t' read -r status message; do
    if [[ -n "$status" ]]; then
      report "$status" "$message"
    fi
  done <<< "$FONT_REPORT"
else
  missing "theme fonts — install python3 >= 3.10, then run: $SETUP"
  if [[ -n "$KIT_ARG" ]]; then
    missing "kit $KIT_ARG fonts and logos — install python3 >= 3.10, then run: $SETUP \"$KIT_ARG\""
  fi
fi

if (( PYTHON_AVAILABLE )) && python3 -c "import kokoro_onnx" 2>/dev/null; then
  ok "kokoro-onnx importable (optional)"
else
  warn "kokoro-onnx — optional script voices; run: $SETUP --voices"
fi

KOKORO_MISSING=""
for file in kokoro-v1.0.onnx voices-v1.0.bin; do
  if [[ ! -s "$KOKORO_DIR/$file" ]]; then
    KOKORO_MISSING="${KOKORO_MISSING:+$KOKORO_MISSING, }$file"
  fi
done
if [[ -z "$KOKORO_MISSING" ]]; then
  ok "Kokoro voice models · $KOKORO_DIR (optional)"
else
  warn "Kokoro voice models ($KOKORO_MISSING) — optional; run: $SETUP --voices"
fi

if command -v deepFilter >/dev/null 2>&1; then
  ok "deepfilternet · $(command -v deepFilter) (optional)"
else
  warn "deepfilternet — optional voice cleanup; run: $SETUP --enhance"
fi

if (( PYTHON_AVAILABLE )) && python3 -c "import cv2" 2>/dev/null; then
  ok "opencv face detector support (optional)"
else
  warn "opencv-python-headless — optional face detection; run: $SETUP --vision"
fi

if [[ -s "$YUNET_DIR/$YUNET_MODEL" ]]; then
  ok "YuNet face model · $YUNET_DIR/$YUNET_MODEL (optional)"
else
  warn "YuNet face model — optional; run: $SETUP --vision"
fi

if command -v yt-dlp >/dev/null 2>&1; then
  ok "yt-dlp · $(command -v yt-dlp) (optional)"
else
  warn "yt-dlp — optional YouTube clips; run: pipx install yt-dlp"
fi

if command -v pdftoppm >/dev/null 2>&1; then
  ok "pdftoppm · $(command -v pdftoppm) (optional)"
else
  warn "pdftoppm — optional PDF excerpts; install poppler"
fi

MAGICK_MISSING=""
for tool in montage convert; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    MAGICK_MISSING="${MAGICK_MISSING:+$MAGICK_MISSING/}$tool"
  fi
done
if [[ -z "$MAGICK_MISSING" ]]; then
  ok "ImageMagick montage/convert (optional)"
else
  warn "ImageMagick $MAGICK_MISSING — optional; install ImageMagick"
fi

if command -v ffmpeg >/dev/null 2>&1 && ffmpeg -hide_banner -filters 2>/dev/null | grep -q libvmaf; then
  ok "ffmpeg libvmaf support (optional)"
else
  warn "ffmpeg libvmaf — optional quality gate; install an ffmpeg build with libvmaf"
fi

printf 'doctor: %d ok · %d warnings · %d missing\n' "$OK" "$WARNINGS" "$MISSING"
if (( MISSING > 0 )); then
  echo "Next: run the fixes above, then re-run doctor.sh"
  exit 1
fi
echo "Next: make a video — see SKILL.md Step 0"
exit 0
