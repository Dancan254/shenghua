# Recording guide

The skill can't add detail a recording never captured. Sharp graphics on top of a soft, heavily
compressed face still look cheap, so the recording sets the ceiling for the finished video. These are the
**minimums** for a good result; below them, quality drops visibly. Send this page to whoever is recording.

The most common cause of a poor result is a recording made in a browser, Zoom or Teams: those save
H.264 *Baseline* at a few Mbps, which smears skin and fine detail before editing starts.

## The file

- [ ] **Resolution:** 1920×1080 minimum, **3840×2160 (4K) recommended**: close-ups stay sharp and a 4K
      upload gets a higher bitrate on YouTube
- [ ] **Bitrate:** **≥ 20 Mbps at 1080p**, **≥ 50 Mbps at 4K**
- [ ] **Frame rate:** **30 fps**, constant; the skill renders at 30
- [ ] **Codec:** H.264 *High* profile or HEVC, straight from the camera, **not** *Baseline*
- [ ] **SDR only:** HDR, HLG and Dolby Vision **off**. HDR footage comes out grey and washed out
- [ ] **The original file**, sent through Google Drive, WeTransfer, Dropbox or AirDrop. **Never** WhatsApp,
      Slack, Telegram or email: they recompress video
- [ ] **Nothing burned in:** no name tag, logo, captions, filters or beauty mode. The edit adds its own

## Phone settings

- [ ] **iPhone:** Settings → Camera → Record Video → **4K at 30 fps**; Settings → Camera → Formats →
      **HDR Video off**
- [ ] **Android:** Camera → Video → **UHD 4K, 30 fps**; **HDR10+ off**; video stabilisation off on a tripod
- [ ] Record in the **phone's own camera app**, not a browser, Zoom, Teams or a social app

## Recording in StreamYard, Zoom, Teams or Riverside

For **one person talking to camera, skip these tools**: a phone at 4K or a camera gives far better
footage. They earn their place for live shows and interviews with guests. When you do use one:

- [ ] **Use the tool's local or separate-track recording**, not the recording of the stream or meeting.
      The stream recording is what was compressed for broadcast, with the layout and overlays baked in;
      local recordings capture each person on their own device, at higher quality, without overlays.
      Whether they're available, and at what resolution, depends on the tool and plan: check its settings
- [ ] **Turn off name banners, logos, backgrounds and lower thirds** for the recording. The edit adds its
      own, and burned-in ones have to be cut out or designed around
- [ ] **Turn off background blur and virtual backgrounds**: they eat into hair and shoulders
- [ ] **Set camera and recording resolution to the highest available**, at least 1080p
- [ ] **Use a real camera or a good webcam and an external mic**: a browser can't make a weak webcam sharp
- [ ] **Turn off the tool's noise suppression** if it lets you; it makes voices sound robotic
- [ ] **Send the per-person file** (each speaker's own recording), and **check it** with the command in
      [Check before sending](#check-before-sending): a stream recording usually fails it on bitrate or
      shows `Constrained Baseline`

## Camera behaviour

- [ ] On a **tripod**, not handheld
- [ ] **Focus, exposure and white balance locked**, so nothing drifts mid-take (iPhone: press and hold on
      the face for AE/AF Lock)
- [ ] **Beauty mode, skin smoothing, portrait and background-blur modes off**

## Framing

- [ ] **Landscape** (16:9)
- [ ] **Head and shoulders**, eyes about a third down from the top, a hand's width of space above the head
- [ ] Camera at **eye level**, **1–1.5 m** from the speaker
- [ ] For vertical Shorts from the same take: record 4K landscape with the speaker centred, so there is
      room to crop

## Light

- [ ] **One soft light in front of the face**, slightly to one side; facing a window works
- [ ] **No bright window or lamp behind the speaker**
- [ ] **No mixed light colours**, such as daylight with a yellow bulb

## Green screen (only when the background is replaced)

A green screen enables **presenter mode**: the speaker is keyed out and placed in the brand's background
for the whole video. The skill measures the screen and refuses a take it can't key cleanly, so these matter:

- [ ] **Screen lit evenly and separately** from the speaker: no shadows, no wrinkles
- [ ] Speaker **at least 1.5 m in front of the screen**, so green light doesn't spill onto skin and hair
- [ ] **No green clothing or accessories**; watch for reflections in glasses

No green screen? A plain, uncluttered background works well; it stays as it is.

## Audio

- [ ] An **external mic**: a clip-on lapel mic or a USB/shotgun mic. **Not** a laptop's built-in mic
- [ ] **48 kHz** sample rate
- [ ] A **quiet room**: no fan, air conditioning or echo
- [ ] **No noise suppression** from Zoom, Teams or the mic's app; the skill cleans the voice itself, and
      app suppression makes voices sound robotic
- [ ] **5 seconds of silence** at the start (room tone)

## The take

- [ ] **Start recording 2 s before speaking; hold still 2 s after the last word.** That gives clean cut
      points
- [ ] **One clean take.** If a line goes wrong, pause, restart the whole sentence, and note the
      timestamp. The skill doesn't cut out fluffed lines

## Send with the video

- [ ] **The script or article**: the spelling reference for names and terms
- [ ] **Brand colours** (hex codes), **font files** or Google Fonts names, and **logos as SVG**: one for
      dark backgrounds, one for light. See the brand kit format in the [README](../README.md#make-it-yours)
- [ ] **The brief**: platform, landscape or vertical, tone, facts or numbers that must appear, and anything
      to avoid

## Check before sending

On a computer, open the file's info (Mac: Get Info; Windows: Properties → Details). Resolution should
read **1920×1080 or 3840×2160** and total bitrate **20,000 kbps or more**. With ffmpeg installed:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,profile,bit_rate -of default=nw=1 recording.mp4
```

Look for `profile=High` (or `Main` for HEVC), not `Constrained Baseline`, and `bit_rate` of 20000000 or more.
