"""The files of Mama Njeri's Kitchen: PDFs, photos, charts and short videos, each with facts planted in it and the
questions that ask for them, graded by the Long Haul's rules (camr_engine.bench.haul.grade).

The people, suppliers and branches are the Long Haul's own world for the same seed (``world.build_world``), so the
files belong to the same project as the history they are told among. What a file states (a total, a price, a time,
a password) is never stated anywhere in the Long Haul.

| Kind | Files | What is planted |
| --- | --- | --- |
| pdf | 3 invoices, a catering menu of 3 pages, a delivery schedule | totals, unit prices, per-guest prices, a time |
| image | 4 receipts and 4 notices, photographed: turned, blurred and grainy | totals, an M-Pesa code, times, a day, a password |
| chart | 5 charts (bars, a line, a pie) | a bar's value, a point's value, a slice's share, the top bar |
| video | 3 videos of a whiteboard, 12 s each, three boards in turn | prices, times and counts written on the middle and last boards |

Never-said questions ask about the same kinds of thing where the file never says it (a supplier that sent no
invoice, a branch the chart leaves out, a drink not on the board): declining is right.

``build(seed, out)`` writes the files under ``out/files/`` and returns the manifest: each file with its kind, the
questions, and for each question the file it is about (a never-said question names the nearest file, for the
contender that is given the file).
"""

from __future__ import annotations

import datetime as dt
import random
import string
from dataclasses import dataclass, field
from pathlib import Path

from camr_engine.bench.haul.words import BRANCHES, SUPPLY_ITEMS, TOWNS
from camr_engine.bench.haul.world import build_world

KINDS = ("pdf", "image", "chart", "video", "never")
FONTS = {"mono": ["/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Courier.ttc"],
         "sans": ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Avenir.ttc"],
         "marker": ["/System/Library/Fonts/MarkerFelt.ttc", "/System/Library/Fonts/Supplemental/Chalkboard.ttc",
                    "/System/Library/Fonts/Noteworthy.ttc"]}
PACKAGES = ["Harusi Gold", "Baraza Classic", "Sherehe Plus", "Jioni Light", "Mavuno Feast"]
EXTRAS = ["a chocolate fountain", "a juice bar", "a nyama choma station", "a coffee cart", "a cake table",
          "waiter service", "a mandazi station"]
DRINKS = ["passion juice", "tamarind juice", "dawa", "mango juice", "chai masala", "ginger tea", "lemonade"]
CHANNELS = ["M-Pesa online", "walk-in cash", "WhatsApp orders", "corporate accounts"]
CHART_DISHES = ["pilau", "biryani", "chapati rolls", "beef samosa", "mukimo", "chicken curry", "githeri"]
ZONES = ["Zone A", "Zone B", "Zone C", "Zone D", "Zone E"]
WIFI_WORDS = ["chapati", "sukuma", "mandazi", "githeri", "pilau", "uji"]
VIDEO_SECONDS, VIDEO_FPS, BOARD_SECONDS = 12, 4, 4  # three boards of 4 s each


@dataclass
class Spec:
    """One file to make, and its questions."""

    name: str
    kind: str  # pdf, image, chart or video (the question family)
    what: str  # what it is, for a person
    draw: dict  # what the renderer draws
    questions: list[dict] = field(default_factory=list)


def font(kind: str, size: int, bold: bool = False):
    from PIL import ImageFont

    for path in FONTS[kind]:
        try:
            return ImageFont.truetype(path, size, index=1 if bold and path.endswith(".ttc") else 0)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _q(qid: str, family: str, ask: str, accept: list[str], others: list[str] = (), file: str | None = None,
       where: str = "") -> dict:
    grader = {"type": "never"} if family == "never" else {"type": "exact", "accept": list(accept),
                                                            "others": [o for o in others if o not in accept]}
    return {"id": qid, "family": family, "ask": ask, "answer": accept[0] if accept else "I don't know",
            "grader": grader, "file": file, "where": where}


