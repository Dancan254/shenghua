---
name: voiceover-video
description: "Turn a voice recording (voice note, narration, podcast snippet) into a fully animated, brand-styled video — local word-level transcription, a timed shot list, kinetic typography, camera moves, real photos and licensed video clips of the people and products it mentions, synthesized sound design and a voice-ducked music bed, rendered as a 1080x1920 Short (or 1920x1080). Also takes a to-camera phone recording: the opening line and sign-off stay on camera as face shots and everything between is animated. With no recording at all, writes an explainer script, voices each cartoon character offline, and animates talking hosts that teach the concept through an analogy. Use when asked to 'make an animated explainer about X', 'explain Kafka with cartoon characters', 'make a video with characters teaching this', or to 'make a video out of this audio', 'animate this voice note', 'turn this narration into a Short', 'edit this like a pro', 'create a video from my voiceover', or 'make a reel from this recording'."
---

# Voiceover Video Skill

Takes an audio file and builds a complete edit around it: every shot is an HTML/GSAP scene timed to
the exact spoken word, rendered frame by frame in headless Chromium, then muxed with a mixed
soundtrack (voice + synthesized SFX + ducked music). The judgement — what each line should *look*
like — is yours. The scripts handle transcription, rendering, audio, and encoding.

Given a to-camera video instead of audio, the opening line and the sign-off stay on camera as face
shots; everything between them is animated over the voice from the same take.

Given only a topic or a script (**script mode**), there is no recording: you write the script, Step 1b
voices it with one synthetic voice per character, and original cartoon hosts act it out. Everything
after Step 1b runs on the generated `<work>/voice.wav` as if it were a recording.

`SKILL_DIR` = the directory containing this SKILL.md.

**Always load `SKILL_DIR/references/scene-blocks.md` before writing the shot list.** It holds the
block catalogue, the pacing rules, and the sound-cue vocabulary.

---

## Step 0 — Gather inputs

| Field | Required | Example |
|-------|----------|---------|
| `audio`, `video` or `topic` | Yes | `~/Downloads/voice-note.m4a` · a to-camera recording `~/Movies/take-1.mp4` · `"explain Kafka consumer groups"` (script mode) |
| `script` | No | the script, plain or with `[FACE]` / `[VOICE]` sections; captions are checked against it. Sections start on their own line with exactly `[FACE]` or `[VOICE]`. In script mode, `Name: line` lines, and it *is* the input |
| `cast` | No | script mode: who's in it and which voice, e.g. `teacher Mama Log, sidekick Pip (squeaky)` |
| `format` | No | `vertical` 1080x1920 (default) · `landscape` 1920x1080 |
| `template` | No | visual theme id from `templates/templates.json` (default `kinetic`) |
| `music` | No | `synth` (default) · path to a royalty-free track · `none` |
| `model` | No | `small` (default) · `base` for clean audio, ~2x faster |
| `vocab` | No | names and terms the speaker uses: `"Kubernetes, Kafka, Jane Doe"` |
| `slug` | No | inferred from the topic, e.g. `java-origin` |

Brand: `./brand.json`, then `~/.config/voiceover-video/brand.json`, then the bundled
`SKILL_DIR/brand.example.json`. Output goes to `<brand.output.dir>/<slug>/`; work files go to
`<brand.output.dir>/<slug>/work/`. Create it now and set `<work>` to that path for the rest of the
workflow:

```bash
mkdir -p <brand.output.dir>/<slug>/work
work="<brand.output.dir>/<slug>/work"
```

Pick the defaults and proceed. Don't interrogate.

**First run only — no brand file anywhere:** the example brand ships someone else's handle and colours,
so ask before rendering. Four questions, each with its default, answered in one message:

| Ask | Default |
|---|---|
| Handle shown in the corner | required, no default |
| Look: `midnight-pink`, `carbon-cyan`, `ink-amber`, `violet-signal`, or their own accent and background | `midnight-pink` |
| Fonts: display and code | `Archivo` / `Geist Mono` |
| Where finished videos go | `~/voiceover-videos` |

```bash
python3 SKILL_DIR/scripts/init_brand.py --handle @theirhandle [--preset carbon-cyan] \
  [--accent '#ff6600' --bg '#0d1117'] [--heading Archivo --mono 'Geist Mono'] [--output-dir ~/voiceover-videos]
```

