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
| `soft` | scale-settle with blur | polished launches, calm reveals |
| `slide` | push in from the right, no blur | next item, next chapter |
| `wipe` | hard-edged left-to-right reveal | news beats, diagram steps |
| `iris` | circle opening from the centre | focusing on one person or thing |
| `flash` | white flash cut | a sudden turn, "and then…" |
| `glitch` | jitter + colour shift + buzz | failures, hacks, retro beats |
| `cut` | hard cut, even when the theme has a default entry | overriding the theme |

Omitting `enter` uses the theme's default (`templates.json` → `motion.enter`): hard cut for
`kinetic`/`brutalist`, `fade` for `documentary`/`minimal`, `wipe` for `newsroom`/`blueprint`, `soft` for
`aurora`, `glitch` for `retro`. The theme also scales every `hit()` shake and flash, so write the same
powers in every theme and let the theme decide how loud they look.

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
counter("#s18n", 0, 200000, 50.6, 51.3, true);   // true adds thousands separators: 200,000
```

### Typewriter / terminal
Code, commands, errors. The template's `.term` gives the window chrome; `typer()` types plain
text and pushes typing SFX. For mixed colours (red error lines), keep a line array and rebuild
`innerHTML` in the `renderText` loop — see `terminal()` in the template.

### Photo tape-in
A person or artefact. Tilted polaroid with a tape strip, slow push-in (`drift` on the `<img>`
scale), a typed name tag and a stamp.

### Pan-and-zoom photo *(Ken Burns)*
Any photo held more than ~1.5s. Full-bleed or inside a `.photo` frame; the frame clips the push-in.
```html
<div class="photo" style="inset:0"><img id="s02img" src="assets/torvalds-portrait.jpg" alt="" style="object-position:50% 30%"></div>
<div class="credit" style="right:40px;top:160px">Krd / CC BY-SA 4.0</div>
```
```js
kenBurns("#s02img", 2.8, 6.1, "in");   // "in" · "out" · "left" · "right"
```

### Lower third
Name and role the first time a person appears on screen. Keep it above the caption zone
(vertical: top ≤ 1300).
```html
<div class="lower" id="s02lt" style="top:1180px"><div class="lower-name">Linus Torvalds</div><div class="lower-role">Creator of Linux &amp; Git</div></div>
```
```js
lowerThird("#s02lt", 3.2, 6.0);   // wipes in, wipes out 0.35s before the end
```

### Clip in frame *(picture-in-picture)*
The person speaking, the product demo, the launch on stage. The box size must match the size passed to
`extract_clip.sh`; always add a `.credit` line.
```html
<div class="pip" id="s04pip" style="left:90px;top:440px;width:900px;height:620px"><img id="s04img" alt=""><span class="tag">LF · 2017</span></div>
<div class="credit" style="left:90px;top:1080px">The Linux Foundation / CC BY 4.0</div>
```
```js
pop("#s04pip", 9.1);
clip("#s04img", "torvalds", 8.9, 12.6);   // same name, in and out as extract_clip.sh
```

### Reaction gif
A punchline beat: the facepalm, the "this is fine" dog. A `.pip` box, never full-bleed, looping for
1.5–2.5s. Fetch it with `find_media.py … --kind gif` and cut it with `extract_clip.sh … --loop`. One
or two per video; the box size matches the size passed to `extract_clip.sh`.
```html
<div class="pip" id="s09pip" style="left:140px;top:520px;width:800px;height:560px;transform:rotate(-3deg)"><img id="s09img" alt=""></div>
<div class="credit" style="left:140px;top:1100px">GIPHY / @creator</div>
```
```js
pop("#s09pip", 31.2);
clip("#s09img", "facepalm", 31.2, 33.4);
```

### Full-bleed clip
Same as the face shot, fed from `extract_clip.sh … vertical …` instead of the camera.
```html
<section class="shot face" id="s07"><img alt=""></section>
```
```js
shot("s07", 20.1, 23.4, "zoom"); clip("#s07>img", "launch", 20.1, 23.4);
```

### B-roll under narration
Footage playing full-bleed while the voice continues. Add a lower-third or a caption-safe headline so the shot still works muted. `broll()` is an alias for `clip()`.
```html
<section class="shot face" id="s08"><img alt=""></section>
<div class="lower" id="s08lt" style="top:1180px"><div class="lower-name">Linux Foundation</div><div class="lower-role">Collaboration Summit · 2017</div></div>
```
```js
shot("s08", 24.0, 28.5, "fade");
broll("#s08>img", "summit", 24.0, 28.5);
lowerThird("#s08lt", 24.2, 28.2);
```

### Portrait quote
The person's own words when their clip can't carry sound, or to repeat the line they just said.
```html
<div class="quote" id="s05q" style="top:420px">
  <div class="portrait"><img src="assets/torvalds-portrait.jpg" alt=""></div>
  <q>People can agree on the end result.</q>
  <cite>Linus Torvalds</cite>
