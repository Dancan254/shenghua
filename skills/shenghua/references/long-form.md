# Long form: YouTube explainers in chapters

A Short is one recording, one project, one render. A 10 to 40 minute video is built as **chapters**: each
chapter is its own recording and its own ordinary project, and `assemble.py` joins the finished chapters into
one master. A fluffed line means re-recording one chapter; a fix means re-rendering one chapter; QA stays the
size of a Short.

Use long form when the user asks for a YouTube video, a deep dive, a course lesson or a talk over about
five minutes, or hands you a script split into chapters or scenes. Everything else in `SKILL.md` still
applies inside each chapter; this file covers what changes.

---

## Project layout

```
<output dir>/<slug>/
├── chapters.json                 the order and the YouTube chapter titles
├── 01-the-question/
│   ├── script.txt                what the speaker reads ([FACE] / [VOICE] / [CODE] sections)
│   ├── take.wav                  the recording (take.mp4 for a face chapter)
│   ├── work/                     the chapter's project: words.json, index.html, sfx.wav, captions.srt …
│   └── 01-the-question.mp4       the chapter's render
├── 02-cpu-cores/
│   └── …
└── assembly/                     written by assemble.py
```

```json
{
  "slug": "threads-are-not-cores",
  "chapters": [
    {"dir": "01-the-question", "title": "The question"},
    {"dir": "02-cpu-cores", "title": "What a CPU core is"}
  ]
}
```

A chapter's render defaults to `<dir>/<dir>.mp4` and its work dir to `<dir>/work`; set `"video"` or `"work"`
on an entry to point elsewhere. The titles become the YouTube chapters, so write them as a viewer would scan
them: short, specific, no numbering.

## Per chapter

Run the normal workflow on each chapter, with its own `work` dir and its take as `<audio>`:
Step 2a trim, Step 2 transcribe, Step 3 proofread, Step 4 shot list, Steps 6 to 8, then Step 9 with
`render-chunks.sh` writing `<dir>/<dir>.mp4`. Skip Step 10a per chapter; delivery happens once, after assembly.

- **One format and one resolution for every chapter.** `assemble.py` joins the video without re-encoding
  and refuses chapters that differ.
- **One kit and one theme for every chapter**, so the viewer never relearns the look.
- **Approve the shot list per chapter**, in order. Show the first chapter's stills before building the
  rest: the visual system is settled there.
- **Face chapters** (an on-camera opening or sign-off) use the bookends pieces from `face-bookends.md` inside
  that chapter only.
- **Screen recordings** (a code demo) are clips: `extract_clip.sh` the recording to the shot's window and
  `clip()` it full-bleed, with the narration as the chapter's audio.

## Pacing

Short-form pacing (a cut every 1 to 4 s, a hit per shot) is exhausting at 30 minutes. Long form:

- **Hold a diagram while it changes.** A shot lasts 5 to 20 s; it stays alive because something on it
  moves on the words: a tile moves to a slot, a timeline fills, a box lights up, a counter climbs. A hold
  with nothing moving for more than ~5 s still needs a slow `drift()`.
- **Build one picture per idea, then evolve it.** Reuse the same rack of slots across several shots instead
  of drawing a new diagram each time; viewers follow a picture they already know.
- **Cut on the idea, not the word.** A new shot when the narration moves to a new idea, not on every
  sentence.
- **Hits are rare.** About one `hit()` a minute, on the reveal the chapter builds to. Use `pop`, `tick` and
  `ding` cues for the small beats; leave whooshes for chapter-level transitions.
- **Chapter cards** (`chapter()`) only when a chapter starts without a spoken title. YouTube already shows
  the chapter name on the progress bar.
- **Code on screen** reads at speaking pace: a `terminal()` line types while the speaker describes it, and
  holds until they move on.

## Captions

Set `CAP_STYLE = "off"` in every chapter: burned-in captions for half an hour fight the diagrams for space.
`build_captions.py` still writes `captions.srt`, and `assemble.py` merges every chapter's file onto the
joined timeline for upload. Keep `"phrase"` only when the user asks for burned-in captions.