It derives the surface and border colours, checks the fonts against Google Fonts, and writes
`~/.config/voiceover-video/brand.json`. Then run Step 1 so the fonts download. Offer a preview: fill the
template and render one still, so they see their look before a full render. If they'd rather skip setup,
say plainly that the video will carry the example brand's `@yourhandle`.

In script mode there is no file to check; go to Step 1b after setup. Otherwise, if the audio or video
path is missing or not a file, say so and stop. With a `video`, pass the video
file wherever a step below takes `<audio>`; ffmpeg reads the voice from its audio track.

---

## Step 1 — Setup (first run only)

```bash
bash SKILL_DIR/scripts/setup.sh
```

Checks `ffmpeg`, `node`, `faster_whisper` and `numpy`; installs `playwright-core` and its matching
Chromium build; downloads GSAP and the brand's fonts into `SKILL_DIR/assets/`. Prints `ready` or names
the missing piece. Re-running is a no-op unless the brand's fonts changed.

---

## Step 1b — Script mode: write and voice the script

Only when there is no recording. **Load `SKILL_DIR/references/explainers.md` first.** It has the
explainer shape, how to pick the analogy, the cast roles and the script format.

1. Write the analogy mapping, then the script as `Name: line` lines, to `<work>/script.txt`. Show both
   to the user and wait for a yes; the script is the cheapest thing to change.
2. Voice it (first run: `bash SKILL_DIR/scripts/setup.sh --voices` installs the offline voice model, ~350 MB):

```bash
python3 SKILL_DIR/scripts/speak.py "$work"/script.txt "$work" [--cast "$work"/cast.json]
```

Writes `voice.wav`, `speech.json`/`speech.js` (who speaks when; the hosts read it), and `words.json` +
`transcript.txt` with estimated word times. Tell the user which voice each character got and ask them
to listen to `voice.wav`; you cannot. Re-voicing a line costs seconds, re-timing thirty shots does not.

From here, `<audio>` in every later step is `"$work"/voice.wav`. Skip Step 2 unless you want exact word
sync (then run it on `voice.wav`; it overwrites `words.json`). In Step 3, `script.txt` is the reference
and fixes are rarely needed.

---

## Step 2 — Transcribe

Tell the user the estimate first: roughly **2–3x realtime on CPU** for `small`.

```bash
python3 SKILL_DIR/scripts/transcribe.py <audio> --outdir "$work" --model small --vocab "<vocab>"
```

Writes `words.json` (every word with start/end) and `transcript.txt` — one phrase per line as
`[start] word@time word@time …`. Read `transcript.txt`; the per-word times are what you cut to.

Run it in the background for anything over two minutes. Never wait silently. The first run downloads
the model, so it may sit at low CPU for a few minutes.

---

## Step 3 — Proofread the captions

Captions are burned in. Scan `transcript.txt` for misheard words — proper nouns and technical terms
break first (observed: `San Micro Systems` → Sun Microsystems, `Ok` → Oak, `CNC++` → C/C++,
`Right once` → Write once). Write `<work>/fixes.json` mapping the raw token to its fix; an empty string
drops the token:

```json
{ "San": "Sun", "Ok.": "Oak.", "CNC++,": "C/C++,", "alias,": "", "that@50.22": "data" }
```

A plain key fixes the token everywhere. For a common word that was misheard once, key it as
`token@time`, with the start time printed in `transcript.txt`, and only that word changes.

Optionally write `<work>/keywords.json`, an array of words that stay in the accent colour once
spoken: `["Kafka", "Java@3.00"]`. A plain word flags every occurrence; `@time` flags one. Keep it to
names and the few nouns the video is about, one per phrase at most.

```bash
python3 SKILL_DIR/scripts/build_captions.py "$work"
```

Writes `<work>/words.js`. Never change timestamps. Tell the user about any token you could not
resolve instead of guessing.

With a `script`, it is the reference for spelling: a token that differs from it goes in `fixes.json`.
Captions follow what was said, so an ad-libbed line stays; tell the user where the take left the script.

---

## Step 4 — Shot list (confirm before building)

Load `references/scene-blocks.md`. Write a shot table — one row per shot, cut on word times:

