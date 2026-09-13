"""
Build every icon size from the artwork in icon_src.png.

The artwork arrives on its own background, so rather than cut the transistor out
(the glow and the circuit traces make a clean matte impossible) it is laid on a
matching navy gradient and shrunk until it sits inside the adaptive icon's safe
circle. Its edges are feathered into that gradient, so there is no visible seam
whatever shape a launcher masks it to.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = "icon_src.png"
NAVY0, NAVY1 = (2, 30, 66), (0, 10, 25)      # sampled from the artwork's own corners


def ground(px):
    y, x = np.mgrid[0:px, 0:px]
    t = ((x + y) / (2.0 * (px - 1)))[..., None]
    g = (np.array(NAVY0) * (1 - t) + np.array(NAVY1) * t).astype(np.uint8)
    return Image.fromarray(g, "RGB").convert("RGBA")


def compose(px, frac, art=None):
    """Artwork centred at `frac` of the canvas, feathered into the ground."""
    art = art or Image.open(SRC).convert("RGBA")
    w = max(1, int(round(px * frac)))
    a = art.resize((w, w), Image.LANCZOS)
    feather = max(2, int(w * 0.10))
    mask = Image.new("L", (w, w), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [feather * 0.6, feather * 0.6, w - feather * 0.6, w - feather * 0.6],
        radius=int(w * 0.12), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather * 0.55))
    a.putalpha(Image.composite(a.getchannel("A"), Image.new("L", (w, w), 0), mask)
               if a.mode == "RGBA" else mask)
    a.putalpha(mask)
    out = ground(px)
    out.alpha_composite(a, ((px - w) // 2, (px - w) // 2))
    return out


if __name__ == "__main__":
    art = Image.open(SRC).convert("RGBA")
    # Android adaptive icon: 108dp canvas. The device fills ~84% of the artwork, so
    # laying the artwork at 78% puts the device at ~66% — inside the safe circle.
    for name, px in {"mdpi": 108, "hdpi": 162, "xhdpi": 216,
                     "xxhdpi": 324, "xxxhdpi": 432}.items():
        d = f"android/app/src/main/res/mipmap-{name}"
        os.makedirs(d, exist_ok=True)
        compose(px, 0.78, art).convert("RGB").save(f"{d}/ic_launcher_background.png")
        print(f"  {d}/ic_launcher_background.png")
    out = {
        "repo/store/icon-512.png":   compose(512, 1.0, art),
        "repo/store/icon-1024.png":  compose(1024, 1.0, art),
        "pwa/icon-192.png":          compose(192, 1.0, art),
        "pwa/icon-512.png":          compose(512, 1.0, art),
        "pwa/apple-touch-icon.png":  compose(180, 1.0, art),
        "pwa/icon-maskable-512.png": compose(512, 0.78, art),
    }
    for path, im in out.items():
        im.convert("RGB").save(path); print(f"  {path:34s} {im.size[0]}px")
