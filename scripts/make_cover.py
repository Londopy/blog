#!/usr/bin/env python3
"""Generate social cards (1200x630) as terminal-window cards.

Same look as the Open Graph cards on londopy.github.io, so a shared post and
a shared project read as one site.

    python scripts/make_cover.py --all
    python scripts/make_cover.py content/posts/<slug>
    python scripts/make_cover.py --site

A post card is written to the bundle as cover.png. Its title and tags come
from the post's front matter. The terminal above the title shows the post's
lines from scripts/covers.json ("$ " lines are commands, the rest output),
or, for a post with no entry there, `cat <slug>.md` and the description.

--site writes static/og-image.png, the card for every page without a cover
(home, about, contact, search, archive, tags). --all writes every post card
and the site card.

Requires Pillow. Strip metadata before committing anyway:
    exiftool -all= -overwrite_original content/posts/<slug>/cover.png
"""
import argparse
import json
import os
import re
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = "#0a0e13"
PANEL = "#0f141b"
TITLEBAR = "#151c25"
BORDER = "#2c3947"
GRID = "#131a23"
TEXT = "#cdd8e3"
DIM = "#8494a6"
FAINT = "#56677a"
ACCENT = "#e9a13a"
AMBER = "#e8b444"
RED = "#e8564f"
NEUTRAL = "#3a4a5a"

PX, PY, PW, PH = 80, 82, 1040, 466
LEFT = 130
MAX_W = PW - 120
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSTS = os.path.join(ROOT, "content", "posts")
MANIFEST = os.path.join(ROOT, "scripts", "covers.json")
PROMPT = [("londopy", ACCENT), ("@", FAINT), ("github", TEXT), (":~$", FAINT)]
MAX_LINES = 5   # prompt + 4; more would push the tags out of the window


def find_font(candidates):
    for p in candidates:
        if os.path.exists(p):
            return p
    raise SystemExit("no font found among:\n  " + "\n  ".join(candidates))


MONO = find_font([
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
    "C:/Windows/Fonts/JetBrainsMonoNerdFont-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/DejaVuSansMono.ttf",
])
MONO_B = find_font([
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
    "C:/Windows/Fonts/JetBrainsMonoNerdFont-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    "C:/Windows/Fonts/DejaVuSansMono-Bold.ttf",
])
SANS = find_font([
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
])


def front_matter(md):
    """Pull title, description and tags out of simple YAML front matter."""
    m = re.match(r"---\n(.*?)\n---\n", md, re.S)
    if not m:
        raise SystemExit("no YAML front matter found")
    fm = m.group(1)

    def scalar(key):
        v = re.search(rf"^{key}:\s*(.*)$", fm, re.M)
        return v.group(1).strip().strip("\"'") if v else ""

    tags = re.search(r"^tags:\s*\[(.*)\]", fm, re.M)
    tags = [t.strip().strip("\"'") for t in tags.group(1).split(",")] if tags else []
    return scalar("title"), scalar("description"), [t for t in tags if t]


def base_card():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=GRID, width=1)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=GRID, width=1)
    d.rounded_rectangle([PX, PY, PX + PW, PY + PH], radius=12,
                        fill=PANEL, outline=BORDER, width=2)
    d.rounded_rectangle([PX + 2, PY + 2, PX + PW - 2, PY + 46], radius=10, fill=TITLEBAR)
    d.rectangle([PX + 2, PY + 30, PX + PW - 2, PY + 46], fill=TITLEBAR)
    for i, c in enumerate([RED, AMBER, NEUTRAL]):
        cx = PX + 32 + i * 24
        d.ellipse([cx - 7, PY + 17, cx + 7, PY + 31], fill=c)

    ft = ImageFont.truetype(MONO, 16)
    bar = "londopy@github: ~/blog"
    d.text((PX + PW / 2 - d.textlength(bar, ft) / 2, PY + 15), bar, font=ft, fill=FAINT)
    fu = ImageFont.truetype(MONO, 22)
    u = "londopy.github.io/blog"
    d.text((W / 2 - d.textlength(u, fu) / 2, 582), u, font=fu, fill=ACCENT)
    return img, d


def segments(d, x, y, parts, font):
    for text, color in parts:
        d.text((x, y), text, font=font, fill=color)
        x += d.textlength(text, font)