```
#   in-out        line (spoken)                      block              sound
01  0.00-2.70     Did you know Java wasn't…          slam + strike      hit@0.44 hit@2.12
02  2.70-6.10     a completely different problem     highlight-box      whoosh, hit@4.60
03  6.10-8.30     Back in the early 1990s            vhs + counter      tick, hit@7.20
```

Rules: a new shot every 1–4 seconds; a hit only on a word that deserves it; captions hidden whenever
the spoken word *is* the visual. Find photos and clips before the table is final (Step 5).
See `SKILL_DIR/examples/kafka-vs-rabbitmq/` for a complete worked shot list.

**Pick the template (theme) now.** Read `templates/templates.json` and choose the `id` whose mood
matches the topic. Each theme changes type, colour, captions *and* motion (default shot entry, shake,
flash), so it is a real choice, not a palette swap:

| id | Pick it for |
|---|---|
| `kinetic` | fast, dark, neon — tech explainers, launches, listicles (default) |
| `documentary` | founder stories, company origins, biographies — serif, film grain, slow fades |
| `newsroom` | announcements, funding, outages, "this week in tech" — condensed type, ticker, wipes |
| `blueprint` | system design, architecture, "how X works under the hood" — grid paper, dashed outlines |
| `brutalist` | hot takes, myth busting — light background, hard black borders, hard cuts, big shake |
| `aurora` | AI and SaaS launches, dev tools — gradients, frosted glass, soft entries |
| `minimal` | thought leadership, deep dives — light, editorial, calm |
| `retro` | history of tech, CLI demos, hacking stories — CRT amber, glitch cuts |

If the user asked for a specific look, use that. Pass it to `fill_template.py` with `--template <id>`.

In script mode, the hosts carry the video: cut shots on `line(who, n)` times from `speech.json`, give the
sidekick a bubble for their lines (`say()`), name each term with a `.pill` the first time it's spoken,
and use lanes and tokens for anything that queues, flows or is numbered. The *Host*, *Speech bubble*,
*Term pill*, *Lane and tokens* and *Failure and recovery* blocks in `scene-blocks.md` cover it.

With a `video`, the first and last rows are face shots (*Face hook*, *Face sign-off*). The hook runs
from 0 to the last word of the script's first `[FACE]` section (no script: the first sentence). The
sign-off runs from the first word of the last `[FACE]` section to the end. A series badge goes on shot 02.

Show the table and the media list (every photo and clip, with its source and licence) to the user.
Wait for a yes — this is the expensive part to change later.

---

## Step 5 — Source photos and clips

Whenever the audio names a person, company, product or event, show it: the founder on stage, the
product launch, the person saying the line. `find_media.py` searches licensed sources (Wikimedia
Commons, Openverse, Internet Archive, and Pexels with `PEXELS_API_KEY`) alongside the open web (Bing
images) and YouTube:

```bash
python3 SKILL_DIR/scripts/find_media.py search "$work" "Yang Zhilin portrait"                       # photos
python3 SKILL_DIR/scripts/find_media.py search "$work" "Yang Zhilin keynote" --kind video           # talks
python3 SKILL_DIR/scripts/find_media.py fetch "$work" m6 --name yang-launch
python3 SKILL_DIR/scripts/find_media.py fetch "$work" m8 --name yang-gtc --section 120-150
python3 SKILL_DIR/scripts/find_media.py fetch "$work" --url "https://youtu.be/…" --name demo --section 30-45
python3 SKILL_DIR/scripts/find_media.py search "$work" "facepalm" --kind gif                        # reactions
python3 SKILL_DIR/scripts/find_media.py fetch "$work" m11 --name facepalm
```

Gifs come from Commons, and from GIPHY when `GIPHY_API_KEY` is set (GIPHY results are marked ⚠). A
fetched gif becomes an mp4 in `clips/src/`; cut it like any clip, adding `--loop` so a 2-second gif
fills a longer shot. Never put a `.gif` in an `<img>`: the browser plays it on its own clock, so every
render would differ. One or two reaction beats per video, on a punchline, never on the point itself.

Results without a licence are marked ⚠. When a licensed result is as good a shot, take it; otherwise
use the best shot. Prefer the subject's own channel (a company's official YouTube) over re-uploads.
Search queries that work: the name plus the company, then name + event ("keynote", "launch",
"interview"). Watermarked stock sites are filtered out.

