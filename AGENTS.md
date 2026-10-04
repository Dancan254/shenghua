# AGENTS.md

Instructions for AI coding agents (Claude Code, Codex, Cursor, and others) working **on this
repository**. If you are *running* the skill to make a video, follow
`skills/voiceover-video/SKILL.md` instead.

## What this repo is

One skill, `voiceover-video`, packaged as a plugin for Claude Code and Kimi Code CLI. It is
model-agnostic and turns a voice recording into an animated vertical video. With no recording (script
mode), `speak.py` voices a written script with one offline voice per character, and cartoon hosts in the
template act it out. Everything lives in `skills/voiceover-video/`.

```
skills/voiceover-video/
├── SKILL.md                     the core workflow the agent follows at run time (every mode)
├── brand.example.json           fallback brand kit (version 2) when the user has none
├── examples/kits/               two fictional kits (dark Northwind, light Lumen) for testing and copying
├── references/
│   ├── scene-blocks.md          scene catalogue, pacing rules, sound cues, safe zones
│   ├── presenter.md             presenter mode: keying, layouts, speaker position, pacing
│   ├── face-bookends.md         bookends mode: face shots, [FACE]/[VOICE] sections, extract_face.sh
│   ├── brand-kits.md            creating and managing kits, the kits folder, the brand board, glyphs
│   └── explainers.md            script mode: explainer shape, analogy, cast, script format, voices
├── templates/                   visual theme engine + themes
│   ├── kinetic.html             the shared HTML/JS engine + demo shots
│   ├── board.html               the brand board: one kit shown in one theme, for approval
│   ├── templates.json           theme catalogue: canvas (dark/light), mood, extra fonts, motion profile
│   └── themes/                  shared.css (kit tokens, backgrounds, people/footage blocks) + one CSS per theme
├── tests/                       unittest suite (numpy only), run from the repo root
└── scripts/
    ├── setup.sh                 dependency check, playwright-core + Chromium, GSAP, fonts; --voices, --vision
    ├── speak.py                 script mode: script → voice.wav + speech.json/js + aligned words.json
    ├── transcribe.py            faster-whisper, word-level timestamps; config.json for model/device defaults
    ├── trim_take.py             cut dead air: lossless voice.wav, word times shifted to 0, take.json
    ├── key_greenscreen.py       green-screen take → presenter/fNNNNN.webp with alpha, resumable; 30 fps edit frames
    ├── retime.py                re-time an edit onto a retake of the same script
    ├── build_captions.py        applies fixes.json → words.js + captions.srt/vtt
    ├── brand_kit.py             kit validation, colour derivation, contrast/glyph report, kits folder, per-kit install
    ├── init_kit.py              answers or client files → a kit in the kits folder; --from converts a version-1 brand.json
    ├── fill_template.py         kit + theme + geometry + duration → work/index.html (or board.html); keeps authored shots
    ├── extract_face.sh          to-camera video → face/fNNNNN.jpg, numbered by edit frame
    ├── find_media.py            photo/video search (Commons, Openverse, Archive, Pexels, web, YouTube) + credits.json
    ├── extract_clip.sh          fetched clip → clips/<name>/fNNNNN.jpg (+ clips/<name>.wav)
    ├── render.js                stills | frames | cues | check | board, driven by window.renderAt(t)
    ├── render-frames.sh         parallel frame rendering, resumable; --resolution 4k, --blur, --force
    ├── render-chunks.sh         default for finals: render + encode in chunks, resumable, ~2 GB peak scratch
    ├── contact-sheet.sh         stills → one review image
    ├── synth_audio.py           cues.json → sfx.wav + music.wav
    ├── mix-encode.sh            voice + ducked clip audio + ducked music + SFX → mp4; --10bit, --embed
    └── deliver.sh               master + web copy + captions + cover + credits.txt → delivery/
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
   The encode also converts RGB frames with the BT.709 matrix and tags the stream BT.709; without both,
   phones shift the brand colours.
6. **Final frames are supersampled PNG.** `render.js` renders at 2x device pixels and saves 1x PNG, so
   edges stay crisp and red text has no JPEG chroma bleed. JPEG frames are for `VV_QUALITY=draft` only,
   and `mix-encode.sh` refuses a frames directory that mixes the two.
7. **Nothing third-party is committed.** GSAP, fonts, `node_modules`, and Chromium are downloaded by
   `setup.sh`. Never add them to git.
8. **Placeholders are `{{dotted.names}}`** filled by `fill_template.py`. A new placeholder needs a value
   there and, if it comes from the kit, a field `brand_kit.py` validates and `brand.example.json` shows.
9. **Every fetched file is credited.** `find_media.py` records each download in `credits.json` with its
   licence, and marks web and YouTube files as unlicensed so the report can name them. A new source must
   do the same, and must be listed in `LICENSED_SOURCES` only if its results genuinely carry a licence.
10. **Every theme styles every block, in the kit's colours.** A theme CSS defines every class `kinetic.css`
   does plus the `--panel`, `--panel-fg`, `--frame`, `--radius`, `--display` tokens `shared.css` reads. Every
   colour is a `--brand-*` token or a `color-mix()` of one; the only literals are pure black and white and
   the `--fx-*` (effect) and `--host-*` (cartoon host) declarations in `shared.css`, and CI fails on any
   other. A theme declares its canvas (`scheme`: dark or light) in `templates.json`; the kit's display font
   always wins, and a theme's own typeface (`templates.json` → `fonts`) is only its fallback.
11. **Hosts are pure functions of `t`.** `renderHosts(t)` derives every mouth, blink and bob from `t` and
   `speech.js`; a host never keeps state between frames. `speech.js` and `faces.js` always exist
   (`fill_template.py` writes an empty one of each), so a recording without speakers or face
   measurements renders hosts idle and photos unshifted rather than failing.
12. **Characters are original.** The shipped hosts are original designs. Never add a host that imitates an
   existing cartoon, film or game character.
13. **Scripts fail loud.** Every script prints a one-line result and a `Next:` line, and on failure names
   the missing input and the fix. Match that shape.
14. **Presenter frames are numbered by edit frame and keying resumes.** `key_greenscreen.py` applies
   `take.json`'s cut when it keys, so frame N of the edit is `presenter/fNNNNN.webp` with no runtime offset.
   A re-run keys only frames whose WebP is incomplete, and workers stop when their parent dies, so a killed
   run never leaves a process writing frames a resumed run is also writing. Keep both properties: agents run
   this step for most of an hour, often past their shell's time limit.
15. **No render on a fallback font.** `render.js` loads every kit family by name before `stills`,
   `frames`, `check` and `board`, and exits 1 if one has no face: a lost font otherwise renders silently in
   a lookalike with different spacing, which no one notices until the captions shift. `check` also flags
   single characters no kit face covers, unless the kit's `fonts.fallback` marks them deliberate.

## Conventions

- **Bash:** `set -euo pipefail`, quote every variable, `SCRIPTS_DIR` resolved from `BASH_SOURCE`. Scripts
  are called from zsh too — never rely on word splitting.
- **Python:** 3.10+, standard library plus `numpy` and `faster-whisper` only (`find_media.py` uses `urllib`;
  `speak.py` alone also needs `kokoro-onnx`, installed by `setup.sh --voices`; `key_greenscreen.py` and
  `find_media.py` use `opencv` only when `setup.sh --vision` installed it). `argparse`, a `main()`
  returning an exit code, errors to stderr.
- **JavaScript:** `render.js` depends on `playwright-core` only; the template on GSAP only.
- **Comments** explain *why*, never *what*. One line.
- **No new dependency** without a reason in the PR description and an entry in `THIRD_PARTY.md`.

## How to verify a change

Run the unit-test suite first (numpy only, no setup needed):

```bash
python3 -m unittest discover -s skills/voiceover-video/tests -t skills/voiceover-video
```

The pipeline itself is verified end to end on a **clean copy**, because a cached setup hides broken
installs:

```bash
C=$(mktemp -d) && cp -r skills/voiceover-video "$C/skill" && S="$C/skill/scripts" && W="$C/work"
K="$C/skill/examples/kits/northwind"                # repeat the run with examples/kits/lumen
bash "$S/setup.sh" "$K"                              # must print "ready"
python3 "$S/brand_kit.py" check "$K"                 # contrast report, exit 0
python3 "$S/fill_template.py" "$W" 6 --format landscape --brand "$K" --template aurora --board
node "$S/render.js" board "$W/board.html" "$W/board.png"     # look at it
python3 "$S/transcribe.py" <any short speech clip> --outdir "$W" --model base
python3 "$S/build_captions.py" "$W"
python3 "$S/fill_template.py" "$W" 9.5 --brand "$K"
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

- Changes to the workflow belong in `SKILL.md`; mode detail lives in `references/` (`presenter.md`,
  `face-bookends.md`, `brand-kits.md`, `explainers.md`); changes to visual vocabulary belong in
  `references/scene-blocks.md` *and* the template helpers.
- Keep `SKILL.md` imperative and short enough for an agent to follow in one pass.
- Do not add per-user or per-brand content to the repo; it lives in the user's own kit folder. The only
  kits in the repo are the fictional ones in `examples/kits/`; never add a real company's brand there.
