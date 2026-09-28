#!/usr/bin/env python3
"""Voice a script with one synthetic voice per character, entirely offline.

  speak.py <script.txt> <work-dir> [--cast cast.json] [--narrator NAME] [--gap S] [--scene-gap S]

Script format, one spoken line per line:

  Keeper: Meet Pip. Pip carries messages between five services.
  Pip: Which wire goes where?!
  ---                      scene break: a longer pause
  (pause 1.2)              explicit silence in seconds
  A line with no name belongs to the narrator (--narrator, else the first speaker).
  # comments are skipped

A cast file picks each speaker's voice. Kokoro (offline, built in) is the default; a speaker can use
your own cloned voice from a running VoiceStudio app instead:

  {"teacher": {"engine": "voicestudio", "voice": "<profile id>", "url": "http://localhost:3900"},
   "pip": {"voice": "am_puck", "pitch": 1.32, "speed": 1.05}}

Writes <work>/voice.wav (the recording the rest of the workflow uses), <work>/speech.json and
<work>/speech.js (who speaks when, read by the template's hosts), <work>/words.json and
transcript.txt (estimated word times in transcribe.py's format), and <work>/script.txt.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np

MODEL_DIR = Path(os.environ.get("VV_KOKORO_DIR", Path.home() / ".cache" / "voiceover-video" / "kokoro"))
MODEL, VOICES = "kokoro-v1.0.onnx", "voices-v1.0.bin"
SR_OUT = 48000
# First speaker gets the first voice, and so on; a pitch above 1 makes a small, squeaky character
DEFAULT_VOICES = [
    {"voice": "af_heart"},
    {"voice": "am_puck", "pitch": 1.32, "speed": 1.05},
    {"voice": "am_michael"},
    {"voice": "bf_emma"},
    {"voice": "am_fenrir"},
    {"voice": "af_nova"},
]
SPEAKER = re.compile(r"^([A-Za-z][\w'-]*(?: [A-Za-z][\w'-]*)?)\s*:\s*(.+)$")
PAUSE = re.compile(r"^\(pause\s+([0-9.]+)\)$", re.I)


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse(text, cast, narrator):
    items, speakers = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "---":
            items.append(("scene", None, None))
            continue
        pause = PAUSE.match(line)
        if pause:
            items.append(("pause", float(pause.group(1)), None))
            continue
        match = SPEAKER.match(line)
        # Only a known cast name, or a short name when there is no cast file, counts as a speaker
        if match and (slug(match.group(1)) in cast or not cast):
            who, words = slug(match.group(1)), match.group(2).strip()
        else:
            who, words = narrator, line
        if who is None:
            print(f"Line has no speaker and no narrator is set: {line[:60]}", file=sys.stderr)
            return None, None
        if who not in speakers:
            speakers.append(who)
        items.append(("line", who, words))
    return items, speakers


def trim(audio, threshold=0.01):
    loud = np.where(np.abs(audio) > threshold)[0]
    if len(loud) == 0:
        return audio
    return audio[max(0, loud[0] - 400): loud[-1] + 800]


def file_to_48k(src, sr, pitch):
    # ffmpeg resamples and pitch-shifts in one pass; pitch keeps the pace close to natural
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "out.wav"
        chain = f"aresample={SR_OUT}"
        if pitch != 1.0:
            chain = f"asetrate={int(sr * pitch)},aresample={SR_OUT},atempo={1 / pitch * 1.08:.4f}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", chain, "-ac", "1",
                        "-c:a", "pcm_s16le", str(dst)], check=True)
        with wave.open(str(dst)) as handle:
            return np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32) / 32767


def to_48k(audio, sr, pitch):
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "in.wav"
        write_wav(src, audio, sr)
        return file_to_48k(src, sr, pitch)


class VoiceStudio:
    """A running VoiceStudio backend: the user's own cloned voice, served locally over its OpenAI-style API."""

    def __init__(self, url):
        self.url = url.rstrip("/")

    def get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=10) as response:
            return response.read()

    def check(self, voice):
        """None when the backend is up and knows the voice, else the reason it can't be used."""
        try:
            self.get("/health")
            voices = self.get("/v1/audio/voices").decode("utf-8", "replace")
        except (urllib.error.URLError, OSError) as e:
            return f"VoiceStudio is not reachable at {self.url} ({e})"
        # The voice list's shape varies by version; the profile id appearing in it is what matters
        if json.dumps(voice) not in voices and voice not in voices:
            return f"VoiceStudio at {self.url} has no voice '{voice}'"
        return None

    def speak(self, text, voice, model):
        body = json.dumps({"model": model, "voice": voice, "input": text, "response_format": "wav"}).encode()
        request = urllib.request.Request(self.url + "/v1/audio/speech", data=body,
                                         headers={"Content-Type": "application/json"})
        # A cloned voice can take a while on CPU; VoiceStudio's own CPU budget is 600 s
        with urllib.request.urlopen(request, timeout=600) as response:
            data = response.read()
        if data[:4] != b"RIFF":
            raise RuntimeError(f"VoiceStudio returned no audio: {data[:200]!r}")
        return data


