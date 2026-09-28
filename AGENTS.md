# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor, and others) working **on this
repository**. If you are *running* the skill to make a video, follow
`skills/voiceover-video/SKILL.md` instead.

## What this repo is

Two skills packaged as one plugin for Claude Code and Kimi Code CLI:

- `voiceover-video` — the model-agnostic engine.
- `kimi-video` — a Kimi-branded edition that reuses the engine scripts and templates.

Both turn a voice recording into an animated vertical video. With no recording (script mode),
`speak.py` voices a written script with one offline voice per character, and cartoon hosts in the
template act it out. The shared engine scripts and templates
live in `skills/voiceover-video/`; the Kimi edition adds its own SKILL.md and brand defaults in
`skills/kimi-video/`.

```
skills/voiceover-video/
├── SKILL.md                     the workflow the agent follows at run time
├── brand.example.json           default brand (colours, fonts, handle)
├── references/scene-blocks.md   scene catalogue, pacing rules, sound cues, safe zones
├── references/explainers.md     script mode: explainer shape, analogy, cast, script format, voices
├── templates/                   visual theme engine + themes
│   ├── kinetic.html             the shared HTML/JS engine + demo shots
│   ├── templates.json           theme catalogue: mood, extra fonts, motion profile
│   └── themes/                  shared.css (people/footage blocks) + one CSS per theme
└── scripts/
    ├── setup.sh                 dependency check, playwright-core + Chromium, GSAP, fonts
    ├── speak.py                 script mode: script → voice.wav + speech.json/js + estimated words.json
    ├── transcribe.py            faster-whisper, word-level timestamps
    ├── build_captions.py        applies fixes.json → words.js
    ├── init_brand.py            first-run answers → ~/.config/voiceover-video/brand.json
    ├── fill_template.py         brand + geometry + duration → work/index.html
    ├── extract_face.sh          to-camera video → face/fNNNNN.jpg, numbered by edit frame
    ├── find_media.py            photo/video search (Commons, Openverse, Archive, Pexels, web, YouTube) + credits.json
    ├── extract_clip.sh          fetched clip → clips/<name>/fNNNNN.jpg (+ clips/<name>.wav)
    ├── render.js                stills | frames | cues | check, driven by window.renderAt(t)
    ├── render-frames.sh         parallel frame rendering
    ├── contact-sheet.sh         stills → one review image
    ├── synth_audio.py           cues.json → sfx.wav + music.wav
    └── mix-encode.sh            voice + ducked clip audio + ducked music + SFX → mp4
```

`.claude-plugin/marketplace.json` registers the skill for Claude Code's `/plugin install`, and
`.kimi-plugin/plugin.json` registers it for Kimi Code CLI's `/plugins install`. Both are additive: other
hosts ignore them and read `SKILL.md` directly.

## What an agent needs to run this

The skill is model-agnostic by construction — no script calls a model, and `SKILL.md` names no vendor.
Keep it that way:

- **Required:** a shell, file writing, reading text output. Every script prints a one-line result and a
  `Next:` line, so an agent can follow the workflow from stdout alone.
- **Optional:** vision. Only Step 5 (judging a downloaded image) and Step 7 (reading the contact sheet)
  benefit. Both have a documented text path: list images for the user to confirm, and
  `render.js check`, which measures every shot and reports defects as text.
- **Never assumed:** audio. Nothing can hear the mix, so the workflow always asks the user to listen.

A change that makes any step impossible without vision, or that ties the workflow to one agent's tool
names, breaks this.

## Invariants — do not break these

1. **Rendering is deterministic.** The composition exposes `window.renderAt(t)` and every frame is a
   seek to `f / 30`. No `Math.random()`, no `Date.now()`, no `requestAnimationFrame`-driven state, no
   GSAP `repeat: -1` or `yoyo` on the main timeline. Grain uses the seeded PRNG in the template.
2. **Every sound comes from a cue.** Helpers that make noise push into `window.SFX`;
   `synth_audio.py` must handle every cue `type` the template or `scene-blocks.md` documents. Adding a
   cue type means changing both.
3. **Frame ranges are two arguments.** `render.js frames <html> <out> <from> <to>`. A single quoted
   `"from to"` renders zero frames; `render.js` rejects it — keep that check.
