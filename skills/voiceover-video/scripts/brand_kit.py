#!/usr/bin/env python3
"""Brand kits: load and validate a kit, derive the colour tokens every theme reads, check contrast,
and install a kit's fonts and logos into its own asset folder.

  brand_kit.py check   [kit] [--scheme dark|light]  validate and print the contrast report
  brand_kit.py install [kit] [--assets DIR]          copy fonts and logos, fetch Google fonts → assets/kits/<id>/

A kit is a folder holding brand.json (version 2) plus the files it names, or a brand.json path.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
FONT_EXTENSIONS = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}
LOGO_EXTENSIONS = {".svg", ".png", ".webp"}
BACKGROUND_STYLES = {"theme", "solid", "glow", "gradient", "grid", "image"}
# A desktop UA makes Google Fonts serve woff2
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
DEFAULT_SUCCESS = "#3ddc84"
DEFAULT_ERROR = "#ff4d4d"


class KitError(Exception):
    """A kit that can't be used; the message names the problem and the fix."""

    def __init__(self, problem, fix):
        super().__init__(problem)
        self.problem = problem
        self.fix = fix


def rgb(color):
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)]


def to_hex(channels):
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in channels)


def mix(color, other, amount):
    return to_hex(a + (b - a) * amount for a, b in zip(rgb(color), rgb(other)))


def luminance(color):
    def linear(channel):
        c = channel / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def is_dark(color):
    return luminance(color) < 0.18


def ink(color, bg, minimum=4.5):
    """The brand colour as text: fills keep the true colour, words get the nearest shade that reads on bg."""
    toward = "#000000" if not is_dark(bg) else "#ffffff"
    for step in range(21):
        candidate = mix(color, toward, step / 20)
        if contrast(candidate, bg) >= minimum:
            return candidate
    return toward


def readable_on(color):
    return "#0b0b0f" if contrast(color, "#0b0b0f") >= contrast(color, "#ffffff") else "#ffffff"


def resolve(explicit=None):
    """The kit to use: an explicit path, ./brand.json, the user's default kit, then the bundled example."""
    candidates = [Path(explicit).expanduser()] if explicit else []
    candidates += [Path("brand.json"), Path.home() / ".config" / "voiceover-video" / "brand.json",
                   SKILL_DIR / "brand.example.json"]
    for candidate in candidates:
        if (candidate / "brand.json" if candidate.is_dir() else candidate).is_file():
            return candidate
    raise KitError("No brand kit found", "run init_kit.py, or pass --brand <kit folder>")


def installed(kit, root, assets=SKILL_DIR / "assets"):
    """The kit's asset folder, if setup.sh installed this exact version of it."""
    target = assets / "kits" / kit_id(kit, root)
    try:
        if json.loads((target / "kit.json").read_text(encoding="utf-8")).get("digest") == digest(kit, root):
            return target
    except (OSError, json.JSONDecodeError):
        pass
    return None


def load(path):
    """Return (kit dict, kit root). Raises KitError with a fix for anything unusable."""
    path = Path(path).expanduser()
    file = path / "brand.json" if path.is_dir() else path
    if not file.is_file():
        raise KitError(f"No brand kit at {path}", "pass a kit folder containing brand.json, or run init_kit.py")
    try:
        kit = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise KitError(f"{file} is not valid JSON ({error})", "fix the JSON, or run init_kit.py to recreate it")
    if kit.get("version") != 2:
        raise KitError(f"{file} is a version-1 brand file", f"convert it: python3 scripts/init_kit.py --from {file}")
    validate(kit, file.parent)
    return kit, file.parent.resolve()


def validate(kit, root):
    colors = kit.get("colors", {})
    for name in ("primary", "bg"):
        if name not in colors:
            raise KitError(f"brand.json has no colors.{name}", f"add colors.{name} as #rrggbb")
    for name, value in colors.items():
        if not HEX.match(str(value)):
            raise KitError(f"colors.{name} must look like #rrggbb, got {value!r}", "use a six-digit hex colour")
    fonts = kit.get("fonts", {})
    if "display" not in fonts:
        raise KitError("brand.json has no fonts.display", 'add {"google": "Family"} or {"file": "fonts/Display.woff2"}')
    for role, font in fonts.items():
        if "file" in font:
            font_file = root / font["file"]
            if not font_file.is_file():
                raise KitError(f"fonts.{role} file {font_file} does not exist", "put the font file in the kit, or name a Google font")
            if font_file.suffix.lower() not in FONT_EXTENSIONS:
                raise KitError(f"fonts.{role} is {font_file.suffix}, not a web font", "use .woff2, .woff, .ttf or .otf")
        elif "google" not in font:
            raise KitError(f"fonts.{role} names no file and no Google family", 'use {"file": …} or {"google": …}')
    for name, logo in flatten_logos(kit.get("logos", {})):
        logo_file = root / logo
        if not logo_file.is_file():
            raise KitError(f"logos.{name} file {logo_file} does not exist", "add the file to the kit or remove the entry")
        if logo_file.suffix.lower() not in LOGO_EXTENSIONS:
            raise KitError(f"logos.{name} is {logo_file.suffix}", "use .svg, .png or .webp")
    background = kit.get("background", {"style": "theme"})
    if background.get("style", "theme") not in BACKGROUND_STYLES:
        raise KitError(f"background.style {background.get('style')!r} is unknown", f"use one of {', '.join(sorted(BACKGROUND_STYLES))}")
    if background.get("style") == "image" and not (root / background.get("image", "")).is_file():
        raise KitError("background.style is image but background.image is missing", "add background.image pointing at a file in the kit")