A YouTube or page fetch downloads the whole video once into `clips/src/.cache/` (720p for anything over
15 minutes), then cuts `--section` (≤120s) from it, so later sections of the same talk are instant. Tell
the user the first fetch of a long talk takes a few minutes. To find a quote inside a section, run
`transcribe.py` on the fetched clip and use the word times as `--from` in Step 6.

**Look at every photo and every preview sheet before using it.** Search results lie: the wrong person
with the same name, a news site's logo or banner burned into the image, a thumbnail with text on it.
Crop around a banner with `object-position` or pick another result. If you cannot view images, list each
file with its source and what you expect it to show, and ask the user to confirm.

Logos: `https://cdn.jsdelivr.net/npm/simple-icons@13/icons/<slug>.svg`. Every fetch is recorded in
`<work>/credits.json`; log hand-sourced files yourself. The report lists every ⚠ file so the user knows
which footage belongs to someone else before posting.

---

## Step 6 — Author the composition

```bash
python3 SKILL_DIR/scripts/fill_template.py "$work" <duration> --format vertical --template <template-id>
# or --format landscape for 1920x1080
# omit --template to use the default kinetic theme
```

`<duration>` = last word end + ~2.5s for the outro; with a `video`, last word end + 0.5s, and never past
the recording's length. Get the recording length with:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 <video>
```

Writes `<work>/index.html` from the template with brand, geometry and duration filled, and links the
vendored assets as `<work>/vendor`.

With a `video`, extract the camera frames for both face shots, using the shot list's in/out times:

```bash
bash SKILL_DIR/scripts/extract_face.sh <video> <work> vertical <hook-in> <hook-out> <signoff-in> <signoff-out>
```

For every clip shot, cut the fetched clip to the shot's in/out. The size is the box it fills — `vertical`
or `landscape` for full-bleed, or the `.pip` box size like `900x620`. `--from` is the second inside the
clip to start at. Add `--audio` when the clip's own sound should play — a founder's line, a crowd:

```bash
bash SKILL_DIR/scripts/extract_clip.sh "$work"/clips/src/torvalds-talk.mp4 "$work" 900x620 torvalds 8.9 12.6 --from 20 --audio
bash SKILL_DIR/scripts/extract_clip.sh "$work"/clips/src/facepalm.mp4 "$work" 900x620 facepalm 31.2 33.4 --loop
```

Clip audio ducks under the narration automatically, so it only really plays over a pause in the voice.
For the speaker's line to land, place the clip over a gap in the recording (a scripted `[CLIP]` beat) or
leave it silent and put the quote on screen with a *Portrait quote*.

**B-roll is the same mechanism.** A full-bleed or picture-in-picture clip playing under narration is just
a `clip()` (or the alias `broll()`). Use the *B-roll under narration* block in `scene-blocks.md` for the
full-bleed + lower-third pattern.

Replace the demo shots between `BEGIN SHOTS` / `END SHOTS` (markup) and `BEGIN TIMELINE` /
`END TIMELINE` (GSAP) with your shot list, using the helpers the template already defines. Keep the
outer `#world` and `#cam` containers intact:
`shot()`, `slam()`, `hit()`, `rise()`, `pop()`, `stagger()`, `drift()`, `kenBurns()`, `lowerThird()`, `ticker()`,
`typer()`, `counter()`, `terminal()`, `faceCam()`, `clip()`, `broll()`, the `NOCAP` ranges, and the `CAP_STYLE` constant. Every helper that makes noise pushes its own sound cue.
See `SKILL_DIR/examples/kafka-vs-rabbitmq/` for a complete worked composition.

The display style (`.xl`) is uppercase and width-expanded; captions are condensed. Size headlines
for the expanded width — a vertical frame fits ~6 characters at 250px.

---

## Step 7 — QA stills (loop until clean)

Pick one timestamp per shot, at the moment of densest content:

```bash
node SKILL_DIR/scripts/render.js stills "$work"/index.html "$work"/stills 0.6,2.4,4.9,…
bash SKILL_DIR/scripts/contact-sheet.sh "$work"/stills "$work"/contact.jpg
```

Pass timestamps as a comma-separated list with **no spaces**; spaces parse as `NaN`.

