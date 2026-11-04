"""The app icon: the weights view in miniature. Amber columns are the model's layers, and one cyan room glows above
them with its notes coming down. Black, crisp, two meaningful colours. Run once; writes Resources/AppIcon.icns."""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024
AMBER, CYAN = (255, 168, 56), (64, 220, 255)


def icon() -> Image.Image:
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill=255)
    bg = Image.new("RGBA", (S, S), (8, 8, 11, 255))
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g, d = ImageDraw.Draw(glow), ImageDraw.Draw(bg)
    cols, rows, x0, y0, w, h = 9, 7, 210, 470, 604, 360
    cw, ch = w / cols, h / rows
    for i in range(cols):
        for j in range(rows):
            a = 0.25 + 0.75 * (((i * 7 + j * 3) % 5) / 4) * (1 - j / rows * 0.6)
            box = (x0 + i * cw + 6, y0 + j * ch + 6, x0 + (i + 1) * cw - 6, y0 + (j + 1) * ch - 6)
            col = tuple(int(c * a) for c in AMBER) + (255,)
            d.rounded_rectangle(box, radius=8, fill=col)
            if a > 0.7:
                g.rounded_rectangle(box, radius=8, fill=AMBER + (160,))
    room = (462, 210, 562, 290)
    g.rounded_rectangle((room[0] - 18, room[1] - 18, room[2] + 18, room[3] + 18), radius=24, fill=CYAN + (200,))
    for i in range(cols):  # the room's notes, down into every layer
        cx = x0 + (i + 0.5) * cw
        g.line([(512, 290), (cx, y0 - 14)], fill=CYAN + (150,), width=10)
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    bg = Image.alpha_composite(bg, glow)
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle(room, radius=14, fill=CYAN + (255,))
    for i in range(cols):
        d.rectangle((x0 + i * cw + 10, y0 - 22, x0 + (i + 1) * cw - 10, y0 - 14), fill=CYAN + (255,))
    base.paste(bg, (0, 0), mask)
    return base


def main() -> None:
    img = icon()
    out = Path(__file__).parent / "Resources"
    out.mkdir(exist_ok=True)
    img.save(out / "AppIcon.png")
    with tempfile.TemporaryDirectory() as t:
        iconset = Path(t) / "AppIcon.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            img.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
            img.resize((size * 2, size * 2), Image.LANCZOS).save(iconset / f"icon_{size}x{size}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out / "AppIcon.icns")], check=True)


if __name__ == "__main__":
    main()