def wrap(d, text, font, max_w, max_lines):
    """Word-wrap into at most max_lines; ellipsize if text was dropped."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(" ".join(lines)) < len(text):
        last = lines[-1] if lines else ""
        while last and d.textlength(last + " …", font) > max_w:
            last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
        lines[-1] = last + " …"
    return lines[:max_lines]


def gitattributes_parts(line):
    """Color one .gitattributes line: pattern, then attributes."""
    if line.lstrip().startswith("#"):
        return [(line, FAINT)]
    parts, first = [], True
    for tok in re.findall(r"\s+|\S+", line):
        if tok.isspace():
            parts.append((tok, TEXT))
        elif first:
            first = False
            parts.append((tok, TEXT))
        elif tok[0] in "-!":
            parts += [(tok[0], FAINT), (tok[1:], ACCENT)]
        elif "=" in tok:
            k, v = tok.split("=", 1)
            parts += [(k, ACCENT), ("=", FAINT), (v, DIM)]
        else:
            parts.append((tok, ACCENT))
    return parts


def yaml_parts(line):
    """Color one YAML line: keys, then plain or quoted values."""
    m = re.match(r"^(\s*)(- )?([\w-]+)(:)(.*)$", line)
    if not m:
        return [(line, TEXT)]
    indent, dash, key, colon, rest = m.groups()
    value = DIM if rest.strip().startswith(('"', "'")) else TEXT
    return [p for p in [(indent, TEXT), (dash or "", FAINT), (key, ACCENT),
                        (colon, FAINT), (rest, value)] if p[0]]


def output_parts(line, cat):
    """Color a line of command output; `cat` is the file the last command printed."""
    if cat.endswith(".gitattributes"):
        return gitattributes_parts(line)
    if cat.endswith((".yml", ".yaml")):
        return yaml_parts(line)
    parts, pos = [], 0
    for m in re.finditer(r"\b[0-9a-f]{7,40}\b|\[[^\]]*\]", line):   # hashes, [branch]
        parts += [(line[pos:m.start()], TEXT),
                  (m.group(), DIM if m.group().startswith("[") else ACCENT)]
        pos = m.end()
    parts.append((line[pos:], TEXT))
    return [p for p in parts if p[0]]


def terminal(d, lines, slug):
    """Draw terminal lines under the title bar and return the y below them."""
    if len(lines) > MAX_LINES:
        raise SystemExit(f"{slug}: {len(lines)} cover lines, the card fits {MAX_LINES}")
    fp = ImageFont.truetype(MONO, 22)
    y, cat = 158, ""
    for i, line in enumerate(lines):
        if line.startswith("$ "):
            cmd = line[2:]
            parts = PROMPT + [(f"  {cmd}", DIM)]
            cat = cmd[4:] if cmd.startswith("cat ") else ""
        else:
            parts = output_parts(line, cat)
        if LEFT + sum(d.textlength(t, fp) for t, _ in parts) > PX + PW - 40:
            raise SystemExit(f"{slug}: cover line too wide for the card: {line!r}")
        segments(d, LEFT, y, parts, fp)
        y = 200 if i == 0 else y + 34
    return y


def cover(post_dir, lines):
    md = open(os.path.join(post_dir, "index.md"), encoding="utf-8").read().replace("\r\n", "\n")
    title, description, tags = front_matter(md)
    slug = os.path.basename(os.path.normpath(post_dir))

    img, d = base_card()
    if lines:
        y = terminal(d, lines, slug)
    else:
        y = terminal(d, [f"$ cat {slug}.md"], slug)
        fd = ImageFont.truetype(SANS, 24)
        for line in wrap(d, description, fd, MAX_W, 3):
            d.text((LEFT + 2, y), line, font=fd, fill=DIM)
            y += 36

    # title: largest size that fits in two lines without dropping words
    for size in range(52, 34, -2):
        fn = ImageFont.truetype(MONO_B, size)
        lines = wrap(d, title, fn, MAX_W, 2)
        if " ".join(lines) == title:
            break
    y += 22
    for line in lines:
        d.text((LEFT - 4, y), line, font=fn, fill=TEXT)
        y += size + 12

    if tags:
        fg = ImageFont.truetype(MONO, 20)
        x = LEFT
        for t in tags:
            w = d.textlength(f"#{t}", fg)
            if x + w > PX + PW - 40:
                break
            segments(d, x, y + 14, [("#", ACCENT), (t, FAINT)], fg)
            x += w + 26

    out = os.path.join(post_dir, "cover.png")
    img.save(out, optimize=True)
    print(f"wrote {out}")


def site_card():
    """The card for pages without a cover: the blog's own title card."""
    img, d = base_card()
    segments(d, LEFT, 172, PROMPT + [("  ls ~/blog/posts", DIM)], ImageFont.truetype(MONO, 24))

    segments(d, LEFT - 4, 218, [("Londopy", TEXT), ("/blog", ACCENT)],
             ImageFont.truetype(MONO_B, 58))

    fs = ImageFont.truetype(SANS, 29)
    segments(d, LEFT, 312, [
        ("Notes on ", DIM), ("security", ACCENT), (", ", DIM),
        ("systems", ACCENT), (", ", DIM), ("radio", ACCENT), (",", DIM),
    ], fs)
    segments(d, LEFT, 352, [("and ", DIM), ("building things", ACCENT), (".", DIM)], fs)

    segments(d, LEFT + 2, 440, [
        ("posts publish here first · full-text RSS ", FAINT), ("▌", ACCENT),
    ], ImageFont.truetype(MONO, 19))

    out = os.path.join(ROOT, "static", "og-image.png")
    img.save(out, optimize=True)
    print(f"wrote {out}")


def manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Render social cards")
    ap.add_argument("post_dir", nargs="?", help="page bundle, e.g. content/posts/<slug>")
    ap.add_argument("--site", action="store_true",
                    help="write static/og-image.png instead of a post cover")
    ap.add_argument("--all", action="store_true",
                    help="write every post cover and the site card")
    a = ap.parse_args()
    if a.all:
        covers = manifest()
        for slug in sorted(os.listdir(POSTS)):
            if os.path.exists(os.path.join(POSTS, slug, "index.md")):
                cover(os.path.join(POSTS, slug), covers.get(slug))
        site_card()
    elif a.site:
        site_card()
    elif a.post_dir:
        slug = os.path.basename(os.path.normpath(a.post_dir))
        cover(a.post_dir, manifest().get(slug))
    else:
        ap.error("give a post directory, --site or --all")
