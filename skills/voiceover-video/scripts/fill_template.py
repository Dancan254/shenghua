#!/usr/bin/env python3
"""Copy the composition template into a work directory with every placeholder filled.

  fill_template.py <work-dir> <duration> [--format vertical|landscape] [--brand kit] [--template id] [--board]

Brand kit resolution order: --brand (a kit folder or its brand.json), ./brand.json,
~/.config/voiceover-video/brand.json, then the bundled brand.example.json. setup.sh must have
installed the kit, so its fonts and logos are on disk.

Template (theme) selection: --template picks a visual theme from templates/templates.json.
If omitted, the default theme is used. Each theme brings its CSS, the canvas it wants (dark or
light) and a motion profile; the kit brings every colour, font and logo.

--board writes board.html instead: one still showing the kit in the theme, for approval.
"""

import argparse
import html as markup
import json
import re
import sys
from pathlib import Path

import brand_kit

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


def signature(manifest):
    handle = markup.escape(manifest.get("handle", ""))
    mark = manifest["logos"].get("mark")
    if mark:
        return f'<img class="sig-mark" src="{mark}" alt="">{handle}'
    return f"<b>&lt;/&gt;</b> {handle}" if handle else ""


def link(path, target):
    if path.is_symlink() or path.exists():
        path.unlink()
    path.symlink_to(target, target_is_directory=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    parser.add_argument("duration", type=float)
    parser.add_argument("--format", choices=FORMATS, default="vertical")
    parser.add_argument("--brand", type=Path, default=None, help="brand kit folder or its brand.json")
    parser.add_argument("--template", default=None, help="theme id from templates/templates.json")
    parser.add_argument("--board", action="store_true", help="write board.html, the kit shown in this theme")
    args = parser.parse_args()

    try:
        kit, root = brand_kit.load(brand_kit.resolve(args.brand))
    except brand_kit.KitError as error:
        print(error.problem, file=sys.stderr)
        print(f"Next: {error.fix}", file=sys.stderr)
        return 1
    kit_assets = brand_kit.installed(kit, root)
    if kit_assets is None:
        print(f"Brand kit {root} is not installed, or changed since it was", file=sys.stderr)
        print(f"Next: bash {SKILL_DIR / 'scripts' / 'setup.sh'} {root}", file=sys.stderr)
        return 1
    manifest = json.loads((kit_assets / "kit.json").read_text(encoding="utf-8"))

    if args.duration <= 0:
        print(f"Duration must be positive, got {args.duration}", file=sys.stderr)
        print("Next: pass the composition length in seconds", file=sys.stderr)
        return 1

    template = resolve_template(args.template)
    if template is None:
        print("No templates found in templates/templates.json", file=sys.stderr)
        print("Next: check that templates/ contains a templates.json manifest", file=sys.stderr)
        return 1

    colors = brand_kit.palette(kit, template.get("scheme"))
    background = manifest["background"]
    geometry = FORMATS[args.format]
    values = {
        "width": geometry["width"],
        "height": geometry["height"],
        "captionTop": geometry["captionTop"],
        "grainWidth": geometry["width"] // 2,
        "grainHeight": geometry["height"] // 2,
        "duration": f"{args.duration:.2f}",
        "brand.tokens": brand_kit.css_tokens(colors),
        "brand.fonts.display": manifest["families"]["display"],
        "brand.fonts.mono": manifest["families"].get("mono", "ui-monospace"),
        "brand.signature": signature(manifest),
        "brand.background": background.get("style", "theme"),
        "brand.backgroundImage": f"url('{background['image']}')" if background.get("image") else "none",
        "brand.json": json.dumps({"name": manifest["name"], "handle": manifest["handle"],
                                  "logos": manifest["logos"], "scheme": colors["scheme"],
                                  "fonts": sorted(set(manifest["families"].values()))}),
    }

    page = "board.html" if args.board else template["file"]
    html = (SKILL_DIR / "templates" / page).read_text(encoding="utf-8")

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
        print(f"{page} has placeholders nothing fills: {', '.join(unfilled)}", file=sys.stderr)
        print("Next: give each one a value in fill_template.py (AGENTS.md invariant 8)", file=sys.stderr)
        return 1

    args.work.mkdir(parents=True, exist_ok=True)
    out = args.work / page.replace(template["file"], "index.html")
    out.write_text(html, encoding="utf-8")
    # The page loads words.js; without a placeholder a preview render fails before captions exist
    captions = args.work / "words.js"
    if not captions.exists():
        captions.write_text("window.PHRASES=[];", encoding="utf-8")
    # speak.py writes speech.js in script mode; a recording has no speakers, so hosts stay idle
    speech = args.work / "speech.js"
    if not speech.exists():
        speech.write_text("window.SPEECH=[];", encoding="utf-8")
    link(args.work / "vendor", SKILL_DIR / "assets")
    # Re-pointed every run, so switching kits in one work dir never renders the old brand
    link(args.work / "kit", kit_assets)

    print(f"{out} · {geometry['width']}x{geometry['height']} · {args.duration:.2f}s · template {template['id']} · kit {manifest['name'] or root}")
    if args.board:
        print(f"Next: node {SKILL_DIR / 'scripts' / 'render.js'} board {out} {args.work / 'board.png'}")
    else:
        print("Next: replace the demo shots between BEGIN/END SHOTS and BEGIN/END TIMELINE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
