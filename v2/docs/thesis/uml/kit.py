"""A small kit for standard diagrams on the Design canvas: every card, line and label a separate placed element.

Cards are absolutely placed boxes; each straight run of a line is its own small <svg> (the canvas's Arrow-tool
form), so a person can drag or retype any part. Lines run from the middle of one card's edge (or a chosen fraction
along it) to another's, straight or with right-angle bends, and the tip stops 1px short of the card it points at.
The same elements also render as a plain page, which is captured as the PNG for the Word chapter.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field

INK, LINE, MUTED, V1 = "#1b2430", "#36424f", "#5d6876", "#6b7785"
FONT = "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif"
SW = 2  # stroke width


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float

    def at(self, side: str, f: float = 0.5) -> tuple[float, float]:
        return {"l": (self.x, self.y + self.h * f), "r": (self.x + self.w, self.y + self.h * f),
                "t": (self.x + self.w * f, self.y), "b": (self.x + self.w * f, self.y + self.h)}[side]

    def toward(self, x: float, y: float) -> tuple[float, float]:
        """Where the line from this ellipse's centre towards (x, y) leaves its edge."""
        a, b, dx, dy = self.w / 2, self.h / 2, x - self.cx, y - self.cy
        t = 1 / (((dx / a) ** 2 + (dy / b) ** 2) ** 0.5 or 1)
        return self.cx + t * dx, self.cy + t * dy

    def hit(self, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float]:
        """Where the line from (x0, y0) aimed at (x1, y1) first meets this ellipse's edge."""
        a, b = self.w / 2, self.h / 2
        px, py, dx, dy = (x0 - self.cx) / a, (y0 - self.cy) / b, (x1 - x0) / a, (y1 - y0) / b
        A, B, C = dx * dx + dy * dy, 2 * (px * dx + py * dy), px * px + py * py - 1
        s = (-B - max(B * B - 4 * A * C, 0) ** 0.5) / (2 * A)
        return x0 + s * (x1 - x0), y0 + s * (y1 - y0)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2


STYLE = {
    "box": f"background:#ffffff;border:1.5px solid {LINE};border-radius:4px",
    "round": f"background:#ffffff;border:1.5px solid {LINE};border-radius:16px",
    "state": f"background:#ffffff;border:1.5px solid {LINE};border-radius:20px",
    "entity": f"background:#eef2f5;border:1.5px solid {LINE};border-radius:2px",
    "process": f"background:#ffffff;border:2px solid {LINE};border-radius:22px",
    "usecase": f"background:#ffffff;border:1.5px solid {LINE};border-radius:50%",
    "head": f"background:#f6f8fa;border:1.5px solid {LINE};border-radius:4px",
    "act": f"background:#ffffff;border:1.5px solid {LINE};border-radius:1px",
    "initial": f"background:{INK};border-radius:50%",
    "final": f"background:radial-gradient(circle, {INK} 0 44%, #ffffff 46% 64%, {INK} 66%);border-radius:50%",
    "bar": f"background:{INK};border-radius:2px",
    "decision": f"background:{LINE};clip-path:polygon(50% 0, 100% 50%, 50% 100%, 0 50%)",
    "decision_in": "background:#ffffff;clip-path:polygon(50% 0, 100% 50%, 50% 100%, 0 50%)",
    "note": f"background:#fffbe8;border:1px solid #b9aa62;clip-path:polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 0 100%)",
    "fold": "background:#e8dc9c;clip-path:polygon(0 0, 0 100%, 100% 100%)",
    "class_name": f"background:#f6f8fa;border:1.5px solid {LINE};border-bottom:1px solid {LINE};border-radius:3px 3px 0 0",
    "class_body": f"background:#ffffff;border:1.5px solid {LINE};border-top:none;border-radius:0 0 3px 3px",
    "node": f"background:#ffffff;border:1.5px solid {LINE};border-radius:0",
    "node_top": "background:#dde4ea;clip-path:polygon(0 100%, 18px 0, 100% 0, calc(100% - 18px) 100%)",
    "node_side": "background:#c7d0d8;clip-path:polygon(0 18px, 100% 0, 100% calc(100% - 18px), 0 100%)",
    "env": f"background:#f7f9fb;border:1.5px solid {LINE};border-radius:2px",
    "bare": "background:transparent",
    "gs_entity": f"background:#ffffff;border:1.5px solid {LINE};border-radius:1px;box-shadow:-6px -6px 0 0 #cfd6dd",
    "gs_top": f"background:#f1f4f7;border:2px solid {LINE};border-bottom:1.5px solid {LINE};border-radius:16px 16px 0 0",
    "gs_body": f"background:#ffffff;border:2px solid {LINE};border-top:none;border-radius:0 0 16px 16px",
    "cylinder": f"background:#ffffff;border:1.5px solid {LINE};border-radius:50% / 18px",
    "cyl_top": f"background:#f1f4f7;border:1.5px solid {LINE};border-radius:50%",
    "frame": f"background:#ffffff;border:1.5px solid {LINE};border-radius:0",
    "tab_out": f"background:{LINE};clip-path:polygon(0 0, 100% 0, 100% 58%, calc(100% - 12px) 100%, 0 100%)",
    "tab_in": "background:#f1f4f7;clip-path:polygon(0 0, 100% 0, 100% 58%, calc(100% - 12px) 100%, 0 100%)",
    "icon": f"background:#ffffff;border:1.5px solid {LINE};border-radius:1px",
    "doc_out": f"background:{LINE};clip-path:polygon(0 0, 62% 0, 100% 32%, 100% 100%, 0 100%)",
    "doc_in": "background:#ffffff;clip-path:polygon(0 0, 62% 0, 100% 32%, 100% 100%, 0 100%)",
    "junction": f"background:{INK};border-radius:50%",
    "cell": f"background:#eef3f8;border:1px solid {LINE};border-radius:0",
    "cell_next": f"background:#fbf0e8;border:1px dashed {LINE};border-radius:0",
}

