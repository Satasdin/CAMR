#!/usr/bin/env python3
"""Draws the report's diagrams on a hand-placed grid. One unit is 0.01 inch, so 626 is the printed text width of an A4 page."""
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyBboxPatch, Polygon, Rectangle

plt.rcParams["font.family"] = ["Arial", "Helvetica", "DejaVu Sans"]
HERE = Path(__file__).parent
INK = "#111111"
SIZE = 7.6


class Sheet:
    def __init__(self, name, width, height):
        self.name, self.width, self.height = name, width, height
        self.figure = plt.figure(figsize=(width / 100, height / 100))
        self.ax = self.figure.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, width)
        self.ax.set_ylim(height, 0)
        self.ax.axis("off")

    def save(self):
        self.figure.savefig(HERE / f"{self.name}.png", dpi=300, facecolor="white")
        plt.close(self.figure)

    def text(self, x, y, words, size=SIZE, ha="center", va="center", weight="normal", style="normal", back=False):
        box = dict(facecolor="white", edgecolor="none", pad=1.2) if back else None
        self.ax.text(x, y, words, fontsize=size, ha=ha, va=va, weight=weight, style=style, color=INK, linespacing=1.15, bbox=box, zorder=6)

    def rect(self, x, y, w, h, words="", dashed=False, weight="normal", size=SIZE, line=0.8, fill="white", z=2):
        self.ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor=INK, lw=line, ls="--" if dashed else "-", zorder=z))
        if words:
            self.text(x + w / 2, y + h / 2, words, weight=weight, size=size)

    def rounded(self, x, y, w, h, words="", radius=8, size=SIZE, z=3):
        self.ax.add_patch(FancyBboxPatch((x + radius, y + radius), w - 2 * radius, h - 2 * radius, boxstyle=f"round,pad={radius}",
                                         facecolor="white", edgecolor=INK, lw=0.8, zorder=z))
        if words:
            self.text(x + w / 2, y + h / 2, words, size=size)

    def ellipse(self, cx, cy, w, h, words):
        self.ax.add_patch(Ellipse((cx, cy), w, h, facecolor="white", edgecolor=INK, lw=0.8, zorder=3))
        self.text(cx, cy, words)

    def diamond(self, cx, cy, half=15):
        self.ax.add_patch(Polygon([(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)], closed=True, facecolor="white", edgecolor=INK, lw=0.8, zorder=3))

    def start(self, x, y):
        self.ax.add_patch(Ellipse((x, y), 13, 13, facecolor=INK, edgecolor=INK, zorder=3))

    def stop(self, x, y):
        self.ax.add_patch(Ellipse((x, y), 17, 17, facecolor="white", edgecolor=INK, lw=0.8, zorder=3))
        self.ax.add_patch(Ellipse((x, y), 10, 10, facecolor=INK, edgecolor=INK, zorder=4))

    def actor(self, cx, cy, words):
        top = cy - 28
        self.ax.add_patch(Ellipse((cx, top + 7), 14, 14, facecolor="white", edgecolor=INK, lw=0.8, zorder=4))
        for a, b in [((cx, top + 14), (cx, top + 34)), ((cx - 14, top + 21), (cx + 14, top + 21)), ((cx, top + 34), (cx - 12, top + 52)), ((cx, top + 34), (cx + 12, top + 52))]:
            self.ax.plot([a[0], b[0]], [a[1], b[1]], color=INK, lw=0.8, zorder=4)
        self.text(cx, top + 63, words)

    def line(self, points, head=None, dashed=False, tail=None, lw=0.8):
        xs, ys = zip(*points)
        self.ax.plot(xs, ys, color=INK, lw=lw, ls=(0, (4, 2.5)) if dashed else "-", zorder=2, solid_capstyle="butt")
        if head:
            self._head(points[-2], points[-1], head)
        if tail:
            self._head(points[1], points[0], tail)

    def _head(self, a, b, kind, length=7.5, half=3.1):
        angle = math.atan2(b[1] - a[1], b[0] - a[0])
        ux, uy = math.cos(angle), math.sin(angle)
        px, py = -uy, ux
        left = (b[0] - length * ux + half * px, b[1] - length * uy + half * py)
        right = (b[0] - length * ux - half * px, b[1] - length * uy - half * py)
        if kind == "open":
            self.ax.plot([left[0], b[0], right[0]], [left[1], b[1], right[1]], color=INK, lw=0.8, zorder=5)
        else:
            self.ax.add_patch(Polygon([left, b, right], closed=True, facecolor=INK, edgecolor=INK, lw=0.4, zorder=5))


def component(s, x, y, w, h, words):
    s.rect(x, y, w, h)
    s.text(x + w / 2 - 4, y + h / 2, words)
    s.rect(x + w - 15, y + 5, 10, 13, z=4)
    s.rect(x + w - 18, y + 8, 6, 2.6, z=5)
    s.rect(x + w - 18, y + 13, 6, 2.6, z=5)


def entity(s, x, y, w, h, words):
    s.rect(x + 3.5, y + 3.5, w, h, fill="#555555", z=2)
    s.rect(x, y, w, h, words, z=3)