Measure first — this needs no eyes and runs in seconds:

```bash
node SKILL_DIR/scripts/render.js check "$work"/index.html ["$work"/check.json]
```

It seeks to each shot at 25%, 50% and 85% of its window and reports text past the frame edge, text sitting under the caption
box, shots that render nothing at all three moments, and `PAGE ERROR` lines. Exit 1 means findings. Fix and re-run until it
is clean; it catches clipped headlines that a full render would waste minutes on.

Then, **if you can view images**, read `contact.jpg` for what measurement cannot judge: crops that cut
off a face or subject, an image that does not match the line, and layouts that fit the frame but read
badly. Fix, re-render only the affected stills, and look again.

If you cannot view images, say so in the report and ask the user to look at `contact.jpg` before
Step 9. Do not start Step 9 with a known defect — a full render costs minutes.

---

## Step 8 — Sound

```bash
node SKILL_DIR/scripts/render.js cues "$work"/index.html "$work"/cues.json
python3 SKILL_DIR/scripts/synth_audio.py "$work"/cues.json <duration> "$work" --template <template-id> --drop <time-of-final-slam>
```

Writes `sfx.wav` and `music.wav`. Pass the same `<template-id>` as Step 6: the music follows the theme's
tempo, key and layers, and varies per video (the slug folder). Omit `--drop` if the video has no final slam; otherwise use the time
of the last big hit. Optional pacing flags:

- `--drums-from <t>` — bring the drums in at `<t>` seconds.
- `--quiet <a>:<b>` — duck the music between `a` and `b` seconds (repeatable).

With `music` set to a file, pass `--no-music` and give that file to Step 10. With `none`, pass
`--no-music` and nothing else.

You cannot hear the result. Say so in the report and ask the user to listen.

---

## Step 9 — Render frames

```bash
bash SKILL_DIR/scripts/render-frames.sh [--blur 4] "$work"/index.html "$work"/frames <duration> [workers] [from_frame to_frame]
```

Frames render supersampled (2x) and are saved as lossless PNG: crisp edges and exact brand colours,
about 1.2 MB a frame (~4 GB for 108s) and 2–3x slower than a draft. Run it in the background. For a
quick preview cut, prefix `VV_QUALITY=draft` (1x JPEG); render the final with the default. The optional
frame range re-renders a single shot after a fix; each bound is its own argument, so it is safe under
zsh. Re-render a range with the same quality as the rest, or Step 10 refuses to mix them.

Pass `--blur 4` (first) for the final render only: it adds motion blur and makes the render about 8×
slower than the default. Render drafts and single-shot fixes without it, unless re-rendering a range of a blurred final.

---

## Step 10 — Mix and encode

```bash
out="<brand.output.dir>/<slug>/<slug>.mp4"
bash SKILL_DIR/scripts/mix-encode.sh "$work" <audio> <duration> "$out" [music-file]
```

