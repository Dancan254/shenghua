#!/usr/bin/env python3
"""Apply fixes.json and keywords.json to words.json and write words.js for the caption engine.

fixes.json maps a raw transcribed token to its correction; an empty string drops the token.
A key written as `token@time` fixes only the word that starts at that time, for tokens like
`that` that are misheard once but correct everywhere else. Timestamps are never touched.

keywords.json is an array of words to keep in the accent colour. An entry matches case-insensitively,
ignoring punctuation; `word@time` flags only the one occurrence.

Also writes captions.srt and captions.vtt from the same phrases, for platforms that index uploaded
caption files. words.json is already shifted to the edit by trim_take.py, so the cue times match the
video after a trim.

--from-srt re-imports text edits by matching cues to the original phrases by time overlap. For a
matched phrase the SRT text wins and fixes.json is skipped; keywords.json still applies. Unmatched
phrases keep the normal fixes.json behavior.
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

PHRASE_MAX_WORDS = 5
# transcript.txt prints times to two decimals, so a typed time is at most 5ms off
TIME_TOLERANCE = 0.006
PUNCTUATION = ".,!?;:\"'()"


def split_phrases(words):
    """Group words into caption phrases. Mirrors transcribe.split_phrases."""
    phrases, current = [], []
    for word in words:
        current.append(word)
        if len(current) >= PHRASE_MAX_WORDS or word["t"][-1] in ".,?!":
            phrases.append(current)
            current = []
    if current:
        phrases.append(current)
    return phrases


def parse_key(key):
    """Split `token@time` into (token, time); a plain token returns (token, None)."""
    token, separator, time = key.rpartition("@")
    if not separator or not token:
        return key, None
    try:
        return token, float(time)
    except ValueError:
        return key, None


def starts_at(word, time):
    return time is None or abs(word["s"] - time) < TIME_TOLERANCE


def bare(token):
    return token.strip(PUNCTUATION).lower()


def load_json(path, expected_type, example):
    """Return the parsed file, a default when it is absent, or None after printing the error."""
    if not path.is_file():
        return expected_type()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"{path} is not valid JSON: {e}", file=sys.stderr)
        print("Next: fix the JSON syntax, then re-run build_captions.py", file=sys.stderr)
        return None
    if not isinstance(data, expected_type):
        print(f"{path} must look like {example}", file=sys.stderr)
        print(f"Next: rewrite {path.name} in that shape, then re-run build_captions.py", file=sys.stderr)
        return None
    return data


def clock(seconds, separator):
    """Format seconds as HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm (VTT)."""
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{ms:03d}"


def caption_cues(phrases):
    """One cue per phrase; a cue stays up until the next phrase, mirroring renderCaptions."""
    cues = []
    for i, phrase in enumerate(phrases):
        start = phrase[0]["s"]
        end = phrase[-1]["e"] + 0.6
        if i + 1 < len(phrases):
            end = min(end, phrases[i + 1][0]["s"])
        cues.append((start, max(end, start + 0.1), " ".join(word["t"] for word in phrase)))
    return cues


def write_caption_files(work, phrases):
    cues = caption_cues(phrases)
    srt = "".join(f"{i}\n{clock(start, ',')} --> {clock(end, ',')}\n{text}\n\n"
                  for i, (start, end, text) in enumerate(cues, 1))
    vtt = "WEBVTT\n\n" + "".join(f"{clock(start, '.')} --> {clock(end, '.')}\n{text}\n\n"
                                 for start, end, text in cues)
    (work / "captions.srt").write_text(srt, encoding="utf-8")
    (work / "captions.vtt").write_text(vtt, encoding="utf-8")
    return len(cues)


def parse_srt_timestamp(value):
    match = re.fullmatch(r"(\d+):([0-5]\d):([0-5]\d),(\d{3})", value)
    if not match:
        raise ValueError(f"invalid timestamp {value!r}; expected HH:MM:SS,mmm")
    hours, minutes, seconds, milliseconds = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def parse_srt(text):
    """Parse sequence numbers, comma-decimal timings and multiline cue text."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ValueError("the SRT contains no cues")
    cues = []
    for block in re.split(r"\n[\t ]*\n", text.strip()):
        lines = block.split("\n")
        if not lines[0].strip().isdigit():
            raise ValueError(f"expected a numeric cue sequence, got {lines[0]!r}")
        sequence = int(lines[0].strip())
        if len(lines) < 3:
            raise ValueError(f"cue {sequence} needs a timing line and text")
        timing = re.fullmatch(
            r"\s*(\d+:\d{2}:\d{2},\d{3})\s+-->\s+"
            r"(\d+:\d{2}:\d{2},\d{3})(?:\s+.*)?", lines[1])
        if not timing:
            raise ValueError(f"cue {sequence} has an invalid timing line: {lines[1]!r}")
        start, end = (parse_srt_timestamp(value) for value in timing.groups())
        if end <= start:
            raise ValueError(f"cue {sequence} must end after it starts")
        cues.append({"sequence": sequence, "s": start, "e": end, "text": "\n".join(lines[2:])})
    return cues