## Sound

- Run `synth_audio.py` per chapter. Music under long narration should sit low: set `audio.levels.music`
  around 0.12 in the kit, or pass `--no-music` for chapters that are mostly explanation and keep the bed for
  the opening and the close.
- Story moments (`--stop`, `--muffle`, `--stutter`) work per chapter; one per chapter at most.
- `assemble.py` measures the joined audio once and applies one gain to -14 LUFS, so the chapters keep their
  relative levels.

## Diagram pieces

Long-form diagrams are built from a few reusable pieces (`scene-blocks.md` → *Slots and tiles* and
*Scheduling timeline*):

| Piece | Markup | Motion |
|---|---|---|
| A row or grid of places (cores, carriers, pool slots) | `.rack` of `.slot` with a `<small>` label | `tl.set("#c3", {attr:{class:"slot on"}}, t)` lights one |
| Things that move between places (threads, tasks, requests) | `.tile`, `.tile.alt`, `.tile.wait` | `moveTo(sel, x, y, t)`; `centerOf("#c3")` gives a slot's centre |
| Who ran where over time | an empty `div` | `gantt(sel, rows, s, e)` grows each block in real time |

Use one tile style per kind of thing for the whole video, and say which is which once, early.

## Layout safe zones (landscape 1920x1080)

```
y=0     ┌──────────────────────────────┐
y=92    │          signature           │
y=150   ├──────────────────────────────┤
        │          shot area           │  x = 120 … 1800
y=860   ├──────────────────────────────┤
y=880   │   captions (when burned in)  │
y=1060  ├──────────────────────────────┤
        └─────────── progress ─────────┘
```

With captions off, the shot area runs to y = 1000. Keep text at 32 px or larger: long-form is watched on
laptops and TVs, but also on phones held sideways.

## Assemble

```bash
python3 SKILL_DIR/scripts/assemble.py <output dir>/<slug>
bash SKILL_DIR/scripts/deliver.sh --cover <seconds> <output dir>/<slug>/assembly <output dir>/<slug>/<slug>.mp4
```

`assemble.py` joins the chapter videos without re-encoding, joins their audio and normalises it once,
and writes `<slug>.mp4`. In `assembly/` it writes `captions.srt`/`.vtt` shifted onto the joined timeline,
`chapters.txt` (YouTube timestamps to paste into the description) and `credits.json` merged from every
chapter. It warns when YouTube would not show the chapters (fewer than three, or one shorter than 10 s) and
names any chapter without captions. `deliver.sh` then builds `assembly/delivery/` as for a Short.

To fix one chapter: change its composition, re-render it with `render-chunks.sh --force` to the same path,
and re-run `assemble.py`. The other chapters are untouched.

## Report

```
<slug>.mp4 · 1920x1080 · 28:41 · 4.1 GB · -14.0 LUFS

  chapters 14 · captions 612 cues (upload assembly/captions.srt) · credits 3

0:00 The question
1:28 What a CPU core is
…

Next: watch the chapter joins, then paste chapters.txt into the description
```

Watch each join before reporting: a cut between chapters should land on a pause, never mid-word.

## Failure states

| Symptom | Cause | Fix |
|---|---|---|
| `… is h264 1280x720 …; the first chapter is h264 1920x1080 …` | a chapter rendered with another format or resolution | re-fill that chapter with the project's `--format`, re-render it |
| `chapter N … has no render at …` | the render went somewhere else | render to `<dir>/<dir>.mp4` or set `"video"` in `chapters.json` |
| `⚠ no captions.srt for …` | `build_captions.py` never ran in that chapter's work dir | run it, then re-run `assemble.py` |
| YouTube shows no chapters | under three chapters, one under 10 s, or the list does not start at 0:00 | `assemble.py` names the problem; merge the short chapter into its neighbour |
| A jump in the music at a join | each chapter's synth bed is its own | expected; pass `--no-music` for the middle chapters, or end each chapter on `--drop` |
