"""Copy the site's images from the repository into site/assets/, sized for the web.

Run from anywhere:  python3 site/tools/build_assets.py   (needs Pillow and numpy)

- App screenshots (apps/mac/screens/) become WebP at two widths. The tensor panels are also cropped out on their own.
- Thesis charts and diagrams (docs/thesis/) are printed black-on-white. They are turned dark here by flipping each
  pixel's lightness while keeping its hue and saturation (c' = c + 1 - max - min), so cyan stays memory, amber stays
  the model and grey stays the cloud yardstick, then laid on the page's own background colour.
The originals are only read, never changed.
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "site" / "assets"
SCREENS = ROOT / "apps" / "mac" / "screens"
FIGS = ROOT / "docs" / "thesis" / "figures" / "ch5"
DIAGRAMS = ROOT / "docs" / "thesis" / "diagrams"
BG = np.array([0x0B, 0x0D, 0x10], dtype=np.float32) / 255  # --panel in style.css

SHOTS = [
    "weights-camr", "weights-rag", "weights-large", "loading-weights",
    "chat-compare-camr-rag-off", "chat-compare-number-plate", "chat-code-block",
    "chat-shelves", "chat-receipt-photo-recalled", "chat-code-cafe-site",
]
# the tensor panel on the right of the 3200 x 1796 weights captures
CROPS = {"weights-camr": (1620, 0, 3200, 1796), "weights-rag": (1620, 0, 3200, 1796)}
FIG_NAMES = ["longhaul_share", "first_word", "ram", "speed", "media"]
DIAGRAM_NAMES = ["architecture", "sequence_question"]


def save(img: Image.Image, name: str, widths: tuple[int, ...], quality: int = 82) -> None:
    for w in widths:
        im = img if img.width <= w else img.resize((w, round(img.height * w / img.width)), Image.LANCZOS)
        path = OUT / f"{name}-{w}.webp"
        im.save(path, "WEBP", quality=quality, method=6)
        print(f"{path.relative_to(ROOT)}  {im.width}x{im.height}  {path.stat().st_size // 1024} KB")


def dark(img: Image.Image) -> Image.Image:
    c = np.asarray(img.convert("RGB"), dtype=np.float32) / 255
    mx = c.max(axis=2, keepdims=True)
    mn = c.min(axis=2, keepdims=True)
    flipped = np.clip(c + (1 - mx - mn), 0, 1)  # lightness L -> 1 - L, same hue and saturation
    out = BG + flipped * (1 - BG)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in SHOTS:
        img = Image.open(SCREENS / f"{name}.png").convert("RGB")
        save(img, name, (1000, 2000))
        if name in CROPS:
            save(img.crop(CROPS[name]), f"{name}-panel", (800, 1400))
    for name in FIG_NAMES:
        save(dark(Image.open(FIGS / f"{name}.png")), f"fig-{name}", (800, 1500), quality=88)
    for name in DIAGRAM_NAMES:
        save(dark(Image.open(DIAGRAMS / f"{name}.png")), f"diagram-{name}", (900, 1800), quality=86)


if __name__ == "__main__":
    main()
