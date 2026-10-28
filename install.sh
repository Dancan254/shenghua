#!/usr/bin/env bash
# install.sh [--dir <skills dir>] [--list] [--check] [--update] [--uninstall] — put the shenghua skill where your agent reads it.
# No arguments: auto-detect every agent on this machine and install into each one's skills dir.
# Piped (curl | bash): clones the repo to a temp dir first. Re-running updates in place and keeps
# the folders setup.sh downloads into (assets/, scripts/node_modules/), so an update re-downloads nothing.
# --check compares each install's recorded commit against the latest main (network, read-only);
# --update is the explicit alias for a normal re-run. Each install records its source commit in
# .installed-from so --check has something to compare.
set -euo pipefail

REPO_URL="https://github.com/Dancan254/shenghua"

usage() {
  cat <<'EOF'
usage: install.sh [--dir <skills dir>] [--list] [--check] [--update] [--uninstall]

  (no args)     install into every detected agent's skills dir
  --dir <path>  install into <path>/shenghua (any harness that reads a skills folder)
  --list        show the detected agents and targets, change nothing
  --check       report whether each install is behind the latest main (read-only)
  --update      update every detected install in place (alias for a normal re-run)
  --uninstall   remove the skill again (with --dir, only from there)

one-liner:  curl -fsSL https://raw.githubusercontent.com/Dancan254/shenghua/main/install.sh | bash
EOF
}

DIR=""
LIST=0
CHECK=0
UPDATE=0
UNINSTALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) DIR="${2:?--dir needs a path}"; shift 2 ;;
    --list) LIST=1; shift ;;
    --check) CHECK=1; shift ;;
    --update) UPDATE=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option $1" >&2; usage >&2; exit 1 ;;
  esac
done

