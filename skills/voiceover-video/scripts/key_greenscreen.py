#!/usr/bin/env python3
"""Key the green screen out of a take: presenter/fNNNNN.webp with alpha, numbered by edit frame.

  key_greenscreen.py <work> [--video take.mp4] [--mask x,y,w,h …] [--quality web|master]
                     [--workers N] [--preview <t>] [--over '#0b1410']

Reads take.json from trim_take.py (without it, the whole video is the edit). Measures the screen from
sample frames instead of hand-set thresholds, and fails with the reason when the take can't be keyed.
Resumable: a re-run keeps every complete frame and re-keys the rest, so a killed run just continues.
--preview <t> keys the one frame at edit time t and writes presenter-preview.png to judge the key first.
"""

import argparse
import concurrent.futures
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

FPS = 30
CHUNK = 450  # largest job: small enough to spread across workers, large enough to amortise the seek


class TakeError(Exception):
    """A take that can't be keyed; carries the problem and the fix."""

    def __init__(self, problem, fix):
        super().__init__(problem)
        self.problem, self.fix = problem, fix


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(video)],
                         capture_output=True, text=True, check=True)
    info = json.loads(out.stdout)
    stream = info["streams"][0]
    return stream["width"], stream["height"], float(info["format"]["duration"])


def read_frame(video, seconds, width, height):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{seconds:.6f}", "-i", str(video), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(height, width, 3)


def dominance(frame):
    rgb = frame.astype(np.int16)
    return rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])


def measure(video, take, width, height):
    """Screen colour and matte thresholds from the frame borders, where the screen shows round the speaker."""
    samples = [take["in"] + take["duration"] * k / 9 for k in range(1, 9)]
    borders, colours = [], []
    bw, bh = max(8, width // 10), max(8, height // 10)
    for seconds in samples:
        frame = read_frame(video, seconds, width, height)
        regions = [frame[:, :bw], frame[:, -bw:], frame[:bh, bw:-bw]]
        for region in regions:
            d = dominance(region).ravel()
            borders.append(d)
            green = region.reshape(-1, 3)[d > 8]
            if len(green):
                colours.append(green)
    border = np.concatenate(borders)
    screen_share = float((border > 8).mean())
    if screen_share < 0.5:
        raise TakeError(f"Less than half of the frame border is green screen ({screen_share:.0%}); this take has no screen to key",
                        "edit it with face shots instead (extract_face.sh), or reframe the recording")
    screen = border[border > 8]
    floor = float(np.percentile(screen, 2))
    if floor < 10:
        raise TakeError(f"The screen is too dim or uneven to key (its greenest 98% only clears the subject by {floor:.0f})",
                        "light the screen evenly and separately from the speaker; see docs/recording-guide.md")
    # The matte ramps from opaque at `low` to clear at `high`, kept below the screen's weakest green
    high = round(floor * 0.75)
    low = max(2, round(high * 0.2))
    colour = np.median(np.concatenate(colours), axis=0).round().astype(int).tolist()
    return {"screen": colour, "low": low, "high": high, "margin": round(floor, 1), "borderGreen": round(screen_share, 2)}


def neighbourhood(plane, combine):
    height, width = plane.shape
    padded = np.pad(plane, 1, mode="edge")
    result = padded[1:-1, 1:-1].copy()
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            if (dy, dx) != (1, 1):
                result = combine(result, padded[dy:dy + height, dx:dx + width])
    return result


def box5(plane):
    return neighbourhood(neighbourhood(plane, np.add), np.add)


def key(frame, matte):
    rgb = frame.astype(np.int16)
    difference = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    alpha = np.clip((matte["high"] - difference) / (matte["high"] - matte["low"]), 0, 1).astype(np.float32)
    alpha[alpha < 0.04] = 0
    for x, y, w, h in matte["masks"]:
        alpha[y:y + h, x:x + w] = 0
    # Compression smears screen colour 1-2px into the subject, so choke the matte past it, then soften
    solid = alpha
    for _ in range(2):
        solid = neighbourhood(solid, np.minimum)
    alpha = np.minimum(alpha, neighbourhood(solid, np.add) / 9)
    # Edge pixels are part screen; give them the subject's own colour from the solid core next to them,
    # which also keeps 4:2:0 chroma from averaging screen green into the edge
    core = (solid >= 0.999).astype(np.float32)
    weight = box5(core)
    edge = (alpha < 1) & (weight > 0)
    for channel in range(3):
        extended = box5(rgb[..., channel] * core)
        rgb[..., channel][edge] = (extended[edge] / weight[edge]).astype(np.int16)
    # Green light bounced onto skin reads as a cast once the screen is gone
    rgb[..., 1] = np.minimum(rgb[..., 1], np.maximum(rgb[..., 0], rgb[..., 2]) + 4)
    out = np.empty(frame.shape[:2] + (4,), np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255)
    out[..., 3] = (alpha * 255).astype(np.uint8)
    return out


def complete(path):
    """A WebP is whole when its RIFF header's size matches the file; a killed writer leaves it short."""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return False
    return len(header) == 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP" and \
        int.from_bytes(header[4:8], "little") + 8 == size


def encoder_args(quality):
    if quality == "master":
        return ["-c:v", "libwebp", "-lossless", "1", "-compression_level", "4", "-pix_fmt", "bgra"]
    return ["-c:v", "libwebp", "-quality", "94", "-compression_level", "4", "-pix_fmt", "yuva420p"]


def key_run(video, out_dir, first_edit, count, take, matte, width, height, quality, parent):
    """Key `count` edit frames starting at `first_edit`; returns how many were written."""
    start = (take["firstFrame"] + first_edit) / FPS
    reader = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{start:.6f}", "-i", str(video), "-an",
                               "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                              stdout=subprocess.PIPE)
    writer = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                               "-s", f"{width}x{height}", "-r", str(FPS), "-i", "-", *encoder_args(quality),
                               "-start_number", str(first_edit), str(out_dir / "f%05d.webp")], stdin=subprocess.PIPE)
    size, written = width * height * 3, 0
    while written < count:
        # A killed run must not leave workers writing frames a resumed run is also writing
        if os.getppid() != parent:
            reader.terminate()
            break
        raw = reader.stdout.read(size)
        if len(raw) < size:
            break
        writer.stdin.write(key(np.frombuffer(raw, np.uint8).reshape(height, width, 3), matte).tobytes())
        written += 1
    writer.stdin.close()
    writer.wait()
    reader.wait()
    return written


