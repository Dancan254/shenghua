#!/usr/bin/env python3
"""Measure face boxes in extracted bookend frames for render.js check.

  face_zones.py <work> [--sample 5]

Samples face/fNNNNN.jpg and writes facezones.js with fractional centre-x, centre-y, width and height.
The optional setup.sh --vision install supplies the YuNet detector; without it this step skips cleanly.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import key_greenscreen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("--sample", type=int, default=5, help="detect every Nth frame (default: 5)")
    args = parser.parse_args()

    face_dir = args.work / "face"
    frames = sorted((path for path in face_dir.glob("f*.jpg") if re.fullmatch(r"f\d{5}", path.stem)),
                    key=lambda path: int(path.stem[1:]))
    if not frames:
        print(f"No face frames in {face_dir}", file=sys.stderr)
        print("Next: run extract_face.sh first", file=sys.stderr)
        return 1
    if args.sample < 1:
        print(f"--sample must be a positive integer, got: {args.sample}", file=sys.stderr)
        print("Next: pass --sample 5, or another positive frame interval", file=sys.stderr)
        return 1

    detector = key_greenscreen.load_detector()
    if detector is None:
        print("face-zone detection skipped: vision not installed")
        print(f"Next: bash {SCRIPTS_DIR / 'setup.sh'} --vision")
        return 0

    import cv2

    selected = frames[::args.sample]
    if selected[-1] != frames[-1]:
        selected.append(frames[-1])
    zones = {}
    for frame in selected:
        bgr = cv2.imread(str(frame))
        if bgr is None:
            print(f"Could not read face frame: {frame}", file=sys.stderr)
            print("Next: re-run extract_face.sh to replace the unreadable frame", file=sys.stderr)
            return 1
        box = key_greenscreen.face_in_image(detector, cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        if box is not None:
            zones[frame.stem] = box

    (args.work / "facezones.js").write_text(f"window.FACE_ZONES={json.dumps(zones)};\n", encoding="utf-8")
    print(f"face zones: {len(zones)}/{len(selected)} frames with a face → facezones.js")
    print(f"Next: node {SCRIPTS_DIR / 'render.js'} check {args.work / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