4. **The mix pads to the full duration.** `mix-encode.sh` uses `apad` + `atrim`; without it `loudnorm`
   trims the tail and the video comes out short.
5. **The encoder caps bitrate.** Film grain defeats CRF alone; removing `-maxrate` produces 800 MB files.
6. **Nothing third-party is committed.** GSAP, fonts, `node_modules`, and Chromium are downloaded by
   `setup.sh`. Never add them to git.
7. **Placeholders are `{{dotted.names}}`** filled by `fill_template.py`. A new placeholder needs a value
   there and, if it comes from the brand, a key in `brand.example.json`.
8. **Every fetched file is credited.** `find_media.py` records each download in `credits.json` with its
   licence, and marks web and YouTube files as unlicensed so the report can name them. A new source must
   do the same, and must be listed in `LICENSED_SOURCES` only if its results genuinely carry a licence.
9. **Every theme styles every block.** A theme CSS defines every class `kinetic.css` does plus the
   `--panel`, `--panel-fg`, `--frame`, `--radius`, `--display` tokens `shared.css` reads. A theme with its
   own typeface lists it in `templates.json` → `fonts`; `setup.sh` downloads it.
10. **Hosts are pure functions of `t`.** `renderHosts(t)` derives every mouth, blink and bob from `t` and
   `speech.js`; a host never keeps state between frames. `speech.js` always exists (`fill_template.py`
   writes an empty one), so a recording without speakers renders hosts idle rather than failing.
11. **Characters are original.** The shipped hosts are original designs. Never add a host that imitates an
   existing cartoon, film or game character.
12. **Scripts fail loud.** Every script prints a one-line result and a `Next:` line, and on failure names
   the missing input and the fix. Match that shape.

## Conventions

- **Bash:** `set -euo pipefail`, quote every variable, `SCRIPTS_DIR` resolved from `BASH_SOURCE`. Scripts
  are called from zsh too — never rely on word splitting.
- **Python:** 3.10+, standard library plus `numpy` and `faster-whisper` only (`find_media.py` uses `urllib`;
  `speak.py` alone also needs `kokoro-onnx`, installed by `setup.sh --voices`). `argparse`, a `main()`
  returning an exit code, errors to stderr.
- **JavaScript:** `render.js` depends on `playwright-core` only; the template on GSAP only.
- **Comments** explain *why*, never *what*. One line.
- **No new dependency** without a reason in the PR description and an entry in `THIRD_PARTY.md`.

## How to verify a change

There is no unit-test suite; the pipeline is verified end to end on a **clean copy**, because a
cached setup hides broken installs.

```bash
C=$(mktemp -d) && cp -r skills/voiceover-video "$C/skill" && S="$C/skill/scripts" && W="$C/work"
bash "$S/setup.sh"                                   # must print "ready"
python3 "$S/transcribe.py" <any short speech clip> --outdir "$W" --model base
python3 "$S/build_captions.py" "$W"
python3 "$S/fill_template.py" "$W" 9.5
node "$S/render.js" stills "$W/index.html" "$W/stills" 1.0,2.4,5.0,7.8
bash "$S/contact-sheet.sh" "$W/stills" "$W/contact.jpg"      # look at it
node "$S/render.js" cues "$W/index.html" "$W/cues.json"
python3 "$S/synth_audio.py" "$W/cues.json" 9.5 "$W"
bash "$S/render-frames.sh" "$W/index.html" "$W/frames" 9.5 8
bash "$S/mix-encode.sh" "$W" <the same clip> 9.5 "$W/out.mp4"
ffmpeg -v error -y -ss 5 -i "$W/out.mp4" -frames:v 1 "$W/verify.jpg"   # look at it
```

A change is verified when: `setup.sh` prints `ready`, every step exits 0, `contact.jpg` and
`verify.jpg` look right, and `mix-encode.sh` reports the expected duration and roughly −14 LUFS.
**Look at the images.** Renders that exit 0 can still be blank, clipped, or in a fallback font.

Do not pipe a step through `tail`/`head` when checking it — the pipe hides the exit code.

## Scope

- Changes to the workflow belong in `SKILL.md`; changes to visual vocabulary belong in
  `references/scene-blocks.md` *and* the template helpers.
- Keep `SKILL.md` imperative and short enough for an agent to follow in one pass.
- Do not add per-user or per-brand content to the repo; that lives in the user's `brand.json`.
