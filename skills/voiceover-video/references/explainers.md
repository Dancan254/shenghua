# Explainers — script mode

Load this when there is no recording: the user gives a topic ("explain Kafka with cartoon
characters") or a script. You write the script, `speak.py` voices it, and the rest of the workflow
runs on `<work>/voice.wav` as if it were a recording.

---

## Shape of an explainer (90–120 s)

| Beat | Length | What happens |
|---|---|---|
| Hook | 5–10 s | the pain, shown: tangled services, a crash, a queue out of control. End on the question |
| Enter the world | 10–15 s | the analogy that carries the whole video (a sorting depot, a restaurant kitchen, a matatu stage) |
| Concepts | 15–25 s each | one concept per scene, never two. Name it once, on screen, as a `.pill` |
| Failure | 10–20 s | break something (a crash, an outage) and show the concept saving the day |
| Recap | 6–10 s | the terms in one breath, ticked off a list |
| Sign-off | 3 s | the handle and a line from the host |

About 150 words a minute: a 2-minute video is ~280 words. A line is one breath, 20 words at most.

## The analogy

Pick one real-world system whose parts map one-to-one onto the concept's parts, and write the mapping
before the script:

| Concept | Analogy |
|---|---|
| producer | a sender dropping letters at the depot |
| topic | a labelled aisle |
| partition | a pigeonhole; letters only go on the end |
| offset | the number stamped on each letter |
| consumer group | a delivery crew; one member per pigeonhole |

Every scene stays inside the analogy and labels the real term on screen. If a part has no match, the
analogy is wrong; pick another. Local analogies land hardest with a local audience.

## The cast

Two hosts carry most explainers:

- **The teacher** narrates and explains. Calm, warm, a little funny. Speaks ~80% of the lines.
- **The sidekick** asks the question the viewer is thinking ("They both get every letter?"), panics
  when things break, celebrates when they're fixed. One short line per scene at most.

The template ships three original designs: `keeper` (glasses, silver bun, clipboard, a calm teacher),
`conductor` (a matatu conductor with a backwards cap, reflective vest and money pouch, an energetic
teacher for anything about routing, queues or traffic) and `drone` (a one-eyed delivery drone, a
sidekick). Give them names that suit the analogy; the name in
the script is how `speak.py` and `host()` connect a voice to a body.

**Original characters only.** Never draw, name or imitate an existing cartoon, film or game character,
however it's rephrased ("a blue hedgehog", "that yellow sponge"). They are protected, and a video with
them gets claimed or taken down. Offer an original host instead.

## Script format

```
Keeper: Meet Pip. Pip carries messages between five services.
Pip: Which wire goes where?!
Keeper: Every service is wired straight to every other one.
---
Keeper: I'm Mama Log. I run a sorting depot, and my depot is Apache Kafka.
(pause 0.8)
```

`Name:` starts a line, `---` is a scene break (a longer pause), `(pause S)` is silence, `#` is a
comment. A line with no name goes to the narrator. If the teacher also introduces themselves, write
it in the first person; a narrator saying "Meet Mama Log" in Mama Log's voice sounds wrong.

Show the script to the user before voicing it. It is the cheapest thing to change.

## Voices

`speak.py` gives the first speaker `af_heart` (warm, clear) and the second `am_puck` pitched up 1.32
(small and squeaky). Override with a cast file:

```json
{ "keeper": {"voice": "af_heart"}, "pip": {"voice": "am_puck", "pitch": 1.32, "speed": 1.05} }
```

Useful voices: `af_heart`, `af_bella`, `af_nova` (American female); `am_michael`, `am_fenrir`,
`am_puck` (American male); `bf_emma`, `bf_isabella`, `bm_george`, `bm_daniel` (British). `pitch` above 1
makes a smaller character; keep it at or below 1.4 or words smear. `speed` 0.9–1.1.

### Your own voice (VoiceStudio)

The strongest teacher voice is the creator's own. [VoiceStudio](https://github.com/debpalash/VoiceStudio)
clones a voice locally from a short, clean recording and serves it over a local API; `speak.py` can
use it for any speaker while the others stay on Kokoro:

```json
{ "teacher": {"engine": "voicestudio", "voice": "<profile id>", "url": "http://localhost:3900"},
  "pip":     {"voice": "am_puck", "pitch": 1.32, "speed": 1.05} }
```

The user runs the VoiceStudio app and creates the profile from their own recording: 3–10 seconds of
clear speech plus its transcript. `speak.py` checks the app is up and the profile exists before voicing
anything. Clone only a voice the user owns or has permission to use.

**Check the engine's licence before a monetized video.** VoiceStudio's default engine (OmniVoice)
ships non-commercial weights (CC-BY-NC). For a channel that earns money, pick an engine whose weights
allow commercial use in VoiceStudio's model settings, and confirm on its model card.

You cannot hear the voices. After `speak.py`, tell the user which voice each character got and ask
them to listen to `voice.wav` before you build the shots. Swapping a voice then costs one re-run.

## Cutting to speech

Every line has exact times in `speech.json`, and the template reads them: `line("pip", 0)` is Pip's
first line, `{s, e, text}`. Cut shots and time bubbles from those instead of typing numbers, so a
re-voiced script re-times itself. `words.json` from `speak.py` holds estimated word times, close
enough for captions; for exact word sync, run `transcribe.py` on `voice.wav`.