def context():
    s = Sheet("context", 626, 365)
    s.rounded(255, 135, 130, 100, radius=9)
    s.line([(255, 160), (385, 160)])
    s.text(320, 148, "0")
    s.text(320, 197, "Burrow\nprivate vault and\nretrieval")
    entity(s, 10, 145, 92, 74, "Person using\nBurrow")
    entity(s, 524, 145, 92, 74, "Ollama\n(local models)")
    entity(s, 262, 12, 116, 52, "MCP client")
    entity(s, 247, 300, 146, 52, "Vault folder and linked\ncode folders (file system)")
    s.line([(105, 165), (255, 165)], "fill")
    s.text(180, 140, "questions, note edits,\nchosen vault, linked folders,\naccepted changes", back=True)
    s.line([(255, 203), (105, 203)], "fill")
    s.text(180, 223, "answers with their sources,\ngraph, proposed changes", back=True)
    s.line([(385, 165), (524, 165)], "fill")
    s.text(454, 146, "excerpts and question,\ntext to embed", back=True)
    s.line([(524, 203), (385, 203)], "fill")
    s.text(454, 223, "generated answer,\nvectors", back=True)
    s.line([(292, 67), (292, 135)], "fill")
    s.text(285, 101, "tool calls", ha="right", back=True)
    s.line([(350, 135), (350, 67)], "fill")
    s.text(357, 101, "tool results", ha="left", back=True)
    s.line([(292, 300), (292, 235)], "fill")
    s.text(285, 268, "notes and code as text", ha="right", back=True)
    s.line([(350, 235), (350, 300)], "fill")
    s.text(357, 268, "new and edited notes, accepted changes", ha="left", back=True)
    s.save()


def use_cases():
    s = Sheet("use_cases", 626, 610)
    s.rect(112, 8, 404, 594, line=0.9, z=1)
    s.text(314, 22, "Burrow", weight="bold", size=8.4)
    left = [(60, "Open a vault"), (116, "Write and edit\nnotes"), (172, "Link a\ncode folder"), (228, "Search\nthe vault"), (284, "Explore\nthe graph"), (390, "Ask a question"), (522, "Accept or reject\na proposed change")]
    person = (56, 305)
    s.actor(*person, "Person")
    for y, words in left:
        s.ellipse(210, y, 150, 44, words)
        s.line([(person[0] + 15, person[1] - 8), (135, y)])
    s.ellipse(410, 60, 150, 44, "Call vault tools")
    s.ellipse(410, 130, 150, 44, "Add a note\nthrough a tool")
    s.actor(575, 110, "MCP client")
    s.line([(558, 95), (485, 62)])
    s.line([(558, 105), (485, 128)])
    s.ellipse(410, 240, 150, 44, "Limit the question\nto one folder")
    s.ellipse(410, 325, 150, 44, "Retrieve excerpts")
    s.ellipse(410, 400, 150, 44, "Generate\nthe answer")
    s.ellipse(410, 475, 150, 44, "Propose a\nchange to a file")
    s.ellipse(410, 552, 150, 44, "Keep the answer\nas a note")
    s.actor(575, 372, "Ollama")
    s.line([(558, 358), (485, 328)])
    s.line([(558, 370), (485, 398)])
    # Ask to the cases around it.
    s.line([(350, 256), (262, 372)], "open", dashed=True)
    s.text(348, 287, "«extend»", back=True)
    s.line([(285, 382), (335, 335)], "open", dashed=True)
    s.text(316, 368, "«include»", back=True)
    s.line([(285, 392), (335, 398)], "open", dashed=True)
    s.text(310, 408, "«include»", back=True)
    s.line([(345, 462), (265, 406)], "open", dashed=True)
    s.text(296, 446, "«extend»", back=True)
    s.line([(352, 537), (232, 412)], "open", dashed=True)
    s.text(270, 482, "«extend»", back=True)
    s.save()


def activity():
    s = Sheet("activity", 626, 640)
    s.rect(4, 6, 618, 628, z=1)
    s.line([(180, 6), (180, 634)])
    s.line([(452, 6), (452, 634)])
    s.line([(4, 28), (622, 28)])
    for x, words in [(92, "Person"), (316, "Burrow engine"), (537, "Ollama")]:
        s.text(x, 17, words, weight="bold", size=8.2)

    def act(cx, cy, words, w=172, h=38):
        s.rounded(cx - w / 2, cy - h / 2, w, h, words, radius=7)

    s.start(92, 47)
    act(92, 95, "Type a question, optionally\npick a folder", w=150)
    s.line([(92, 54), (92, 76)], "fill")
    act(316, 95, "Re-read any files that changed")
    s.line([(167, 95), (230, 95)], "fill")
    act(316, 155, "Embed the question")
    s.line([(316, 114), (316, 136)], "fill")
    act(537, 155, "Return its vector", w=140)
    s.line([(402, 149), (467, 149)], "fill")
    s.line([(467, 162), (402, 162)], "fill")
    act(316, 215, "Rank pieces by words and by\nmeaning; merge the two rankings")
    s.line([(316, 174), (316, 196)], "fill")
    act(316, 275, "Lower tests and past output;\nexact names and paths go first")
    s.line([(316, 234), (316, 256)], "fill")
    act(316, 335, "Take the best piece of\nup to four entry files")
    s.line([(316, 294), (316, 316)], "fill")
    act(316, 395, "Follow links for up to two hops,\nwithin 12,000 characters")
    s.line([(316, 354), (316, 376)], "fill")
    act(316, 455, "Mark excerpts as data and\nbuild the prompt")
    s.line([(316, 414), (316, 436)], "fill")
    act(537, 455, "Generate and stream\nthe answer", w=140)
    s.line([(402, 455), (467, 455)], "fill")
    act(316, 515, "Remove reasoning text and\nattach the sources")
    s.line([(537, 474), (537, 515), (402, 515)], "fill")
    act(92, 515, "Read the answer and\nopen its sources", w=150)
    s.line([(230, 515), (167, 515)], "fill")
    s.diamond(92, 572)
    s.line([(92, 534), (92, 557)], "fill")
    s.text(140, 562, "[keep it]", size=7.2)
    act(316, 572, "Write it as a Markdown note")
    s.line([(107, 572), (230, 572)], "fill")
    s.text(104, 594, "[leave it]", size=7.2, ha="left")
    s.stop(92, 615)
    s.line([(92, 587), (92, 606)], "fill")
    s.line([(316, 591), (316, 615), (101, 615)], "fill")
    s.save()


