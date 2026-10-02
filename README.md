# voiceover-video

**An AI-agent skill that turns a voice recording into a fully edited, animated short video.**

Drop in a voice note. Your agent transcribes it word by word, designs a shot list, finds licensed photos and video of the people and products you mention, builds
every scene as kinetic typography and motion graphics timed to your words, adds sound design and a
music bed that ducks under your voice, and renders a 1080×1920 Short.

This repo ships one skill, `voiceover-video`: model-agnostic, it works in Claude Code, Kimi Code CLI, or
any agent that can run shell commands.

![A 42-second Kafka vs RabbitMQ explainer made with this skill: word-synced captions, a message-queue diagram, stamps and kinetic type on the blueprint theme](docs/demo.gif)

The full 42 s with sound, made from one voice note (shot list and composition in
[`examples/kafka-vs-rabbitmq`](skills/voiceover-video/examples/kafka-vs-rabbitmq/)):

https://github.com/user-attachments/assets/ce171d59-121d-4193-b6d0-cd011345ef41

No stock templates, no subscription editor, no uploads: transcription, rendering and audio all run on
your machine.

---

## What you get

- **Word-level captions** with a highlight box that follows the word being spoken
- **A new shot every 1–4 seconds**, cut on the word, not the sentence
- **Kinetic typography**: slams, highlight boxes, strike-throughs, stacked slogans, counters
- **Scene blocks**: terminals typing, stamps, VHS and CRT era looks, diagrams with flowing packets,
  charts, photo tape-ins, logo walls, montages
- **Eight themes that move differently**: kinetic, documentary, newsroom, blueprint, brutalist, aurora,
  minimal, retro. Each brings its own type, colour, captions *and* motion (default transition, shake,
  flash); the agent picks one to fit the topic
- **Real people, real footage**: mention a founder and the agent finds their photos and talks (Wikimedia
  Commons, Openverse, Internet Archive, web image search, YouTube, optional Pexels), shows them with a
  lower third, a picture-in-picture clip or a portrait quote, and hands you the credits for the description
- **Clip audio**: a speaking clip can carry its own sound, ducked under your narration
- **Camera moves**: whips, punch-in zooms, micro-shake on hits
- **Sound design**: 10 synthesized cue types (hits, whooshes, typing, ticks, risers…) placed by the
  timeline itself
- **A music bed** that ducks automatically under the voice and drops out before the final line
- **Film finish**: grain, vignette, loudness normalised to −14 LUFS
- **High-quality output**: frames rendered at 2x and saved lossless, encoded at CRF 16 with correct
  BT.709 colour, so edges stay crisp and brand colours stay true after the platform re-encodes it.
  `VV_QUALITY=draft` gives a fast preview cut
- **No recording? Script mode**: give it a topic ("explain Kafka with cartoon characters") and the agent
  writes an analogy-driven explainer, voices each character offline (a warm teacher, a squeaky
  sidekick), and animates original cartoon hosts who talk when their lines play, with speech bubbles,
  term labels and tokens flying into queues. `setup.sh --voices` installs the voice model once
- **Optional face-cam bookends**: film the script on your phone in one take; your opening line and
  sign-off stay on camera and everything between is animated
- **Presenter mode for green-screen talks**: the speaker is keyed out and stays on screen in your brand's
  background, moving between full-frame, split and close-up layouts while panels, checklists and diagrams
  build beside them; dead air at both ends is trimmed automatically. Keying measures the screen itself
  and resumes if interrupted
- **QA gates**: the agent reviews a contact sheet of every shot before the full render, and checks the
  encoded file, not just the preview

## How it works

```
voice.mp4                                    ┌ or, with no recording (script mode):
  │                                          │ topic → the agent writes script.txt → you approve it
  │                                          │ speak.py  offline voices per character → voice.wav
  │                                          └ + speech.json (who speaks when) + aligned word times
  │  transcribe.py        faster-whisper, local, word timestamps
  ▼
transcript.txt ── you proofread ──► build_captions.py
  │
  ▼  the agent writes a shot list  ──► you approve it
  │
  ▼  find_media.py        photos + clip sections from licensed sources, the web and YouTube, credits.json
  ▼  extract_clip.sh      clips → frames numbered by edit frame (+ clip audio)
  ▼  fill_template.py + the agent authors the scenes (HTML + GSAP)
  │
  ▼  render.js stills → contact-sheet.sh → the agent reviews, fixes, repeats
  │
  ├─► render.js cues → synth_audio.py      sfx.wav + music.wav
  └─► render-frames.sh                     headless Chromium, frame-exact
          │
          ▼  mix-encode.sh                  voice + ducked clip audio + ducked music + SFX → mp4
```

