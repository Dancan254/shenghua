#!/usr/bin/env bash
# make.sh — the one-command happy path around the creative middle.
#
#   make.sh prepare <audio-or-video> <work> [--model small] [--vocab "…"] [--mode bookends|presenter|audio] [--topic "…"]
#     doctor → transcribe → trim, then prints the take's duration and three theme suggestions.
#     The agent (or you) then writes fixes.json and the shot list and fills the template — the
#     creative judgement no script can make.
#
#   make.sh finish <work> <duration> <audio> <out.mp4> [--blur 4] [--music file] [--cover s]
#                  [--source video] [--skip-quality]
#     render-chunks → deliver (with its quality gate) → a verify frame + ffprobe line.
#
# Long renders outlast shell time limits: run finish detached (nohup … &) and poll the log;
# re-running the same command resumes at the first missing chunk.
set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CMD="${1:-}"
[[ -n "$CMD" ]] || { echo "Usage: make.sh prepare <input> <work> [options] | make.sh finish <work> <duration> <audio> <out> [options]"; echo "Next: see SKILL.md for the creative steps in between"; exit 1; }
shift

if [[ "$CMD" == prepare ]]; then
  INPUT="${1:-}"; WORK="${2:-}"
  [[ -f "$INPUT" ]] || { echo "No such recording: ${INPUT:-<missing>}"; echo "Next: pass the audio or video file as the first argument"; exit 1; }
  [[ -n "$WORK" ]] || { echo "prepare needs a work dir as the second argument"; exit 1; }
  shift 2
  MODEL=small
  VOCAB=""
  MODE=audio
  TOPIC=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --model) MODEL="${2:?--model needs a name}"; shift 2 ;;
      --vocab) VOCAB="${2:-}"; shift 2 ;;
      --mode) MODE="${2:?--mode needs bookends|presenter|audio}"; shift 2 ;;
      --topic) TOPIC="${2:-}"; shift 2 ;;
      *) echo "unknown option $1"; echo "Next: prepare takes --model, --vocab, --mode, --topic"; exit 1 ;;
    esac
  done
  mkdir -p "$WORK"
  # Doctor guards the render, not the transcript: warn about gaps now, don't block the prep
  bash "$SCRIPTS_DIR/doctor.sh" || echo "warning: doctor found gaps — fix them before the render (make.sh finish)"
  python3 "$SCRIPTS_DIR/transcribe.py" "$INPUT" --outdir "$WORK" --model "$MODEL" ${VOCAB:+--vocab "$VOCAB"}
  python3 "$SCRIPTS_DIR/trim_take.py" "$INPUT" "$WORK"
  DURATION=$(python3 -c "import json; print(json.load(open('$WORK/take.json'))['duration'])")
  if [[ "$INPUT" =~ \.(mp4|mov|mkv|webm|MP4|MOV)$ ]] && [[ "$MODE" == audio ]]; then MODE=bookends; fi
  python3 "$SCRIPTS_DIR/suggest_theme.py" --mode "$MODE" --topic "$TOPIC"
  echo "prepared · $DURATION s in $WORK"
  echo "Next: proofread transcript.txt (fixes.json), write the shot list, fill_template.py $WORK $DURATION --template <id>, then Steps 5-8 in SKILL.md"
elif [[ "$CMD" == finish ]]; then
  WORK="${1:-}"; DURATION="${2:-}"; AUDIO="${3:-}"; OUT="${4:-}"
  [[ -f "$WORK/index.html" ]] || { echo "No composition at ${WORK:-<missing>}/index.html"; echo "Next: finish takes <work> <duration> <audio> <out.mp4> — fill_template.py first"; exit 1; }
  [[ -f "$AUDIO" ]] || { echo "No audio at ${AUDIO:-<missing>}"; echo "Next: pass the voice.wav from the work dir"; exit 1; }
  [[ -n "$OUT" ]] || { echo "finish needs an output mp4 as the fourth argument"; exit 1; }
  shift 4
  BLUR=()
  MUSIC=()
  COVER=()
  SOURCE=()
  SKIP=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --blur) BLUR=(--blur "${2:?--blur needs a sample count}"); shift 2 ;;
      --music) MUSIC=(--music "${2:?--music needs a file}"); shift 2 ;;
      --cover) COVER=(--cover "${2:?--cover needs seconds}"); shift 2 ;;
      --source) SOURCE=(--source "${2:?--source needs a video}"); shift 2 ;;
      --skip-quality) SKIP=(--skip-quality); shift ;;
      *) echo "unknown option $1"; echo "Next: finish takes --blur, --music, --cover, --source, --skip-quality"; exit 1 ;;
    esac
  done
  bash "$SCRIPTS_DIR/render-chunks.sh" ${BLUR[@]+"${BLUR[@]}"} ${MUSIC[@]+"${MUSIC[@]}"} "$WORK/index.html" "$WORK" "$DURATION" "$AUDIO" "$OUT"
  bash "$SCRIPTS_DIR/deliver.sh" ${COVER[@]+"${COVER[@]}"} ${SOURCE[@]+"${SOURCE[@]}"} ${SKIP[@]+"${SKIP[@]}"} "$WORK" "$OUT"
  ffmpeg -v error -y -ss 1 -i "$OUT" -frames:v 1 -vf scale=360:-1 "$WORK/verify.jpg"
  ffprobe -v error -show_entries format=duration,size -of compact "$OUT"
  echo "Next: look at $WORK/verify.jpg and the delivery folder, listen to the mix, then post"
else
  echo "unknown command: $CMD"
  echo "Next: make.sh prepare <input> <work> — or make.sh finish <work> <duration> <audio> <out>"
  exit 1
fi