def architecture():
    s = Sheet("architecture", 626, 500)
    tops = [(7, "burrow-trial\nagent test"), (112, "Burrow.app\nMac app"), (217, "burrow\ncommand line"), (322, "BurrowTUI\nterminal view"), (427, "BurrowChat\nterminal chat"), (532, "BurrowMCP\nMCP server")]
    for x, words in tops:
        component(s, x, 12, 90, 54, words)
    component(s, 7, 140, 140, 50, "BurrowTrial\nagent test logic")
    component(s, 322, 140, 300, 50, "BurrowTools\nthe same seven tools for chat and MCP")
    s.rect(7, 240, 615, 130, z=1)
    s.text(16, 254, "«component»  BurrowCore", ha="left", weight="bold")
    for x, words in [(16, "Scanner"), (118, "Chunker"), (220, "LinkFinder"), (322, "Retrieval"), (424, "Asking"), (526, "Standing, Asked")]:
        s.rect(x, 268, 92, 36, words)
    for x, words in [(16, "Vault"), (118, "Database"), (220, "Graph"), (322, "Ollama client")]:
        s.rect(x, 318, 92, 36, words)
    s.line([(52, 66), (52, 140)], "open", dashed=True)
    s.line([(128, 66), (128, 140)], "open", dashed=True)
    s.text(133, 104, "reply format", size=7.1, ha="left", back=True)
    s.line([(180, 66), (180, 240)], "open", dashed=True)
    s.line([(262, 66), (262, 240)], "open", dashed=True)
    s.line([(290, 66), (290, 165), (322, 165)], "open", dashed=True)
    for x in (367, 472, 577):
        s.line([(x, 66), (x, 140)], "open", dashed=True)
    s.line([(77, 190), (77, 240)], "open", dashed=True)
    s.line([(472, 190), (472, 240)], "open", dashed=True)
    for x, w, words in [(40, 150, "Vault folder and\nlinked folders"), (238, 150, "index.sqlite\n(FTS5, WAL)"), (436, 150, "Ollama server\n127.0.0.1:11434")]:
        s.rect(x, 430, w, 54, words)
        s.line([(x + w / 2, 370), (x + w / 2, 430)], "open", dashed=True)
    s.save()


def sequence():
    s = Sheet("sequence", 626, 560)
    names = [(46, ":Person"), (168, ":Workspace"), (300, ":Vault"), (432, ":Index (SQLite)"), (566, ":Ollama")]
    for x, words in names:
        s.rect(x - 44, 8, 88, 28, words)
        s.line([(x, 36), (x, 548)], dashed=True, lw=0.6)
    for x, a, b in [(168, 62, 532), (300, 96, 266), (432, 148, 240), (566, 114, 148), (566, 310, 498)]:
        s.rect(x - 4, a, 8, b - a, z=4)

    def message(a, b, y, words, reply=False):
        s.line([(a, y), (b, y)], "open" if reply else "fill", dashed=reply)
        s.text((a + b) / 2, y - 7, words, back=True, size=7.2)

    message(46, 164, 66, "ask(question, scope)")
    message(172, 296, 100, "retrieve(question, scope)")
    message(304, 562, 118, "embed(question)")
    message(562, 304, 146, "vector", True)
    message(304, 428, 168, "rank by words and vector")
    message(428, 304, 192, "ranked pieces", True)
    message(304, 428, 216, "neighbours(entry files)")
    message(428, 304, 238, "links and best pieces", True)
    message(296, 172, 266, "excerpts with reasons", True)
    message(164, 50, 290, "sources shown", True)
    message(172, 562, 318, "chat(system rules, marked excerpts, question)")
    y = 352
    s.rect(112, y, 500, 92, z=1)
    s.rect(112, y, 40, 16, "loop", size=7.2)
    s.text(158, y + 8, "[until the answer ends]", ha="left", size=7.2, back=True)
    message(562, 172, y + 38, "next words of the answer", True)
    message(164, 50, y + 72, "answer grows on screen", True)
    message(562, 172, 490, "reasoning removed, full answer", True)
    message(164, 50, 524, "answer with files and lines", True)
    s.save()


