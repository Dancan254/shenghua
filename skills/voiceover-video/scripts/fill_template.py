#!/usr/bin/env python3
"""Copy the composition template into a work directory with every placeholder filled.

  fill_template.py <work-dir> <duration> [--format vertical|landscape] [--brand path] [--template id]

Brand resolution order: --brand, ./brand.json, ~/.config/voiceover-video/brand.json,
then the bundled brand.example.json.

Template (theme) selection: --template picks a visual theme from templates/templates.json.
If omitted, the default theme is used. Each theme brings its CSS and a motion profile
(default shot entry, shake, flash, caption pulse); templates.json says which mood each suits.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
FORMATS = {
    "vertical": {"width": 1080, "height": 1920, "captionTop": 1500},
    "landscape": {"width": 1920, "height": 1080, "captionTop": 880},
}


def load_templates():
    manifest_path = SKILL_DIR / "templates" / "templates.json"
    if not manifest_path.is_file():
        return {"templates": []}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def resolve_brand(explicit):
    candidates = [explicit] if explicit else []
    candidates += [Path("brand.json"), Path.home() / ".config" / "voiceover-video" / "brand.json",
                   SKILL_DIR / "brand.example.json"]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    return None


def resolve_template(template_id):
    templates = load_templates().get("templates", [])
    by_id = {t["id"]: t for t in templates}
    if template_id:
        if template_id not in by_id:
            print(f"Unknown template '{template_id}'", file=sys.stderr)
            print(f"Next: use one of {', '.join(by_id)} or omit --template for the default", file=sys.stderr)
            return None
        return by_id[template_id]
    for t in templates:
        if t.get("default"):
            return t
    if templates:
        return templates[0]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    parser.add_argument("duration", type=float)
    parser.add_argument("--format", choices=FORMATS, default="vertical")
    parser.add_argument("--brand", type=Path, default=None)
    parser.add_argument("--template", default=None, help="theme id from templates/templates.json")
    args = parser.parse_args()

    brand_path = resolve_brand(args.brand)
    if brand_path is None:
        print("No brand file found", file=sys.stderr)
        print(f"Next: copy {SKILL_DIR / 'brand.example.json'} to ./brand.json and edit it", file=sys.stderr)
        return 1

    brand = json.loads(brand_path.read_text(encoding="utf-8"))

    required = {
        "handle": brand.get("handle"),
        "fonts.heading": brand.get("fonts", {}).get("heading"),
        "fonts.mono": brand.get("fonts", {}).get("mono"),
        "colors.bg": brand.get("colors", {}).get("bg"),
        "colors.accent": brand.get("colors", {}).get("accent"),
        "colors.surface1": brand.get("colors", {}).get("surface1"),
        "colors.surface2": brand.get("colors", {}).get("surface2"),
        "colors.border": brand.get("colors", {}).get("border"),
        "colors.textBody": brand.get("colors", {}).get("textBody"),
        "colors.textMuted": brand.get("colors", {}).get("textMuted"),
    }
    missing = [k for k, v in required.items() if v is None]
    if missing:
        print(f"Brand file {brand_path} is missing keys: {', '.join(missing)}", file=sys.stderr)
        print("Next: add them or run init_brand.py to generate a complete brand file", file=sys.stderr)
        return 1

    if args.duration <= 0:
        print(f"Duration must be positive, got {args.duration}", file=sys.stderr)
        print("Next: pass the composition length in seconds", file=sys.stderr)
        return 1

    template = resolve_template(args.template)
    if template is None:
        print("No templates found in templates/templates.json", file=sys.stderr)
        print("Next: check that templates/ contains a templates.json manifest", file=sys.stderr)
        return 1

    geometry = FORMATS[args.format]
    values = {
        "width": geometry["width"],
        "height": geometry["height"],
        "captionTop": geometry["captionTop"],
        "grainWidth": geometry["width"] // 2,
        "grainHeight": geometry["height"] // 2,
        "duration": f"{args.duration:.2f}",
        "brand.handleWithoutAt": brand["handle"].lstrip("@"),
        "brand.fonts.heading": brand["fonts"]["heading"],
        "brand.fonts.mono": brand["fonts"]["mono"],
    }
    values.update({f"brand.colors.{key}": value for key, value in brand["colors"].items()})

    html = (SKILL_DIR / "templates" / template["file"]).read_text(encoding="utf-8")

    # Inject the theme CSS so each work dir is self-contained and the agent can switch themes
    themes_dir = SKILL_DIR / "templates" / "themes"
    theme_css = (themes_dir / "shared.css").read_text(encoding="utf-8") + "\n" + \
        (themes_dir / f"{template['id']}.css").read_text(encoding="utf-8")
    for key, value in values.items():
        theme_css = theme_css.replace("{{" + key + "}}", str(value))
    values["theme.css"] = theme_css
    values["theme.motion"] = json.dumps(template.get("motion", {}))

    for key, value in values.items():
        html = html.replace("{{" + key + "}}", str(value))

    unfilled = sorted(set(re.findall(r"\{\{[^}]+\}\}", html)))
    if unfilled:
        print(f"Brand file {brand_path} is missing: {', '.join(unfilled)}", file=sys.stderr)
        print("Next: add those keys (see brand.example.json)", file=sys.stderr)
        return 1

    args.work.mkdir(parents=True, exist_ok=True)
    (args.work / "index.html").write_text(html, encoding="utf-8")
    # The page loads words.js; without a placeholder a preview render fails before captions exist
    captions = args.work / "words.js"
    if not captions.exists():
        captions.write_text("window.PHRASES=[];", encoding="utf-8")
    # speak.py writes speech.js in script mode; a recording has no speakers, so hosts stay idle
    speech = args.work / "speech.js"
    if not speech.exists():
        speech.write_text("window.SPEECH=[];", encoding="utf-8")
    vendor = args.work / "vendor"
    if not vendor.exists():
        vendor.symlink_to(SKILL_DIR / "assets", target_is_directory=True)

    print(f"{args.work / 'index.html'} · {geometry['width']}x{geometry['height']} · {args.duration:.2f}s · template {template['id']} · brand {brand_path}")
    print("Next: replace the demo shots between BEGIN/END SHOTS and BEGIN/END TIMELINE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