def match_srt_cues(cues, phrases):
    """Greedily assign greatest-overlap pairs without reusing a cue or phrase."""
    candidates = []
    for cue_index, cue in enumerate(cues):
        for phrase_index, phrase in enumerate(phrases):
            overlap = min(cue["e"], phrase[-1]["e"]) - max(cue["s"], phrase[0]["s"])
            if overlap > 0:
                candidates.append((-overlap, cue_index, phrase_index))
    candidates.sort()
    matches = {}
    used_phrases = set()
    for _, cue_index, phrase_index in candidates:
        if cue_index not in matches and phrase_index not in used_phrases:
            matches[cue_index] = phrase_index
            used_phrases.add(phrase_index)
    unmatched = [index for index in range(len(cues)) if index not in matches]
    return matches, unmatched


def interpolated_words(tokens, start, end):
    step = (end - start) / len(tokens)
    result = []
    for index, token in enumerate(tokens):
        word_end = end if index == len(tokens) - 1 else start + (index + 1) * step
        result.append({"t": token, "s": start + index * step, "e": word_end})
    return result


def insertion_span(phrase, index, cue):
    left = phrase[index - 1] if index else None
    right = phrase[index] if index < len(phrase) else None
    if left and right:
        return left["e"], right["s"]
    if right:
        return (cue["s"] if cue else right["s"]), right["s"]
    if left:
        return left["e"], (cue["e"] if cue else left["e"])
    raise ValueError("cannot align text to an empty phrase")


def align_phrase(phrase, text, cue=None):
    """Apply edited cue text while retaining or interpolating the original word times."""
    edited = text.split()
    matcher = difflib.SequenceMatcher(a=[word["t"] for word in phrase], b=edited, autojunk=False)
    aligned = []
    for operation, i1, i2, j1, j2 in matcher.get_opcodes():
        tokens = edited[j1:j2]
        if operation == "equal":
            aligned.extend(dict(word) for word in phrase[i1:i2])
        elif operation == "delete":
            continue
        elif operation == "replace":
            aligned.extend(interpolated_words(tokens, phrase[i1]["s"], phrase[i2 - 1]["e"]))
        elif operation == "insert":
            start, end = insertion_span(phrase, i1, cue)
            aligned.extend(interpolated_words(tokens, start, end))
    return aligned


