"""Draw the FET Lab mark: three channel sheets through one gate."""
from PIL import Image, ImageDraw

BG, GATE, SHEET = (13, 16, 21), (79, 199, 216), (244, 239, 230)

def icon(px, bg=True, safe=1.0):
    """safe<1 shrinks the mark inside the canvas, for maskable icons."""
    s = px / 108.0
    im = Image.new("RGBA", (px, px), BG + (255,) if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    def rr(x0, y0, x1, y1, r, fill):
        c = 54.0
        x0, x1 = c + (x0 - c) * safe, c + (x1 - c) * safe
        y0, y1 = c + (y0 - c) * safe, c + (y1 - c) * safe
        d.rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=r * s * safe, fill=fill)
    rr(46, 26, 62, 82, 8, GATE)                       # gate, behind
    for y in (34, 50, 66):                            # three sheets, in front
        rr(36, y, 72, y + 8, 4, SHEET)
    return im

if __name__ == "__main__":
    out = {
        "repo/store/icon-512.png":            icon(512),
        "repo/store/icon-1024.png":           icon(1024),
        "pwa/icon-192.png":                   icon(192),
        "pwa/icon-512.png":                   icon(512),
        "pwa/apple-touch-icon.png":           icon(180),
        "pwa/icon-maskable-512.png":          icon(512, safe=0.72),   # room for the mask
    }
    for path, im in out.items():
        im.save(path); print(f"  {path:34s} {im.size[0]}px")
