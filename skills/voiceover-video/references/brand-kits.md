# Brand kits — create, manage, choose

Load this when a kit has to be created, converted or picked: the first run with no kit, a client's
brand, several kits to choose between, or a contrast/glyph problem. A kit is a folder holding
`brand.json` (version 2) plus the fonts and logos it names; `SKILL_DIR/examples/kits/` has two
fictional ones (dark Northwind, light Lumen) to copy.

---

## Where kits live and which one a video uses

Named kits live in `~/.config/voiceover-video/kits/<name>/`; `init_kit.py --name <Name>` writes there
by default (`--out <folder>` puts a kit anywhere else, e.g. a client's project folder). The
single-kit `~/.config/voiceover-video/brand.json` keeps working as the user's own kit.

The kit a video uses, in order: the `kit` input (a path **or a kit name**), then `./brand.json`,
then the configured default, then the legacy `brand.json`, then the bundled
`SKILL_DIR/brand.example.json`. `--brand <name>` resolves a kit name as well as a path everywhere a
kit is accepted (`setup.sh`, `fill_template.py`, the board, `brand_kit.py check`).

```bash
python3 SKILL_DIR/scripts/brand_kit.py list                 # every kit in the kits folder, default marked
python3 SKILL_DIR/scripts/brand_kit.py default              # show the default
python3 SKILL_DIR/scripts/brand_kit.py default <name>       # set it (config.json → "defaultKit")
python3 SKILL_DIR/scripts/brand_kit.py resolve <name|path>  # print the kit a name or path resolves to
```

**Choosing at Step 0:** when `brand_kit.py list` shows more than one kit and the request names none,
list them (name, colours, fonts, which is the default) and ask which to use *before anything
renders*. A request that names one — "in the Acme kit", `--brand acme` — skips the question. With one
kit or none configured, proceed without asking.

## Creating a kit

**First run — no kit anywhere:** the example kit ships someone else's handle and colours, so ask
before rendering. Four questions, each with its default, answered in one message:

| Ask | Default |
|---|---|
| Name and handle shown on the video | required, no default |
| Look: `midnight-pink`, `carbon-cyan`, `ink-amber`, `violet-signal`, or their own colours | `midnight-pink` |
| Fonts: display and code — a Google font name, or a font file they have | `Archivo` / `Geist Mono` |
| Where finished videos go | `~/voiceover-videos` |

```bash
python3 SKILL_DIR/scripts/init_kit.py --name "Their Name" --handle @theirhandle [--preset carbon-cyan] \
  [--primary '#ff6600' --bg '#0d1117'] [--display Archivo --mono 'Geist Mono'] [--output-dir ~/voiceover-videos]
```

Then `brand_kit.py default <name>` makes it the default if it is the user's own kit.

**A client's brand** (a company video): build a kit from what the client supplies — never fetch a
company's logo or font from the web. Ask for the brand colours, the font files or Google names, and
the logo files (a mark, and a wordmark for dark and for light backgrounds), then:

```bash
python3 SKILL_DIR/scripts/init_kit.py --name Acme --handle acme.com --primary '#e50914' --bg '#0a0a0a' \
  --display ~/client/fonts/AcmeSans.woff2 --mono 'JetBrains Mono' --mark ~/client/logo-mark.svg \
  --wordmark-on-dark ~/client/wordmark-white.svg --wordmark-on-light ~/client/wordmark.svg \
  --background glow --out ~/clients/acme-kit
```

A light brand also passes `--bg-alt` and `--text-alt`: dark themes use them. `--background` is
`theme` (the theme's own canvas), `solid`, `glow`, `gradient` or `grid`; `--background-image <file>`
uses a picture. Only `primary`, `bg` and a display font are required; everything else is derived and
checked (panel and border shades, a readable text shade of the brand colour, a canvas for themes
designed for the other scheme).

**A version-1 brand file** (no `"version": 2`; scripts say so): convert it once. The original is
kept as `brand.v1.json`:

```bash
python3 SKILL_DIR/scripts/init_kit.py --from ~/.config/voiceover-video/brand.json
```

## The brand board (Step 1a)

First run, and every new kit:

```bash
python3 SKILL_DIR/scripts/fill_template.py "$work" 6 --format landscape --brand <kit> --template <template-id> --board
node SKILL_DIR/scripts/render.js board "$work"/board.html "$work"/board.png
python3 SKILL_DIR/scripts/brand_kit.py check <kit>
```

The board shows the kit inside the theme: headline and highlight, a panel, a lower third, captions, a
pill, a stamp, the end card with the logo, and the colour swatches. `render.js board` fails if a kit
font fell back to a default face. `brand_kit.py check` prints the contrast report (exit 1 below WCAG
AA; `--scheme dark|light` reports the other canvas) and warns when a logo has no variant for the
canvas. Show the board and wait for a yes; if you cannot view images, give the user `board.png` and
the contrast report. A wrong colour costs seconds here and a full render later. Pick the theme in
Step 4 first if the user hasn't — the board renders one theme. To compare themes, render one board
per theme and show them side by side.

## Glyph coverage: `check --text` and `fonts.fallback`

Kit fonts that lack a character render it silently in a fallback face. Two tools catch that:

- `brand_kit.py check <kit> --text <file>` reports the characters in a file (the script, the
  transcript) the kit's fonts lack.
- `render.js check` (Step 7) flags every missing glyph in the composition, naming the characters and
  the family.

A kit can declare `"fonts": { "fallback": "<family>" }` for characters it deliberately covers
elsewhere (an emoji or CJK family): `check` then reports those characters as covered, deliberately.
Otherwise swap the characters, or give the kit a fallback family that covers them.

---

## Failure states

| Symptom | Cause | Fix |
|---|---|---|
| `… is a version-1 brand file` | a brand.json from before kits | `init_kit.py --from <that file>` |
| `No kit named 'acme' in …/kits` | the name is wrong or the kit lives elsewhere | `brand_kit.py list`, or pass the folder path |
| `Brand kit … is not installed, or changed since it was` | the kit is new or was edited after setup | `setup.sh <kit>` |
| `font … did not load` from `render.js board` | a kit font file is missing or broken, or a Google family name is misspelled | fix the kit's `fonts`, re-run `setup.sh <kit>` |
| Logo invisible on the end card | a dark logo on a dark canvas, or an SVG with no size | add `wordmark.onDark`; give the `<img>` a height (see *Logo end card*) |
| `font X lacks glyphs for: …` from `render.js check` | characters the kit's fonts don't cover | swap the characters, or set `fonts.fallback` in brand.json |
| Contrast report shows `BELOW` | a derived shade fails WCAG AA | adjust the kit's colours; check the other `--scheme` |
