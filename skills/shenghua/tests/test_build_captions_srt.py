"""Unit tests for build_captions.py --from-srt parsing, matching and word alignment."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_captions as bc


def word(t, s, e):
    return {"t": t, "s": s, "e": e}


class ParseSrtTest(unittest.TestCase):
    def test_multiline_cues_and_comma_decimals(self):
        cues = bc.parse_srt(
            "1\n00:00:01,250 --> 00:00:02,500\nHello\nbrave world,\n\n"
            "2\n01:02:03,004 --> 01:02:04,005\nNext phrase\n")
        self.assertEqual(cues, [
            {"sequence": 1, "s": 1.25, "e": 2.5, "text": "Hello\nbrave world,"},
            {"sequence": 2, "s": 3723.004, "e": 3724.005, "text": "Next phrase"},
        ])

    def test_crlf_and_trailing_timing_settings(self):
        cues = bc.parse_srt("7\r\n00:00:00,000 --> 00:00:01,000 align:start\r\nHello\r\n")
        self.assertEqual(cues[0]["sequence"], 7)
        self.assertEqual(cues[0]["text"], "Hello")

    def test_dot_decimals_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid timing line"):
            bc.parse_srt("1\n00:00:00.000 --> 00:00:01.000\nHello\n")


class MatchSrtCuesTest(unittest.TestCase):
    def test_greatest_overlap_wins_and_pairs_stay_one_to_one(self):
        phrases = [[word("first", 0.0, 1.0)], [word("second", 1.0, 2.0)]]
        cues = [
            {"sequence": 1, "s": 0.8, "e": 1.2, "text": "first"},
            {"sequence": 2, "s": 0.8, "e": 1.8, "text": "second"},
        ]
        matches, unmatched = bc.match_srt_cues(cues, phrases)
        self.assertEqual(matches, {1: 1, 0: 0})
        self.assertEqual(unmatched, [])

    def test_zero_overlap_does_not_match(self):
        cues = [{"sequence": 4, "s": 2.0, "e": 3.0, "text": "elsewhere"}]
        matches, unmatched = bc.match_srt_cues(cues, [[word("only", 0.0, 1.0)]])
        self.assertEqual(matches, {})
        self.assertEqual(unmatched, [0])


class AlignPhraseTest(unittest.TestCase):
    def test_unchanged_words_keep_exact_original_times(self):
        original = [word("Hello", 0.0, 0.3), word("world,", 0.4, 0.7)]
        aligned = bc.align_phrase(original, "Hello world,")
        self.assertEqual(aligned, original)
        self.assertIsNot(aligned[0], original[0])

    def test_replacements_interpolate_across_the_replaced_span(self):
        original = [word("old", 0.0, 0.4), word("tokens", 0.5, 1.0)]
        aligned = bc.align_phrase(original, "new words")
        self.assertEqual(aligned, [word("new", 0.0, 0.5), word("words", 0.5, 1.0)])

    def test_insertion_uses_the_neighbouring_gap(self):
        original = [word("Hello", 0.0, 0.2), word("world", 0.5, 0.8)]
        aligned = bc.align_phrase(original, "Hello brave world")
        self.assertEqual(aligned[1], word("brave", 0.2, 0.5))
        self.assertEqual((aligned[0]["s"], aligned[0]["e"]), (0.0, 0.2))
        self.assertEqual((aligned[2]["s"], aligned[2]["e"]), (0.5, 0.8))

    def test_deleted_words_vanish_without_retiming_the_rest(self):
        original = [word("one", 0.0, 0.2), word("two", 0.3, 0.5), word("three", 0.6, 0.9)]
        aligned = bc.align_phrase(original, "one three")
        self.assertEqual(aligned, [original[0], original[2]])


class FromSrtMainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, srt, words=None, fixes=None, keywords=None):
        if words is None:
            words = [
                word("Hello", 0.0, 0.3),
                word("world,", 0.4, 0.7),
                word("San", 1.0, 1.3),
                word("that", 2.0, 2.2),
            ]
        (self.work / "words.json").write_text(json.dumps(words), encoding="utf-8")
        if fixes is not None:
            (self.work / "fixes.json").write_text(json.dumps(fixes), encoding="utf-8")
        if keywords is not None:
            (self.work / "keywords.json").write_text(json.dumps(keywords), encoding="utf-8")
        edited = self.work / "edited.srt"
        edited.write_text(srt, encoding="utf-8")
        argv = ["build_captions.py", str(self.work), "--from-srt", str(edited)]
        with mock.patch.object(sys, "argv", argv), \
             contextlib.redirect_stdout(self.stdout), \
             contextlib.redirect_stderr(self.stderr):
            return bc.main()

    def phrases(self):
        text = (self.work / "words.js").read_text(encoding="utf-8")
        return json.loads(text[len("window.PHRASES="):-1])

    def test_reimport_uses_writers_and_srt_wins_over_fixes(self):
        code = self.run_main(
            "1\n00:00:00,000 --> 00:00:01,000\nHello brave\nworld,\n",
            fixes={"Hello": "Howdy", "San": "Sun"},
            keywords=["brave"])
        self.assertEqual(code, 0, self.stderr.getvalue())
        flat = [word for phrase in self.phrases() for word in phrase]
        self.assertEqual([word["t"] for word in flat], ["Hello", "brave", "world,", "Sun", "that"])
        self.assertEqual((flat[1]["s"], flat[1]["e"]), (0.3, 0.4))
        self.assertEqual(flat[1]["k"], 1)
        self.assertIn("Hello brave world,", (self.work / "captions.srt").read_text(encoding="utf-8"))
        self.assertIn("Hello brave world,", (self.work / "captions.vtt").read_text(encoding="utf-8"))
        self.assertIn("captions re-imported · 1 phrases updated from edited.srt", self.stdout.getvalue())
        self.assertIn("Next: re-render the affected ranges", self.stdout.getvalue())

    def test_no_matching_phrase_fails_loud_without_writing(self):
        code = self.run_main("9\n00:00:10,000 --> 00:00:11,000\nElsewhere\n")
        self.assertEqual(code, 1)
        self.assertIn("1 of 1 cues match no phrase", self.stderr.getvalue())
        self.assertIn("SRT sequences: 9", self.stderr.getvalue())
        self.assertIn("Next: use fixes.json for wholesale rewrites", self.stderr.getvalue())
        self.assertFalse((self.work / "words.js").exists())


if __name__ == "__main__":
    unittest.main()
