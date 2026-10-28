"""Unit tests for trim_take.py's opt-in filler removal, plus one real ffmpeg cut."""

import contextlib
import io
import json
import math
import shutil
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import trim_take


def word(t, s, e):
    return {"t": t, "s": s, "e": e}


class FillerDetectionTest(unittest.TestCase):
    def test_standalone_fillers_and_you_know_ignore_case_and_punctuation(self):
        words = [
            word("Hello", 0.2, 0.4),
            word("UM!!!", 0.6, 0.8),
            word("you,", 1.0, 1.2),
            word("Know?", 1.2, 1.4),
            word("like", 1.6, 1.8),
            word("so", 2.0, 2.2),
            word("well", 2.4, 2.6),
            word("Er.", 3.0, 3.2),
            word("world", 3.5, 3.8),
        ]
        fillers = trim_take.find_fillers(words, 0.0, 4.0)
        self.assertEqual([f["text"] for f in fillers], ["UM!!!", "you, Know?", "Er."])
        self.assertEqual([(f["start"], f["end"]) for f in fillers],
                         [(0.6, 0.8), (1.0, 1.4), (3.0, 3.2)])

    def test_only_the_documented_fillers_match(self):
        words = [word("hmm", 0.5, 0.7), word("like", 1.0, 1.2), word("so", 1.5, 1.7),
                 word("well", 2.0, 2.2), word("ummer", 2.5, 2.7), word("mmm", 3.0, 3.2)]
        fillers = trim_take.find_fillers(words, 0.0, 4.0)
        self.assertEqual([f["text"] for f in fillers], ["mmm"])

    def test_fillers_near_either_cut_boundary_are_kept(self):
        words = [word("um", 1.05, 1.1), word("hello", 1.5, 1.7), word("uh", 2.9, 2.95)]
        self.assertEqual(trim_take.find_fillers(words, 1.0, 3.0), [])

    def test_cuts_closer_than_fifty_milliseconds_are_merged(self):
        words = [word("um", 1.0, 1.2), word("uh", 1.24, 1.4), word("ah", 1.43, 1.6)]
        fillers = trim_take.find_fillers(words, 0.0, 3.0)
        self.assertEqual(len(fillers), 1)
        self.assertEqual((fillers[0]["start"], fillers[0]["end"]), (1.0, 1.6))
        self.assertEqual(fillers[0]["text"], "um uh ah")


class FillerTimingTest(unittest.TestCase):
    def test_remaining_words_shift_by_all_preceding_cuts(self):
        words = [word("before", 1.2, 1.4), word("um", 2.0, 2.5),
                 word("middle", 2.6, 2.8), word("you", 3.0, 3.1), word("know", 3.1, 3.25),
                 word("after", 3.4, 3.6)]
        fillers = [{"start": 2.0, "end": 2.5}, {"start": 3.0, "end": 3.25}]
        shifted = trim_take.shift_words(words, 1.0, fillers)
        self.assertEqual([w["t"] for w in shifted], ["before", "middle", "after"])
        self.assertEqual([(w["s"], w["e"]) for w in shifted],
                         [(0.2, 0.4), (1.1, 1.3), (1.65, 1.85)])

    def test_edit_time_is_continuous_across_a_cut(self):
        fillers = [{"start": 2.0, "end": 2.5}]
        self.assertEqual(trim_take.edit_time(2.0, 1.0, fillers), 1.0)
        self.assertEqual(trim_take.edit_time(2.5, 1.0, fillers), 1.0)
        self.assertEqual(trim_take.edit_time(3.0, 1.0, fillers), 1.5)


class FillerMainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.source = root / "take.wav"
        self.source.write_bytes(b"not really audio")
        self.work = root / "work"
        self.work.mkdir()
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def tearDown(self):
        self.tmp.cleanup()

    def write_words(self, words):
        (self.work / "words.json").write_text(json.dumps(words), encoding="utf-8")
        (self.work / "transcript.txt").write_text("transcript\n", encoding="utf-8")

    def run_main(self, *extra, words, probe=None):
        self.write_words(words)
        argv = ["trim_take.py", str(self.source), str(self.work), *extra]
        ffmpeg = mock.Mock(return_value=mock.Mock(returncode=0, stderr=""))
        with mock.patch.object(sys, "argv", argv), \
             mock.patch("trim_take.probe_duration", return_value=10.0), \
             mock.patch("trim_take.probe_source", return_value=probe), \
             mock.patch("trim_take.subprocess.run", ffmpeg), \
             contextlib.redirect_stdout(self.stdout), \
             contextlib.redirect_stderr(self.stderr):
            code = trim_take.main()
        return code, ffmpeg

    def test_video_input_is_refused_before_ffmpeg(self):
        probe = {"width": 1080, "height": 1920, "fps": 30.0, "codec": "h264", "hdr": False}
        code, ffmpeg = self.run_main("--remove-fillers", probe=probe,
                                     words=[word("hello", 1.0, 1.4), word("um", 2.0, 2.2)])
        self.assertEqual(code, 1)
        self.assertIn("filler cuts are audio-only for now: mid-take cuts would break the "
                      "face/presenter frame mapping", self.stderr.getvalue())
        self.assertIn("Next: use it on audio-only projects, or cut by hand with --in/--out",
                      self.stderr.getvalue())
        ffmpeg.assert_not_called()
        self.assertFalse((self.work / "take.json").exists())

    def test_no_fillers_keeps_duration_and_words(self):
        words = [word("hello", 1.0, 1.4), word("like", 2.0, 2.2), word("world", 3.0, 3.4)]
        code, ffmpeg = self.run_main("--remove-fillers", "--in", "0.5", "--out", "4", words=words)
        self.assertEqual(code, 0, self.stderr.getvalue())
        take = json.loads((self.work / "take.json").read_text(encoding="utf-8"))
        self.assertEqual(take["fillers"], [])
        self.assertEqual(take["duration"], 3.5)
        self.assertEqual([w["t"] for w in json.loads((self.work / "words.json").read_text())],
                         ["hello", "like", "world"])
        self.assertIn("voice.wav · 0 filler cuts (0.00s removed) · new duration 3.50s",
                      self.stdout.getvalue())
        command = ffmpeg.call_args[0][0]
        self.assertIn("-af", command)
        self.assertNotIn("-filter_complex", command)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg and ffprobe required")
class FillerFfmpegTest(unittest.TestCase):
    def test_real_cut_concatenates_48khz_lossless_wav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "take.wav"
            work = root / "work"
            work.mkdir()
            with wave.open(str(source), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(48000)
                output.writeframes(b"".join(
                    struct.pack("<h", int(4000 * math.sin(2 * math.pi * 440 * i / 48000)))
                    for i in range(96000)))
            words = [word("hello", 0.2, 0.4), word("um", 0.6, 0.8), word("world", 1.0, 1.2)]
            (work / "words.json").write_text(json.dumps(words), encoding="utf-8")
            (work / "transcript.txt").write_text("transcript\n", encoding="utf-8")
            argv = ["trim_take.py", str(source), str(work), "--in", "0", "--out", "2",
                    "--remove-fillers"]
            stdout = io.StringIO()
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                code = trim_take.main()
                self.assertEqual(code, 0)
                code = trim_take.main()
            self.assertEqual(code, 0)
            with wave.open(str(work / "voice.wav"), "rb") as result:
                self.assertEqual(result.getframerate(), 48000)
                self.assertEqual(result.getsampwidth(), 3)
                self.assertAlmostEqual(result.getnframes() / result.getframerate(), 1.8, places=3)
            shifted = json.loads((work / "words.json").read_text(encoding="utf-8"))
            self.assertEqual([(w["t"], w["s"], w["e"]) for w in shifted],
                             [("hello", 0.2, 0.4), ("world", 0.8, 1.0)])
            take = json.loads((work / "take.json").read_text(encoding="utf-8"))
            self.assertEqual(take["fillers"], [{"start": 0.6, "end": 0.8, "text": "um"}])
            self.assertIn("voice.wav · 1 filler cuts (0.20s removed) · new duration 1.80s",
                          stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