def _money(n: int) -> str:
    return f"{n:,}"


def _code(rng: random.Random) -> str:
    """An M-Pesa reference: ten capitals and digits, starting with a letter, with no O or 0 to misread."""
    pool = [c for c in string.ascii_uppercase + string.digits if c not in "O0I1"]
    return "Q" + "".join(rng.choice(pool) for _ in range(9))


def specs(seed: int, dates: list[dt.date]) -> list[Spec]:
    """Every file for ``seed``, with its questions. ``dates`` are the days the files can be dated by."""
    rng = random.Random(f"{seed}:files")
    world = build_world(random.Random(f"{seed}:world"))
    suppliers = world.suppliers[:] + world.hop_suppliers[:]
    rng.shuffle(suppliers)
    staff = [p.first for p in world.staff]
    branches = BRANCHES[:]
    rng.shuffle(branches)
    out: list[Spec] = []
    never: list[dict] = []

    def date() -> dt.date:
        return rng.choice(dates[:40])

    # -- PDFs: three invoices, the catering menu, the delivery schedule
    items = SUPPLY_ITEMS[:]
    rng.shuffle(items)
    for k in range(3):
        sup, branch = suppliers.pop(), branches[k]
        lines = []
        for item in items[k * 4:k * 4 + rng.choice([3, 4])]:
            qty, price = rng.choice([5, 8, 10, 12, 20, 25, 40]), rng.randrange(60, 900, 5)
            lines.append((item, qty, price, qty * price))
        sub = sum(x[3] for x in lines)
        vat = round(sub * 0.16)
        total = sub + vat
        name = f"invoice-{sup.split()[0].lower()}-{k + 1}.pdf"
        s = Spec(name, "pdf", f"an invoice from {sup}", {"form": "invoice", "supplier": sup, "town": rng.choice(TOWNS),
                                                         "number": f"INV-{rng.randint(2100, 9899)}",
                                                         "date": date().isoformat(), "branch": branch,
                                                         "lines": lines, "subtotal": sub, "vat": vat,
                                                         "total": total})
        s.questions.append(_q(f"pdf-invoice-{k + 1}-total", "pdf",
                              f"What was the total, VAT included, on the invoice {sup} sent us, in shillings?",
                              [str(total)], [str(sub), str(vat)] + [str(x[3]) for x in lines], name, "page 1"))
        if k == 0:
            item, _, price, _ = lines[1]
            s.questions.append(_q("pdf-invoice-1-price", "pdf",
                                  f"On the invoice from {sup}, what was the unit price of {item}, in shillings?",
                                  [str(price)], [str(x[2]) for x in lines] + [str(x[3]) for x in lines], name,
                                  "page 1"))
            never.append(_q("never-invoice-item", "never",
                            f"On the invoice from {sup}, what was the unit price of {items[20]}, in shillings?",
                            [], file=name))
        out.append(s)
    unused = [suppliers.pop(), suppliers.pop()]  # suppliers that sent nothing
    never.append(_q("never-invoice-supplier", "never",
                    f"What was the total, VAT included, on the invoice {unused[0]} sent us, in shillings?", [],
                    file=out[0].name))

    packages = rng.sample(PACKAGES, 4)
    prices = rng.sample(range(950, 3400, 50), 4)
    extras = rng.sample(EXTRAS, 5)
    extra_prices = rng.sample(range(4000, 36000, 500), 5)
    minimum = rng.choice([30, 35, 40, 45, 60])
    s = Spec("catering-menu-2025.pdf", "pdf", "the catering menu, three pages",
             {"form": "menu", "packages": list(zip(packages, prices)), "extras": list(zip(extras, extra_prices)),
              "minimum": minimum, "notice_days": rng.choice([5, 7, 10])})
    s.questions += [
        _q("pdf-menu-package", "pdf", f"On the catering menu PDF, how much per guest is the {packages[1]} package, "
           "in shillings?", [str(prices[1])], [str(p) for p in prices], s.name, "page 1"),
        _q("pdf-menu-extra", "pdf", f"On the catering menu PDF, how much does {extras[2]} cost, in shillings?",
           [str(extra_prices[2])], [str(p) for p in extra_prices], s.name, "page 2"),
        _q("pdf-menu-minimum", "pdf", "What is the smallest number of guests the catering menu PDF takes a booking "
           "for?", [str(minimum)], [], s.name, "page 3")]
    never.append(_q("never-menu-package", "never", f"On the catering menu PDF, how much per guest is the "
                    f"{[p for p in PACKAGES if p not in packages][0]} package, in shillings?", [], file=s.name))
    out.append(s)

    rows = []
    for sup in suppliers[-5:]:
        h, m = rng.choice([5, 6, 7, 8, 9, 10]), rng.choice([0, 15, 30, 45])
        rows.append((sup, rng.choice(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]), f"{h}:{m:02d} am",
                     rng.choice(branches[:6])))
    s = Spec("delivery-schedule.pdf", "pdf", "the suppliers' delivery schedule", {"form": "schedule", "rows": rows})
    sup, day_, time_, branch = rows[2]
    s.questions.append(_q("pdf-schedule-time", "pdf", f"According to the delivery schedule PDF, at what time does "
                          f"{sup} deliver?", [time_], [r[2] for r in rows], s.name, "page 1"))
    out.append(s)
    del suppliers[-5:]

    # -- photos: receipts and notices
    for k in range(4):
        sup = suppliers.pop()
        lines = [(it, rng.choice([1, 2, 3, 5, 10]), rng.randrange(40, 1500, 10)) for it in rng.sample(items[12:], 3)]
        total = sum(q * p for _, q, p in lines)
        code = _code(rng)
        name = f"receipt-{k + 1}.jpg"
        s = Spec(name, "image", f"a photo of a receipt from {sup}",
                 {"form": "receipt", "shop": sup, "town": rng.choice(TOWNS), "number": f"{rng.randint(10000, 99999)}",
                  "date": date().isoformat(), "lines": lines, "total": total, "code": code,
                  "served": rng.choice(staff), "angle": rng.uniform(-9, 9), "blur": rng.uniform(0.6, 1.2),
                  "seed": rng.randrange(1 << 30)})
        s.questions.append(_q(f"image-receipt-{k + 1}-total", "image",
                              f"What was the total on the receipt from {sup}, in shillings?", [str(total)],
                              [str(q * p) for _, q, p in lines] + [str(p) for _, _, p in lines], name))
        if k == 1:
            s.questions.append(_q("image-receipt-2-code", "image",
                                  f"What was the M-Pesa reference on the receipt from {sup}?", [code], [], name))
        out.append(s)
    never.append(_q("never-receipt", "never", f"What was the total on the receipt from {unused[1]}, in "
                    "shillings?", [], file="receipt-1.jpg"))

    meet_branch, other_branch = branches[0], branches[7]
    hh, mm = rng.choice([2, 3, 4, 5]), rng.choice([0, 15, 30, 45])
    fum = dates[rng.randrange(45, 70)]
    fum_day = fum + dt.timedelta(days=(5 - fum.weekday()) % 7)  # the Saturday after
    gas_day = rng.choice(["Monday", "Tuesday", "Wednesday", "Thursday"])
    word = f"{rng.choice(WIFI_WORDS)}{rng.randint(20, 99)}"
    notices = [
        ("notice-meeting.jpg", f"STAFF MEETING", [f"All {meet_branch} staff:", f"Thursday at {hh}:{mm:02d} pm",
                                                  "in the dining room.", "Bring your rota questions."],
         _q("image-notice-meeting", "image", f"At what time is the {meet_branch} staff meeting on the notice?",
            [f"{hh}:{mm:02d} pm"], [], "notice-meeting.jpg")),
        ("notice-fumigation.jpg", "FUMIGATION", [f"The {branches[1]} kitchen closes", f"on Saturday {fum_day.day} "
                                                 f"{fum_day:%B}", "for fumigation.", "No orders that day."],
         _q("image-notice-fumigation", "image", f"On which date does the {branches[1]} kitchen close for "
            "fumigation, according to the notice?", [f"{fum_day.day} {fum_day:%B}", f"{fum_day:%B} {fum_day.day}"],
            [], "notice-fumigation.jpg")),
        ("notice-gas.jpg", "GAS DELIVERIES", ["From next week the LPG gas", f"cylinders come every {gas_day}.",
                                              "Keep the cage clear."],
         _q("image-notice-gas", "image", "On which day of the week do the LPG gas cylinders come now, by the "
            "notice?", [gas_day], ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "notice-gas.jpg")),
        ("notice-wifi.jpg", "STAFF WI-FI", ["Network: MNK-Staff", f"Password: {word}", "Do not share with guests."],
         _q("image-notice-wifi", "image", "What is the staff Wi-Fi password on the notice?", [word], [],
            "notice-wifi.jpg")),
    ]
    for name, title, body, q in notices:
        out.append(Spec(name, "image", f"a photo of a notice: {title.lower()}",
                        {"form": "notice", "title": title, "body": body, "angle": rng.uniform(-7, 7),
                         "blur": rng.uniform(0.5, 1.1), "seed": rng.randrange(1 << 30)}, [q]))
    never.append(_q("never-notice-meeting", "never", f"At what time is the {other_branch} staff meeting on the "
                    "notice?", [], file="notice-meeting.jpg"))

    # -- charts
    month = rng.choice(["January", "February", "March"])
    cb = rng.sample(BRANCHES, 6)
    kg = rng.sample(range(180, 960, 5), 5)
    left_out = cb[5]
    s = Spec("chart-charcoal.png", "chart", "a bar chart of charcoal used per branch",
             {"form": "bars", "title": f"Charcoal used per branch, {month} (kg)", "labels": cb[:5], "values": kg,
              "ylabel": "kg"})
    s.questions.append(_q("chart-charcoal", "chart", f"In the chart of charcoal used per branch, how many kilograms "
                          f"did {cb[2]} use?", [str(kg[2])], [str(v) for v in kg], s.name))
    out.append(s)
    never.append(_q("never-chart-branch", "never", f"In the chart of charcoal used per branch, how many kilograms "
                    f"did {left_out} use?", [], file=s.name))
    weeks = [rng.randrange(8, 60) for _ in range(8)]
    wk = rng.randrange(2, 7)
    s = Spec("chart-catering-orders.png", "chart", "a line chart of catering orders per week",
             {"form": "line", "title": "Catering orders per week", "labels": [f"Week {i + 1}" for i in range(8)],
              "values": weeks, "ylabel": "orders"})
    s.questions.append(_q("chart-catering-week", "chart", f"In the chart of catering orders per week, how many "
                          f"orders were there in week {wk + 1}?", [str(weeks[wk])],
                          [str(v) for i, v in enumerate(weeks) if i != wk], s.name))
    out.append(s)
    shares = _shares(rng, len(CHANNELS))
    ch = rng.randrange(len(CHANNELS))
    s = Spec("chart-sales-channels.png", "chart", "a pie chart of sales by channel",
             {"form": "pie", "title": f"Sales by channel, {month}", "labels": CHANNELS, "values": shares})
    s.questions.append(_q("chart-sales-share", "chart", f"In the pie chart of sales by channel, what share of sales "
                          f"came through {CHANNELS[ch]}, in percent?", [str(shares[ch])],
                          [str(v) for v in shares], s.name))
    out.append(s)
    dishes = rng.sample(CHART_DISHES, 6)
    counts = sorted(rng.sample(range(40, 420, 3), 6), reverse=True)
    s = Spec("chart-top-dishes.png", "chart", "a bar chart of the most ordered dishes",
             {"form": "hbars", "title": f"Most ordered dishes, {month}", "labels": dishes, "values": counts,
              "ylabel": "orders"})
    s.questions += [_q("chart-top-dish", "chart", "Which dish was ordered most in the chart of the most ordered "
                       "dishes?", [dishes[0]], dishes[1:], s.name),
                    _q("chart-dish-count", "chart", f"In the chart of the most ordered dishes, how many orders did "
                       f"{dishes[3]} have?", [str(counts[3])], [str(c) for c in counts], s.name)]
    out.append(s)
    mins = rng.sample(range(18, 75), 5)
    z = rng.randrange(5)
    s = Spec("chart-delivery-times.png", "chart", "a bar chart of average delivery time by zone",
             {"form": "bars", "title": "Average delivery time by zone (minutes)", "labels": ZONES, "values": mins,
              "ylabel": "minutes"})
    s.questions.append(_q("chart-delivery-zone", "chart", f"In the chart of average delivery time by zone, how many "
                          f"minutes does {ZONES[z]} take?", [str(mins[z])], [str(v) for v in mins], s.name))
    out.append(s)

    # -- videos of a whiteboard
    drinks = rng.sample(DRINKS, 4)
    dprices = rng.sample(range(80, 400, 10), 3)
    s = Spec("video-drinks-board.mp4", "video", "a video of the kitchen whiteboard: the event drinks",
             {"form": "video", "seed": rng.randrange(1 << 30), "boards": [
                 ["Mama Njeri's Kitchen", f"{branches[2]} kitchen", "Events this week"],
                 ["EVENT DRINKS (per glass)"] + [f"{d.capitalize()} - {p}" for d, p in zip(drinks, dprices)],
                 ["Remember:", "Wash the jugs", "Ice from the big freezer"]]})
    s.questions += [_q("video-drink-1", "video", f"On the whiteboard in the video, how much was a glass of "
                       f"{drinks[0]} for events, in shillings?", [str(dprices[0])], [str(p) for p in dprices], s.name,
                       "0:04"),
                    _q("video-drink-2", "video", f"On the whiteboard in the video, how much was a glass of "
                       f"{drinks[2]} for events, in shillings?", [str(dprices[2])], [str(p) for p in dprices], s.name,
                       "0:04")]
    never.append(_q("never-video-drink", "never", f"On the whiteboard in the video, how much was a glass of "
                    f"{drinks[3]} for events, in shillings?", [], file=s.name))
    out.append(s)
    rh, rm = rng.choice([5, 6, 7]), rng.choice([15, 30, 45])
    th = rng.choice([10, 11, 12])
    s = Spec("video-rider-board.mp4", "video", "a video of the riders' whiteboard",
             {"form": "video", "seed": rng.randrange(1 << 30), "boards": [
                 ["RIDERS", f"{branches[3]} branch", "This week"],
                 ["Morning shift", f"starts at {rh}:{rm:02d} am", "Helmets on!"],
                 ["Saturday", f"tasting at {th}:00", "for the new menu"]]})
    s.questions += [_q("video-rider-shift", "video", "In the video of the riders' whiteboard, at what time does the "
                       "morning shift start?", [f"{rh}:{rm:02d} am"], [f"{th}:00"], s.name, "0:04"),
                    _q("video-tasting", "video", "In the video of the riders' whiteboard, at what time is the "
                       "Saturday tasting?", [f"{th}:00"], [f"{rh}:{rm:02d}"], s.name, "0:08")]
    out.append(s)
    cyl, trays = rng.randrange(3, 15), rng.randrange(16, 60)
    s = Spec("video-stock-board.mp4", "video", "a video of the stock-take whiteboard",
             {"form": "video", "seed": rng.randrange(1 << 30), "boards": [
                 ["STOCK TAKE", f"{branches[4]} store", "Friday"],
                 ["Gas cylinders left:", f"{cyl}", "Call the depot"],
                 ["Order this week:", f"{trays} trays of eggs", "and 2 bags of rice"]]})
    s.questions += [_q("video-cylinders", "video", "In the stock-take whiteboard video, how many gas cylinders were "
                       "left?", [str(cyl)], [str(trays)], s.name, "0:04"),
                    _q("video-eggs", "video", "In the stock-take whiteboard video, how many trays of eggs were to be "
                       "ordered?", [str(trays)], [str(cyl)], s.name, "0:08")]
    out.append(s)
    never.append(_q("never-video-flour", "never", "In the stock-take whiteboard video, how many bags of maize flour "
                    "were to be ordered?", [], file=s.name))
    out.append(Spec("", "never", "", {}, never))
    return out


