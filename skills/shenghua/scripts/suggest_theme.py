#!/usr/bin/env python3
"""Rank the bundled themes for a project, so nobody has to pick a look blind.

  suggest_theme.py [--mode bookends|presenter|audio|script] [--topic "kafka consumer groups"]

Prints the top three themes with a one-line reason each. Scoring is deterministic: a mode prior
(face-forward takes want calm, graphic-heavy layouts want energy) plus keyword matches between the
topic and each theme's best_for/mood from templates.json.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Why each mode favours a look: face time wants calm type, graphics beside a speaker want energy
MODE_PRIORS = {
    "bookends": ({"documentary": 3, "minimal": 2, "newsroom": 1},
                 "a to-camera take keeps the speaker on screen, so calm type wins"),
    "presenter": ({"kinetic": 2, "aurora": 2, "blueprint": 1},
                  "the keyed speaker stays on screen; graphics build beside them"),
    "audio": ({"kinetic": 2, "aurora": 1},
              "a fully animated edit carries the energy"),
    "script": ({"kinetic": 1, "aurora": 1, "minimal": 1},
               "the cartoon hosts act the script out; the theme sets their stage"),
}


def score(theme, prior, words):
    value = prior.get(theme["id"], 0)
    haystack = " ".join([theme.get("mood", ""), theme["id"]] + theme.get("best_for", [])).lower()
    for word in words:
        if word in haystack:
            value += 2
    # The default theme breaks ties, so a topic with no keywords still gets a sensible answer
    if theme.get("default"):
        value += 0.5
    return value


def main():
    parser = argparse.ArgumentParser(description="suggest a theme for a shenghua project")
    parser.add_argument("--mode", choices=sorted(MODE_PRIORS), default="audio")
    parser.add_argument("--topic", default="", help="what the video is about, in a few words")
    args = parser.parse_args()

    catalogue = Path(__file__).resolve().parent.parent / "templates" / "templates.json"
    try:
        themes = json.loads(catalogue.read_text(encoding="utf-8"))["templates"]
    except (OSError, json.JSONDecodeError, KeyError) as error:
        print(f"cannot read {catalogue}: {error}", file=sys.stderr)
        print("Next: re-install the skill, or pass --template to fill_template.py directly", file=sys.stderr)
        return 1

    prior, reason = MODE_PRIORS[args.mode]
    words = [w for w in re.split(r"[^a-z0-9+#]+", args.topic.lower()) if len(w) > 2]
    ranked = sorted(themes, key=lambda t: score(t, prior, words), reverse=True)[:3]
    for theme in ranked:
        matches = [b for b in theme.get("best_for", []) if any(w in b.lower() for w in words)]
        why = f" · matches “{matches[0]}”" if matches else ""
        print(f"{theme['id']} — {theme['mood']}{why}")
    print(f"({args.mode} mode: {reason})")
    print(f"Next: fill_template.py … --template {ranked[0]['id']} (re-run with --template to change the look)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
