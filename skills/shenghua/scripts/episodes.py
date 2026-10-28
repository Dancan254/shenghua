#!/usr/bin/env python3
"""Split a script or timed transcript into episode projects, or inspect a series.

  episodes.py split <script.txt|transcript.txt> --episodes N --outdir <dir> [--slug name]
  episodes.py status <outdir>

Splits happen only at sentence boundaries in plain scripts or phrase boundaries in transcripts.
Each epN-... folder contains only that episode's script.txt, ready for the normal workflow.
"""

import argparse
import math
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

SENTENCE_END = re.compile(r"[.!?]+(?:[\"'”’)\]]*)?(?=\s|$)")
TRANSCRIPT_START = re.compile(r"^\[(-?(?:\d+(?:\.\d+)?|\.\d+))]\s+")
TRANSCRIPT_LINE = re.compile(r"^\[(-?(?:\d+(?:\.\d+)?|\.\d+))]\s+(\S.*)$")


class EpisodeError(Exception):
    def __init__(self, message: str, next_step: str):
        super().__init__(message)
        self.next_step = next_step


@dataclass
class Segment:
    text: str
    words: int
    duration: float | None = None


def word_count(text: str) -> int:
    return len(text.split())


def plain_segments(text: str) -> list[Segment]:
    segments, start = [], 0
    for match in SENTENCE_END.finditer(text):
        sentence = text[start:match.end()].strip()
        if sentence:
            segments.append(Segment(sentence, word_count(sentence)))
        start = match.end()
    remainder = text[start:].strip()
    if remainder:
        segments.append(Segment(remainder, word_count(remainder)))
    if not segments:
        raise EpisodeError("The input has no script content", "pass a non-empty script or transcript")
    return segments


def transcript_segments(text: str) -> list[Segment]:
    phrases = []
    previous_time = None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = TRANSCRIPT_LINE.fullmatch(line.strip())
        if not match:
            raise EpisodeError(f"Malformed transcript line {number}: {line.strip()}",
                               "use transcript.txt lines like [12.34] word@12.34 word@12.90")
        words, times = [], []
        for token in match.group(2).split():
            word, separator, stamp = token.rpartition("@")
            try:
                seconds = float(stamp) if separator and word else math.nan
            except ValueError:
                seconds = math.nan
            if not math.isfinite(seconds):
                raise EpisodeError(f"Malformed word timing on transcript line {number}: {token}",
                                   "give every word an @seconds timestamp")
            if previous_time is not None and seconds < previous_time:
                raise EpisodeError(f"Transcript timings go backwards on line {number}",
                                   "sort the transcript by its original word timings")
            words.append(word)
            times.append(seconds)
            previous_time = seconds
        phrases.append((" ".join(words), times))
    if not phrases:
        raise EpisodeError("The transcript has no phrases", "pass a non-empty timed transcript")

    starts = [times[0] for _, times in phrases]
    phrase_gaps = [starts[index + 1] - times[-1] for index, (_, times) in enumerate(phrases[:-1])
                   if starts[index + 1] > times[-1]]
    word_gaps = [later - earlier for phrase in phrases for earlier, later in zip(phrase[1], phrase[1][1:]) if later > earlier]
    tail = statistics.median(phrase_gaps or word_gaps) if phrase_gaps or word_gaps else 0.5
    segments = []
    for index, (phrase, times) in enumerate(phrases):
        end = starts[index + 1] if index + 1 < len(starts) else times[-1] + tail
        segments.append(Segment(phrase, len(times), max(0.0, end - times[0])))
    return segments


def load_segments(path: Path) -> tuple[list[Segment], bool]:
    if not path.is_file():
        raise EpisodeError(f"No such script or transcript: {path}", "pass an existing script.txt or transcript.txt")
    text = path.read_text(encoding="utf-8")
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    timed = bool(TRANSCRIPT_START.match(first))
    return (transcript_segments(text) if timed else plain_segments(text)), timed


