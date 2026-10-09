#!/usr/bin/env python3
"""Synthesize the sound design for a composition.

  synth_audio.py <cues.json> <duration> <work-dir> [--template ID] [--drop T] [--quiet A:B] [--no-music]

Writes sfx.wav (every cue the timeline pushed) and music.wav (the theme's pad, bass, pluck and
pulse layers at its own tempo and key, drums from --drums-from onward). The chord order and pluck
pattern vary per video (the slug folder above work/). Without a kit audio block everything is generated
here, so there is nothing to license.

The kit's audio block (work/kit/kit.json, installed by fill_template.py) can swap any cue for recorded
files, change its gain or mute it, replace the synth music with a track or none, and set the mix
levels. mix.json records those levels and the music file for mix-encode.sh and render-chunks.sh.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SR = 48000
TEMPLATES_JSON = Path(__file__).resolve().parent.parent / "templates" / "templates.json"
rng = np.random.default_rng(7)


def t_axis(seconds):
    return np.arange(int(SR * seconds)) / SR


def smooth(x, width):
    return np.convolve(x, np.ones(width) / width, mode="same")


def envelope(n, attack, release):
    env = np.ones(n)
    a, r = max(1, int(SR * attack)), max(1, int(SR * release))
    env[:a] = np.linspace(0, 1, a)
    env[-r:] *= np.exp(-np.linspace(0, 6, r))
    return env


def note(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def place(buffer, sound, at):
    start = int(at * SR)
    if start < 0:
        sound, start = sound[-start:], 0
    if start >= len(buffer):
        return
    end = min(len(buffer), start + len(sound))
    buffer[start:end] += sound[: end - start]


def hit(power):
    t = t_axis(0.9)
    body = np.sin(2 * np.pi * np.cumsum(38 + 90 * np.exp(-t * 28)) / SR) * np.exp(-t * 5.5)
    click = rng.standard_normal(len(t)) * np.exp(-t * 60) * 0.5
    boom = smooth(rng.standard_normal(len(t)), 40) * np.exp(-t * 3) * 0.6
    return (body * 0.9 + click + boom) * 0.55 * power


def whoosh():
    t = t_axis(0.45)
    noise = rng.standard_normal(len(t))
    return (smooth(noise, 6) - smooth(noise, 60)) * np.sin(np.pi * t / t[-1]) ** 2 * 0.35


def riser(duration):
    t = t_axis(duration)
    k = t / duration
    noise = rng.standard_normal(len(t))
    tone = np.sin(2 * np.pi * np.cumsum(180 + 900 * k ** 2) / SR)
    return ((noise - smooth(noise, 45)) * 0.12 + tone * 0.08) * k ** 2


def down(duration):
    t = t_axis(duration)
    k = t / duration
    tone = np.sin(2 * np.pi * np.cumsum(700 * (1 - k) + 60) / SR)
    return tone * 0.12 * (1 - k) * np.sin(np.pi * np.minimum(k * 8, 1) / 2)


def repeated(sound, duration, interval, jitter):
    out = np.zeros(int(SR * duration) + SR // 10)
    position = 0.0
    while position < duration:
        place(out, sound() * (0.6 + 0.4 * rng.random()), position)
        position += interval + jitter * rng.random()
    return out


def key_click():
    t = t_axis(0.03)
    return rng.standard_normal(len(t)) * np.exp(-t * 250) * 0.12


def tick():
    t = t_axis(0.04)
    return np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 120) * 0.08


def pop():
    t = t_axis(0.12)
    return np.sin(2 * np.pi * np.cumsum(500 + 900 * np.exp(-t * 40)) / SR) * np.exp(-t * 35) * 0.12


def ding():
    t = t_axis(0.6)
    return (np.sin(2 * np.pi * 1318 * t) + 0.5 * np.sin(2 * np.pi * 1975 * t)) * np.exp(-t * 8) * 0.07


def stamp():
    t = t_axis(0.35)
    return smooth(rng.standard_normal(len(t)), 25) * np.exp(-t * 18) * 0.9


def error():
    t = t_axis(0.22)
    return np.sign(np.sin(2 * np.pi * 180 * t)) * np.exp(-t * 14) * 0.05


# The synth sound a recorded file stands in for; its peak is the level the file is matched to
REFERENCE = {
    "hit": lambda: hit(1), "whoosh": whoosh, "riser": lambda: riser(1.0), "down": lambda: down(0.6),
    "type": key_click, "tick": tick, "pop": pop, "ding": ding, "stamp": stamp, "error": error,
}


def decode(path):
    """Any audio file → mono float at SR. Plain WAV needs only the standard library."""
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as handle:
                if handle.getsampwidth() == 2 and handle.getframerate() == SR:
                    data = np.frombuffer(handle.readframes(handle.getnframes()), np.int16).astype(float) / 32768
                    return data.reshape(-1, handle.getnchannels()).mean(axis=1)
        except wave.Error:
            pass
    if not shutil.which("ffmpeg"):
        raise SystemExit(f"decoding {path} needs ffmpeg\nNext: install ffmpeg, or give the kit 16-bit {SR} Hz WAV files")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


class Sounds:
    """Each cue's sound: the synth by default, or the kit's files in rotation, at the kit's gain."""

    def __init__(self, sfx_settings, work):
        self.settings = sfx_settings
        self.files = {}
        self.turn = {}
        for cue, setting in sfx_settings.items():
            if setting.get("files") and not setting.get("mute"):
                # Restoring rng's state keeps measuring the reference from shifting every synth cue's noise
                state = rng.bit_generator.state
                reference = float(np.max(np.abs(REFERENCE[cue]()))) or 1.0
                rng.bit_generator.state = state
                decoded = [decode(work / name) for name in setting["files"]]
                self.files[cue] = [clip / (np.max(np.abs(clip)) or 1.0) * reference for clip in decoded]

    def muted(self, cue):
        return self.settings.get(cue, {}).get("mute", False)

    def gain(self, cue):
        return self.settings.get(cue, {}).get("gain", 1)

    def recorded(self, cue):
        """The next file for this cue, or None when the cue stays synthesized."""
        if cue not in self.files:
            return None
        index = self.turn.get(cue, 0)
        self.turn[cue] = index + 1
        return self.files[cue][index % len(self.files[cue])]


