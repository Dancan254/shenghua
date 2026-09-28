# Third-party software and assets

None of the items below are committed to this repository. `setup.sh` downloads each item onto your
machine, and each stays under its own licence.

| Item | Used for | Licence |
|---|---|---|
| [GSAP](https://gsap.com) 3.12.5 | the animation timeline | GSAP Standard "No Charge" licence — free, including commercial use ([terms](https://gsap.com/standard-license)) |
| [Archivo](https://fonts.google.com/specimen/Archivo) | default display and caption type | SIL Open Font License 1.1 |
| [Geist Mono](https://fonts.google.com/specimen/Geist+Mono) | default code and terminal type | SIL Open Font License 1.1 |
| [Fraunces](https://fonts.google.com/specimen/Fraunces) | `documentary` theme type | SIL Open Font License 1.1 |
| [Oswald](https://fonts.google.com/specimen/Oswald) | `newsroom` theme type | SIL Open Font License 1.1 |
| [Anton](https://fonts.google.com/specimen/Anton) | `brutalist` theme type | SIL Open Font License 1.1 |
| [playwright-core](https://github.com/microsoft/playwright) + Chromium headless shell | deterministic frame rendering | Apache 2.0 (Chromium: BSD-style) |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | local transcription | MIT |
| [FFmpeg](https://ffmpeg.org) | mixing and encoding | LGPL / GPL depending on your build |
| [Node.js](https://nodejs.org) + npm | running render.js and installing playwright-core | MIT |
| [curl](https://curl.se) | downloading fonts and GSAP in setup.sh | curl licence |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) *(script mode, `setup.sh --voices`)* | offline text-to-speech for character voices | MIT |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model and voices, via kokoro-onnx's release files | the voices themselves | Apache 2.0 — commercial use allowed |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) *(installed with kokoro-onnx)* | running the voice model on CPU | MIT |
| [VoiceStudio](https://github.com/debpalash/VoiceStudio) *(optional, installed by you, never by `setup.sh`)* | your own cloned voice for a script-mode speaker, over its local API | AGPL-3.0; each voice engine's weights carry their own licence (the default OmniVoice weights are CC-BY-NC, non-commercial) |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) *(optional, not installed by setup.sh)* | YouTube search and downloads; fetches its own [EJS](https://github.com/yt-dlp/yt-dlp/wiki/EJS) challenge solver on first use | Unlicense |

## Photos, clips and logos in your videos

The skill finds photos and video on [Wikimedia Commons](https://commons.wikimedia.org),
[Openverse](https://openverse.org), the [Internet Archive](https://archive.org), Bing image search,
YouTube and, with API keys, [Pexels](https://www.pexels.com/license/) and [GIPHY](https://giphy.com/terms), and logos from
[Simple Icons](https://simpleicons.org). Those are **not** covered by this repository's licence:

- Each file carries its own licence, often requiring attribution. `find_media.py` records a credit for
  every file it downloads in `credits.json`; put those credits in your video description.
- Web images, YouTube videos and GIPHY gifs come with no licence. They are someone else's copyrighted work: whether
  your use is fair use is your call, and YouTube's Content ID may claim, demonetise or block a video
  that contains them. `credits.json` marks each one.
- A photo or clip of a person can carry personality and publicity rights beyond its copyright licence.
  Don't imply someone endorses you or your product.
- Brand logos are trademarks of their owners. Simple Icons' [legal disclaimer](https://github.com/simple-icons/simple-icons/blob/develop/DISCLAIMER.md)
  applies; check a brand's guidelines before using its mark.
