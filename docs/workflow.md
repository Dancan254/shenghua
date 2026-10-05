# Workflow: from a fresh machine to a finished video

Every step, in order, for any coding agent that can run shell commands and read files. Copy the
prompts as they are; replace only the parts in `<angle brackets>`.

| Step | What | How often |
|---|---|---|
| [1](#1-install-the-tools) | Install the tools | once per machine |
| [2](#2-install-or-update-the-skill) | Install or update the skill | once, then to update |
| [3](#3-start-your-agent-in-a-project-folder) | Start your agent in a project folder | every project |
| [4](#4-create-a-brand-kit) | Create a brand kit | once per brand |
| [5](#5-choose-a-theme) | Choose a theme | every project |
| [6](#6-edit-the-video) | Edit the video | every video |
| [7](#7-your-approval-points) | Approve at four points | every video |

---

## 0. Before you start

You need:

- **A coding agent** that can run shell commands and read files. Vision helps (the agent can judge
  stills and boards itself) but isn't required: without it, the agent hands you the images to check.
- **The recording**: the original file, not a copy re-sent through a chat app.
- **The script or article**, if there is one: the spelling reference for names and terms.
- **Brand assets**: colours as hex codes, font files or Google Fonts names, logo files as SVG (one for
  dark backgrounds, one for light). These come from the brand owner.

Check the recording in a terminal:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,profile,bit_rate -of default=nw=1 "<recording>"
```

Good: `profile=High` (or `Main`), 1920×1080 or 3840×2160, `r_frame_rate=30/1`, `bit_rate` of 20000000
or more. Below that it still works, it just looks softer. How to record well:
[recording guide](recording-guide.md).

---

## 1. Install the tools

**macOS:**

```bash
brew install ffmpeg node python@3.12
# presenter mode (green-screen keying) needs libwebp, which Homebrew's core ffmpeg dropped:
# brew install ffmpeg-full   # replaces ffmpeg
python3.12 -m venv ~/.venvs/shenghua
~/.venvs/shenghua/bin/pip install faster-whisper 'av<19' numpy
echo 'export PATH="$HOME/.venvs/shenghua/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Linux (Debian/Ubuntu):**

```bash
sudo apt install ffmpeg nodejs npm python3-pip
pip install faster-whisper 'av<19' numpy
```

**Windows:** use WSL and follow the Linux steps.

Open a new terminal afterwards, so your agent sees the new tools.

## 2. Install or update the skill

There are two ways; use whichever your agent supports.

**A. As an installed skill or plugin**, if your agent has a skill or plugin system. See
[Add the skill](../README.md#add-the-skill) in the README; updating is that system's update command.
In the prompts below, start with *"Use the shenghua skill"*.

**B. As a cloned folder**, which works with any agent:

```bash
git clone https://github.com/Dancan254/shenghua ~/skills/shenghua
```

Update it later with:

```bash
git -C ~/skills/shenghua pull
git -C ~/skills/shenghua describe --tags     # the version you're on
```

In the prompts below, start with *"Read ~/skills/shenghua/skills/shenghua/SKILL.md
and follow it exactly"*. Every prompt in this guide uses this form; with option A, swap that first line.

## 3. Start your agent in a project folder

One folder per project keeps the brand kit, the source files and the outputs together:

```bash
mkdir -p ~/videos/<project> && cd ~/videos/<project>
```

Start your agent here. Put the brand's logo files in `./logos/` and the recording in `./source/`. The
prompts below use these paths relative to this folder.

---

## 4. Create a brand kit

Once per brand. Paste:

```text
Read ~/skills/shenghua/skills/shenghua/SKILL.md and follow it exactly.

Set up the skill, then create a brand kit at ./brand-kit:
name <Brand>, handle <handle or domain>,
primary <#hex>, secondary <#hex>, background <#hex>, text <#hex>,
display font <Google font or ./fonts/file.woff2>, code font <Google font or ./fonts/file.woff2>,
background style <glow | solid | gradient | grid | theme>,
mark logo ./logos/<mark>.svg,
wordmark for dark backgrounds ./logos/<wordmark-light>.svg,
wordmark for light backgrounds ./logos/<wordmark-dark>.svg.
Run setup.sh with the kit and show me the contrast report.
```

A brand with a light background also gives a dark one for dark themes: add
`dark background <#hex>, text on dark background <#hex>`.

**You check:** setup prints `ready`, and the contrast report has no `BELOW` lines. A warning about a
logo means it may be invisible on the background; supply the other wordmark.

Kits live in `~/.config/shenghua/kits/<name>/` (a kit made with `--out` lives wherever you put
it). Working with several brands, `brand_kit.py list` shows every kit with the default marked, and
`brand_kit.py default <name>` sets the one used when a prompt names none. Name a kit in the prompt —
`Brand kit: acme` — to use it for that video; with several kits and none named, the agent asks before
anything renders.

## 5. Choose a theme

```text
Using the brand kit at ./brand-kit, render brand boards (landscape) for the themes
<theme>, <theme> and <theme>, and show them to me side by side. Wait for me to pick one.
```

| Theme | Feel | Good for |
|---|---|---|
| kinetic | bold, uppercase, punchy | dynamic explainers, launches |
| aurora | soft glows, polished | product and AI talks |
| newsroom | accent bars, wipes, broadcast | announcements, news |
| blueprint | linework on tinted paper | architecture, how it works |
| documentary | cinematic, serif, grain | stories, origins |
| minimal | light, editorial, calm | thought leadership |
| brutalist | light, hard borders, loud | hot takes |
| retro | CRT monospace | history of tech, CLI demos |

**You check:** the board that fits the brand and the talk. Every theme takes its colours from the kit.

---

## 6. Edit the video

Pick the prompt for your recording.

### A. A green-screen talk (presenter mode)

The speaker is cut out of the green screen and stays on screen in the brand's background throughout.

```text
Read ~/skills/shenghua/skills/shenghua/SKILL.md and follow it exactly,
including references/scene-blocks.md. Edit this video in presenter mode.

Video:     ./source/<recording>
Brand kit: ./brand-kit
Format:    <landscape 1920x1080 | vertical 1080x1920 | square 1080x1080 | portrait 1080x1350>, theme <theme>
Trim:      auto
Position:  <auto | bottom-right | bottom-left | left | right | full>

First check the video with ffprobe and show me the result. Keying scales a 4K take itself
(--max-height) and converts any frame rate to 30 fps edit frames — no manual downscale.

Spelling reference: ./source/<script or article>.

Pacing: make the speaker's appearance dynamic, not a fixed cycle:
- Never use the same presenter layout twice in a row; mix full, splits, close-ups and corner bubbles
  unpredictably.
- Vary how long each layout holds: some 2 s, some 4 s, a few up to 8 s, matched to the sentence,
  not a fixed rhythm.
- Use close-ups for punchlines and strong claims, with a hit() camera punch on the key word.
- Cut to full-screen graphics (diagrams, stats, comparisons) often, and vary their entrances
  (zoom, whip, wipe, slide); don't use the same transition twice in a row.
- Every split panel builds line by line on the spoken words, never all at once.

Content: a chapter card for each heading in the script; a lower third "<Speaker name> ·
<role>" at the start. Must show: <facts, numbers, product names>. Avoid: <anything to leave out,
e.g. competitor logos>.

Run every long step (transcribe, key_greenscreen.py, render-frames.sh, mix-encode.sh)
detached with nohup and a log file, and poll the log; never block on one command. If keying or frame
rendering stops, re-run the same command; both resume. Render the final with render-chunks.sh
(the default over ~1 minute: ~2 GB peak scratch, resume at the first missing chunk) — it encodes
and mixes too, so skip mix-encode.sh after it.

Stop and wait for my approval at: the key preview, the shot list (include a layout column so I can
see the variety), and the draft. Then render the final, verify a frame from the encoded file, and
report duration, size, loudness and where the file is.
```

### B. A talk without a green screen (face shots at start and end)

```text
Read ~/skills/shenghua/skills/shenghua/SKILL.md and follow it exactly,
including references/scene-blocks.md.

Edit ./source/<recording>: the opening line and the sign-off stay on camera, everything between is
animated. Brand kit ./brand-kit, <landscape | vertical | square | portrait>, theme <theme>.
Spelling reference: ./source/<script or article>.
Must show: <facts, numbers, product names>. Avoid: <anything to leave out>.

Run long steps detached with nohup and a log, and poll it. Stop and wait for my approval at the shot
list and the draft. Then render the final, verify a frame from the encoded file, and report.
```

### C. A voice note or narration (no video)

```text
Read ~/skills/shenghua/skills/shenghua/SKILL.md and follow it exactly,
including references/scene-blocks.md.

Make a <60-second vertical Short | landscape | square | portrait video> from ./source/<audio file>.
Brand kit ./brand-kit, theme <theme>. Spelling reference: ./source/<script, if any>.
Find licensed photos and clips of the people and products it names, and credit every one.

Stop and wait for my approval at the shot list and the draft. Then render the final, verify a frame
from the encoded file, and report with the credits ready to paste.
```

### A Short from a long talk

Add this line to prompt A or B: *"Make it a 60-second vertical Short from <m:ss> to <m:ss> of the
recording."* The trim cuts the excerpt and keeps captions in sync.

### Choosing a transcription model

The default `small` is right for most recordings. Pass another in the prompt ("use the base model") or
set it once in `~/.config/shenghua/config.json`:

```json
{ "whisper": { "model": "large-v3-turbo", "device": "cuda", "compute_type": "float16" } }
```

A CLI flag beats `config.json`, which beats the built-in default; `VV_CONFIG` points at another config
file. `--device` is `auto` (CUDA when a GPU is present), `cpu` or `cuda` — a GPU runs several times
faster than CPU. `--model` also accepts a local CTranslate2 model folder, used as-is with no download.
Script mode's line alignment reads the same settings.

| Model | Accuracy | Speed on CPU (rough) | Download |
|---|---|---|---|
| `tiny` | draft only — names and terms suffer | ~10× realtime | ~80 MB |
| `base` | decent on clean audio | ~7× realtime | ~150 MB |
| `small` *(default)* | good | ~2–3× realtime | ~500 MB |
| `medium` | better with accents and noise | ~1× realtime | ~1.5 GB |
| `large-v3` | best | ~0.5× realtime — use a GPU | ~3 GB |
| `large-v3-turbo` | near-large, much faster | ~1–2× realtime | ~1.6 GB |

---

## 7. Your approval points

| When | What you look at | What to say |
|---|---|---|
| Video check | resolution, bitrate, audio | "go", or re-record if it's badly off |
| Key preview *(presenter mode)* | one keyed frame: clean hair, glasses and shoulders, no green edges | "go", or what's wrong |
| Shot list | layouts vary (no repeating pattern); spelling of names | "more variety" or corrections, then "go" |
| Draft | watch **and listen**, ideally on a phone: timing, sound levels, wrong words | timestamps, e.g. "1:42 SFX too loud" |
| Final | plays correctly; duration and loudness reported; the `delivery/` folder when you asked for it | done |

The shot list is the cheapest place to change anything; after the final render, every change means
re-rendering.

## 8. How long it takes

For a ~6-minute talk in presenter mode. Machine time only; add your review time.

| Step | 4-core laptop | Fast 12–16-core machine |
|---|---|---|
| Transcribe | 15–20 min | ~5 min |
| Key the speaker | ~45 min | ~10–15 min |
| Draft render | ~30 min | ~8–10 min |
| Final render | ~45–60 min | ~15 min |
| Final encode | ~25 min | ~8 min |

A 60-second Short takes roughly a sixth of that. Fast-machine times are estimates.

## 9. If something goes wrong

| What you see | What to do |
|---|---|
| "screen too dim or uneven to key" | light the green screen evenly and re-record, or use prompt B |
| "no screen to key" | the recording has no green screen: use prompt B |
| Keying stopped part-way | ask the agent to re-run the same key command; it continues |
| Frame rendering stopped part-way | re-run the same render command; completed frames are skipped |
| `vendor/ or kit/ is a dangling symlink` | an old project after a skill update: `fill_template.py <work> <duration> --relink` |
| "font … did not load" | ask the agent to re-run `setup.sh` with the kit |
| "version-1 brand file" | ask the agent to convert it: `init_kit.py --from <that file>` |
| A name banner burned into the recording | tell the agent where it is; it adds a `--mask` (the vision setup's key preview suggests one) |
| The edit feels repetitive | reject the shot list and repeat the pacing rules from prompt A |
| A step was killed by a time limit | ask the agent to run it detached with `nohup` and poll the log |

## 10. The next video

Skip steps 1, 2 and 4: tools, skill and kit are done. Update the skill, start your agent in a new
project folder (step 3), pick a theme (step 5), and paste the edit prompt (step 6). For a new brand,
create a new kit (step 4).
