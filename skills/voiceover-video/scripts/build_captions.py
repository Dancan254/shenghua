#!/usr/bin/env python3
"""Apply fixes.json to words.json and write words.js for the caption engine.

fixes.json maps a raw transcribed token to its correction; an empty string drops the token.
Timestamps are never touched.
"""

import json
import sys
from pathlib import Path

from transcribe import split_phrases


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: build_captions.py <work-dir>", file=sys.stderr)
        return 1

    work = Path(sys.argv[1])
    words_path = work / "words.json"
    if not words_path.is_file():
        print(f"No words.json in {work}", file=sys.stderr)
        print("Next: run transcribe.py with --outdir pointing at this directory", file=sys.stderr)
        return 1

    fixes_path = work / "fixes.json"
    fixes = json.loads(fixes_path.read_text(encoding="utf-8")) if fixes_path.is_file() else {}
    words = json.loads(words_path.read_text(encoding="utf-8"))

    applied = 0
    fixed = []
    for word in words:
        replacement = fixes.get(word["t"], word["t"])
        if replacement != word["t"]:
            applied += 1
        if replacement:
            fixed.append({**word, "t": replacement})

    unused = [token for token in fixes if not any(w["t"] == token for w in words)]
    phrases = split_phrases(fixed)
    (work / "words.js").write_text("window.PHRASES=" + json.dumps(phrases) + ";", encoding="utf-8")

    print(f"{len(fixed)} words · {len(phrases)} phrases · {applied} fixes applied")
    if unused:
        print(f"  unmatched fixes: {', '.join(unused)} — tokens must match transcript.txt exactly, punctuation included")
    print(f"Next: write the shot list (load references/scene-blocks.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
