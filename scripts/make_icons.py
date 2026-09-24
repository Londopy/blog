#!/usr/bin/env python3
"""Generate every icon the site links, from the portfolio's >_ mark.

    python scripts/make_icons.py

Writes into static/:
  favicon.svg                  the mark as vector paths; also the header logo
  safari-pinned-tab.svg        one-color mask for Safari pinned tabs
  favicon.ico                  16, 32 and 48 px
  favicon-16x16.png, favicon-32x32.png
  apple-touch-icon.png         180 px, square (iOS rounds the corners itself)
  android-chrome-192x192.png, android-chrome-512x512.png   (site.webmanifest)

The mark matches public/favicon.svg on londopy.github.io: ">_" in JetBrains
Mono Bold, size 15 at x=5 on baseline 22 of a 32-unit tile. The SVGs trace
the glyphs from the font, so they render the same on machines without it.
Requires Pillow and fontTools.
"""
import os
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

BG, EDGE, GREEN = "#0a0e13", "#1d2632", "#45d483"
MARK = ">_"
SIZE, X, BASELINE = 15, 5, 22      # placement inside the 32-unit tile
S = 16                             # raster master: 32 units -> 512 px

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")


def find_font(candidates):
    for p in candidates:
        if os.path.exists(p):
            return p
    raise SystemExit("no font found among:\n  " + "\n  ".join(candidates))


FONT = find_font([
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
    "C:/Windows/Fonts/JetBrainsMonoNerdFont-Bold.ttf",
    "C:/Windows/Fonts/JetBrainsMono-Bold.ttf",
])
TT = TTFont(FONT)


def trace(pen_factory, size, x, baseline):
    """Draw MARK through fontTools pens, font units -> SVG user units."""
    glyphs, cmap = TT.getGlyphSet(), TT.getBestCmap()
    scale = size / TT["head"].unitsPerEm
    pen = pen_factory(glyphs)
    for ch in MARK:
        name = cmap[ord(ch)]
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        x += TT["hmtx"][name][0] * scale
    return pen


def path_d(size, x, baseline):
    ntos = lambda v: f"{v:.2f}".rstrip("0").rstrip(".")
    return trace(lambda g: SVGPathPen(g, ntos=ntos), size, x, baseline).getCommands()


def svg_icons():
    tile = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">\n'
        '  <rect width="32" height="32" rx="6" fill="{bg}"/>\n'
        '  <rect x="1" y="1" width="30" height="30" rx="5" fill="none" stroke="{edge}" stroke-width="1"/>\n'
        '  <path fill="{fg}" d="{d}"/>\n'
        '</svg>\n'
    ).format(bg=BG, edge=EDGE, fg=GREEN, d=path_d(SIZE, X, BASELINE))
    write("favicon.svg", tile)

    # The mask has no tile behind it, so center the mark and let it fill the box.
    x0, y0, x1, y1 = trace(BoundsPen, SIZE, 0, 0).bounds
    k = 28 / (x1 - x0)
    size = SIZE * k
    x = (32 - (x1 - x0) * k) / 2 - x0 * k
    baseline = (32 - (y1 - y0) * k) / 2 - y0 * k
    write("safari-pinned-tab.svg",
          f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
          f'<path d="{path_d(size, x, baseline)}"/></svg>\n')


def master(rounded):
    img = Image.new("RGBA", (32 * S, 32 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, 32 * S - 1, 32 * S - 1], radius=6 * S, fill=BG)
        # 1-unit stroke centred on the x=1..31 rect spans 0.5..1.5
        d.rounded_rectangle([S // 2, S // 2, 32 * S - S // 2 - 1, 32 * S - S // 2 - 1],
                            radius=int(5.5 * S), outline=EDGE, width=S)
    else:
        d.rectangle([0, 0, 32 * S, 32 * S], fill=BG)
    d.text((X * S, BASELINE * S), MARK, font=ImageFont.truetype(FONT, SIZE * S),
           fill=GREEN, anchor="ls")
    return img


def raster_icons():
    tile = master(rounded=True)
    for px, name in [(16, "favicon-16x16.png"), (32, "favicon-32x32.png"),
                     (192, "android-chrome-192x192.png"), (512, "android-chrome-512x512.png")]:
        save(tile.resize((px, px), Image.Resampling.LANCZOS), name)
    tile.save(os.path.join(STATIC, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("wrote static/favicon.ico")
    square = master(rounded=False).convert("RGB")
    save(square.resize((180, 180), Image.Resampling.LANCZOS), "apple-touch-icon.png")


def write(name, text):
    with open(os.path.join(STATIC, name), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote static/{name}")


def save(img, name):
    img.save(os.path.join(STATIC, name), optimize=True)
    print(f"wrote static/{name}")


if __name__ == "__main__":
    svg_icons()
    raster_icons()