def _shares(rng: random.Random, n: int) -> list[int]:
    """``n`` whole percentages, all different, summing to 100."""
    while True:
        cuts = sorted(rng.sample(range(5, 96), n - 1))
        parts = [b - a for a, b in zip([0] + cuts, cuts + [100])]
        if min(parts) >= 6 and len(set(parts)) == n:
            return parts


# -- drawing -------------------------------------------------------------------------------------------------------


def _grain(im, sigma: float, seed: int):
    import numpy as np
    from PIL import Image

    a = np.asarray(im, dtype=np.float32)
    a += np.random.default_rng(seed).normal(0, sigma, a.shape)
    return Image.fromarray(a.clip(0, 255).astype("uint8"))


def _photo(paper, d: dict, ground: tuple[int, int, int], size: tuple[int, int]):
    """A sheet photographed on a surface: turned, lit unevenly, a little out of focus and grainy."""
    import numpy as np
    from PIL import Image, ImageFilter

    rng = np.random.default_rng(d["seed"])
    base = Image.new("RGB", size, ground)
    base = _grain(base, 14, d["seed"] + 1).filter(ImageFilter.GaussianBlur(2))
    sheet = paper.rotate(d["angle"], resample=Image.BICUBIC, expand=True, fillcolor=(0, 0, 0))
    mask = Image.new("L", paper.size, 255).rotate(d["angle"], resample=Image.BICUBIC, expand=True)
    x = (size[0] - sheet.size[0]) // 2 + int(rng.integers(-30, 30))
    y = (size[1] - sheet.size[1]) // 2 + int(rng.integers(-30, 30))
    base.paste(sheet, (x, y), mask)
    w, h = size
    light = np.linspace(1.08, 0.82, w)[None, :, None] * np.linspace(1.0, 0.9, h)[:, None, None]
    lit = Image.fromarray((np.asarray(base, dtype=np.float32) * light).clip(0, 255).astype("uint8"))
    return _grain(lit.filter(ImageFilter.GaussianBlur(d["blur"])), 7, d["seed"] + 2)