def flatten_logos(logos, prefix=""):
    for name, value in logos.items():
        if isinstance(value, dict):
            yield from flatten_logos(value, f"{prefix}{name}.")
        else:
            yield f"{prefix}{name}", value


def kit_id(kit, root):
    slug = re.sub(r"[^a-z0-9]+", "-", kit.get("name", "kit").lower()).strip("-") or "kit"
    return f"{slug}-{hashlib.sha1(str(root).encode()).hexdigest()[:8]}"


def palette(kit, scheme=None):
    """Every colour a theme may read, derived from the few the kit names.

    scheme: "dark", "light" or None for the kit's own canvas. A light theme on a dark brand gets
    the kit's bgAlt, or a light canvas tinted with the primary, so the theme keeps its character.
    """
    colors = kit["colors"]
    primary = colors["primary"]
    bg = colors["bg"]
    switched = bool(scheme) and is_dark(bg) != (scheme == "dark")
    if switched:
        bg = colors.get("bgAlt") or (mix("#f7f7f4", primary, 0.04) if scheme == "light" else mix("#0e0f13", primary, 0.06))
    dark = is_dark(bg)
    # The kit's text colour belongs to its own canvas; on the switched canvas it would vanish
    text = colors.get("textAlt" if switched else "text") or ("#eef0f2" if dark else "#14161a")
    lift = "#ffffff" if dark else "#000000"
    secondary = colors.get("secondary") or mix(primary, "#ffffff" if dark else "#000000", 0.35)
    return {
        "scheme": "dark" if dark else "light",
        "primary": primary,
        "primary-ink": ink(primary, bg),
        "secondary": secondary,
        "bg": bg,
        "text": text,
        "muted": mix(text, bg, 0.42),
        "surface1": mix(mix(bg, lift, 0.04), primary, 0.03),
        "surface2": mix(mix(bg, lift, 0.075), primary, 0.045),
        "border": mix(mix(bg, lift, 0.13), primary, 0.08),
        "on-primary": readable_on(primary),
        "success": colors.get("success", DEFAULT_SUCCESS),
        "error": colors.get("error", DEFAULT_ERROR),
        "on-error": readable_on(colors.get("error", DEFAULT_ERROR)),
    }


def css_tokens(colors):
    return ";".join(f"--brand-{name}:{value}" for name, value in colors.items() if name != "scheme")


def contrast_report(colors):
    """(label, ratio, minimum) for the pairs viewers must read; minimums are WCAG AA."""
    return [
        ("body text on background", contrast(colors["text"], colors["bg"]), 4.5),
        ("body text on panels", contrast(colors["text"], colors["surface2"]), 4.5),
        ("muted text on background", contrast(colors["muted"], colors["bg"]), 3.0),
        ("caption word on its highlight", contrast(colors["on-primary"], colors["primary"]), 4.5),
        ("accent-coloured text on background", contrast(colors["primary-ink"], colors["bg"]), 4.5),
    ]


def logo_warnings(kit, colors):
    """A logo that matches the canvas vanishes; flag kits with no variant for the canvas in use."""
    logos = dict(flatten_logos(kit.get("logos", {})))
    if not logos:
        return ["no logos: the end card and corner fall back to the name and handle"]
    wanted = "wordmark.onDark" if colors["scheme"] == "dark" else "wordmark.onLight"
    if wanted not in logos:
        return [f"no logos.{wanted}: check the mark and wordmark are visible on {colors['bg']} in the board"]
    return []


