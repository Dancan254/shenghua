"""Unit tests for scripts/episodes.py: boundary-safe splitting and series status."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import episodes


SCRIPT = "Threads need CPU cores. Cores run threads. Scheduling switches between them! Want more throughput?"


class EpisodeCommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, *args):
        with mock.patch.object(sys, "argv", ["episodes.py", *map(str, args)]), \
             contextlib.redirect_stdout(self.stdout), \
             contextlib.redirect_stderr(self.stderr):
            return episodes.main()

    def write_source(self, text, name="script.txt"):
        source = self.root / name
        source.write_text(text, encoding="utf-8")
        return source

    def test_plain_script_splits_at_sentences_with_near_equal_word_counts(self):
        source = self.write_source(SCRIPT)
        code = self.run_main("split", source, "--episodes", "2", "--outdir", self.root / "series")
        self.assertEqual(code, 0, self.stderr.getvalue())
        first = (self.root / "series/ep1-threads-need-cpu-cores/script.txt").read_text()
        second = (self.root / "series/ep2-scheduling-switches-between-them/script.txt").read_text()
        self.assertEqual(first, "Threads need CPU cores.\nCores run threads.\n")
        self.assertEqual(second, "Scheduling switches between them!\nWant more throughput?\n")
        self.assertEqual(len(first.split()), len(second.split()))

    def test_never_splits_mid_sentence_even_when_lengths_differ(self):
        text = "One short sentence. This is a considerably longer sentence with many more words in it. Last one!"
        groups = episodes.partition(episodes.plain_segments(text), 2)
        self.assertEqual([len(group) for group in groups], [1, 2])
        for group in groups:
            for segment in group:
                self.assertIn(segment.text[-1], ".!?")
        self.assertEqual(" ".join(segment.text for group in groups for segment in group), text)

    def test_transcript_partitions_have_near_equal_durations(self):
        names = ["First phrase", "Second phrase", "Third phrase", "Fourth phrase", "Fifth phrase", "Sixth phrase"]
        lines = []
        for index, name in enumerate(names):
            first, second = name.split()
            start = index * 10
            lines.append(f"[{start:.2f}] {first}@{start:.2f} {second}@{start + 4:.2f}")
        source = self.write_source("\n".join(lines) + "\n", "transcript.txt")
        code = self.run_main("split", source, "--episodes", "3", "--outdir", self.root / "series")
        self.assertEqual(code, 0, self.stderr.getvalue())
        episode_lines = [line for line in self.stdout.getvalue().splitlines() if line.startswith("ep")]
        self.assertEqual(len(episode_lines), 3)
        durations = [float(line.split(" · ")[1].removesuffix("s")) for line in episode_lines]
        self.assertEqual(durations, [20.0, 20.0, 20.0])
        self.assertTrue(all("4 words" in line for line in episode_lines))

    def test_transcript_uses_only_phrase_boundaries(self):
        text = "[0.00] A@0.00 phrase@1.00 without@2.00 punctuation@3.00\n[5.00] Another@5.00 phrase@6.00 here@7.00\n"
        groups = episodes.partition(episodes.transcript_segments(text), 2)
        self.assertEqual(groups[0][0].text, "A phrase without punctuation")
        self.assertEqual(groups[1][0].text, "Another phrase here")

    def test_too_many_episodes_fails_loud_and_writes_nothing(self):
        source = self.write_source("Only one sentence.")
        outdir = self.root / "series"
        code = self.run_main("split", source, "--episodes", "2", "--outdir", outdir)
        self.assertEqual(code, 1)
        self.assertIn("Not enough material", self.stderr.getvalue())
        self.assertIn("Next: ask for fewer episodes or a longer script", self.stderr.getvalue())
        self.assertFalse(outdir.exists())

    def test_slug_prefix_adds_the_episode_number(self):
        source = self.write_source(SCRIPT)
        code = self.run_main("split", source, "--episodes", "2", "--outdir", self.root / "series",
                             "--slug", "Concurrency Basics")
        self.assertEqual(code, 0, self.stderr.getvalue())
        self.assertTrue((self.root / "series/ep1-concurrency-basics-1/script.txt").is_file())
        self.assertTrue((self.root / "series/ep2-concurrency-basics-2/script.txt").is_file())

    def test_status_lists_artefacts_and_names_undelivered_episodes(self):
        series = self.root / "series"
        first, second = series / "ep1-intro", series / "ep2-cores"
        (first / "delivery").mkdir(parents=True)
        second.mkdir(parents=True)
        (first / "script.txt").write_text("intro\n")
        (first / "words.json").write_text("[]\n")
        (first / "index.html").write_text("html\n")
        (first / "delivery/intro.mp4").write_bytes(b"video")
        (second / "script.txt").write_text("cores\n")
        (second / "index.html").write_text("html\n")
        code = self.run_main("status", series)
        self.assertEqual(code, 0, self.stderr.getvalue())
        lines = self.stdout.getvalue().splitlines()
        self.assertEqual(lines[0], "ep1-intro · script.txt=yes · words.json=yes · index.html=yes · delivery=intro.mp4")
        self.assertEqual(lines[1], "ep2-cores · script.txt=yes · words.json=no · index.html=yes · delivery=none")
        self.assertIn("Next: no delivery mp4 yet: ep2-cores", lines[2])


if __name__ == "__main__":
    unittest.main()
