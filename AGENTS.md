# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor, and others) working **on this
repository**. If you are *running* the skill to make a video, follow
`skills/voiceover-video/SKILL.md` instead.

## What this repo is

One Claude Code skill, `voiceover-video`, packaged as a plugin. It turns a voice recording into an
animated vertical video. The skill is a workflow document plus the scripts it calls:

```
skills/voiceover-video/
├── SKILL.md                     the workflow the agent follows at run time
├── brand.example.json           default brand (colours, fonts, handle)
├── references/scene-blocks.md   scene catalogue, pacing rules, sound cues, safe zones
├── templates/composition.html   the animation engine + 3 demo shots
└── scripts/
    ├── setup.sh                 dependency check, playwright-core + Chromium, GSAP, fonts
    ├── transcribe.py            faster-whisper, word-level timestamps
    ├── build_captions.py        applies fixes.json → words.js
    ├── init_brand.py            first-run answers → ~/.config/voiceover-video/brand.json
    ├── fill_template.py         brand + geometry + duration → work/index.html
    ├── extract_face.sh          to-camera video → face/fNNNNN.jpg, numbered by edit frame
    ├── render.js                stills | frames | cues | check, driven by window.renderAt(t)
    ├── render-frames.sh         parallel frame rendering
    ├── contact-sheet.sh         stills → one review image
    ├── synth_audio.py           cues.json → sfx.wav + music.wav
    └── mix-encode.sh            voice + ducked music + SFX → mp4
```

`.claude-plugin/marketplace.json` registers the skill for `/plugin install`. It is additive: other
hosts ignore it and read `SKILL.md` directly.

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
8. **Scripts fail loud.** Every script prints a one-line result and a `Next:` line, and on failure names
   the missing input and the fix. Match that shape.

## Conventions

- **Bash:** `set -euo pipefail`, quote every variable, `SCRIPTS_DIR` resolved from `BASH_SOURCE`. Scripts
  are called from zsh too — never rely on word splitting.
- **Python:** 3.10+, standard library plus `numpy` and `faster-whisper` only. `argparse`, a `main()`
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