Every frame is rendered by seeking a paused timeline to an exact timestamp, so the same composition
always produces the same video, however slow the machine.

---

## Install

### Requirements

| | |
|---|---|
| [Claude Code](https://claude.com/claude-code) or [Kimi Code CLI](https://www.kimi.com/code) | the agent that runs the skill |
| Node 18+ | frame rendering |
| Python 3.10+ with `faster-whisper` and `numpy` | transcription and sound synthesis |
| FFmpeg | mixing and encoding |
| `yt-dlp` *(optional)* + `node` or `deno` | YouTube and other video pages; the JS runtime solves YouTube's download challenge |
| `PEXELS_API_KEY` *(optional)* | adds Pexels stock photos and video to media search ([free key](https://www.pexels.com/api/)) |
| `GIPHY_API_KEY` *(optional)* | adds GIPHY to reaction gif search ([free key](https://developers.giphy.com/dashboard/)) |

Runs on macOS and Linux. On Windows, run your agent inside WSL: the scripts are bash.

```bash
pip install faster-whisper 'av<19' numpy
# macOS: brew install ffmpeg node   ·   Debian/Ubuntu: sudo apt install ffmpeg nodejs npm
```

### Add the skill

**As a plugin** (recommended):

Inside Claude Code:

```
/plugin marketplace add Dancan254/voiceover-video-skill
/plugin install voiceover-video@voiceover-video-skill
```

Inside Kimi Code CLI:

```
/plugins install https://github.com/Dancan254/voiceover-video-skill
```

Then start a fresh session (`/new` in Kimi Code, or `/restart` in Claude Code).

**Or copy it** into your personal skills:

```bash
git clone https://github.com/Dancan254/voiceover-video-skill
# Claude Code
cp -r voiceover-video-skill/skills/voiceover-video ~/.claude/skills/
# Kimi Code CLI
cp -r voiceover-video-skill/skills/voiceover-video ~/.kimi-code/skills/
```

### One-time setup

Nothing to run by hand: the agent runs `setup.sh` the first time you use the skill. It installs
`playwright-core` and its Chromium build, and downloads GSAP and the fonts. It prints `ready` or names
exactly what is missing.

If you copied the skill instead of installing the plugin, you can run it yourself first:

```bash
bash ~/.claude/skills/voiceover-video/scripts/setup.sh
# or, for Kimi Code CLI:
bash ~/.kimi-code/skills/voiceover-video/scripts/setup.sh
```

---

## Use it

In Claude Code or Kimi Code CLI:

> make a video out of ~/Downloads/voice-note.m4a

The agent will tell you the transcription estimate, show you the shot list for approval, and hand you the
finished file with image credits and anything it could not verify.

Want to be on camera? Film yourself saying the script on your phone in one take and pass the video:

> make a video out of ~/Movies/take-1.mp4 with my face on the first and last line

Your opening line and sign-off stay on camera, and everything between is animated over the same take.
Record in SDR, not HDR, or the face shots come out washed out.

Useful follow-ups:

> make the intro punchier · use my music track ~/Music/bed.mp3 · render a landscape version

---

## Use it with another agent

Nothing here is tied to one model. `skills/voiceover-video/SKILL.md` is a plain workflow document, and
the scripts are Python, Node and bash that call no model at all. Any agent that can run shell commands
and write files can follow it:

```bash
git clone https://github.com/Dancan254/voiceover-video-skill
bash voiceover-video-skill/skills/voiceover-video/scripts/setup.sh
```

Then point your agent at `SKILL.md` and give it the audio file. Claude Code users get the same thing
through `/plugin install`, and Kimi Code CLI users through `/plugins install`, which only saves the cloning.

**What the agent needs:** a shell, file writing, and the ability to read text output. Vision is
optional and improves Step 5 (judging sourced images) and Step 7 (reviewing the contact sheet): an
agent that cannot see images lists each image source for you to confirm and runs `render.js check`,
which measures every shot and reports problems as text. No step needs audio, so every agent has to ask
you to listen to the mix before posting.

## Make it yours

Every video wears a **brand kit**: a folder with a `brand.json` and the fonts and logos it names. The
first time you use the skill, the agent asks for your name and handle, your colours (a named look or your
own), your fonts and where videos should go, then writes your kit to `~/.config/voiceover-video/`. Every
question has a default, so "just use the defaults" is a valid answer.

```
acme-kit/
  brand.json
  fonts/       AcmeSans.woff2            (or Google Fonts names in brand.json)
  logos/       mark.svg, wordmark-white.svg, wordmark.svg
```

```json
{
  "version": 2,
  "name": "Acme",
  "handle": "acme.com",
  "colors": { "primary": "#e50914", "secondary": "#ff8a00", "bg": "#0a0a0a", "text": "#f2f2f2" },
  "fonts": { "display": { "file": "fonts/AcmeSans.woff2" }, "mono": { "google": "JetBrains Mono" } },
  "logos": { "mark": "logos/mark.svg", "wordmark": { "onDark": "logos/wordmark-white.svg", "onLight": "logos/wordmark.svg" } },
  "background": { "style": "glow" }
}
```

Only `primary`, `bg` and a display font are required. Everything else is derived and checked: panel and
border shades, a readable text shade of the brand colour, caption contrast against WCAG AA, and a light
(or dark) canvas for themes designed for the other one. Before the first render the agent shows a
**brand board**, one image of the kit inside the chosen theme, so a wrong colour costs seconds, not a
render. Fonts can be any Google Font or the brand's own files; logos come from the brand, never from a
web search. `examples/kits/` has two fictional kits to copy.

Create one yourself:

```bash
# Adjust the path if you installed the skill as a plugin or copied it elsewhere
python3 ~/.claude/skills/voiceover-video/scripts/init_kit.py --name "Your Name" --handle @yourhandle --preset carbon-cyan
```

**Upgrading from 2.0:** brand files changed format in 2.1. Convert yours once; the original is kept as
`brand.v1.json`:

```bash
python3 ~/.claude/skills/voiceover-video/scripts/init_kit.py --from ~/.config/voiceover-video/brand.json
```

### Editing for a company

Each client gets their own kit folder, and kits install side by side, so their fonts never mix. A
prompt that gets the best result:

```text
Use the voiceover-video skill to edit this video.

Video:        ~/Projects/acme/keynote-take3.mp4
Brand kit:    ~/Projects/acme/brand-kit/   (or: colours #e50914 / #0a0a0a, fonts in ./fonts, logos in ./logos)
Script:       ~/Projects/acme/script.md    (spelling reference for names and terms)
Company:      Acme. We are the client; these brand assets are approved for this video
Audience:     developers on YouTube; landscape
Tone:         confident and calm, not hype
Must show:    the 3 product names, the 40% latency stat, our logo on the end card
Avoid:        competitor logos, red except for errors
Deliver:      brand board first, then the shot list, then a draft, then the final
```

The default type is **Archivo** (expanded black for headlines, condensed for captions) with
**Geist Mono** for code.

---

## Good to know

- **The recording sets the ceiling.** Sharp graphics can't rescue a soft, heavily compressed face. Before a
  shoot, send the speaker the [recording guide](docs/recording-guide.md): 1080p at 20 Mbps or more
  (4K recommended), the phone's own camera app rather than a browser or Zoom, an external mic.
- **The agent cannot hear the result.** Loudness is measured, taste is not. Listen before you post.
- **Render time.** High-quality frames take 2–3x longer than the old 1x JPEG ones (roughly 6–9 minutes
  for a 108-second Short on 10 CPU workers), plus transcription at 2–3x realtime. `VV_QUALITY=draft`
  renders a fast preview first.
- **Disk.** Lossless frames are ~1.2 MB each, about 4 GB for a 108-second Short, deleted with `work/`.
- **File size.** Film grain resists compression; the encoder caps the bitrate so a 108-second vertical
  lands around 200 MB. That headroom is what keeps it sharp after the platform re-compresses it.
- **Images and logos** found during an edit keep their own licences. See [THIRD_PARTY.md](THIRD_PARTY.md).

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Working on the repo
with an AI agent? Point it at [AGENTS.md](AGENTS.md).

## Licence

MIT for this repository. Downloaded tools, fonts, and assets keep their own licences — see
[THIRD_PARTY.md](THIRD_PARTY.md).
