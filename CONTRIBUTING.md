# Contributing

Thanks for helping make voiceover-video better. Bug reports, new scene blocks, better sound design,
and docs fixes are all welcome.

AI coding agents: read [AGENTS.md](AGENTS.md) — it has the invariants and the verification procedure.

---

## Reporting a bug

Open an issue with:

- the **step** that failed (setup, transcribe, stills, frames, mix-encode…)
- the **exact command** and its **full output** — not piped through `tail`
- your OS, `node --version`, `python3 --version`, `ffmpeg -version | head -1`
- for visual bugs, the contact sheet or a frame extracted from the output

Please do not attach the voice recording unless you are happy for it to be public.

## Suggesting a scene block or feature

Open an issue first describing the *moment in a video* it is for ("a stat that should count up",
"a before/after code diff"). A block earns its place when it serves a kind of line people actually say.

---

## Development setup

```bash
git clone https://github.com/Dancan254/voiceover-video-skill
cd voiceover-video-skill
bash skills/voiceover-video/scripts/setup.sh
```

To try your working copy inside Claude Code, point a skill at it:

```bash
ln -sfn "$PWD/skills/voiceover-video" ~/.claude/skills/voiceover-video
```

## Making a change

1. **Branch from `main`:** `feat/count-up-block`, `fix/mix-duration`, `docs/branding-guide`.
2. **Keep it to one concern.** A new block and a refactor of the mixer are two pull requests.
3. **Respect the invariants** in [AGENTS.md](AGENTS.md) — determinism, cue coverage, full-duration mix,
   bitrate cap, nothing third-party committed.
4. **Verify on a clean copy** using the procedure in [AGENTS.md](AGENTS.md#how-to-verify-a-change). A
   cached `assets/` or `node_modules/` hides broken setup.
5. **Look at the output.** Attach the contact sheet (and a GIF or frame for visual changes) to the PR.

### Adding a scene block

1. Add the markup pattern and GSAP recipe to `references/scene-blocks.md`, with when to use it.
2. If it needs new CSS or a helper, add it to `templates/composition.html` — deterministic, and
   pushing its own sound cues.
3. If it introduces a cue type, handle it in `scripts/synth_audio.py` and list it in the cue table.
4. Render a short composition that uses it and include the stills in the PR.

### Adding a dependency

Say why in the PR, why the existing tools can't do it, and add it to `THIRD_PARTY.md` with its licence.
Downloaded assets go through `setup.sh`, never into git.

---

## Commit messages

[Conventional commits](https://www.conventionalcommits.org):

```
type(scope): short imperative description

Optional body explaining why.
```

Types: `feat` · `fix` · `refactor` · `docs` · `chore` · `ci`. Scope is the area touched: `render`,
`audio`, `setup`, `template`, `blocks`, `docs`.

## Pull requests

- Title in the same format as a commit subject.
- Description: **what** changed, **why**, and **how you verified it** (commands + attached images).
- `main` is protected: no force pushes, no deletion. Rebase your branch rather than rewriting `main`.

## Licence

By contributing you agree your contribution is licensed under the [MIT licence](LICENSE).