def schema():
    s = Sheet("schema", 626, 288)

    def table(x, y, w, name, rows, dashed=False):
        h = 22 + 15 * len(rows) + 6
        s.rect(x, y, w, h, dashed=dashed, z=2)
        s.rect(x, y, w, 22, name, weight="bold", dashed=dashed, z=3)
        for i, row in enumerate(rows):
            s.text(x + 7, y + 34 + 15 * i, row, ha="left", size=7.3)

    table(16, 14, 176, "files", ["PK  id", "      path (unique)", "      is_note", "      cluster", "      hash"])
    table(258, 14, 170, "chunks", ["PK  id", "FK  file_id", "      start_line", "      end_line", "      body"])
    table(482, 14, 134, "vectors", ["PK, FK  chunk_id", "      vector"])
    table(258, 186, 170, "chunks_fts  (full-text index)", ["PK  rowid = chunks.id", "      path", "      body"], dashed=True)
    table(16, 186, 176, "links", ["PK  source", "PK  target", "PK  kind (imports, uses, about)", "      via"])
    s.line([(192, 60), (258, 60)])
    s.text(200, 52, "1", size=7.5)
    s.text(248, 52, "0..*", size=7.5)
    s.line([(428, 60), (482, 60)])
    s.text(436, 52, "1", size=7.5)
    s.text(470, 52, "0..1", size=7.5)
    s.line([(343, 117), (343, 186)])
    s.text(351, 127, "1", size=7.5)
    s.text(351, 176, "1", size=7.5)
    s.line([(104, 117), (104, 186)], dashed=True)
    s.text(112, 127, "1", size=7.5)
    s.text(116, 176, "0..*", size=7.5)
    s.text(96, 152, "by path", size=7.2, ha="right")
    s.save()


def node(s, x, y, w, h, words):
    d = 12
    s.ax.add_patch(Polygon([(x, y), (x + d, y - d), (x + w + d, y - d), (x + w, y)], closed=True, facecolor="white", edgecolor=INK, lw=0.8, zorder=1))
    s.ax.add_patch(Polygon([(x + w, y), (x + w + d, y - d), (x + w + d, y + h - d), (x + w, y + h)], closed=True, facecolor="white", edgecolor=INK, lw=0.8, zorder=1))
    s.rect(x, y, w, h, z=1)
    s.text(x + 9, y + 15, words, ha="left", weight="bold")


def deployment():
    s = Sheet("deployment", 626, 400)
    node(s, 8, 24, 440, 360, "«device» Mac with Apple silicon")
    s.rect(24, 50, 408, 322, z=1)
    s.text(32, 63, "«execution environment» macOS", ha="left")
    s.rect(40, 82, 180, 44, "«artifact»\nBurrow.app", z=3)
    s.rect(236, 82, 180, 44, "«artifact»\nburrow (command line)", z=3)
    s.rect(66, 166, 324, 78, z=2)
    s.text(74, 178, "Data on disk", ha="left")
    s.rect(78, 190, 144, 44, "Vault and\nlinked folders", z=3)
    s.rect(234, 190, 144, 44, ".burrow/index.sqlite", z=3)
    s.rect(138, 296, 180, 44, "«service»\nOllama with Qwen3 models", z=3)
    s.line([(130, 126), (130, 166)], "open", dashed=True)
    s.line([(326, 126), (326, 166)], "open", dashed=True)
    s.line([(50, 126), (50, 318), (138, 318)], "open", dashed=True)
    s.line([(406, 126), (406, 318), (318, 318)], "open", dashed=True)
    s.text(228, 354, "HTTP on the loopback address only", size=7.1)
    node(s, 490, 80, 112, 76, "«process»")
    s.text(546, 124, "MCP client\n(optional)")
    s.line([(416, 104), (490, 104)])
    s.text(462, 91, "stdio,\nJSON-RPC", size=7.1, back=True)
    s.save()


def states():
    s = Sheet("states", 626, 236)
    s.start(24, 104)
    s.rounded(96, 76, 140, 56, "Waiting\nshown as a comparison", radius=9)
    s.rounded(430, 26, 140, 52, "Accepted\nwritten to the file", radius=9)
    s.rounded(430, 136, 140, 52, "Rejected\nfile left alone", radius=9)
    s.stop(600, 52)
    s.stop(600, 162)
    s.line([(31, 104), (96, 104)], "fill")
    s.text(60, 92, "proposed", size=7.1)
    s.line([(236, 92), (330, 52), (430, 52)], "fill")
    s.text(330, 28, "Accept [file unchanged since proposal]\n/ write the new text", size=7.2, back=True)
    s.line([(236, 118), (330, 162), (430, 162)], "fill")
    s.text(330, 180, "Reject", size=7.2, back=True)
    s.line([(570, 52), (591, 52)], "fill")
    s.line([(570, 162), (591, 162)], "fill")
    s.line([(150, 132), (150, 192), (190, 192), (190, 132)], "fill")
    s.text(170, 212, "Accept [file changed] / report it, write nothing", size=7.2, back=True)
    s.save()