def fit(sound, duration, end_aligned):
    """Crop a recorded riser to end on its cue, or a recorded down-sweep to stop with it."""
    length = int(SR * duration)
    if duration <= 0 or len(sound) <= length:
        return sound
    if end_aligned:
        return sound[-length:]
    fade = min(length, SR // 20)
    out = sound[:length].copy()
    out[length - fade:] *= np.linspace(1, 0, fade)
    return out


def build_sfx(cues, samples, sounds):
    sfx = np.zeros(samples)
    unknown = set()
    for cue in cues:
        kind, at, duration = cue["type"], cue["t"], cue.get("dur", 0)
        if kind not in REFERENCE:
            unknown.add(kind)
            continue
        if sounds.muted(kind):
            continue
        gain = sounds.gain(kind)
        if kind in ("type", "tick"):
            if kind == "type" and duration <= 0.05:
                continue
            unit = (lambda: sounds.recorded(kind)) if kind in sounds.files else (key_click if kind == "type" else tick)
            interval, jitter = (0.055, 0.04) if kind == "type" else (0.07, 0)
            place(sfx, repeated(unit, duration, interval, jitter) * gain, at)
            continue
        recorded = sounds.recorded(kind)
        if recorded is not None:
            if kind == "riser":
                recorded = fit(recorded, duration, end_aligned=True)
                at += max(0.0, duration - len(recorded) / SR)
            elif kind == "down":
                recorded = fit(recorded, duration, end_aligned=False)
            sound = recorded * (cue.get("power", 1) if kind == "hit" else 1)
        elif kind == "hit":
            sound = hit(cue.get("power", 1))
        elif kind in ("riser", "down"):
            sound = riser(duration) if kind == "riser" else down(duration)
        else:
            sound = REFERENCE[kind]()
        place(sfx, sound * gain, at)
    return sfx, unknown



def pulse_note(midi, seconds):
    t = t_axis(seconds)
    saw = sum(np.sin(2 * np.pi * note(midi) * k * t) / k for k in range(1, 7))
    return saw * np.exp(-t * 18) * 0.05


def build_music(duration, samples, drums_from, drop, quiet, profile, music_rng):
    beat = 60 / profile["bpm"]
    bar = beat * 4
    root, layers = profile["root"], profile["layers"]
    rotation = int(music_rng.integers(0, 4))
    progression = profile["progression"][rotation:] + profile["progression"][:rotation]
    pluck_order = [int(i) for i in music_rng.permutation(3)]
    music = np.zeros(samples)
    for b in range(int(duration / bar) + 2):
        start = b * bar
        offsets = progression[b % 4]
        chord = [root + o for o in offsets]
        if "pad" in layers:
            pad_t = t_axis(bar + 0.5)
            pad = sum(
                np.sin(2 * np.pi * note(m) * 2 ** (d / 12) * pad_t) + 0.3 * np.sin(4 * np.pi * note(m) * 2 ** (d / 12) * pad_t)
                for m in chord for d in (-0.12, 0.0, 0.12)
            ) / 9
            place(music, pad * envelope(len(pad_t), 0.6, 0.8) * 0.16, start)
        if "bass" in layers:
            bass_t = t_axis(bar)
            place(music, np.sin(2 * np.pi * note(root + offsets[0] - 12) * bass_t) * envelope(len(bass_t), 0.05, 0.4) * 0.14, start)
        if "pluck" in layers:
            for i in range(8):
                pluck_t = t_axis(0.25)
                place(music, np.sin(2 * np.pi * note(chord[pluck_order[i % 3]] + 12) * pluck_t) * np.exp(-pluck_t * 14) * 0.05, start + i * beat / 2)
        if "pulse" in layers:
            for i in range(8):
                place(music, pulse_note(root + offsets[0], beat / 2), start + i * beat / 2)
        if drums_from is not None and start >= drums_from:
            for i in range(4):
                kick_t = t_axis(0.3)
                place(music, np.sin(2 * np.pi * np.cumsum(50 + 120 * np.exp(-kick_t * 30)) / SR) * np.exp(-kick_t * 9) * 0.2, start + i * beat)
                hat_t = t_axis(0.05)
                hat = rng.standard_normal(len(hat_t))
                place(music, (hat - smooth(hat, 4)) * np.exp(-hat_t * 90) * 0.03, start + i * beat + beat / 2)

    return music * music_gain(duration, samples, quiet, drop)


def music_gain(duration, samples, quiet, drop):
    t = np.arange(samples) / SR
    gain = np.clip(t / 1.5, 0, 1) * np.clip((duration - t) / 1.2, 0, 1)
    for a, b in quiet:
        gain[(t > a) & (t < b)] *= 0.55
    if drop is not None:
        # Silence right before the final slam makes the punchline land harder
        gain[(t > drop - 0.3) & (t < drop)] = 0.0
        gain[t >= drop] *= 1.25
    return gain


def track_music(path, duration, samples, quiet, drop):
    """The kit's own music track, looped to the video's length, under the same fades and drop."""
    track = decode(path)
    if not len(track):
        raise SystemExit(f"{path} decoded to no audio\nNext: check the file plays, or set audio.music to synth")
    music = np.tile(track, samples // len(track) + 1)[:samples]
    return music * music_gain(duration, samples, quiet, drop)


def kit_audio(work):
    """The audio block fill_template.py installed with the kit, or the defaults for a work dir without one."""
    try:
        audio = json.loads((work / "kit" / "kit.json").read_text(encoding="utf-8")).get("audio")
    except (OSError, json.JSONDecodeError):
        audio = None
    return audio or {"music": "synth", "levels": {"music": 0.22, "sfx": 0.5}, "sfx": {}}


def write_wav(path, data):
    peak = np.max(np.abs(data)) or 1.0
    pcm = (data / peak * 0.9 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(pcm.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cues", type=Path)
    parser.add_argument("duration", type=float)
    parser.add_argument("work", type=Path)
    parser.add_argument("--template", default="kinetic", help="theme id whose music profile to use")
    parser.add_argument("--drop", type=float, default=None, help="time of the final slam")
    parser.add_argument("--drums-from", type=float, default=None, help="bring drums in at this time")
    parser.add_argument("--quiet", action="append", default=[], help="A:B range where music sits lower")
    parser.add_argument("--no-music", action="store_true")
    args = parser.parse_args()

    if not args.cues.is_file():
        print(f"No such cues file: {args.cues}", file=sys.stderr)
        print("Next: run render.js cues first", file=sys.stderr)
        return 1

    templates = json.loads(TEMPLATES_JSON.read_text())["templates"]
    profiles = {entry["id"]: entry["music"] for entry in templates}
    if args.template not in profiles:
        print(f"Unknown template: {args.template} (valid: {', '.join(profiles)})", file=sys.stderr)
        print("Next: pass the same --template id you gave fill_template.py", file=sys.stderr)
        return 1
    profile = profiles[args.template]

    samples = int(SR * args.duration)
    cues = json.loads(args.cues.read_text())
    audio = kit_audio(args.work)
    sfx, unknown = build_sfx(cues, samples, Sounds(audio["sfx"], args.work))
    write_wav(args.work / "sfx.wav", sfx)
    written = ["sfx.wav"]
    music_source = "none" if args.no_music else audio["music"]

    if music_source != "none":
        quiet = []
        for q in args.quiet:
            parts = q.split(":")
            if len(parts) != 2:
                print(f"--quiet must be A:B, got: {q}", file=sys.stderr)
                print("Next: pass a numeric range like --quiet 2.5:4.0", file=sys.stderr)
                return 1
            try:
                a, b = float(parts[0]), float(parts[1])
            except ValueError:
                print(f"--quiet times must be numbers, got: {q}", file=sys.stderr)
                print("Next: pass a numeric range like --quiet 2.5:4.0", file=sys.stderr)
                return 1
            quiet.append((a, b))
        if music_source == "synth":
            resolved_work = args.work.resolve()
            seed_key = f"{resolved_work.parent.name}/{resolved_work.name}"
            seed = int.from_bytes(hashlib.sha256(seed_key.encode()).digest()[:8], "big")
            music = build_music(args.duration, samples, args.drums_from, args.drop, quiet, profile, np.random.default_rng(seed))
        else:
            music = track_music(args.work / music_source, args.duration, samples, quiet, args.drop)
        write_wav(args.work / "music.wav", music)
        written.append("music.wav")

    # The mix scripts read this, so a stale music.wav from an earlier run never sneaks into a --no-music mix
    mix = {**audio["levels"], "music_file": "music.wav" if music_source != "none" else None}
    (args.work / "mix.json").write_text(json.dumps(mix, indent=2) + "\n", encoding="utf-8")

    tempo = {"none": "", "synth": f" · {args.template} {profile['bpm']} bpm"}.get(music_source, f" · kit track {Path(music_source).name}")
    tuned = sorted(cue for cue, setting in audio["sfx"].items() if setting.get("files") or setting.get("mute") or setting.get("gain", 1) != 1)
    if tuned:
        tempo += f" · kit sounds: {', '.join(tuned)}"
    print(f"{len(cues)} cues · {args.duration:.1f}s{tempo} → {' + '.join(written)}")
    if unknown:
        print(f"  ignored unknown cue types: {', '.join(sorted(unknown))}")
    print("Next: run render-frames.sh, then mix-encode.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