</div>
```
```js
rise("#s05q", 12.7, .5);
```

### Duo
Two people, two products, before/after: two photos side by side.
```html
<div class="duo" style="left:70px;right:70px;top:380px;height:760px">
  <div class="photo"><img src="assets/a.jpg" alt=""></div><div class="photo"><img src="assets/b.jpg" alt=""></div>
</div>
```

### Ticker
A scrolling news band, mostly for `newsroom`. Place it under the signature (vertical: top 150).
Make the text long enough to fill the shot's scroll: ~160px per second.
```html
<div class="ticker" style="top:150px"><span id="s04tk">BREAKING · … · BREAKING · …</span></div>
```
```js
ticker("#s04tk", 8.9, 12.6);
```

### Stamp
Verdicts: `NOT READY`, `CONFIDENTIAL`, `SUN MICROSYSTEMS`.

```html
<div class="cx stamp" id="s04stamp" style="top:840px;color:var(--accent);font-size:120px">CONFIDENTIAL</div>
```
```js
stamp("#s04stamp", 4.2);
```

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
```js
stagger("#s09 .logo", 20.4, .09);   // one pop and one pop cue per card, in DOM order
```

### Path / journey
An SVG curve drawing slowly through labelled milestones — for "found its purpose along the way".

### Reflective photo
Full-bleed photo, darkened gradient, slow drift, large sentence fading in. No hits, music ducked.

### Host *(script mode)*
A cartoon character that talks when its lines play: mouth or bounce follow `speech.js`, blinks and bobs
run on their own. `kind` is `keeper` (teacher), `conductor` (teacher: a matatu conductor, cap on
backwards, reflective vest, money pouch) or `drone` (sidekick); `who` is the speaker's name in the
script. The element is only a box; size it for the shot. `keeper` and `conductor` use a ~0.69 width to
height box (330x480); `drone` is about square.
```html
<div class="host" id="s04pip" style="left:340px;top:520px;width:400px;height:420px"></div>
<div class="host" id="s04k" style="left:30px;top:1020px;width:330px;height:480px"></div>
```
```js
host("#s04pip","drone","pip"); host("#s04k","keeper","keeper");   // once per element, before the shots
mood("#s04pip","panic", 3.6, 5.2);    // "panic": shakes and sweats · "happy": eye becomes a smile
look("#s04pip", -1, .4, 0, 3.6);      // pupil direction, -1..1
point("#s04k", 6.6, 9.0);             // keeper or conductor raises an arm while explaining
wave("#s04c", 2.0, 4.5);              // conductor waves: greeting, calling passengers on
```
A host appears in several shots as several elements; call `host()` on each. Keep a host in the same
spot across a scene so it reads as one character, and give the bubble side room.

### Speech bubble
The line a host is saying, on screen while it's said. Captions step aside while it's up.
```html
<div class="bubble tail-down" id="s04b" style="left:250px;top:330px">Which wire goes where?!</div>
```
```js
say("#s04b","pip",0);                 // times itself to Pip's first line in speech.js
bubble("#s04b", 3.5, 5.2);            // or explicit in/out
```
Tails: `tail-down`, `tail-up`, `tail-left`, `tail-right`; point it at the speaker. Short lines only,
under ~8 words. The teacher's narration stays in captions; bubbles are for the lines a character
says *in* the scene.

### Term pill
The first time a term is said, name it on screen. One pill per term, per video.
```html
<div class="pill" id="s05t" style="left:340px;top:250px">Topic: orders</div>
```
```js
pop("#s05t", line("keeper",4).s + 1.2);
```
Colour a pill by what it names (`style="background:#2dd4bf"`); keep one colour per kind of thing.

### Lane and tokens
An ordered log, a queue, a pipeline stage: a lane with a label, and tokens (letters, messages, jobs)
that fly into it. The token's number badge is its position (an offset, a ticket number).
```html
<div class="lane" id="s05l" style="left:190px;top:560px;width:820px;--lane:#ffb020"><span class="lane-name">P0</span></div>
<div class="token" id="s05a" style="left:540px;top:-80px;--tag:#9b7bff"><b>0</b></div>
```
```js
send("#s05a", 270, 635, 6.7);          // arc to (x, y), whoosh out, pop on landing
tl.set("#s05l",{borderColor:"#3ddc84"}, 17); // outline turns green: "in order"
```
Tokens are positioned by `left`/`top` (the token's centre) so `send()` can read where they start.
Slots in a lane: `left + 80 + i * 120`, centred on `top + 75`. `--tag` colours the strip that marks a
key; `--lane` colours the label. Start a token off-frame (`top:-80px`) to drop it in from above.

### Failure and recovery
Break the thing the video is about, then show the concept fixing it: a host crashes (`mood(…,"panic")`,
a red `.pill` "CRASHED", `hit()`), a lane dims (`tl.to("#s07l",{opacity:.3},t)`), then the fix lands
with a green pill and the sidekick goes `happy`. This beat is what makes the concept stick.

### Outro
Stacked slams for the final line, mascot bouncing in, `follow @handle`. Hold ~2.5s. With a video
input, use *Face sign-off* instead.

### Face hook *(video input)*
The speaker on camera saying the opening line. Always shot 01, ending on the hook's last word.
```html
<section class="shot face" id="s01"><img alt=""></section>
```
```js
faceCam("s01", 0, 2.4);
hit(1.62, .5);
```
One punch-in on the word that lands the claim. Keep captions on: most viewers watch muted. Enter the
next shot with `zoom`. The `faceCam()` in/out times must exactly match the `extract_face.sh` range
for this shot.

### Series badge
Series name and episode, shown and never spoken. Pops on the first animated shot and leaves before
its cut. Place it inside that shot's section, not the face shot.
```html
<div class="cx" style="top:170px;z-index:5"><span class="badge" id="s02badge">SERIES NAME #04</span></div>
```
```js
pop("#s02badge", 2.5); tl.to("#s02badge",{opacity:0,duration:.3,ease:E},4.3);
```

### Face sign-off *(video input)*
The speaker on camera for the closing line. Always the last shot, from its first word to the end of
the composition. `fade` entry, no hits, no mascot.
```html
<section class="shot face" id="s24"><img alt=""></section>
```
```js
faceCam("s24", 84.1, D, "fade");
```
Face shots are full-bleed; check stills for a crop that cuts off the head. The `faceCam()` in/out
times must exactly match the `extract_face.sh` range for this shot.

---

## Captions

Captions are burned in automatically from `words.js`. Hide them whenever the spoken word *is* the
visual (a huge headline, a counter, a terminal) by adding its time range to `NOCAP` in the template:

```js
const NOCAP = [[1.2, 2.4], [4.1, 5.6]];
```

Never cover the element the viewer is meant to read; hide captions instead.

Two caption styles, set with `CAP_STYLE` in the template:

| `CAP_STYLE` | Feel | Use for |
|---|---|---|
| `"phrase"` *(default)* | whole phrase dimmed, one pulse, the spoken word marked | calm explainers, long sentences |
| `"pop"` | each word pops in on its own timestamp | fast Shorts, listicles, hype |

Both use the theme's mark for the spoken word. Words flagged in `keywords.json` stay in the accent
colour after they are spoken.

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

The music bed ducks under the voice automatically at mix time (`mix-encode.sh`). Use `--drop <t>`
in `synth_audio.py` to cut the music just before the final slam — silence before the punchline is
the strongest hit.

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