def classes():
    s = Sheet("classes", 626, 560)

    def cls(x, y, w, name, fields, methods, stereotype=None):
        head = 22 if not stereotype else 34
        h = head + 12 * len(fields) + 6 + 12 * len(methods) + 6
        s.rect(x, y, w, h, z=2)
        if stereotype:
            s.text(x + w / 2, y + 10, stereotype, size=7.1)
            s.text(x + w / 2, y + 23, name, weight="bold")
        else:
            s.text(x + w / 2, y + 11, name, weight="bold")
        s.line([(x, y + head), (x + w, y + head)])
        for i, field in enumerate(fields):
            s.text(x + 6, y + head + 9 + 12 * i, field, ha="left", size=7)
        sep = y + head + 12 * len(fields) + 6
        s.line([(x, sep), (x + w, sep)])
        for i, method in enumerate(methods):
            s.text(x + 6, sep + 9 + 12 * i, method, ha="left", size=7)
        return h

    cls(200, 14, 226, "Vault", ["root : URL", "store : URL", "everything : Bool"], ["refresh(embedder) : IndexReport", "retrieve(question, mode, scope) : Retrieved", "ask(question, mode, answerer) : Answer", "addNote(text, kind) : String", "neighbours(of) : [Neighbour]", "stats() : VaultStats", "applyChange(path, expecting, with)"])
    cls(14, 14, 142, "Database", ["handle, lock"], ["execute(sql)", "rows(sql, arguments)", "transaction(work)"])
    cls(14, 150, 142, "Chunker", ["aim = 45, most = 80", "mostCharacters = 3,000"], ["chunks(of) : [Chunk]"], "«utility»")
    cls(14, 268, 142, "Scanner", ["dataExtensions"], ["paths(in) : [String]", "read(path, in) : Found"], "«utility»")
    cls(14, 390, 142, "LinkFinder", [], ["links(files, notes) : [Link]", "definedSymbols(in) : Set"], "«utility»")
    cls(472, 14, 142, "Budget", ["characters = 12,000", "entryFiles = 4", "hops = 2", "longestExcerpt = 3,000"], [])
    cls(472, 122, 142, "Mode", ["none", "search", "walk"], [], "«enumeration»")
    cls(200, 240, 226, "Retrieved", ["mode : Mode", "excerpts : [Excerpt]", "seconds : Double"], ["paths : [String]"])
    cls(200, 346, 226, "Excerpt", ["path : String", "startLine, endLine : Int", "text : String", "reason : Reason", "isNote : Bool"], [])
    cls(472, 240, 142, "Reason", ["search", "link(from, kind, via)"], [], "«enumeration»")
    cls(472, 346, 142, "Asked", ["wantsTests, wantsOutput", "names"], ["weight(of) : Double"])
    cls(472, 448, 142, "Standing", ["main", "test", "output"], [], "«enumeration»")
    cls(200, 470, 226, "«protocol» Embedder, Answerer", [], ["embed(texts) : [[Float]]", "answer(system, user, onWord) : ChatResult"])
    s.line([(200, 50), (156, 50)], "open")
    s.text(178, 41, "1", size=7.1)
    s.line([(200, 140), (178, 140), (178, 180), (156, 180)], "open", dashed=True)
    s.line([(200, 152), (184, 152), (184, 300), (156, 300)], "open", dashed=True)
    s.line([(200, 160), (190, 160), (190, 425), (156, 425)], "open", dashed=True)
    s.line([(200, 166), (195, 166), (195, 505), (200, 505)], "open", dashed=True)
    s.line([(426, 40), (472, 40)], "open", dashed=True)
    s.line([(426, 130), (450, 130), (450, 155), (472, 155)], "open", dashed=True)
    s.line([(313, 168), (313, 240)], "open", dashed=True)
    s.text(322, 226, "creates", size=7.1, ha="left")
    s.line([(313, 318), (313, 346)], "open")
    s.text(305, 340, "0..*", size=7.1, ha="right")
    s.line([(426, 385), (449, 385), (449, 270), (472, 270)], "open")
    s.line([(543, 416), (543, 448)], "open", dashed=True)
    s.save()


def framework():
    s = Sheet("framework", 626, 400)
    columns = [(10, 176, "Input variables"), (206, 214, "Processing variables"), (440, 176, "Output variables")]
    for x, w, words in columns:
        s.rect(x, 26, w, 346)
        s.text(x + w / 2, 15, words, weight="bold", size=8.4)
    for y, words in [(68, "Question or task\nasked by the person"), (138, "Markdown notes\ndecisions, rejected fixes,\nreasons, general notes"), (214, "Linked code folders\nread-only source files"), (290, "Real issues and\nsynthetic task briefs\n(evaluation only)")]:
        s.rect(22, y - 30, 152, 60, words)
    s.rect(218, 40, 190, 66, "Index\npieces, words, vectors, links\n(rebuilt from the files)")
    s.rect(218, 126, 190, 112)
    s.text(313, 138, "Memory condition", weight="bold")
    s.rect(230, 150, 166, 24, "None: no excerpts")
    s.rect(230, 178, 166, 24, "Search: words and meaning")
    s.rect(230, 206, 166, 24, "Walk: search, then links")
    s.rect(218, 258, 190, 44, "Same 12,000 character limit,\nsame reading allowance, same seed")
    s.rect(218, 318, 190, 42, "Local Qwen3 model through Ollama")
    for y, words in [(62, "Answer naming files\nand lines"), (118, "Later tasks passed"), (168, "Earlier decisions kept"), (224, "“Not recorded” when no\nreason was written down"), (284, "Changed files reached\non real bug fixes"), (340, "Index size and speed")]:
        s.rect(452, y - 22, 152, 44, words)
    s.line([(174, 200), (218, 200)], "fill")
    s.line([(313, 106), (313, 126)], "fill")
    s.line([(313, 238), (313, 258)], "fill")
    s.line([(313, 302), (313, 318)], "fill")
    s.line([(408, 200), (452, 200)], "fill")
    s.line([(528, 372), (528, 390), (98, 390), (98, 372)], "fill", dashed=True)
    s.text(313, 390, "kept answers become notes for later questions", size=7.2, back=True)
    s.save()