def word_times(words, s, e):
    """Spread a line's words over its audio by length; punctuation adds the pause a voice leaves there."""
    tokens = words.split()
    weights = [len(w.strip(".,!?;:\"'()")) + 2 for w in tokens]
    pauses = [4 if w[-1] in ".!?" else 2.5 if w[-1] in ",;:" else 0 for w in tokens]
    unit = (e - s) / (sum(weights) + sum(pauses[:-1]) or 1)
    out, t = [], s
    for w, weight, pause in zip(tokens, weights, pauses):
        out.append({"t": w, "s": round(t, 2), "e": round(t + weight * unit, 2)})
        t += (weight + pause) * unit
    return out


def split_phrases(words):
    """Mirrors transcribe.split_phrases, so transcript.txt reads the same either way."""
    phrases, current = [], []
    for word in words:
        current.append(word)
        if len(current) >= 5 or word["t"][-1] in ".,?!":
            phrases.append(current)
            current = []
    if current:
        phrases.append(current)
    return phrases


def write_wav(path, data, sr):
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(pcm.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("script", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--cast", type=Path, default=None, help='{"pip": {"voice": "am_puck", "pitch": 1.32, "speed": 1.05}}')
    parser.add_argument("--narrator", default=None, help="speaker for lines without a name")
    parser.add_argument("--gap", type=float, default=0.25, help="silence between lines")
    parser.add_argument("--scene-gap", type=float, default=0.7, help="silence at a --- scene break")
    parser.add_argument("--lead", type=float, default=0.4, help="silence before the first line")
    args = parser.parse_args()

    if not args.script.is_file():
        print(f"No such script: {args.script}", file=sys.stderr)
        print("Next: write the script as 'Name: line' lines and pass its path", file=sys.stderr)
        return 1
    cast = {}
    if args.cast:
        try:
            cast = {slug(k): v for k, v in json.loads(args.cast.read_text(encoding="utf-8")).items()}
        except (OSError, json.JSONDecodeError) as e:
            print(f"Cannot read cast file {args.cast}: {e}", file=sys.stderr)
            print('Next: fix the JSON, e.g. {"keeper": {"voice": "af_heart"}}', file=sys.stderr)
            return 1

    text = args.script.read_text(encoding="utf-8")
    narrator = slug(args.narrator) if args.narrator else None
    if narrator is None:
        first = next((SPEAKER.match(l.strip()) for l in text.splitlines() if SPEAKER.match(l.strip())), None)
        narrator = slug(first.group(1)) if first else "narrator"
    items, speakers = parse(text, cast, narrator)
    if items is None:
        print("Next: add a 'Name:' to that line or pass --narrator", file=sys.stderr)
        return 1
    if not speakers:
        print(f"No spoken lines in {args.script}", file=sys.stderr)
        print("Next: write lines as 'Name: what they say'", file=sys.stderr)
        return 1

    for i, who in enumerate(speakers):
        cast.setdefault(who, DEFAULT_VOICES[i % len(DEFAULT_VOICES)])

    tts, studios = None, {}
    if any(cast[w].get("engine", "kokoro") == "kokoro" for w in speakers):
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            print("kokoro-onnx is not installed", file=sys.stderr)
            print("Next: run setup.sh --voices", file=sys.stderr)
            return 1
        if not (MODEL_DIR / MODEL).is_file() or not (MODEL_DIR / VOICES).is_file():
            print(f"Voice model missing in {MODEL_DIR}", file=sys.stderr)
            print("Next: run setup.sh --voices (downloads ~350 MB once)", file=sys.stderr)
            return 1
        tts = Kokoro(str(MODEL_DIR / MODEL), str(MODEL_DIR / VOICES))
    available = set(tts.get_voices()) if tts else set()
    for who in speakers:
        spec = cast[who]
        engine = spec.get("engine", "kokoro")
        if engine == "voicestudio":
            url = spec.get("url", "http://localhost:3900")
            studios.setdefault(url, VoiceStudio(url))
            problem = studios[url].check(spec.get("voice", ""))
            if problem:
                print(f"{problem} (speaker {who})", file=sys.stderr)
                print("Next: open VoiceStudio, create the voice profile, and put its id in the cast file as \"voice\"", file=sys.stderr)
                return 1
        elif engine != "kokoro":
            print(f"Unknown engine '{engine}' for {who}", file=sys.stderr)
            print('Next: use "kokoro" (built in) or "voicestudio" (your cloned voice)', file=sys.stderr)
            return 1
        elif spec.get("voice") not in available:
            print(f"Unknown voice '{spec.get('voice')}' for {who}", file=sys.stderr)
            print(f"Next: pick one of {', '.join(sorted(available))}", file=sys.stderr)
            return 1

    parts, speech, t = [np.zeros(int(SR_OUT * args.lead), dtype=np.float32)], [], args.lead
    for kind, a, b in items:
        if kind in ("scene", "pause"):
            seconds = args.scene_gap if kind == "scene" else a
            parts.append(np.zeros(int(SR_OUT * seconds), dtype=np.float32))
            t += seconds
            continue
        who, words = a, b
        spec = cast[who]
        pitch = float(spec.get("pitch", 1.0))
        if spec.get("engine", "kokoro") == "voicestudio":
            try:
                data = studios[spec.get("url", "http://localhost:3900")].speak(words, spec["voice"], spec.get("model", "tts-1"))
            except (urllib.error.URLError, OSError, RuntimeError) as e:
                print(f"VoiceStudio failed on {who}'s line \"{words[:50]}\": {e}", file=sys.stderr)
                print("Next: check the VoiceStudio app for a missing model or a busy GPU, then re-run", file=sys.stderr)
                return 1
            with tempfile.TemporaryDirectory() as tmp:
                src = Path(tmp) / "vs.wav"
                src.write_bytes(data)
                with wave.open(str(src)) as handle:
                    sr = handle.getframerate()
                audio = trim(file_to_48k(src, sr, pitch))
        else:
            audio, sr = tts.create(words, voice=spec["voice"], speed=float(spec.get("speed", 1.0)), lang=spec.get("lang", "en-us"))
            audio = to_48k(trim(np.asarray(audio, dtype=np.float32)), sr, pitch)
        d = len(audio) / SR_OUT
        speech.append({"i": len(speech), "who": who, "s": round(t, 3), "e": round(t + d, 3), "text": words})
        parts += [audio, np.zeros(int(SR_OUT * args.gap), dtype=np.float32)]
        t += d + args.gap

    voice = np.concatenate(parts)
    voice *= 0.9 / (np.max(np.abs(voice)) or 1.0)
    args.work.mkdir(parents=True, exist_ok=True)
    write_wav(args.work / "voice.wav", voice, SR_OUT)
    (args.work / "speech.json").write_text(json.dumps(speech, indent=1), encoding="utf-8")
    (args.work / "speech.js").write_text("window.SPEECH=" + json.dumps(speech) + ";", encoding="utf-8")
    (args.work / "script.txt").write_text("\n".join(x["text"] for x in speech) + "\n", encoding="utf-8")
    (args.work / "cast.json").write_text(json.dumps(cast, indent=1), encoding="utf-8")
    # Same shape transcribe.py writes, so build_captions.py runs without a transcription pass
    words = [w for x in speech for w in word_times(x["text"], x["s"], x["e"])]
    (args.work / "words.json").write_text(json.dumps(words), encoding="utf-8")
    with (args.work / "transcript.txt").open("w", encoding="utf-8") as handle:
        for phrase in split_phrases(words):
            handle.write(f"[{phrase[0]['s']:.2f}] " + " ".join(f"{w['t']}@{w['s']:.2f}" for w in phrase) + "\n")

    end = speech[-1]["e"]
    voices = " · ".join(f"{w}={cast[w]['voice']}" + (" (VoiceStudio)" if cast[w].get("engine") == "voicestudio" else "")
                        + (f"@{cast[w]['pitch']}" if cast[w].get("pitch") else "") for w in speakers)
    print(f"voice.wav · {len(speech)} lines · {end:.1f}s · {voices}")
    print(f"  words.json has estimated word times; for exact sync run transcribe.py on voice.wav")
    print(f"Next: run build_captions.py {args.work} (composition duration ≈ {end + 2.5:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
