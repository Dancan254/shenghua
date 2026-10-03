#!/usr/bin/env bash
# mix-encode.sh [--10bit] [--embed] <work-dir> <voice-audio> <duration> <out.mp4> [music-file]
#
# Voice is denoised, de-essed, compressed and normalised; clip audio and music duck under it via sidechain,
# SFX sit on top, and the mix is padded/trimmed to the exact duration, then measured, then given one linear gain to −14 LUFS with a −1.5 dBFS peak limiter.
# Draft JPEG frames encode veryfast/CRF 20 (VV_PRESET overrides the preset); --10bit encodes yuv420p10le
# High 10 against banding in dark gradients; --embed muxes captions.srt as a soft subtitle track, and any
# captions.srt/captions.vtt are copied next to the mp4.
set -euo pipefail

TEN_BIT=0
EMBED=0
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --10bit) TEN_BIT=1 ;;
    --embed) EMBED=1 ;;
    *) echo "unknown flag: $1"; echo "Next: pass --10bit or --embed first, then the work dir, voice audio, duration and output mp4"; exit 1 ;;
  esac
  shift
done

WORK="$1"
trap 'rm -f "$WORK/premix.wav"' EXIT
VOICE="$2"
DURATION="$3"
OUT="$4"
MUSIC="${5:-$WORK/music.wav}"
FPS=30