def procedure():
    s = Sheet("procedure", 626, 214)
    steps = [(8, "Problem and\nobjectives"), (134, "Build the\nartefact"), (260, "Tune on the\ntuning project"), (386, "Freeze a\ntagged version"), (512, "Score held-back\nprojects once")]
    for x, words in steps:
        s.rounded(x, 28, 106, 58, words, radius=8)
    for x in (114, 240, 366, 492):
        s.line([(x, 57), (x + 20, 57)], "fill")
    s.rounded(260, 138, 106, 58, "Find faults,\nlog decisions", radius=8)
    s.line([(313, 86), (313, 138)], "fill")
    s.line([(260, 167), (187, 167), (187, 86)], "fill")
    s.text(224, 158, "revise", size=7.2, back=True)
    s.rounded(512, 138, 106, 58, "Report every\nresult, once", radius=8)
    s.line([(565, 86), (565, 138)], "fill")
    s.text(573, 112, "no changes after this point", size=7.1, ha="right", back=True)
    s.save()


def methodology():
    s = Sheet("methodology", 626, 300)
    stages = [(10, "Establish\nprototype\nobjectives"), (167, "Define\nprototype\nfunctionality"), (324, "Develop\nprototype"), (481, "Evaluate\nprototype")]
    outputs = ["Prototyping plan", "Outline definition", "Executable prototype", "Evaluation report"]
    for (x, words), out in zip(stages, outputs):
        s.rounded(x, 28, 135, 70, words, radius=8)
        s.rect(x + 12, 142, 111, 34, out)
        s.line([(x + 67, 98), (x + 67, 142)], "fill")
    for x in (145, 302, 459):
        s.line([(x, 63), (x + 22, 63)], "fill")
    s.line([(548, 176), (548, 216), (234, 216), (234, 176)], "fill", dashed=True)
    s.text(391, 216, "Iterate in short cycles: refine what the evaluation exposed", size=7.4, back=True)
    s.rounded(10, 240, 606, 50, "Stages applied in this project (Section 3.4): planning, initial prototype development,\niterative refinement, testing and final prototype evaluation", radius=6, size=7.5)
    s.save()


def domain():
    s = Sheet("domain", 626, 430)

    def cls(x, y, w, name, rows):
        h = 20 + 13.5 * len(rows) + 6
        s.rect(x, y, w, h, z=2)
        s.rect(x, y, w, 20, name, weight="bold", z=3)
        for i, row in enumerate(rows):
            s.text(x + 6, y + 31 + 13.5 * i, row, ha="left", size=7.3)
        return h

    cls(10, 14, 130, "Person", ["name", "asks questions", "accepts changes"])
    cls(246, 14, 134, "Vault", ["folder", "index is disposable"])
    cls(486, 14, 130, "LinkedFolder", ["name", "read-only"])
    cls(10, 152, 130, "Question", ["text", "folder limit (optional)", "mode"])
    cls(246, 152, 134, "File", ["path", "is note or code", "content hash"])
    cls(486, 152, 130, "Link", ["kind: imports, uses, about", "name that made it"])
    cls(10, 296, 130, "Answer", ["text", "files and lines used"])
    cls(246, 296, 134, "Piece", ["start and end line", "text", "vector (optional)"])
    cls(486, 296, 130, "ProposedChange", ["file", "text it was based on", "state"])
    def lab(x, y, words):
        s.text(x, y, words, size=7.2, back=True)
    s.line([(140, 40), (246, 40)]); lab(152, 31, "1"); lab(236, 31, "1..*"); lab(193, 50, "opens")
    s.line([(380, 40), (486, 40)]); lab(392, 31, "1"); lab(474, 31, "0..*"); lab(433, 50, "links in")
    s.line([(313, 67), (313, 152)]); lab(322, 78, "1"); lab(325, 142, "0..*"); lab(290, 110, "holds")
    s.line([(551, 67), (551, 118), (350, 118), (350, 152)]); lab(560, 78, "1"); lab(362, 142, "0..*"); lab(452, 118, "contains")
    s.line([(75, 80.5), (75, 152)]); lab(84, 92, "1"); lab(87, 142, "0..*"); lab(52, 115, "asks")
    s.line([(75, 218.5), (75, 296)]); lab(84, 230, "1"); lab(84, 286, "1"); lab(45, 258, "answered by")
    s.line([(380, 190), (486, 190)]); lab(392, 181, "1"); lab(474, 181, "0..*"); lab(433, 200, "source / target")
    s.line([(313, 218.5), (313, 296)]); lab(322, 230, "1"); lab(325, 286, "1..*"); lab(290, 258, "cut into")
    s.line([(140, 340), (246, 340)], "open"); lab(152, 331, "0..*"); lab(236, 331, "1..*"); lab(193, 350, "cites")
    s.line([(75, 349), (75, 402), (551, 402), (551, 362.5)], "open"); lab(313, 402, "may propose"); lab(84, 361, "1"); lab(563, 374, "0..1")
    s.save()


