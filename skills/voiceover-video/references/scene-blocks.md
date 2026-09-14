# Scene Blocks

The vocabulary for a voiceover edit. A shot is one `<section class="shot">` plus its timeline
lines. Pick a block for each line of speech, then time it to the word.

---

## Pacing

- **Cut every 1–4 seconds.** A shot held longer than ~5s needs internal motion (a push-in, a
  line drawing, a counter) or the viewer scrolls.
- **Cut on the word, not the sentence.** The shot starts at the first word of its idea.
- **Hits are punctuation.** Use `hit()` / `slam()` on the one word per shot that lands the
  point: a year, a name, a reveal, a punchline. More than ~2 hits per shot reads as noise.
- **Contrast beats intensity.** Slow down for reflective lines (fade entries, no hits, music
  down); speed up for montages (one word per cut).
- **End on a slam, then hold.** The last ~2.5s after the final word is the outro: handle, mascot,
  call to action.

## Transitions (`shot(id, in, out, enter)`)

| enter | Feel | Use for |
|---|---|---|
| *(none)* | hard cut | the default between fast beats |
| `whip` | sideways blur-whip | moving forward in the story |
| `whipUp` | vertical whip | lists, rising energy, "then…" |
| `zoom` | punch in from blur | reveals, new chapter |
| `fade` | soft | reflective lines, setup before a reveal |

---

## Blocks

### Kinetic slam
One huge word crashing in, everything else small around it.
```html
<div class="cx xl" id="s01a" style="top:520px;font-size:340px">JAVA</div>
```
```js
slam("#s01a", 0.44, 1.2);
```

### Strike-through
Kill a wrong assumption ("not built for the web").
```html
<span style="position:relative;display:inline-block">the web?<span class="strike" id="s01s"></span></span>
```
```js
tl.fromTo("#s01s",{scaleX:0},{scaleX:1,duration:.25,ease:EX},2.1); hit(2.12,.7);
```

### Highlight box
Marker-pen accent behind the key word.
```html
<span class="hl"><i id="s02hl"></i>DIFFERENT</span>
```
```js
tl.fromTo("#s02hl",{scaleX:0},{scaleX:1,duration:.3,ease:EX},4.58); hit(4.6,.6);
```

### Stacked slams
Each word of a slogan on its own line, one hit each ("WRITE / ONCE. / RUN / ANYWHERE.").
Add a `#pinkflash` burst on the last word. Hide captions.

### Counter
Years, stats, "30+ years later". Ease-out so it settles on the number.
```js
counter("#s03y", 1984, 1991, 6.5, 7.2); hit(7.2,.8);
```

### Typewriter / terminal
Code, commands, errors. The template's `.term` gives the window chrome; `typer()` types plain
text and pushes typing SFX. For mixed colours (red error lines), keep a line array and rebuild
`innerHTML` in the render loop — see `renderTerminal` in the template.

### Photo tape-in
A person or artefact. Tilted polaroid with a tape strip, slow push-in (`drift` on the `<img>`
scale), a typed name tag and a stamp.

### Stamp
Verdicts: `NOT READY`, `CONFIDENTIAL`, `SUN MICROSYSTEMS`. Scale from 3 → 1 in 0.2s and add a
`stamp` cue.

### Era look
Period-specific texture for historical beats:
- **VHS**: `.scan` overlay, `.vhs` chromatic text, moving `.track` bars, blinking `● SP`, date stamp
- **CRT monitor**: beige bezel `div` around a period screenshot with `.scan` at 40%
- **Dossier**: dark manila card, mono metadata, stamped title

### Diagram
Hub-and-spoke or tree. Draw paths with `strokeDashoffset`, `pop()` the nodes, send `.pkt`
dots along the routes, then turn nodes green with a `ding` per node. Keep diagrams inside
y = 150…1450 on vertical so captions never collide.

### Chart
One SVG path drawn over 2–4s. A crash is a line that climbs then falls; pair it with a `down`
cue and a stamp.

### Montage
One shot per word, 0.8–2s each, a `whip` and a `hit` on each: an icon or logo plus one word.
The emotional "it's everywhere" beat.

### Logo wall
3x3 grid of `.logo` cards popping with a stagger; nine `pop` cues.

### Path / journey
An SVG curve drawing slowly through labelled milestones — for "found its purpose along the way".

### Reflective photo
Full-bleed photo, darkened gradient, slow drift, large sentence fading in. No hits, music ducked.

### Outro
Stacked slams for the final line, mascot bouncing in, `follow @handle`. Hold ~2.5s.

---

## Sound cues

Every helper pushes its own cue into `SFX`; add extras with `SFX.push({t, type, dur?, power?})`.

| type | Sound | Pair with |
|---|---|---|
| `hit` | sub boom + click | `hit()`, `slam()` |
| `whoosh` | filtered noise sweep | transitions (auto from `shot()` enter) |
| `stamp` | dull thud | stamps |
| `pop` | pitched blip | `pop()` |
| `ding` | bell | success ticks |
| `type` (dur) | key clicks | `typer()` |
| `tick` (dur) | fast ticks | `counter()` |
| `riser` (dur) | rising noise + tone | the 1–2s before a big reveal |
| `down` (dur) | falling tone | crashes, failures |
| `error` | square buzz | red error lines |

The music bed ducks under the voice automatically. Use `--drop <t>` in `synth_audio.py` to cut
the music just before the final slam — silence before the punchline is the strongest hit.

---

## Layout safe zones (vertical 1080x1920)

```
y=0      ┌───────────────┐
y=92     │   signature   │
y=150    ├───────────────┤
         │   shot area   │  keep diagrams and cards here
y=1450   ├───────────────┤
y=1500   │   captions    │  70px, up to 3 lines
y=1800   ├───────────────┤
y=1910   └── progress ───┘
```

Full-bleed photos and backgrounds may fill the whole frame; readable elements may not.
