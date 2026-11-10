#!/usr/bin/env python3
"""Draws the conceptual framework of Section 2.5 as an input, processing, output flow of the system.
Icons are macOS system symbols rendered by icons/render_icons.swift. Output: word/framework.png."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
W, H = 2400, 3040
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
A = "/System/Library/Fonts/Supplemental/Arial.ttf"
AB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
AI = "/System/Library/Fonts/Supplemental/Arial Italic.ttf"
def f(size, face=A): return ImageFont.truetype(face, size)

BLUE, BLUE_BG, BLUE_LINE = "#1D4ED8", "#EFF6FF", "#93C5FD"
PURPLE, PURPLE_BG, PURPLE_LINE = "#6D28D9", "#F5F3FF", "#C4B5FD"
TEAL = "#0F766E"
GREEN, GREEN_BG, GREEN_LINE = "#15803D", "#F0FDF4", "#86EFAC"
ORANGE = "#C2410C"
GREY, GREY_BG, INK, SOFT = "#64748B", "#F8FAFC", "#0F172A", "#334155"
STAGE = ["#7C3AED", "#6D28D9", "#0F766E", "#5B21B6", "#4C1D95"]

def icon(name, colour, box, size):
    im = Image.open(HERE / "icons" / f"{name}-{colour}.png").convert("RGBA")
    scale = size / max(im.size)
    im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    x, y = box
    img.paste(im, (int(x - im.width / 2), int(y - im.height / 2)), im)

def wrap(text, font, width):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = (line + " " + word).strip()
            if d.textlength(trial, font=font) <= width: line = trial
            else:
                lines.append(line); line = word
        lines.append(line)
    return lines

def text(x, y, words, font, fill=INK, width=None, gap=1.28, anchor="l"):
    lines = wrap(words, font, width) if width else words.split("\n")
    step = int(font.size * gap)
    for i, line in enumerate(lines):
        if anchor == "m": d.text((x, y + i * step), line, font=font, fill=fill, anchor="ma")
        else: d.text((x, y + i * step), line, font=font, fill=fill)
    return y + len(lines) * step

def box(xy, fill, line, radius=28, width=5, dash=False):
    if not dash:
        d.rounded_rectangle(xy, radius=radius, fill=fill, outline=line, width=width); return
    d.rounded_rectangle(xy, radius=radius, fill=fill)
    x0, y0, x1, y1 = xy
    for (a, b, c, e) in ((x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1)):
        length = max(abs(c - a), abs(e - b)); n = int(length // 36)
        for i in range(n + 1):
            t0, t1 = i * 36, min(i * 36 + 20, length)
            if a == c: d.line((a, b + t0, a, b + t1), fill=line, width=width)
            else: d.line((a + t0, b, a + t1, b), fill=line, width=width)

def arrow(points, colour, width=9, head=30, dash=False, both=False):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if dash:
            length = max(abs(x1 - x0), abs(y1 - y0)); n = int(length // 40)
            for i in range(n + 1):
                t0, t1 = i * 40, min(i * 40 + 24, length)
                if x0 == x1:
                    s = 1 if y1 > y0 else -1; d.line((x0, y0 + s * t0, x0, y0 + s * t1), fill=colour, width=width)
                else:
                    s = 1 if x1 > x0 else -1; d.line((x0 + s * t0, y0, x0 + s * t1, y0), fill=colour, width=width)
        else:
            d.line((x0, y0, x1, y1), fill=colour, width=width)
    def tip(p, q):
        (x0, y0), (x1, y1) = p, q
        if x0 == x1:
            s = 1 if y1 > y0 else -1
            d.polygon([(x1, y1 + s * 4), (x1 - head * 0.62, y1 - s * head), (x1 + head * 0.62, y1 - s * head)], fill=colour)
        else:
            s = 1 if x1 > x0 else -1
            d.polygon([(x1 + s * 4, y1), (x1 - s * head, y1 - head * 0.62), (x1 - s * head, y1 + head * 0.62)], fill=colour)
    tip(points[-2], points[-1])
    if both: tip(points[1], points[0])

def pill(x, y, words, colour):
    font = f(46, AB); w = d.textlength(words, font=font) + 64
    d.rounded_rectangle((x, y, x + w, y + 74), radius=37, fill=colour)
    d.text((x + 32, y + 12), words, font=font, fill="white")

# Title
text(W / 2, 34, "Burrow: a memory engine beside a frozen on-device model", f(60, AB), anchor="m")
text(W / 2, 112, "The vault, the index, the engine and the model all run on the person's own device", f(40, AI), fill=SOFT, anchor="m")

# INPUT
pill(60, 190, "1  INPUT", BLUE)
box((60, 286, 1130, 700), BLUE_BG, BLUE_LINE)
icon("person.fill", "1D4ED8", (160, 380), 110); icon("questionmark.bubble.fill", "1D4ED8", (160, 540), 120)
text(250, 318, "The person's question", f(54, AB), fill=BLUE)
text(250, 392, "Knowledge-bound: “What does my note on the budget rule say?”", f(42), width=850)
text(250, 516, "Reasoning-bound: “A shop sells pens at 15 shillings each. How much do 4 pens cost?”", f(42), width=850)

box((1210, 286, 2250, 700), BLUE_BG, BLUE_LINE)
icon("folder.fill", "1D4ED8", (1310, 390), 125); icon("doc.text.fill", "1D4ED8", (1310, 560), 100)
text(1400, 318, "The person's vault", f(54, AB), fill=BLUE)
text(1400, 396, "Markdown notes, documents and linked code folders, with the links the person wrote between them.", f(42), width=830)
text(1400, 572, "Skills: methods kept as notes.", f(42), width=830)

# PROCESSING
pill(60, 790, "2  PROCESSING: the Burrow engine", PURPLE)
box((60, 886, 2250, 2170), PURPLE_BG, PURPLE_LINE, radius=36)
stages = [
    ("Decide", "arrow.triangle.branch", "One search. Is the vault needed? Search it, or follow its links? Which skill fits the question?"),
    ("Fit", "ruler.fill", "The model was measured once. Show it only as many characters as it reads well: the token budget."),
    ("Answer", "text.bubble.fill", "The frozen model answers from the question, the skill and the excerpts, naming a file and line."),
    ("Check", "checkmark.seal", "Was every cited file and line among the excerpts shown? If not, ask once more."),
    ("Learn", "lightbulb.fill", "Propose up to three notes backed by the person's own words. Write only with consent."),
]
rows = []
for i, (name, sym, words) in enumerate(stages):
    y0 = 930 + i * 244
    box((100, y0, 1340, y0 + 214), "white", STAGE[i], radius=24, width=6)
    d.rounded_rectangle((100, y0, 300, y0 + 214), radius=24, fill=STAGE[i])
    d.rectangle((270, y0, 300, y0 + 214), fill=STAGE[i])
    icon(sym, "FFFFFF", (200, y0 + 82), 96)
    d.text((200, y0 + 150), f"Step {i + 1}", font=f(36, AB), fill="white", anchor="ma")
    text(332, y0 + 16, name, f(52, AB), fill=STAGE[i])
    text(332, y0 + 82, words, f(38), width=985, gap=1.22)
    rows.append(y0 + 107)
for a, b in zip(rows, rows[1:]):
    arrow([(720, a + 107), (720, b - 107)], PURPLE, width=8, head=24)

# The frozen model, beside Answer
box((1500, 1140, 2200, 1700), TEAL, TEAL, radius=30)
icon("cpu.fill", "FFFFFF", (1850, 1250), 150)
text(1850, 1350, "Frozen on-device model", f(50, AB), fill="white", anchor="m")
text(1850, 1420, "An open-weight local model,", f(40), fill="white", anchor="m")
text(1850, 1472, "run by a local model service", f(40), fill="white", anchor="m")
icon("lock.fill", "FFFFFF", (1640, 1612), 60)
text(1690, 1586, "Weights never change", f(42, AB), fill="white")
arrow([(1340, rows[2] - 30), (1500, rows[2] - 30)], TEAL, width=9)
arrow([(1500, rows[2] + 40), (1340, rows[2] + 40)], TEAL, width=9)
text(1420, rows[2] - 96, "prompt", f(34, AI), fill=TEAL, anchor="m")
text(1420, rows[2] + 60, "answer", f(34, AI), fill=TEAL, anchor="m")

# The index, beside Decide
box((1500, 930, 2200, 1090), "white", PURPLE_LINE, radius=24)
icon("cylinder.split.1x2.fill", "6D28D9", (1580, 1010), 96)
text(1660, 950, "Rebuildable index", f(42, AB), fill=PURPLE)
text(1660, 1004, "SQLite: words, vectors, links", f(36), fill=SOFT)
arrow([(1340, rows[0]), (1500, rows[0])], PURPLE, width=8, head=24, both=True)

# Laptop note
icon("laptopcomputer", "0F766E", (1590, 1900), 130)
text(1680, 1800, "On the device, no cloud call:", f(40, AB), fill=TEAL)
text(1680, 1856, "The engine reaches only the local model service on the same machine.", f(36), fill=SOFT, width=500)

# OUTPUT
pill(60, 2254, "3  OUTPUT", GREEN)
outs = [
    ("text.bubble.fill", "Answer with its sources", "Each statement names the file and line it came from.",
     "The budget note: “Rent stays under 30%.” (Notes/budget.md, line 4)\nThe pens: “4 × 15 = 60 shillings.”"),
    ("info.circle", "Decision line", "Vault read or left out, the reason, and the skill used.",
     "The budget note: vault searched, close matches.\nThe pens: vault left out, a calculation."),
    ("note.text", "Kept notes", "What the person decided, saved as new Markdown notes.",
     "The budget note: a decision the person agrees to keep.\nThe pens: nothing to keep."),
]
for i, (sym, name, words, example) in enumerate(outs):
    x0 = 60 + i * 740
    box((x0, 2350, x0 + 710, 2770), GREEN_BG, GREEN_LINE)
    icon(sym, "15803D", (x0 + 80, 2428), 92)
    text(x0 + 150, 2386, name, f(46, AB), fill=GREEN)
    y = text(x0 + 36, 2490, words, f(38), width=640, gap=1.22)
    text(x0 + 36, y + 14, example, f(34, AI), fill=SOFT, width=640, gap=1.22)

# Flow arrows between the bands
arrow([(1040, 700), (1040, 886)], BLUE, width=12, head=36)
arrow([(1730, 700), (1730, 886)], BLUE, width=12, head=36)
arrow([(480, 2170), (480, 2350)], GREEN, width=12, head=36)
arrow([(1155, 2170), (1155, 2350)], GREEN, width=12, head=36)
arrow([(1895, 2170), (1895, 2350)], GREEN, width=12, head=36)

# Feedback: kept notes return to the vault
arrow([(2250, 2560), (2340, 2560), (2340, 493), (2250, 493)], ORANGE, width=10, head=34, dash=True)
label = Image.new("RGBA", (1100, 60), (255, 255, 255, 0))
ImageDraw.Draw(label).text((550, 4), "FEEDBACK: kept notes return to the vault", font=f(40, AB), fill=ORANGE, anchor="ma")
label = label.rotate(90, expand=True)
img.paste(label, (2346, 940), label)

# Comparison and measures
box((60, 2840, 1130, 3010), GREY_BG, GREY, dash=True, width=5)
icon("cloud.fill", "64748B", (150, 2925), 110)
text(230, 2862, "Comparison only: cloud model (Claude)", f(40, AB), fill=SOFT)
text(230, 2918, "The same questions, alone and with the same memory. It is not part of the engine.", f(34), fill=SOFT, width=870, gap=1.2)
box((1210, 2840, 2250, 3010), GREY_BG, GREY, width=5)
icon("chart.bar.fill", "334155", (1300, 2925), 100)
text(1380, 2862, "Measured on every answer", f(40, AB), fill=SOFT)
text(1380, 2918, "Right or wrong, share of the gap to the cloud model closed, tokens read, seconds.", f(34), fill=SOFT, width=840, gap=1.2)
arrow([(1130, 2925), (1210, 2925)], GREY, width=8, head=24, dash=False)

(HERE / "word").mkdir(exist_ok=True)
img.save(HERE / "word" / "framework.png", dpi=(380, 380))
print("saved", img.size)