def activity_index():
    s = Sheet("activity_index", 560, 560)
    cx = 280
    s.start(cx, 16)
    steps = [(46, "List files in the vault and linked folders,\nleaving out hidden, ignored and large data files"), (104, "Compute a digest of each file and compare\nit with the digest stored in the index")]
    for y, words in steps:
        s.rounded(cx - 150, y, 300, 40, words)
    s.line([(cx, 22), (cx, 46)], "fill")
    s.line([(cx, 86), (cx, 104)], "fill")
    s.line([(cx, 144), (cx, 164)], "fill")
    s.diamond(cx, 179)
    s.text(cx + 22, 171, "[file changed, new or\nindex is out of date]", ha="left", size=7.2)
    s.text(cx - 22, 171, "[unchanged]", ha="right", size=7.2)
    s.rounded(cx - 150, 216, 300, 40, "Remove the file's old pieces, cut it into\npieces of at most 80 lines and 3,000 characters")
    s.rounded(cx - 150, 276, 300, 30, "Store the pieces in the full-text table")
    s.line([(cx, 194), (cx, 216)], "fill")
    s.line([(cx, 256), (cx, 276)], "fill")
    s.line([(cx, 306), (cx, 326)], "fill")
    s.rounded(cx - 150, 326, 300, 40, "Rebuild every link from imports, name\nuses, wiki links and notes that name code")
    s.line([(cx - 15, 179), (70, 179), (70, 346), (cx - 150, 346)], "fill")
    s.line([(cx, 366), (cx, 386)], "fill")
    s.diamond(cx, 401)
    s.text(cx + 22, 393, "[Ollama reachable]", ha="left", size=7.2)
    s.text(cx - 22, 393, "[not reachable]", ha="right", size=7.2)
    s.line([(cx, 416), (cx, 436)], "fill")
    s.rounded(cx - 150, 436, 300, 30, "Compute a vector for each piece without one")
    s.line([(cx, 466), (cx, 486)], "fill")
    s.rounded(cx - 150, 486, 300, 30, "Report what was added, changed and removed")
    s.line([(cx - 15, 401), (70, 401), (70, 501), (cx - 150, 501)], "fill")
    s.line([(cx, 516), (cx, 536)], "fill")
    s.stop(cx, 545)
    s.save()


def sequence_change():
    s = Sheet("sequence_change", 626, 470)
    names = [(46, ":Person"), (190, ":Workspace"), (340, ":Vault"), (470, ":File system"), (580, ":Ollama")]
    for x, words in names:
        s.rect(x - 42, 8, 84, 28, words)
        s.line([(x, 36), (x, 458)], dashed=True, lw=0.6)
    for x, a, b in [(190, 58, 440), (340, 84, 128), (580, 140, 190), (340, 318, 410), (470, 336, 396)]:
        s.rect(x - 4, a, 8, b - a, z=4)

    def message(a, b, y, words, reply=False):
        s.line([(a, y), (b, y)], "open" if reply else "fill", dashed=reply)
        s.text((a + b) / 2, y - 7, words, back=True, size=7.2)

    message(46, 186, 62, "ask for a change")
    message(194, 336, 88, "retrieve(question)")
    message(336, 194, 124, "excerpts", True)
    message(194, 576, 146, "chat(change rules, excerpts, request)")
    message(576, 194, 186, "reply with whole file text", True)
    message(186, 50, 216, "show proposal, line by line", True)
    y = 244
    s.rect(112, y, 500, 192, z=1)
    s.rect(112, y, 34, 16, "alt", size=7.2)
    s.text(152, y + 8, "[person accepts]", ha="left", size=7.2, back=True)
    message(46, 186, y + 34, "accept")
    message(194, 336, y + 74, "applyChange(path, expected, new)")
    message(344, 466, y + 94, "read current text")
    message(466, 344, y + 112, "current text", True)
    message(344, 466, y + 136, "write only if it matches expected")
    message(336, 194, y + 166, "written, or changed since", True)
    s.line([(112, 424), (612, 424)], dashed=True, lw=0.6)
    s.text(118, 431, "[person rejects: nothing is written]", ha="left", size=7.2, back=True)
    s.save()


def _window(s, x, y, w, h, title=True):
    s.rect(x, y, w, h, line=1.0)
    if title:
        s.rect(x, y, w, 26, line=0.8)
        for i in range(3):
            s.ax.add_patch(Ellipse((x + 12 + 11 * i, y + 13), 7, 7, facecolor="white", edgecolor=INK, lw=0.7, zorder=4))


def wire_main():
    s = Sheet("wire_main", 626, 390)
    _window(s, 8, 8, 610, 374)
    s.text(105, 21, "New  |  Hide sidebar", size=7.1)
    s.text(300, 21, "Back  Forward   Vault name, counts of notes, files, links", size=7.1)
    s.text(575, 21, "Search  Inspector", size=7.1)
    s.rect(8, 34, 140, 348)
    s.rect(16, 42, 124, 22, "Files | Search | Tags", size=7.2)
    s.rect(16, 70, 124, 20, "Graph", size=7.2)
    s.rect(16, 94, 124, 20, "Ask", size=7.2)
    s.rect(16, 122, 124, 200, "File tree\nfolders first\nlinked folders marked", size=7.2)
    s.rect(16, 330, 124, 44, "Add: note, folder,\ntoday's note, link a folder", size=7.2)
    s.rect(148, 34, 320, 26)
    s.rect(154, 39, 90, 16, "Open tab", size=7.1)
    s.rect(248, 39, 22, 16, "+", size=7.1)
    s.rect(148, 60, 320, 322)
    s.text(308, 80, "Note title", weight="bold", size=8.2)
    s.rect(172, 96, 272, 34, "Properties from the note's front matter", size=7.2)
    s.rect(172, 138, 272, 220, "Editor and reading view\n\nMarkdown marks visible only on the line being edited\nWiki links open the linked note\nTyping [[ opens the note suggestions", size=7.4)
    s.rect(468, 34, 150, 348)
    s.rect(476, 44, 134, 86, "Local graph\nthe note and its neighbours", size=7.2)
    s.rect(476, 138, 134, 62, "Outline\nheadings in the note", size=7.2)
    s.rect(476, 208, 134, 76, "Links\nlinks out and\nmentions of this note", size=7.2)
    s.rect(476, 292, 134, 80, "Latest answer\nshown after a question", size=7.2)
    s.save()


