#!/usr/bin/env python3
"""Trim a take to its speech: cut the dead air before the first word and after the last.

  trim_take.py <source> <work> [--in auto|<s>] [--out auto|<s>] [--lead 0.5] [--tail 2.5]

Cut points inside the speech make an excerpt: the words outside them are dropped.

Run after transcribe.py. Writes a lossless trimmed voice.wav, shifts words.json and transcript.txt so
the first kept moment is t=0 (the originals stay as words.raw.json and transcript.raw.txt), and
records the cut in take.json for key_greenscreen.py and extract_face.sh. The source video is never
re-encoded. Re-running trims from the raw transcript again, so the cut can be adjusted freely.
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from transcribe import probe_duration, split_phrases

FPS = 30


def edge(value, default):
    return default if value == "auto" else float(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Trim a take to its speech.")
    parser.add_argument("source", type=Path, help="the recording transcribe.py read (video or audio)")
    parser.add_argument("work", type=Path)
    parser.add_argument("--in", dest="cut_in", default="auto", help="seconds into the source to start, or auto")
    parser.add_argument("--out", dest="cut_out", default="auto", help="seconds into the source to end, or auto")
    parser.add_argument("--lead", type=float, default=0.5, help="seconds kept before the first word with --in auto")
    parser.add_argument("--tail", type=float, default=2.5, help="seconds kept after the last word with --out auto (the outro)")
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"No such recording: {args.source}", file=sys.stderr)
        print("Next: pass the same file transcribe.py read", file=sys.stderr)
        return 1
    words_path, raw_path = args.work / "words.json", args.work / "words.raw.json"
    transcript_path, raw_transcript = args.work / "transcript.txt", args.work / "transcript.raw.txt"
    if not raw_path.exists():
        if not words_path.exists():
            print(f"No words.json in {args.work}", file=sys.stderr)
            print("Next: run transcribe.py first", file=sys.stderr)
            return 1
        shutil.copy2(words_path, raw_path)
        shutil.copy2(transcript_path, raw_transcript)
    words = json.loads(raw_path.read_text(encoding="utf-8"))
    length = probe_duration(args.source)

    # Snap to frame boundaries so edit frame N is exactly source frame N + firstFrame
    first_frame = math.floor(max(0.0, edge(args.cut_in, words[0]["s"] - args.lead)) * FPS)
    last_frame = math.ceil(min(length, edge(args.cut_out, words[-1]["e"] + args.tail)) * FPS)
    cut_in, cut_out = first_frame / FPS, min(length, last_frame / FPS)
    # Cutting inside the speech makes an excerpt (a Short from a long talk); words outside it are dropped
    kept = [w for w in words if w["s"] >= cut_in and w["e"] <= cut_out]
    if not kept:
        print(f"No words between {cut_in:.2f}s and {cut_out:.2f}s", file=sys.stderr)
        print("Next: pick --in and --out around the speech you want, or use auto", file=sys.stderr)
        return 1
    dropped = len(words) - len(kept)
    words = kept
    duration = cut_out - cut_in

    # The tail fades so a reach for the stop button never ends the video on a thump
    fade = min(1.0, max(0.0, duration - words[-1]["e"] + cut_in - 0.2))
    voice = args.work / "voice.wav"
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(args.source), "-vn",
         "-af", f"atrim=start={cut_in:.6f}:end={cut_out:.6f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:d=0.03,afade=t=out:st={duration - fade:.3f}:d={fade:.3f}",
         "-c:a", "pcm_s24le", str(voice)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg could not cut the voice: {result.stderr.strip()[-300:]}", file=sys.stderr)
        print("Next: check the recording has an audio track (ffprobe it)", file=sys.stderr)
        return 1

    shifted = [{**w, "s": round(w["s"] - cut_in, 2), "e": round(w["e"] - cut_in, 2)} for w in words]
    words_path.write_text(json.dumps(shifted), encoding="utf-8")
    with transcript_path.open("w", encoding="utf-8") as handle:
        for phrase in split_phrases(shifted):
            handle.write(f"[{phrase[0]['s']:.2f}] " + " ".join(f"{w['t']}@{w['s']:.2f}" for w in phrase) + "\n")
    take = {"source": str(args.source.resolve()), "in": round(cut_in, 6), "out": round(cut_out, 6),
            "duration": round(duration, 6), "firstFrame": first_frame, "fps": FPS}
    (args.work / "take.json").write_text(json.dumps(take, indent=2) + "\n", encoding="utf-8")

    excerpt = f" · excerpt: {dropped} words outside the cut dropped" if dropped else ""
    print(f"trimmed {cut_in:.2f}–{cut_out:.2f}s of {length:.2f}s → {duration:.2f}s · first word at "
          f"{shifted[0]['s']:.2f}s, last ends {shifted[-1]['e']:.2f}s{excerpt} · {voice}")
    print(f"Next: proofread transcript.txt (times now start at 0); use {voice.name} as the audio and "
          f"{duration:.2f} as the duration from here on")
    return 0


if __name__ == "__main__":
    sys.exit(main())