def _receipt(d: dict):
    from PIL import Image, ImageDraw

    f, big = font("mono", 22), font("mono", 26, bold=True)
    when = dt.date.fromisoformat(d["date"])
    rows = [(d["shop"].upper(), big), (d["town"], f), ("-" * 30, f), (f"Receipt No: {d['number']}", f),
            (f"Date: {when:%d/%m/%Y}", f), ("-" * 30, f)]
    for item, qty, price in d["lines"]:
        rows += [(item.title(), f), (f"  {qty} x {_money(price)}".ljust(20) + f"{_money(qty * price):>10}", f)]
    rows += [("-" * 30, f), (f"TOTAL KSh".ljust(18) + f"{_money(d['total']):>12}", big), ("Paid: M-PESA", f),
             (f"Ref: {d['code']}", f), (f"Served by: {d['served']}", f), ("Asante! Karibu tena", f)]
    paper = Image.new("RGB", (520, 60 + 36 * len(rows)), (250, 248, 240))
    draw = ImageDraw.Draw(paper)
    for i, (text, ft) in enumerate(rows):
        draw.text((28, 30 + 36 * i), text, fill=(40, 40, 46), font=ft)
    return _photo(paper, d, (120, 84, 58), (1000, max(1200, paper.size[1] + 260)))