# detection table: <config dir that proves the agent exists>|<skills dir>|<label>
detect_entries() {
  cat <<EOF
$HOME/.claude|$HOME/.claude/skills|Claude Code
$HOME/.kimi-code|$HOME/.kimi-code/skills|Kimi Code CLI
$HOME/.codex|$HOME/.agents/skills|Codex CLI
$HOME/.agents|$HOME/.agents/skills|shared (Codex / OpenCode / Gemini)
$HOME/.cursor|$HOME/.cursor/skills|Cursor
$HOME/.gemini|$HOME/.gemini/skills|Gemini CLI
${XDG_CONFIG_HOME:-$HOME/.config}/opencode|${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills|OpenCode
EOF
}

# prints "<skills dir>|<label>" lines, each skills dir once
detected_targets() {
  local seen="" line marker skills label
  detect_entries | while IFS='|' read -r marker skills label; do
    [[ -d "$marker" ]] || continue
    printf '%s|%s\n' "$skills" "$label"
  done | awk -F'|' '!seen[$1]++'
}

if (( LIST )); then
  targets=$(detected_targets)
  if [[ -z "$targets" ]]; then
    echo "no agent detected — would install to $HOME/.agents/skills (the shared Agent Skills folder)"
  else
    printf '%s\n' "$targets" | while IFS='|' read -r skills label; do
      if [[ -f "$skills/shenghua/SKILL.md" ]]; then state="installed"; else state="not installed"; fi
      printf '%-40s %-28s %s\n' "$skills" "$label" "$state"
    done
  fi
  exit 0
fi

if (( CHECK )); then
  if [[ -n "$DIR" ]]; then targets="$DIR|(--dir)"; else targets=$(detected_targets); fi
  command -v git >/dev/null || { echo "git not found — cannot check for updates" >&2; exit 1; }
  latest=$(git ls-remote "$REPO_URL" HEAD 2>/dev/null | awk '{print $1}')
  if [[ -z "$latest" ]]; then
    echo "could not reach $REPO_URL — update check skipped"
    echo "Next: re-run --check when online"
    exit 0
  fi
  found=0
  behind=0
  while IFS='|' read -r skills label; do
    dest="$skills/shenghua"
    [[ -f "$dest/SKILL.md" ]] || continue
    found=1
    installed=$(awk -F= '/^commit=/{print $2}' "$dest/.installed-from" 2>/dev/null || true)
    if [[ -z "$installed" ]]; then
      state="unknown age (predates commit tracking) — update recommended"; behind=1
    elif [[ "$installed" == "$latest" ]]; then
      state="up to date"
    else
      state="update available"; behind=1
    fi
    printf '%-40s %-28s %s\n' "$dest" "$label" "$state"
  done <<< "$targets"
  (( found )) || echo "no shenghua install found"
  echo "latest main: ${latest:0:12}"
  if (( behind )); then
    echo "Next: bash install.sh --update (keeps assets and node_modules)"
  else
    echo "Next: nothing to do — every install is current"
  fi
  exit 0
fi

if (( UNINSTALL )); then
  if [[ -n "$DIR" ]]; then targets="$DIR|(--dir)"; else targets=$(detected_targets); fi
  removed=0
  if [[ -n "$targets" ]]; then
    while IFS='|' read -r skills label; do
      dest="$skills/shenghua"
      # only ever remove a folder that is genuinely this skill
      if [[ -f "$dest/SKILL.md" ]] && grep -q '^name: shenghua' "$dest/SKILL.md"; then
        rm -rf "$dest"
        echo "removed · $dest"
        removed=1
      fi
    done <<< "$targets"
  fi
  (( removed )) || echo "nothing to remove — no shenghua skill found"
  exit 0
fi

(( UPDATE )) && echo "updating in place — assets and node_modules are kept"

# Locate the skill source: beside this script in a checkout, or clone when piped via curl
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || SELF_DIR=""
CLONE=""
if [[ -z "$SELF_DIR" || ! -f "$SELF_DIR/skills/shenghua/SKILL.md" ]]; then
  command -v git >/dev/null || { echo "git not found — install git, or clone $REPO_URL and run install.sh from the checkout" >&2; exit 1; }
  CLONE="$(mktemp -d)"
  trap 'rm -rf "$CLONE"' EXIT
  echo "fetching $REPO_URL"
  git clone --quiet --depth 1 "$REPO_URL" "$CLONE/shenghua"
  SELF_DIR="$CLONE/shenghua"
fi
SKILL_SRC="$SELF_DIR/skills/shenghua"

install_one() {
  local target="$1" label="$2" dest tmp keep commit
  dest="$target/shenghua"
  mkdir -p "$target"
  tmp="$(mktemp -d "$target/.shenghua-install.XXXXXX")"
  # exclude the folders setup.sh fills; an existing install's copies are moved back in below
  tar -C "$SKILL_SRC" --exclude='./assets' --exclude='./scripts/node_modules' --exclude='./scripts/__pycache__' -cf - . | tar -C "$tmp" -xf -
  # --check compares this commit against the remote main; a piped install records the clone's HEAD
  commit=$(git -C "$SELF_DIR" rev-parse HEAD 2>/dev/null || echo unknown)
  { echo "commit=$commit"; echo "installed=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; } > "$tmp/.installed-from"
  if [[ -d "$dest" ]]; then
    for keep in assets scripts/node_modules; do
      if [[ -d "$dest/$keep" ]]; then
        mkdir -p "$tmp/$(dirname "$keep")"
        mv "$dest/$keep" "$tmp/$keep"
      fi
    done
    rm -rf "$dest"
    echo "updated · $label → $dest (kept assets and node_modules)"
  else
    echo "installed · $label → $dest"
  fi
  mv "$tmp" "$dest"
}

if [[ -n "$DIR" ]]; then
  targets="$DIR|(--dir)"
else
  targets=$(detected_targets)
  if [[ -z "$targets" ]]; then
    targets="$HOME/.agents/skills|shared Agent Skills folder (no agent detected)"
    echo "no agent detected — installing to the shared folder; point your agent at it or re-run with --dir"
  fi
fi

count=0
while IFS='|' read -r skills label; do
  install_one "$skills" "$label"
  count=$((count + 1))
done <<< "$targets"

echo "done · shenghua in $count skills dir$([[ $count -eq 1 ]] || echo s)"
echo "Next: start a fresh session in your agent (skills load at session start), then: make a video out of <a recording>"