STICK = ('<svg width="44" height="76" viewBox="0 0 44 76" aria-hidden="true" style="flex:none;fill:none;stroke:%s;'
         'stroke-width:2;stroke-linecap:round"><circle cx="22" cy="10" r="9"></circle><path d="M22 19 L22 46 M4 30 '
         'L40 30 M22 46 L7 72 M22 46 L37 72"></path></svg>') % INK


class Diagram:
    def __init__(self, name: str, title: str, w: int, h: int, subtitle: str | None = None):
        self.name, self.title, self.w, self.h = name, title, w, h
        self.layers: dict[int, list[str]] = {0: [], 1: [], 2: [], 3: []}
        self.marks = 0
        self.text(64, 40, w - 128, title, size=24, weight=600, align="left", color=INK)
        if subtitle:
            self.text(64, 76, w - 128, subtitle, size=14, align="left", color=MUTED)

    # ---------------------------------------------------------------- elements
    def band(self, x, y, w, h, label=None, style="frame", label_side="left") -> Box:
        css = {"frame": f"border:1.5px solid {LINE};border-radius:4px;background:#ffffff",
               "lane": f"border:1px solid #c5ccd3;background:#fafbfc",
               "boundary": "border:2px solid #2a78d6;border-radius:6px;background:#f7fbff",
               "package": f"border:1.5px solid {LINE};border-radius:2px;background:#fbfcfd",
               "region": f"border:1.5px dashed {MUTED};border-radius:10px;background:#ffffff"}[style]
        self.layers[0].append(f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
                              f'box-sizing:border-box;{css}"></div>')
        if label:
            lx = x + 14 if label_side == "left" else x + w - 14 - 9 * len(label)
            self.text(lx, y + 10, max(60, 9 * len(label) + 20), label, size=15, weight=600, align="left", color=INK,
                      layer=0)
        return Box(x, y, w, h)

    def card(self, x, y, w, h, label: str, kind="box", size=15, align="center", pad=8, valign="center") -> Box:
        just = {"center": "center", "left": "flex-start"}[align]
        al = {"center": "center", "top": "flex-start"}[valign]
        self.layers[2].append(
            f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;box-sizing:border-box;'
            f'padding:{pad}px;display:flex;align-items:{al};justify-content:{just};text-align:{align};'
            f'font-size:{size}px;line-height:1.3;color:{INK};{STYLE[kind]}">' + (f"<span>{label}</span>" if label else "")
            + "</div>")
        return Box(x, y, w, h)

    def deco(self, x, y, w, h, kind, layer=2):
        self.layers[layer].append(f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
                                  f'box-sizing:border-box;{STYLE[kind]}"></div>')

    def text(self, x, y, w, t, size=14, weight=400, align="center", color=MUTED, layer=3, italic=False, bg=None):
        back = f"background:{bg};" if bg else ""
        self.layers[layer].append(
            f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;font-size:{size}px;line-height:1.3;'
            f'font-weight:{weight};text-align:{align};color:{color};{back}{"font-style:italic;" if italic else ""}">{t}</div>')

    def raw(self, x, y, w, h, css: str, layer=2):
        self.layers[layer].append(f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
                                  f'box-sizing:border-box;{css}"></div>')

    def actor(self, cx, top, name, width=180) -> Box:
        self.layers[2].append(
            f'<div style="position:absolute;left:{cx - width / 2}px;top:{top}px;width:{width}px;height:124px;'
            f'box-sizing:border-box;display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center;'
            f'font-size:15px;line-height:1.25;color:{INK}">{STICK}<span>{name}</span></div>')
        return Box(cx - 22, top, 44, 76)  # the figure, for lines

    def decision(self, cx, cy, w=72, h=72) -> Box:
        self.deco(cx - w / 2, cy - h / 2, w, h, "decision")
        self.deco(cx - w / 2 + 2.5, cy - h / 2 + 2.5, w - 5, h - 5, "decision_in")
        return Box(cx - w / 2, cy - h / 2, w, h)

    def note(self, x, y, w, h, t, size=13) -> Box:
        b = self.card(x, y, w, h, t, kind="note", size=size, align="left", pad=12)
        self.deco(x + w - 16, y, 16, 16, "fold")
        return b

    def klass(self, x, y, w, name, rows: list[str], stereo=None, size=14) -> Box:
        """A UML class box: «stereotype» and name, then one attribute per row."""
        head_h = 48 if stereo else 34
        label = (f'<span style="font-size:12px;color:{MUTED}">«{stereo}»</span><br><b>{name}</b>' if stereo
                 else f"<b>{name}</b>")
        self.card(x, y, w, head_h, label, kind="class_name", size=15, pad=6)
        body_h = round(20 + size * 1.3 * len(rows))
        self.card(x, y + head_h, w, body_h, "<br>".join(rows), kind="class_body", size=size, align="left", pad=10,
                  valign="top")
        return Box(x, y, w, head_h + body_h)

    def node(self, x, y, w, h, label, depth=18, size=15, fill="#ffffff", layer=0) -> Box:
        """A UML node: a box with its top and right faces drawn, so it reads as a 3-D block."""
        d = depth
        self.raw(x, y - d, w + d, d + 1, f"background:{LINE};clip-path:polygon(0 100%, {d}px 0, 100% 0, "
                 f"calc(100% - {d}px) 100%)", layer)
        self.raw(x + 1.5, y - d + 1.5, w + d - 3, d - 1.5, f"background:#e3e8ed;clip-path:polygon(0 100%, {d - 1}px 0, "
                 f"100% 0, calc(100% - {d}px) 100%)", layer)
        self.raw(x + w - 1, y - d, d + 1, h + d, f"background:{LINE};clip-path:polygon(0 {d}px, 100% 0, 100% "
                 f"calc(100% - {d}px), 0 100%)", layer)
        self.raw(x + w, y - d + 2.5, d - 1.5, h + d - 4, f"background:#cdd5dc;clip-path:polygon(0 {d - 1}px, 100% 0, "
                 f"100% calc(100% - {d}px), 0 100%)", layer)
        self.raw(x, y, w, h, f"background:{fill};border:1.5px solid {LINE}", layer)
        self.text(x + 12, y + 10, w - 24, label, size=size, align="left", color=INK, layer=layer)
        return Box(x, y, w, h)

    def frame(self, x, y, w, h, label: str, tab_w: float | None = None) -> Box:
        """A UML frame: a rectangle named in a pentagon at its top left (sd, stm, act, cmp, pkg ...)."""
        self.deco(x, y, w, h, "frame", layer=0)
        tw = tab_w or 8 * len(label) + 34
        self.deco(x, y, tw, 32, "tab_out", layer=0)
        self.deco(x + 1.5, y + 1.5, tw - 3.5, 29, "tab_in", layer=0)
        self.text(x + 10, y + 7, tw - 24, label, size=14, weight=600, align="left", color=INK, layer=0)
        return Box(x, y, w, h)

    def component(self, x, y, w, h, name: str, detail: str = "", stereo: str | None = None, size=15) -> Box:
        """A UML component: its name (and «stereotype») with the two-tab component icon at the top right."""
        head = f'<span style="font-size:12px;color:{MUTED}">«{stereo}»</span><br>' if stereo else ""
        body = (f'<b style="display:inline-block;padding:0 18px">{name}</b>'
                + (f'<br><span style="color:{MUTED}">{detail}</span>' if detail else ""))
        self.card(x, y, w, h, head + body, kind="box", size=size, pad=10)
        ix, iy = x + w - 24, y + 8
        self.deco(ix, iy, 14, 18, "icon", layer=3)
        self.deco(ix - 4, iy + 3, 9, 5, "icon", layer=3)
        self.deco(ix - 4, iy + 10, 9, 5, "icon", layer=3)
        return Box(x, y, w, h)

    def artifact(self, x, y, w, h, name: str, detail: str = "", size=14, stereo="artifact") -> Box:
        """A UML artifact: «artifact», its name, and the dog-eared document icon at the top right."""
        head = f'<span style="font-size:12px;color:{MUTED}">«{stereo}»</span><br>' if stereo else ""
        body = f'<b>{name}</b>' + (f'<br><span style="color:{MUTED}">{detail}</span>' if detail else "")
        self.card(x, y, w, h, head + body, kind="box", size=size, pad=10)
        self.deco(x + w - 22, y + 8, 13, 17, "doc_out", layer=3)
        self.deco(x + w - 20.5, y + 9.5, 10, 14, "doc_in", layer=3)
        return Box(x, y, w, h)

    def cylinder(self, x, y, w, h, label: str, size=14) -> Box:
        """A data store drawn as a cylinder."""
        self.card(x, y, w, h, label, kind="cylinder", size=size, pad=12)
        self.deco(x, y, w, 36, "cyl_top", layer=2)
        return Box(x, y, w, h)

    def gs_entity(self, x, y, w, h, label: str, size=15) -> Box:
        """A Gane–Sarson external entity: a box shaded on its top and left edges."""
        return self.card(x + 6, y + 6, w - 6, h - 6, label, kind="gs_entity", size=size)

    def gs_process(self, x, y, w, h, number: str, label: str, size=16) -> Box:
        """A Gane–Sarson process: a rounded box with its number in a band at the top."""
        self.card(x, y, w, 40, f"<b>{number}</b>", kind="gs_top", size=15)
        self.card(x, y + 40, w, h - 40, label, kind="gs_body", size=size)
        return Box(x, y, w, h)

    # ---------------------------------------------------------------- lines
    def route(self, a: Box, sa: str, b: Box, sb: str, fa=0.5, fb=0.5, via=None, diag=False):
        p, q = a.at(sa, fa), b.at(sb, fb)
        if diag or p[0] == q[0] or p[1] == q[1]:
            return [p, q]
        if sa in "lr" and sb in "lr":
            m = via if via is not None else round((p[0] + q[0]) / 2)
            return [p, (m, p[1]), (m, q[1]), q]
        if sa in "tb" and sb in "tb":
            m = via if via is not None else round((p[1] + q[1]) / 2)
            return [p, (p[0], m), (q[0], m), q]
        if sa in "lr":
            return [p, (q[0], p[1]), q]
        return [p, (p[0], q[1]), q]

    def link(self, a, sa, b, sb, head="filled", dashed=False, label=None, lx=None, ly=None, lw=None, fa=0.5, fb=0.5,
             via=None, diag=False, color=LINE, pts=None):
        pts = pts or self.route(a, sa, b, sb, fa, fb, via, diag)
        self.path(pts, head, dashed, color)
        if label:
            w = lw or min(260, 8 * max(len(s) for s in label.split("<br>")) + 16)
            if lx is None:  # above the middle of the longest straight run
                segs = list(zip(pts, pts[1:]))
                (x1, y1), (x2, y2) = max(segs, key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
                lines = label.count("<br>") + 1
                if y1 == y2:
                    lx, ly = (x1 + x2) / 2 - w / 2, y1 - 8 - 17 * lines
                else:
                    lx, ly = x1 + 12, (y1 + y2) / 2 - 8 * lines
            self.text(round(lx), round(ly), w, label, size=14, color=MUTED)

    def along(self, p, q, t: str, side: int = 1, at: float = 0.5, w: float | None = None, color=MUTED):
        """A label beside the straight line p→q, ``at`` of the way along, 8px clear on ``side`` (+1 or -1)."""
        lines = t.count("<br>") + 1
        w = w or 7.6 * max(len(s) for s in t.split("<br>")) + 4
        h = 18 * lines
        (x1, y1), (x2, y2) = p, q
        d = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1
        nx, ny = -(y2 - y1) / d * side, (x2 - x1) / d * side
        gap = 9 + abs(nx) * w / 2 + abs(ny) * h / 2
        mx, my = x1 + (x2 - x1) * at + nx * gap, y1 + (y2 - y1) * at + ny * gap
        self.text(round(mx - w / 2), round(my - h / 2), round(w), t, size=14, color=color)

    def path(self, pts, head="filled", dashed=False, color=LINE):
        pts = [tuple(map(float, p)) for p in pts]
        if head:  # the tip stops 1px short of the card it points at
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            d = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1
            pts[-1] = (x2 - (x2 - x1) / d, y2 - (y2 - y1) / d)
        for i, (p, q) in enumerate(zip(pts, pts[1:])):
            last = i == len(pts) - 2
            self._segment(p, q, head if last else None, dashed, color)

    def _segment(self, p, q, head, dashed, color):
        h = {"filled": 2 * SW, "triangle": 3.5 * SW, "open": 0, None: 0}[head]
        (x1, y1), (x2, y2) = p, q
        left, top = min(x1, x2), min(y1, y2)
        w, hgt = abs(x2 - x1), abs(y2 - y1)
        dash = "stroke-dasharray:7 6;" if dashed else ""
        if hgt == 0:  # horizontal
            box = (left, y1 - 4, w, 8)
            a, b = ((0, 4), (w, 4)) if x2 > x1 else ((w, 4), (0, 4))
        elif w == 0:
            box = (x1 - 4, top, 8, hgt)
            a, b = ((4, 0), (4, hgt)) if y2 > y1 else ((4, hgt), (4, 0))
        else:  # a straight diagonal (associations in use-case diagrams)
            box = (left, top, w, hgt)
            a, b = (x1 - left, y1 - top), (x2 - left, y2 - top)
        d = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 or 1
        end = (b[0] - (b[0] - a[0]) * h / d, b[1] - (b[1] - a[1]) * h / d)
        bx, by, bw, bh = (round(v, 2) for v in box)
        defs, mark = "", ""
        if head:
            self.marks += 1
            mid = f"{self.name.lower()}-head-{self.marks}"
            if head == "filled":
                shape = (f'<path d="M0 0 L4 2 L0 4 Z" fill="{color}" stroke="none" style="stroke: none; fill: {color}; '
                         f'fill: context-stroke"/>')
                ref = 2
            elif head == "triangle":
                shape = f'<path d="M0 0 L7 3.5 L0 7 Z" fill="#ffffff" stroke="{color}" stroke-width="0.6" style="fill:#ffffff;stroke:{color};stroke-dasharray:none"/>'
                ref = 3.5
            else:  # open arrowhead: two strokes, tip on the line's end
                shape = f'<path d="M0 0 L5.5 2.75 L0 5.5" fill="none" stroke="{color}" stroke-width="0.6" style="fill:none;stroke:{color};stroke-dasharray:none"/>'
                ref = 5.5
            size = {"filled": 4, "triangle": 7, "open": 5.5}[head]
            defs = (f'<defs><marker id="{mid}" orient="auto" markerWidth="{size + 1}" markerHeight="{size + 1}" refX="{ref}" refY="{size / 2}" '
                    f'overflow="visible">{shape}</marker></defs>')
            mark = f' marker-end="url(#{mid})"'
        self.layers[1].append(
            f'<svg width="{bw}" height="{bh}" viewBox="0 0 {bw} {bh}" preserveAspectRatio="none" style="position: '
            f'absolute; left: {bx}px; top: {by}px; width: {bw}px; height: {bh}px; overflow: visible; fill: none; '
            f'stroke: {color}; stroke-width: {SW}; stroke-linecap: round; stroke-linejoin: round;{dash}">{defs}'
            f'<path d="M {a[0]:.2f} {a[1]:.2f} L {end[0]:.2f} {end[1]:.2f}"{mark}></path></svg>')

    # ---------------------------------------------------------------- output
    def body(self) -> str:
        inner = "\n".join(self.layers[0] + self.layers[1] + self.layers[2] + self.layers[3])
        return (f'<div style="position: relative; width: {self.w}px; height: {self.h}px; background: #ffffff; '
                f'font-family: {FONT}; color: {INK}">\n{inner}\n</div>')

    def dc_html(self) -> str:
        props = json.dumps({"$preview": {"width": self.w, "height": self.h}})
        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(self.title)}</title>
<script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&amp;display=swap">
<style>
body{{margin:0}}
a{{color:#2a78d6}}a:hover{{color:#1b5fae}}
</style>
</helmet>
{self.body()}
</x-dc>
<script type="text/x-dc" data-dc-script data-props='{props}'>
class Component extends DCLogic {{
renderVals() {{
return {{}};
}}
}}
</script>
</body>
</html>
"""

    def plain_html(self) -> str:
        return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" '
                f'href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&display=swap">'
                f'<style>body{{margin:0}}</style></head><body>{self.body()}</body></html>')