Normalises the voice, ducks the music under it, lays the SFX on top, pads everything to the full
duration, and targets −14 LUFS. Video is H.264 at CRF 16 (slow preset, capped at 16 Mbps so film grain
can't balloon the file), converted and tagged as BT.709 so phones show the brand colours as designed.
A 108s vertical lands around 200 MB: high enough to survive the platform's own re-encode.

---

## Step 11 — Verify, then report

Before reporting, extract a frame from the **encoded file** at a shot you changed, read it, and check
the duration and size:

```bash
ffmpeg -v error -y -ss <t> -i <out.mp4> -frames:v 1 -vf scale=360:-1 <work>/verify.jpg
ffprobe -v error -show_entries format=duration,size -of compact <out.mp4>
```

A still rendered from the HTML is not proof the video contains the fix.

```
<slug>.mp4 · 1080x1920 · 108.2s · 112 MB · -14.7 LUFS

  shots 30 · sound cues 117 · images 4 · clips 2 · captions fixed 6

  credits     James Gosling 2008 (Wikimedia, CC BY-SA) · Solitary oak (geograph, CC BY-SA)
  unverified  music taste — listen before posting · timeline years are stylistic

Next: preview it on a phone, then post it with the credits in the description
```

`mix-encode.sh` prints raw `ffprobe` output; reformat it into the line above for the report. Get the
credits with `find_media.py credits "$work"` and give them to the user ready to paste into the description.
Name any unlicensed clip on its own line.

---

## Non-negotiables

- **Shot list confirmed before authoring.** Rendering is cheap; redesigning thirty shots is not.
- **Every image and clip is looked at before it is used.** Never ship media you have not seen.
- **Every file is credited.** Licensed or not, each photo and clip goes in the description credits, and
  the report names every ⚠ file.
- **Every fix is verified in the encoded file**, not just in a still.
- Transcription is local. Never upload the audio. Voices are synthesized locally too.
- Characters are original. Never draw, name or imitate an existing cartoon, film or game character.
- Synthetic voices are named in the report, so the user can disclose them when they post.
- One brand accent. Green only for success states, red only for errors.
- Timelines are deterministic: no `Math.random()`, no `Date.now()`. The grain uses a seeded PRNG.
- Captions never cover the element the viewer is meant to read; hide them via `NOCAP` instead.
- Report every image credit and every invented detail (dates, labels) that isn't in the audio.
- Never commit rendered files or `work/`.
- `faceCam()` in/out times match the `extract_face.sh` ranges exactly; never re-time a face shot alone.
  The same holds for `clip()` and `extract_clip.sh`.

---

## Failure states

| Symptom | Cause | Fix |
|---|---|---|
| `Executable doesn't exist at …ms-playwright…` | playwright-core updated, its Chromium build isn't installed | re-run `setup.sh` |
| Fix visible in stills but not in the video | frames never re-rendered — a range passed as one quoted string renders zero frames | use `render-frames.sh` with the range as two separate args; check frame mtimes |
| Video shorter than the audio | an audio filter trimmed the stream | `mix-encode.sh` pads and trims to the duration; don't hand-roll the mix |
| Output file is hundreds of MB | film grain defeats compression at constant CRF | keep the `-maxrate` cap in `mix-encode.sh` |
| `frames/ mixes high-quality PNG and draft JPEG frames` | a range was re-rendered with a different `VV_QUALITY` | re-render the whole video with one setting |
| Accent colour looks orange or washed out on a phone | an encode without the BT.709 conversion and tags | use `mix-encode.sh`; don't hand-roll the encode |
| Frame render fills the disk | high-quality PNG frames are ~1.2 MB each | free space, or preview with `VV_QUALITY=draft` and render the final once |
| Wrong or fallback font in stills | fonts not downloaded for this brand | re-run `setup.sh` with the brand file |
| `PAGE ERROR` in render output | a script error in the timeline | fix it; GSAP only warns on missing selectors, so also check each shot visually |
| Whisper sits at low CPU for minutes | model download on first run | expected once; the model is cached afterwards |
| Shot renders blank | `shot()` start ≥ end, or the shot id is misspelled | check the shot row's in/out times |
| `missing frame face/… ` or `clips/…` stops the render | a `faceCam()` / `clip()` range is wider than the extracted one | re-run `extract_face.sh` / `extract_clip.sh` with that shot's in/out |
| `find_media.py` search returns nothing | query too specific, or a source is down (its error prints on stderr) | the name plus the company; then `--kind video`; then a logo or an era look |
| YouTube fetch crawls or fails with a challenge warning | no JS runtime, or yt-dlp is out of date | needs `node` or `deno` on PATH; `pipx upgrade yt-dlp` |
| Clip shows the wrong moment | `--from` is in the fetched clip's seconds, not the original's | subtract the `--section` start |
| Old clip sound still in the mix | a stale `clips/<name>.wav` from an earlier cut | re-run `extract_clip.sh` for that clip; it removes the old `.wav` |
| `kokoro-onnx is not installed` / `Voice model missing` | script mode set up without voices | `setup.sh --voices` |
| `Unknown voice` from `speak.py` | a cast file names a voice that doesn't exist | pick one from the list it prints |
| A host never moves its mouth | its `who` doesn't match the speaker name in the script | use the lowercase name from `speech.json` |
| `speech.js has no line N for …` in `PAGE ERROR` | `line()`/`say()` asks for a line the script doesn't have | count that speaker's lines in `speech.json` from 0 |
| Face shots look grey and washed out | HDR (HLG) phone recording, tone-mapped without metadata | record in SDR (iPhone: Settings › Camera › Formats, HDR Video off) |