def partition(segments: list[Segment], episodes: int) -> list[list[Segment]]:
    if episodes < 1:
        raise EpisodeError("--episodes must be at least 1", "pass a positive episode count")
    if episodes > len(segments):
        raise EpisodeError(
            f"Not enough material for {episodes} episodes: only {len(segments)} sentence/phrase boundaries",
            "ask for fewer episodes or a longer script",
        )
    timed = segments[0].duration is not None
    weights = [segment.duration if timed else segment.words for segment in segments]
    groups, start = [], 0
    for remaining in range(episodes, 0, -1):
        target = sum(weights[start:]) / remaining
        latest_end = len(segments) - remaining + 1
        end, total = start, 0.0
        while end < latest_end:
            weight = weights[end]
            if end > start and abs(total - target) <= abs(total + weight - target):
                break
            total += weight
            end += 1
        groups.append(segments[start:end])
        start = end
    return groups


def slugify(text: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", text.lower())) or "episode"


def episode_slug(group: list[Segment], prefix: str | None, number: int) -> str:
    if prefix is not None:
        return f"{slugify(prefix)}-{number}"
    return slugify(" ".join(group[0].text.split()[:4]))


def opening(text: str) -> str:
    words = text.split()
    return " ".join(words[:6]) + ("…" if len(words) > 6 else "")


def split_command(args: argparse.Namespace) -> int:
    segments, timed = load_segments(args.source)
    groups = partition(segments, args.episodes)
    args.outdir.mkdir(parents=True, exist_ok=True)
    print(f"Split {args.source.name} into {len(groups)} episodes → {args.outdir}")
    for number, group in enumerate(groups, 1):
        folder = args.outdir / f"ep{number}-{episode_slug(group, args.slug, number)}"
        folder.mkdir(parents=True, exist_ok=True)
        script = "\n".join(segment.text for segment in group) + "\n"
        (folder / "script.txt").write_text(script, encoding="utf-8")
        words = sum(segment.words for segment in group)
        duration = f"{sum(segment.duration for segment in group):.1f}s · " if timed else ""
        print(f"{folder.name} · {duration}{words} words · starts '{opening(group[0].text)}'")
    print("Next: run each episode through the normal workflow (transcribe/speak → trim → shot list)")
    return 0


def episode_order(path: Path) -> tuple[int, str]:
    match = re.match(r"ep(\d+)(?:-|$)", path.name)
    return (int(match.group(1)) if match else sys.maxsize, path.name)


def status_command(args: argparse.Namespace) -> int:
    if not args.outdir.is_dir():
        raise EpisodeError(f"No such series directory: {args.outdir}", "pass the --outdir used by episodes.py split")
    folders = sorted((path for path in args.outdir.glob("ep*") if path.is_dir()), key=episode_order)
    if not folders:
        raise EpisodeError(f"No ep* episode folders in {args.outdir}", "run episodes.py split first")
    missing = []
    for folder in folders:
        videos = sorted(path.name for path in (folder / "delivery").glob("*.mp4")) if (folder / "delivery").is_dir() else []
        if not videos:
            missing.append(folder.name)
        artefacts = [f"{name}={'yes' if (folder / name).is_file() else 'no'}"
                     for name in ("script.txt", "words.json", "index.html")]
        artefacts.append(f"delivery={', '.join(videos) if videos else 'none'}")
        print(f"{folder.name} · " + " · ".join(artefacts))
    if missing:
        print(f"Next: no delivery mp4 yet: {', '.join(missing)}; finish these through the normal workflow")
    else:
        print("Next: all episodes have a delivery mp4; review and publish the series")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    split = commands.add_parser("split", help="split a script or transcript into episode folders")
    split.add_argument("source", type=Path)
    split.add_argument("--episodes", type=int, required=True)
    split.add_argument("--outdir", type=Path, required=True)
    split.add_argument("--slug", default=None, help="folder prefix; episode number is appended")
    status = commands.add_parser("status", help="show pipeline artefacts for each episode")
    status.add_argument("outdir", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return split_command(args) if args.command == "split" else status_command(args)
    except EpisodeError as error:
        print(error, file=sys.stderr)
        print(f"Next: {error.next_step}", file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as error:
        print(f"Could not read or write episode files: {error}", file=sys.stderr)
        print("Next: check the input encoding and choose a readable input and writable outdir", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
