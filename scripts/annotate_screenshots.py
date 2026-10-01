"""Add numbered "click here" markers to inspector screenshots for the setup guide.

Input screenshots come from scripts/screenshot_inspector.py (1440 px wide).
Each marker is a highlight box around the control plus a numbered badge and a
short instruction, so the README can say "step 2: click the marked radio".
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SRC = Path("docs/figures/inspector")
OUT = Path("docs/figures/setup")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ACCENT = "#eb6834"  # orange from the validated figure palette; stands out on the light UI

# (source image, output name, [(box x0, y0, x1, y1), badge number, label, label position]).
STEPS = {
    "inspector_select_run.png": ("main_1_run_dashboard.png", [
        ((26, 336, 274, 386), 1, "Pick the run (treatment label)", (26, 396)),
        ((26, 206, 160, 228), 2, "Run Dashboard = headline results", (170, 205)),
        ((604, 362, 1196, 404), 3, "Gap closed per task type", (720, 412)),
    ]),
    "inspector_query_trace.png": ("grow-100_3_query_trace.png", [
        ((26, 252, 140, 274), 1, "Click Query Trace", (150, 251)),
        ((376, 198, 1364, 240), 2, "Choose the benchmark run", (900, 160)),
        ((376, 282, 1364, 324), 3, "Choose a question", (900, 330)),
        ((376, 620, 1364, 696), 4, "Admitted notes (what the model read)", (760, 700)),
    ]),
    "inspector_memory_store.png": ("grow-100_4_memory_store.png", [
        ((26, 274, 150, 296), 1, "Click Memory Store", (160, 273)),
    ]),
    "inspector_ablations.png": ("main_2_ablations.png", [
        ((26, 230, 130, 252), 1, "Click Ablations", (140, 229)),
    ]),
}


def badge(d: ImageDraw.ImageDraw, x: int, y: int, n: int, font) -> None:
    d.ellipse([x - 15, y - 15, x + 15, y + 15], fill=ACCENT, outline="white", width=3)
    d.text((x, y), str(n), font=font, fill="white", anchor="mm")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    big, small = ImageFont.truetype(FONT, 18), ImageFont.truetype(FONT, 17)
    for out_name, (src, marks) in STEPS.items():
        img = Image.open(SRC / src).convert("RGB")
        d = ImageDraw.Draw(img)
        for (x0, y0, x1, y1), n, label, (lx, ly) in marks:
            d.rounded_rectangle([x0, y0, x1, y1], radius=6, outline=ACCENT, width=4)
            badge(d, x0 - 2, y0 - 2, n, big)
            tw = d.textlength(label, font=small)
            d.rounded_rectangle([lx, ly, lx + tw + 20, ly + 28], radius=6, fill=ACCENT)
            d.text((lx + 10, ly + 14), label, font=small, fill="white", anchor="lm")
        img.save(OUT / out_name)
        print("wrote", OUT / out_name)


if __name__ == "__main__":
    main()