def apply_fixes(words, parsed_fixes, used_fixes):
    fixed = []
    applied = 0
    for word in words:
        replacement = word["t"]
        for (token, time), value in parsed_fixes:
            if word["t"] == token and starts_at(word, time):
                replacement = value
                used_fixes.add((token, time))
                break
        if replacement != word["t"]:
            applied += 1
        if replacement:
            fixed.append({**word, "t": replacement})
    return fixed, applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Build timed captions, optionally re-importing an edited SRT.")
    parser.add_argument("work", type=Path, metavar="work-dir")
    parser.add_argument("--from-srt", type=Path, metavar="FILE",
                        help="re-import cue text; SRT wins over fixes.json for matched phrases")
    args = parser.parse_args()

    work = args.work
    words_path = work / "words.json"
    if not words_path.is_file():
        print(f"No words.json in {work}", file=sys.stderr)
        print("Next: run transcribe.py with --outdir pointing at this directory", file=sys.stderr)
        return 1

    fixes = load_json(work / "fixes.json", dict, '{"San": "Sun", "that@50.22": "data"}')
    keywords = load_json(work / "keywords.json", list, '["Java", "Kafka@12.40"]')
    if fixes is None or keywords is None:
        return 1
    words = json.loads(words_path.read_text(encoding="utf-8"))

    edited_cues = None
    original_phrases = None
    matches = None
    if args.from_srt:
        try:
            edited_cues = parse_srt(args.from_srt.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as e:
            print(f"Cannot re-import {args.from_srt}: {e}", file=sys.stderr)
            print("Next: fix the SRT file, then re-run build_captions.py --from-srt", file=sys.stderr)
            return 1
        original_phrases = split_phrases(words)
        matches, unmatched = match_srt_cues(edited_cues, original_phrases)
        if unmatched:
            sequences = ", ".join(str(edited_cues[index]["sequence"]) for index in unmatched)
            print(f"{args.from_srt}: {len(unmatched)} of {len(edited_cues)} cues match no phrase "
                  f"in words.json (SRT sequences: {sequences})", file=sys.stderr)
            print("Next: use fixes.json for wholesale rewrites, or check you edited the captions.srt "
                  "this work dir produced", file=sys.stderr)
            return 1

    # Timed keys go first so `that@50.22` wins over a plain `that`
    parsed_fixes = sorted(((parse_key(key), value) for key, value in fixes.items()), key=lambda f: f[0][1] is None)
    used_fixes = set()
    applied = 0
    if edited_cues is None:
        fixed, applied = apply_fixes(words, parsed_fixes, used_fixes)
    else:
        aligned = {phrase_index: align_phrase(original_phrases[phrase_index], edited_cues[cue_index]["text"],
                                              edited_cues[cue_index])
                   for cue_index, phrase_index in matches.items()}
        fixed = []
        for phrase_index, phrase in enumerate(original_phrases):
            if phrase_index in aligned:
                fixed.extend(aligned[phrase_index])
            else:
                phrase_fixed, phrase_applied = apply_fixes(phrase, parsed_fixes, used_fixes)
                fixed.extend(phrase_fixed)
                applied += phrase_applied

    parsed_keywords = [parse_key(entry) for entry in keywords if isinstance(entry, str) and bare(entry)]
    used_keywords = set()
    marked = 0
    for word in fixed:
        for token, time in parsed_keywords:
            if bare(word["t"]) == bare(token) and starts_at(word, time):
                word["k"] = 1
                used_keywords.add((token, time))
                marked += 1
                break

    phrases = split_phrases(fixed)
    (work / "words.js").write_text("window.PHRASES=" + json.dumps(phrases) + ";", encoding="utf-8")
    cue_count = write_caption_files(work, phrases)

    unused_fixes = [key for key in fixes if parse_key(key) not in used_fixes]
    unused_keywords = [entry for entry in keywords if isinstance(entry, str) and parse_key(entry) not in used_keywords]
    if edited_cues is None:
        print(f"{len(fixed)} words · {len(phrases)} phrases · {applied} fixes applied · {marked} keywords flagged"
              f" · {cue_count} cues in captions.srt + captions.vtt")
    else:
        print(f"captions re-imported · {len(matches)} phrases updated from {args.from_srt.name}")
    if unused_fixes:
        print(f"  unmatched fixes: {', '.join(unused_fixes)} — tokens must match transcript.txt exactly, punctuation included; @time must be the word's start")
    if unused_keywords:
        print(f"  unmatched keywords: {', '.join(unused_keywords)} — match ignores case and punctuation; @time must be the word's start")
    if edited_cues is None:
        print("Next: write the shot list (load references/scene-blocks.md)")
    else:
        print("Next: re-render the affected ranges")
    return 0


if __name__ == "__main__":
    sys.exit(main())