def wire_ask():
    s = Sheet("wire_ask", 626, 430)
    _window(s, 8, 8, 610, 414)
    s.text(313, 21, "Toolbar, as in the main window", size=7.1)
    s.rect(8, 34, 120, 388, "Sidebar", size=7.4)
    s.text(372, 54, "Ask your vault", weight="bold", size=8.4)
    s.text(372, 70, "The model on this Mac reads only what Burrow finds", size=7.2)
    s.rect(150, 84, 444, 30, "Previous question (right aligned)", size=7.2)
    s.rect(150, 122, 444, 40, "Reading strip: file and lines read, shown before the answer begins", size=7.2)
    s.rect(150, 170, 444, 74, "Answer text with file and line citations", size=7.4)
    s.rect(150, 252, 444, 26, "Used: files and lines, each opens at the line", size=7.2)
    s.rect(150, 286, 300, 60, "Proposed change (when asked for)\nold and new lines side by side", size=7.2)
    s.rect(460, 286, 64, 26, "Accept", size=7.2)
    s.rect(530, 286, 64, 26, "Reject", size=7.2)
    s.rect(460, 320, 134, 26, "Keep as Note", size=7.2)
    s.rect(150, 362, 106, 40, "Folder limit\nEverything or one folder", size=7.1)
    s.rect(264, 362, 268, 40, "Ask field", size=7.4)
    s.rect(540, 362, 24, 40, "Δ", size=8)
    s.rect(570, 362, 24, 40, "↑", size=8)
    s.save()


def wire_graph():
    s = Sheet("wire_graph", 626, 370)
    _window(s, 8, 8, 610, 354)
    s.text(313, 21, "Toolbar, as in the main window", size=7.1)
    s.rect(8, 34, 120, 328, "Sidebar", size=7.4)
    s.rect(128, 34, 340, 328)
    s.rect(138, 44, 104, 72, "Filter\nNotes\nCode and files\nUnconnected", size=7.2)
    s.rect(260, 80, 196, 200, "Force-directed graph\n\nfile = node, link = line\nfolders gather and are named\nfiles read for an answer brighten", size=7.3)
    s.rect(150, 324, 300, 26, "Ask field", size=7.4)
    s.rect(150, 296, 150, 18, "Activity strip while answering", size=7.1)
    s.rect(468, 34, 150, 328, "Inspector\n\nlatest question\nand answer", size=7.4)
    s.save()


def wire_terminal():
    s = Sheet("wire_terminal", 626, 300)
    s.rect(8, 8, 610, 284, line=1.0)
    s.rect(8, 8, 150, 256, "Tree pane\nfolders first,\nlinked folders marked\nfolds and unfolds", size=7.3)
    s.rect(158, 8, 300, 256, "Reading pane\n\ntext capped at 80 columns\nheadings, lists, code, tables, wiki links\nfollow a link and come back", size=7.3)
    s.rect(458, 8, 160, 256, "Side pane\nbacklinks, outline,\nanswer and its sources\n\n(dropped in middle-sized\nwindows)", size=7.3)
    s.rect(8, 264, 610, 28, "Key hints, status and the Ask line  |  below 40 by 12 the view says the window is too small", size=7.3)
    s.save()


def screen_flow():
    s = Sheet("screen_flow", 626, 300)
    s.rounded(10, 120, 112, 56, "Open a vault\n(choose a folder)")
    s.rounded(170, 120, 112, 56, "Main window\nfile tree, tabs,\ninspector")
    s.rounded(340, 20, 118, 50, "Note page\nedit or read")
    s.rounded(340, 90, 118, 50, "Graph page")
    s.rounded(340, 160, 118, 50, "Ask page")
    s.rounded(340, 230, 118, 50, "Search and tags\n(sidebar)")
    s.rounded(504, 124, 112, 46, "Review change\naccept or reject")
    s.rounded(504, 196, 112, 46, "Kept note")
    s.line([(122, 148), (170, 148)], "fill")
    for y in (45, 115, 185, 255):
        s.line([(282, 148), (311, 148), (311, y), (340, y)], "fill")
    s.line([(458, 175), (480, 175), (480, 147), (504, 147)], "fill")
    s.line([(458, 195), (480, 195), (480, 219), (504, 219)], "fill")
    s.line([(399, 90), (399, 70)], "fill")
    s.text(434, 80, "click a node", size=7.1, back=True)
    s.line([(399, 160), (399, 140)], "fill", dashed=True)
    s.text(447, 150, "files read brighten", size=7.1, back=True)
    s.save()



if __name__ == "__main__":
    for draw in (use_cases, activity, activity_index, architecture, sequence, sequence_change, schema, deployment, states, classes, domain, framework, procedure, methodology, wire_main, wire_ask, wire_graph, wire_terminal, screen_flow):
        draw()