[[ -d "$WORK/frames" ]] || { echo "No frames in $WORK/frames"; echo "Next: run render-frames.sh"; exit 1; }
# render.js writes PNG (high) or JPEG (draft); one video must come from one kind
shopt -s nullglob
PNGS=("$WORK"/frames/f*.png); JPGS=("$WORK"/frames/f*.jpg)
shopt -u nullglob
if (( ${#PNGS[@]} > 0 && ${#JPGS[@]} > 0 )); then
  echo "frames/ mixes high-quality PNG and draft JPEG frames"
  echo "Next: re-run render-frames.sh over the whole video with one VV_QUALITY setting"
  exit 1
fi
FRAME_EXT=png
(( ${#PNGS[@]} == 0 )) && FRAME_EXT=jpg
[[ -f "$WORK/sfx.wav" ]] || { echo "No sfx.wav in $WORK"; echo "Next: run synth_audio.py"; exit 1; }

# Draft JPEGs are a throwaway preview cut, so encode speed beats the last bit of quality;
# final PNGs keep the slow preset. VV_PRESET overrides either, e.g. medium on a slow machine.
PRESET=slow
CRF=16
if [[ "$FRAME_EXT" == jpg ]]; then
  PRESET=veryfast
  CRF=20
fi
PRESET="${VV_PRESET:-$PRESET}"

PIX_FMT=yuv420p
X264_PROFILE=()
if (( TEN_BIT )); then
  PIX_FMT=yuv420p10le
  X264_PROFILE=(-profile:v high10)
fi

if (( EMBED )); then
  [[ -f "$WORK/captions.srt" ]] || { echo "--embed needs captions.srt in $WORK"; echo "Next: run build_captions.py so it writes captions.srt, then re-run with --embed"; exit 1; }
  EMBED_ARGS=(-i "$WORK/captions.srt" -map 2 -c:s mov_text -metadata:s:s:0 language=eng)
else
  EMBED_ARGS=()
fi

# Clip audio from extract_clip.sh --audio: a speaking founder, a crowd, a product sound
shopt -s nullglob
CLIP_WAVS=("$WORK"/clips/*.wav)
shopt -u nullglob

INPUTS=(-i "$VOICE")
FILTER="[0:a]aresample=48000,apad=whole_dur=${DURATION},highpass=f=80,afftdn=nr=12:nf=-40:tn=1,deesser=i=0.4,equalizer=f=3500:t=q:w=1.2:g=2,acompressor=threshold=-18dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-2,aresample=48000,asplit=3[voice][vkey][ckey];"
LAYERS="[voice]"
COUNT=1
NEXT=1

if (( ${#CLIP_WAVS[@]} > 0 )); then
  CLIP_LABELS=""
  for wav in "${CLIP_WAVS[@]}"; do
    INPUTS+=(-i "$wav")
    FILTER+="[${NEXT}:a]aresample=48000[c${NEXT}];"
    CLIP_LABELS+="[c${NEXT}]"
    NEXT=$(( NEXT + 1 ))
  done
  # Narration wins where they overlap; over a pause in the voice the clip plays at full level
  FILTER+="${CLIP_LABELS}amix=inputs=${#CLIP_WAVS[@]}:normalize=0:duration=longest,apad=whole_dur=${DURATION},asplit=2[craw][cclip];"
  FILTER+="[craw][ckey]sidechaincompress=threshold=0.03:ratio=6:attack=15:release=250[clips];"
  FILTER+="[vkey][cclip]amix=inputs=2:normalize=0:duration=first[key];"
  LAYERS+="[clips]"
  COUNT=$(( COUNT + 1 ))
else
  FILTER+="[ckey]anullsink;[vkey]anull[key];"
fi

if [[ -f "$MUSIC" ]]; then
  INPUTS+=(-i "$MUSIC")
  FILTER+="[${NEXT}:a]aresample=48000,volume=0.22[mus];[mus][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck];"
  LAYERS+="[duck]"
  COUNT=$(( COUNT + 1 ))
  NEXT=$(( NEXT + 1 ))
else
  FILTER+="[key]anullsink;"
fi

INPUTS+=(-i "$WORK/sfx.wav")
FILTER+="[${NEXT}:a]aresample=48000,volume=0.5[fx];"
LAYERS+="[fx]"
COUNT=$(( COUNT + 1 ))

ffmpeg -v error -y "${INPUTS[@]}" -filter_complex "\
${FILTER}\
${LAYERS}amix=inputs=${COUNT}:normalize=0:duration=longest,alimiter=limit=0.95,aresample=48000,atrim=0:${DURATION}[out]" \
  -map "[out]" -c:a pcm_f32le "$WORK/premix.wav"

# Measuring first lets pass 2 apply one static gain; loudnorm linear=true falls back to dynamic when the limited premix can't take the gain within TP
MEASURED=$(ffmpeg -hide_banner -nostats -i "$WORK/premix.wav" -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1) || {
  printf '%s\n' "$MEASURED" | tail -n 15 >&2
  echo "loudnorm measurement failed on $WORK/premix.wav"; echo "Next: fix the ffmpeg error above and check that the voice file is valid audio"; exit 1; }
GAIN_DB=$(printf '%s' "$MEASURED" | python3 -c '
import json, re, sys
match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", sys.stdin.read(), re.S)
if not match:
    sys.exit(1)
print("{:.2f}".format(-14 - float(json.loads(match.group(0))["input_i"])))
') || { echo "Could not parse loudnorm measurement JSON for $WORK/premix.wav"; echo "Next: run ffmpeg -i premix.wav -af loudnorm=print_format=json -f null - and check its output"; exit 1; }

# 0.8414 = -1.5 dBFS ceiling; the limiter catches peaks the gain pushes over it
ffmpeg -v error -y -i "$WORK/premix.wav" \
  -af "volume=${GAIN_DB}dB,alimiter=limit=0.8414:level=disabled,aresample=48000,apad=whole_dur=${DURATION},atrim=0:${DURATION}" "$WORK/mix.wav"

TOTAL_FRAMES=$(python3 -c "import math; print(math.ceil($DURATION * $FPS))")

# Frames are RGB; convert with the BT.709 matrix and tag it, or phones shift the brand colours.
# CRF 16 on a slow preset keeps edges clean through the platform's re-encode; grain defeats CRF on
# its own, so the maxrate cap keeps a 108s vertical near 200 MB instead of 800+.
# -progress emits machine-readable blocks; the filter throttles them to a status line every few seconds.
ffmpeg -v error -nostats -progress pipe:1 -y \
  -framerate "$FPS" -i "$WORK/frames/f%05d.$FRAME_EXT" -i "$WORK/mix.wav" \
  ${EMBED_ARGS[@]+"${EMBED_ARGS[@]}"} \
  -map 0:v -map 1:a \
  -vf "scale=out_color_matrix=bt709:out_range=tv:flags=lanczos+accurate_rnd+full_chroma_int,format=$PIX_FMT" \
  -c:v libx264 -preset "$PRESET" -crf "$CRF" ${X264_PROFILE[@]+"${X264_PROFILE[@]}"} -maxrate 16M -bufsize 32M -x264-params aq-mode=3 \
  -colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
  -c:a aac -b:a 256k -t "$DURATION" -movflags +faststart "$OUT" \
  | python3 -c '
import sys, time
total = int(sys.argv[1])
fields = {}
last = 0.0
for line in sys.stdin:
    key, _, value = line.partition("=")
    fields[key.strip()] = value.strip()
    if key.strip() != "progress":
        continue
    now = time.monotonic()
    if now - last < 3 and fields.get("progress") != "end":
        continue
    last = now
    frame = int(fields.get("frame") or 0)
    try:
        fps = float(fields.get("fps") or 0)
    except ValueError:
        fps = 0.0
    left = int((total - frame) / fps) if fps > 0 else 0
    print("encode: {}/{} frames · {:.0f} fps · ~{}s left".format(frame, total, fps, left), flush=True)
' "$TOTAL_FRAMES"

# Platforms index uploaded caption files; burned-in captions can't be searched, translated or switched off
BASE_OUT="${OUT%.*}"
CAPTIONS=""
for ext in srt vtt; do
  if [[ -f "$WORK/captions.$ext" ]]; then
    cp "$WORK/captions.$ext" "$BASE_OUT.$ext"
    CAPTIONS+="$ext "
  fi
done

LOUDNESS=$(ffmpeg -hide_banner -i "$WORK/mix.wav" -af ebur128 -f null - 2>&1 | awk '/I:/{v=$2} END{print v}')
INFO=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of default=nw=1 "$OUT" | tr '\n' ' ')$(ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$OUT" | tr '\n' ' ')
NOTE=" · preset $PRESET"
(( TEN_BIT )) && NOTE+=" · 10-bit"
[[ -n "$CAPTIONS" ]] && NOTE+=" · captions: ${CAPTIONS% }"
echo "$(basename "$OUT") · ${LOUDNESS} LUFS · ${INFO}${NOTE}"
echo "Next: extract a frame from $(basename "$OUT") at a shot you changed and verify it"