def _notice(d: dict):
    from PIL import Image, ImageDraw

    paper = Image.new("RGB", (760, 980), (252, 252, 247))
    draw = ImageDraw.Draw(paper)
    draw.rectangle((24, 24, 736, 956), outline=(200, 30, 30), width=6)
    draw.text((380, 130), d["title"], fill=(190, 25, 25), font=font("sans", 70, bold=True), anchor="mm")
    body = font("marker", 50)
    for i, line in enumerate(d["body"]):
        draw.text((380, 300 + 110 * i), line, fill=(25, 25, 30), font=body, anchor="mm")
    draw.text((380, 900), "- Mama Njeri", fill=(60, 60, 70), font=font("marker", 36), anchor="mm")
    return _photo(paper, d, (168, 122, 78), (1200, 1300))


def _chart(d: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5), dpi=110)
    labels, values = d["labels"], d["values"]
    if d["form"] == "bars":
        bars = ax.bar(labels, values, color="#3d7ea6")
        ax.bar_label(bars, padding=3)
        ax.set_ylabel(d.get("ylabel", ""))
    elif d["form"] == "hbars":
        bars = ax.barh(labels[::-1], values[::-1], color="#c8553d")
        ax.bar_label(bars, padding=3)
        ax.set_xlabel(d.get("ylabel", ""))
    elif d["form"] == "line":
        ax.plot(labels, values, marker="o", color="#2a9d8f")
        for x, v in zip(labels, values):
            ax.annotate(str(v), (x, v), textcoords="offset points", xytext=(0, 8), ha="center")
        ax.set_ylabel(d.get("ylabel", ""))
        ax.set_ylim(0, max(values) * 1.2)
    else:
        ax.pie(values, labels=labels, autopct="%d%%", startangle=90, counterclock=False)
        ax.axis("equal")
    ax.set_title(d["title"])
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _board(lines: list[str], shake: tuple[int, int], seed: int):
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (1280, 720), (92, 96, 102))
    draw = ImageDraw.Draw(im)
    dx, dy = shake
    draw.rectangle((90 + dx, 50 + dy, 1190 + dx, 670 + dy), fill=(238, 240, 236), outline=(160, 160, 165), width=10)
    head, body = font("marker", 64), font("marker", 54)
    for i, line in enumerate(lines):
        color = (180, 30, 30) if i == 0 else (20, 50, 140)
        draw.text((640 + dx, 150 + 120 * i + dy), line, fill=color, font=head if i == 0 else body, anchor="mm")
    return _grain(im, 3, seed)


