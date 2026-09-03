"""Draw the home-screen icons into site/ (run once; the PNGs are committed).

    python scripts/make_icons.py

Dark green tile, a big amber "26", a coral dot for tonight's bed. Everything
sits inside the central 80% so the maskable variant survives Android's crop.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
FONTS = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]


def font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def icon(px: int) -> Image.Image:
    s = px / 512
    im = Image.new("RGBA", (px, px), (12, 22, 20, 255))
    d = ImageDraw.Draw(im)
    # a soft lighter panel behind the number
    d.rounded_rectangle([64 * s, 64 * s, px - 64 * s, px - 64 * s], radius=64 * s, fill=(19, 38, 34, 255),
                        outline=(63, 180, 166, 90), width=max(1, int(3 * s)))
    f = font(int(250 * s))
    text = "26"
    box = d.textbbox((0, 0), text, font=f, anchor="ls")
    w = box[2] - box[0]
    x = (px - w) / 2 - box[0]
    y = px / 2 + 92 * s
    d.text((x, y), text, font=f, fill=(242, 179, 61, 255), anchor="ls")
    # tonight's bed: the coral dot over the "2"
    r = 22 * s
    cx, cy = px / 2 - 62 * s, px / 2 - 118 * s
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(232, 100, 58, 255), outline=(255, 255, 255, 230), width=max(1, int(6 * s)))
    return im


for px in (180, 192, 512):
    out = SITE / f"icon-{px}.png"
    icon(px).save(out, optimize=True)
    print(f"wrote {out.relative_to(ROOT)}")