def runs(missing, workers):
    """Contiguous runs of missing frames, split so every worker gets a share of a short take too."""
    size = max(30, min(CHUNK, math.ceil(len(missing) / workers)))
    jobs, start, previous = [], None, None
    for frame in missing:
        if start is None or frame != previous + 1 or frame - start >= size:
            if start is not None:
                jobs.append((start, previous - start + 1))
            start = frame
        previous = frame
    if start is not None:
        jobs.append((start, previous - start + 1))
    return jobs


def parse_mask(text):
    try:
        x, y, w, h = (int(v) for v in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"--mask takes x,y,w,h in source pixels, got {text!r}")
    return x, y, w, h


def main() -> int:
    parser = argparse.ArgumentParser(description="Key a green-screen take into transparent presenter frames.")
    parser.add_argument("work", type=Path)
    parser.add_argument("--video", type=Path, help="the take (default: the source recorded in take.json)")
    parser.add_argument("--mask", type=parse_mask, action="append", default=[],
                        help="x,y,w,h in source pixels to make transparent, e.g. a burned-in name banner (repeatable)")
    parser.add_argument("--quality", choices=["web", "master"], default="web",
                        help="web: 4:2:0 lossy WebP (~70 KB/frame) · master: lossless full colour (~10x larger)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--preview", type=float, help="key only the frame at this edit time and write presenter-preview.png")
    parser.add_argument("--over", default="#0b1410", help="background colour for --preview")
    args = parser.parse_args()

    take_path = args.work / "take.json"
    take = json.loads(take_path.read_text(encoding="utf-8")) if take_path.exists() else None
    video = args.video or (Path(take["source"]) if take else None)
    if video is None or not video.is_file():
        print(f"No take to key: {video or 'pass --video, or run trim_take.py first'}", file=sys.stderr)
        print("Next: pass --video <the to-camera recording>", file=sys.stderr)
        return 1
    width, height, length = probe(video)
    if take is None:
        take = {"in": 0.0, "duration": length, "firstFrame": 0}
    frames = math.ceil(take["duration"] * FPS)

    try:
        matte = measure(video, take, width, height)
    except TakeError as error:
        print(error.problem, file=sys.stderr)
        print(f"Next: {error.fix}", file=sys.stderr)
        return 1
    matte["masks"] = args.mask
    print(f"screen rgb{tuple(matte['screen'])} · margin {matte['margin']} · matte {matte['low']}–{matte['high']} · "
          f"{len(args.mask)} mask(s)", flush=True)

    if args.preview is not None:
        frame = read_frame(video, take["in"] + args.preview, width, height)
        keyed = key(frame, matte).astype(np.float32)
        over = np.array([int(args.over[i:i + 2], 16) for i in (1, 3, 5)], np.float32)
        a = keyed[..., 3:4] / 255
        composite = (keyed[..., :3] * a + over * (1 - a)).round().astype(np.uint8)
        target = args.work / "presenter-preview.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}",
                        "-i", "-", "-frames:v", "1", "-update", "1", str(target)], input=composite.tobytes(), check=True)
        print(f"preview → {target}")
        print("Next: look at it (hair, glasses, shoulders, any banner); fix with --mask, then run without --preview")
        return 0

    out_dir = args.work / "presenter"
    out_dir.mkdir(exist_ok=True)
    missing = [n for n in range(frames) if not complete(out_dir / f"f{n:05d}.webp")]
    if not missing:
        print(f"{frames}/{frames} presenter frames already keyed → {out_dir}")
        print("Next: author the composition with presenter(); see the Presenter blocks in scene-blocks.md")
        return 0
    jobs = runs(missing, args.workers)
    print(f"keying {len(missing)} of {frames} frames ({frames - len(missing)} already done) · {len(jobs)} jobs · "
          f"{args.workers} workers", flush=True)
    started, done = time.time(), 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(key_run, video, out_dir, first, count, take, matte, width, height, args.quality, os.getpid())
                   for first, count in jobs]
        for future in concurrent.futures.as_completed(futures):
            done += future.result()
            rate = done / max(1e-6, time.time() - started)
            print(f"  {done}/{len(missing)} keyed · {rate:.1f} fps · ~{(len(missing) - done) / max(rate, 1e-6) / 60:.0f} min left",
                  flush=True)
    left = [n for n in range(frames) if not complete(out_dir / f"f{n:05d}.webp")]
    if left:
        print(f"{len(left)} frames still missing (first: {left[0]})", file=sys.stderr)
        print("Next: re-run the same command; it keys only what is missing", file=sys.stderr)
        return 1
    print(f"{frames}/{frames} presenter frames → {out_dir} · {(time.time() - started) / 60:.1f} min")
    print("Next: author the composition with presenter(); see the Presenter blocks in scene-blocks.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