def google_css(family, axes=None):
    """Fetch a family's CSS: the variable axes asked for, else the full weight range, else 400/700."""
    attempts = [axes] if axes else []
    attempts += ["wght@100..900", "wght@400;700", None]
    last_error = ""
    for spec in attempts:
        query = "family=" + urllib.parse.quote(family) + (f":{spec}" if spec else "") + "&display=swap"
        request = urllib.request.Request(f"https://fonts.googleapis.com/css2?{query}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            # 400 means the family exists but not with these axes; try a plainer request
            last_error = f"Google Fonts returned {error.code} for {family!r}"
            if error.code != 400:
                break
        except OSError as error:
            raise KitError(f"could not reach Google Fonts ({error})", "check the connection, or use local font files in the kit")
    raise KitError(last_error, "check the exact family name on fonts.google.com")


def install(kit, root, assets):
    """Copy fonts, logos and background into assets/kits/<id>/ and write fonts.css and kit.json there."""
    existing = installed(kit, root, assets)
    if existing:
        return existing
    target = assets / "kits" / kit_id(kit, root)
    fingerprint = digest(kit, root)
    if target.exists():
        shutil.rmtree(target)
    (target / "fonts").mkdir(parents=True)
    faces = []
    families = {}
    for role, font in kit["fonts"].items():
        if "file" in font:
            source = root / font["file"]
            shutil.copy2(source, target / "fonts" / source.name)
            family = font.get("family", f"Brand {role.title()}")
            weight = font.get("weight", "100 900")
            fmt = FONT_EXTENSIONS[source.suffix.lower()]
            faces.append(f"@font-face{{font-family:'{family}';src:url('fonts/{source.name}') format('{fmt}');"
                         f"font-weight:{weight};font-style:normal;font-display:block}}")
        else:
            family = font["google"]
            css = google_css(family, font.get("axes"))
            for url in sorted(set(re.findall(r"https://fonts\.gstatic\.com[^)]*", css))):
                name = url.removeprefix("https://fonts.gstatic.com/s/").replace("/", "-")
                download(url, target / "fonts" / name)
                css = css.replace(url, f"fonts/{name}")
            faces.append(css)
        families[role] = family
    (target / "fonts.css").write_text("\n".join(faces) + "\n", encoding="utf-8")
    logos = {}
    for name, logo in flatten_logos(kit.get("logos", {})):
        source = root / logo
        destination = target / "logos" / source.name
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(source, destination)
        logos[name] = f"kit/logos/{source.name}"
    background = dict(kit.get("background", {"style": "theme"}))
    if background.get("style") == "image":
        source = root / background["image"]
        shutil.copy2(source, target / source.name)
        background["image"] = f"kit/{source.name}"
    manifest = {"id": target.name, "name": kit.get("name", ""), "handle": kit.get("handle", ""),
                "families": families, "logos": logos, "background": background, "root": str(root),
                "digest": fingerprint}
    (target / "kit.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


def digest(kit, root):
    """Changes whenever brand.json or any file it names changes, so an unchanged kit installs once."""
    sha = hashlib.sha1(json.dumps(kit, sort_keys=True).encode())
    files = [font["file"] for font in kit["fonts"].values() if "file" in font]
    files += [logo for _, logo in flatten_logos(kit.get("logos", {}))]
    files += [kit["background"]["image"]] if kit.get("background", {}).get("style") == "image" else []
    for name in sorted(files):
        sha.update((root / name).read_bytes())
    return sha.hexdigest()


def download(url, destination):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            destination.write_bytes(response.read())
    except OSError as error:
        raise KitError(f"could not download {url} ({error})", "check the connection and re-run setup.sh")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and install voiceover-video brand kits.")
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check", help="validate a kit and print its tokens and contrast report")
    check_parser.add_argument("kit", type=Path, nargs="?", help="kit folder or brand.json (default: resolved like setup.sh)")
    check_parser.add_argument("--scheme", choices=["dark", "light"], help="the canvas a theme asks for")
    install_parser = sub.add_parser("install", help="install a kit's fonts and logos into the skill's assets")
    install_parser.add_argument("kit", type=Path, nargs="?", help="kit folder or brand.json (default: resolved like setup.sh)")
    install_parser.add_argument("--assets", type=Path, default=SKILL_DIR / "assets")
    args = parser.parse_args()

    try:
        kit, root = load(resolve(args.kit))
        if args.command == "install":
            target = install(kit, root, args.assets)
            print(f"{kit.get('name', 'kit')} installed → {target}")
            print("Next: fill_template.py with --brand pointing at this kit")
            return 0
        colors = palette(kit, args.scheme)
        failing = 0
        print(f"{kit.get('name', 'kit')} · {colors['scheme']} · primary {colors['primary']} on {colors['bg']}")
        for warning in logo_warnings(kit, colors):
            print(f"  warning: {warning}")
        for label, ratio, minimum in contrast_report(colors):
            verdict = "ok" if ratio >= minimum else f"BELOW {minimum}:1"
            failing += ratio < minimum
            print(f"  {ratio:5.2f}:1  {label}  {verdict}")
        if failing:
            print(f"{failing} contrast pair(s) below WCAG AA", file=sys.stderr)
            print("Next: darken or lighten colors.primary or colors.text, or set them explicitly in brand.json", file=sys.stderr)
            return 1
        print("Next: render the brand board, then show it for approval")
        return 0
    except KitError as error:
        print(error.problem, file=sys.stderr)
        print(f"Next: {error.fix}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