def _video(d: dict, path: Path) -> None:
    import imageio.v2 as imageio
    import numpy as np

    rng = np.random.default_rng(d["seed"])
    writer = imageio.get_writer(str(path), fps=VIDEO_FPS, codec="libx264", quality=5, macro_block_size=16,
                                ffmpeg_log_level="error")
    try:
        for i in range(VIDEO_SECONDS * VIDEO_FPS):
            board = d["boards"][min(i // (BOARD_SECONDS * VIDEO_FPS), len(d["boards"]) - 1)]
            shake = (int(rng.integers(-3, 4)), int(rng.integers(-3, 4)))
            writer.append_data(np.asarray(_board(board, shake, d["seed"] + i)))
    finally:
        writer.close()


def _pdf(d: dict, path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    if d["form"] == "invoice":
        when = dt.date.fromisoformat(d["date"])
        c.setFont("Helvetica-Bold", 20)
        c.drawString(60, h - 80, d["supplier"])
        c.setFont("Helvetica", 11)
        c.drawString(60, h - 100, f"{d['town']}, Kenya")
        c.setFont("Helvetica-Bold", 16)
        c.drawRightString(w - 60, h - 80, "TAX INVOICE")
        c.setFont("Helvetica", 11)
        c.drawRightString(w - 60, h - 100, f"Invoice {d['number']}")
        c.drawRightString(w - 60, h - 116, f"Date {when:%d %B %Y}")
        c.drawString(60, h - 150, f"Bill to: Mama Njeri's Kitchen, {d['branch']} branch, Nairobi")
        y = h - 200
        c.setFont("Helvetica-Bold", 11)
        for x, t in ((60, "Item"), (300, "Qty"), (380, "Unit price (KSh)"), (w - 60, "Amount (KSh)")):
            (c.drawRightString if x == w - 60 else c.drawString)(x, y, t)
        c.line(60, y - 6, w - 60, y - 6)
        c.setFont("Helvetica", 11)
        for item, qty, price, amount in d["lines"]:
            y -= 22
            c.drawString(60, y, item.capitalize())
            c.drawString(300, y, str(qty))
            c.drawString(380, y, _money(price))
            c.drawRightString(w - 60, y, _money(amount))
        y -= 16
        c.line(300, y, w - 60, y)
        for label, value, bold in (("Subtotal", d["subtotal"], False), ("VAT 16%", d["vat"], False),
                                   ("Total due", d["total"], True)):
            y -= 22
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 12 if bold else 11)
            c.drawString(300, y, label)
            c.drawRightString(w - 60, y, _money(value))
        c.setFont("Helvetica", 10)
        c.drawString(60, 80, "Payment within 30 days by M-Pesa Paybill or bank transfer. Thank you for your business.")
        c.showPage()
    elif d["form"] == "menu":
        pages = [("Catering packages", [f"{n} - KSh {_money(p)} per guest" for n, p in d["packages"]]
                  + ["Every package comes with chapati, pilau and kachumbari."]),
                 ("Drinks and extras", [f"{n.capitalize()} - KSh {_money(p)} per event" for n, p in d["extras"]]),
                 ("Booking terms", [f"We cater for {d['minimum']} guests or more.",
                                    f"Please book at least {d['notice_days']} days before the event.",
                                    "Tastings are free for confirmed bookings."])]
        for k, (title, lines) in enumerate(pages, start=1):
            c.setFont("Helvetica-Bold", 22)
            c.drawString(60, h - 90, "Mama Njeri's Kitchen - Catering")
            c.setFont("Helvetica-Bold", 16)
            c.drawString(60, h - 130, title)
            c.setFont("Helvetica", 12)
            for i, line in enumerate(lines):
                c.drawString(70, h - 170 - 24 * i, line)
            c.setFont("Helvetica", 9)
            c.drawRightString(w - 60, 50, f"Page {k} of {len(pages)}")
            c.showPage()
    else:
        c.setFont("Helvetica-Bold", 20)
        c.drawString(60, h - 80, "Supplier delivery schedule")
        c.setFont("Helvetica-Bold", 11)
        y = h - 130
        for x, t in ((60, "Supplier"), (270, "Day"), (360, "Time"), (440, "Branch")):
            c.drawString(x, y, t)
        c.setFont("Helvetica", 11)
        for sup, day, time_, branch in d["rows"]:
            y -= 22
            for x, t in ((60, sup), (270, day), (360, time_), (440, branch)):
                c.drawString(x, y, t)
        c.showPage()
    c.save()


def draw(spec: Spec, folder: Path) -> Path:
    """Make one file in ``folder``."""
    path = Path(folder) / spec.name
    d = spec.draw
    if spec.kind == "pdf":
        _pdf(d, path)
    elif spec.kind == "chart":
        _chart(d, path)
    elif spec.kind == "video":
        _video(d, path)
    else:
        (_receipt if d["form"] == "receipt" else _notice)(d).save(path, quality=72)
    return path


def build(seed: int, out: Path, dates: list[dt.date]) -> dict:
    """Write every file under ``out/files`` and return {files: [...], questions: [...]}."""
    folder = Path(out) / "files"
    folder.mkdir(parents=True, exist_ok=True)
    files, questions = [], []
    for s in specs(seed, dates):
        questions += s.questions
        if s.kind == "never":
            continue
        path = draw(s, folder)
        files.append({"name": s.name, "kind": s.kind, "what": s.what, "path": str(path.relative_to(out)),
                      "bytes": path.stat().st_size, "questions": [q["id"] for q in s.questions]})
    return {"seed": seed, "files": files, "questions": questions}
