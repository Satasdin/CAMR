#!/usr/bin/env python3
"""Draws the diagrams of the rewritten Chapter 4 into figures/v2/.
Same hand-placed grid as diagrams.py: one unit is 0.01 inch, so 626 is the printed text width of an A4 page.
Run: python3 docs/report/figures/diagrams2.py [name ...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Polygon

from diagrams import INK, SIZE, Sheet as OldSheet, component, node

OUT = Path(__file__).parent / "v2"
SMALL = 7.1


class Sheet(OldSheet):
    def save(self):
        OUT.mkdir(exist_ok=True)
        self.figure.savefig(OUT / f"{self.name}.png", dpi=300, facecolor="white")
        plt.close(self.figure)

    def hollow(self, a, b, length=10, half=5.5):
        """A line from a to b ending in the hollow triangle of a generalisation."""
        import math
        angle = math.atan2(b[1] - a[1], b[0] - a[0])
        ux, uy = math.cos(angle), math.sin(angle)
        base = (b[0] - length * ux, b[1] - length * uy)
        self.line([a, base])
        left = (base[0] - half * uy, base[1] + half * ux)
        right = (base[0] + half * uy, base[1] - half * ux)
        self.ax.add_patch(Polygon([left, b, right], closed=True, facecolor="white", edgecolor=INK, lw=0.8, zorder=5))

    def note(self, x, y, w, h, words, size=SMALL):
        """A UML note: a rectangle with a folded corner."""
        fold = 8
        self.ax.add_patch(Polygon([(x, y), (x + w - fold, y), (x + w, y + fold), (x + w, y + h), (x, y + h)], closed=True,
                                  facecolor="white", edgecolor=INK, lw=0.7, zorder=3))
        self.line([(x + w - fold, y), (x + w - fold, y + fold), (x + w, y + fold)], lw=0.7)
        self.text(x + w / 2, y + h / 2, words, size=size)


def act(s, cx, cy, words, w=172, h=38, size=SIZE):
    s.rounded(cx - w / 2, cy - h / 2, w, h, words, radius=7, size=size)


# ---------------------------------------------------------------- analysis

def use_cases():
    s = Sheet("use_cases", 626, 470)
    s.rect(112, 8, 392, 454, line=0.9, z=1)
    s.text(308, 22, "Burrow", weight="bold", size=8.4)

    person = (50, 250)
    s.actor(*person, "Person")
    left = [(90, "Index a vault"), (250, "Ask a question"), (340, "Keep what a\nconversation decided"), (424, "Measure a model")]
    for y, words in left:
        s.ellipse(208, y, 152, 46, words)
        s.line([(person[0] + 16, person[1] - 6), (132, y)])

    s.ellipse(408, 66, 156, 46, "Prepare a task for\nanother model")
    s.ellipse(408, 150, 156, 46, "Decide and pack\nthe excerpts")
    s.ellipse(408, 226, 156, 46, "Check the citations")

    # Ask includes deciding and checking; preparing a task includes deciding.
    s.line([(250, 231), (352, 167)], "open", dashed=True)
    s.text(280, 192, "«include»", size=SMALL, back=True)
    s.line([(282, 244), (331, 232)], "open", dashed=True)
    s.text(306, 252, "«include»", size=SMALL)
    s.line([(408, 89), (408, 127)], "open", dashed=True)
    s.text(436, 108, "«include»", size=SMALL, back=True)

    s.actor(570, 52, "Outside model\nor tool")
    s.line([(553, 50), (486, 64)])
    s.actor(570, 176, "Cloud model\n(evaluation only)")
    s.hollow((570, 146), (570, 106))

    s.actor(570, 340, "Local model\n(Ollama)")
    s.line([(553, 330), (283, 256)])
    s.line([(553, 338), (284, 340)])
    s.line([(553, 346), (282, 418)])
    s.save()


def activity():
    s = Sheet("activity", 626, 838)
    s.rect(4, 6, 618, 826, z=1)
    s.line([(134, 6), (134, 832)])
    s.line([(470, 6), (470, 832)])
    s.line([(4, 28), (622, 28)])
    for x, words in [(69, "Person"), (302, "Burrow engine"), (546, "Local model")]:
        s.text(x, 17, words, weight="bold", size=8.2)
    P, E, M = 69, 302, 546

    s.start(P, 46)
    act(s, P, 88, "Ask a question", w=112, h=30)
    s.line([(P, 53), (P, 73)], "fill")
    act(s, E, 88, "Search the vault once: closeness of the\nnearest piece, number of word matches", w=220)
    s.line([(125, 88), (192, 88)], "fill")

    # Decide
    s.diamond(E, 146)
    s.line([(E, 107), (E, 131)], "fill")
    s.text(E - 22, 137, "[nothing close]", size=SMALL, ha="right")
    s.text(E + 7, 170, "[close enough]", size=SMALL, ha="left")
    act(s, 196, 226, "Leave the vault\nout", w=100)
    s.line([(E - 15, 146), (196, 146), (196, 207)], "fill")
    s.diamond(E, 200)
    s.line([(E, 161), (E, 185)], "fill")
    s.text(E + 20, 191, "[closest files are code]", size=SMALL, ha="left")
    s.text(E - 6, 268, "[notes,\ndocuments]", size=SMALL, ha="right")
    act(s, 404, 248, "Follow the links\nbetween files", w=112)
    s.line([(E + 15, 200), (404, 200), (404, 229)], "fill")
    s.diamond(E, 306)
    s.line([(E, 215), (E, 291)], "fill")
    s.line([(196, 245), (196, 306), (E - 15, 306)], "fill")
    s.line([(404, 267), (404, 306), (E + 15, 306)], "fill")

    act(s, E, 356, "Match one skill to the question,\nor fall back by the kind of material", w=220)
    s.line([(E, 321), (E, 337)], "fill")
    # Fit, answer
    act(s, E, 414, "Pack rules, skill and excerpts within\nthe model's character budget", w=220)
    s.line([(E, 375), (E, 395)], "fill")
    act(s, M, 414, "Answer from the\nexcerpts shown", w=128)
    s.line([(412, 414), (482, 414)], "fill")
    # Check
    act(s, E, 474, "Check every file and line cited\nagainst the excerpts shown", w=220)
    s.line([(M, 433), (M, 474), (412, 474)], "fill")
    s.diamond(E, 530)
    s.line([(E, 493), (E, 515)], "fill")
    s.text(E + 20, 515, "[a citation was not shown]", size=SMALL, ha="left")
    s.text(E - 7, 562, "[all shown]", size=SMALL, ha="right")
    act(s, M, 530, "Answer again with\nthe correction", w=128)
    s.line([(E + 15, 530), (482, 530)], "fill")
    act(s, 392, 592, "Keep the second answer\nonly if it is better grounded", w=148)
    s.line([(M, 549), (M, 592), (466, 592)], "fill")
    act(s, E, 654, "Report the answer, the decision\nand any citation left unverified", w=220)
    s.line([(E, 545), (E, 635)], "fill")
    s.line([(392, 611), (392, 635)], "fill")
    act(s, P, 654, "Read the answer\nand its sources", w=112)
    s.line([(192, 654), (125, 654)], "fill")

    # Learn
    s.diamond(P, 712)
    s.line([(P, 673), (P, 697)], "fill")
    s.text(P + 18, 703, "[keep]", size=SMALL, ha="left")
    s.text(P - 7, 738, "[done]", size=SMALL, ha="right")
    act(s, E, 712, "Ask the model what the person decided", w=220, h=30)
    s.line([(P + 15, 712), (192, 712)], "fill")
    act(s, M, 712, "List decisions, each\nwith the person's words", w=134)
    s.line([(412, 712), (479, 712)], "fill")
    act(s, E, 766, "Drop any item the person did not say,\nor that the vault already holds", w=220)
    s.line([(M, 731), (M, 766), (412, 766)], "fill")
    act(s, P, 790, "Accept or decline\neach note", w=112)
    s.line([(192, 772), (160, 772), (160, 790), (125, 790)], "fill")
    act(s, E, 812, "Write accepted notes, refresh the index", w=220, h=28)
    s.line([(125, 798), (160, 798), (160, 812), (192, 812)], "fill")
    s.stop(P, 754)
    s.line([(P, 727), (P, 745)], "fill")
    s.stop(444, 812)
    s.line([(412, 812), (435, 812)], "fill")
    s.save()


def _lifelines(s, names, bottom, half=44):
    for x, words in names:
        s.rect(x - half, 8, 2 * half, 28, words)
        s.line([(x, 36), (x, bottom)], dashed=True, lw=0.6)


def _message(s, a, b, y, words, reply=False, size=7.2):
    s.line([(a, y), (b, y)], "open" if reply else "fill", dashed=reply)
    s.text((a + b) / 2, y - 7, words, back=True, size=size)


def _self(s, x, y, words, size=7.2, drop=16):
    s.line([(x + 4, y), (x + 30, y), (x + 30, y + drop), (x + 4, y + drop)], "fill")
    s.text(x + 36, y + drop / 2, words, ha="left", size=size, back=True)


def _frame(s, x, y, w, h, kind, guard, guard_x=None):
    s.rect(x, y, w, h, z=1)
    s.rect(x, y, 30, 15, kind, size=7.2, z=3)
    s.text(guard_x or x + 36, y + 9, guard, ha="left", size=7.2)


def sequence_engine():
    s = Sheet("sequence_engine", 626, 640)
    P, C, V, I, O = 40, 164, 304, 446, 576
    _lifelines(s, [(P, ":Person"), (C, ":burrow"), (V, ":Vault"), (I, ":Index"), (O, ":Ollama")], 628, half=38)
    for x, a, b in [(C, 58, 612), (V, 76, 104), (V, 122, 592), (O, 140, 164), (I, 186, 210), (I, 250, 274), (O, 330, 356), (O, 462, 488)]:
        s.rect(x - 4, a, 8, b - a, z=4)

    _message(s, P, C - 4, 62, "ask(question)")
    _message(s, C + 4, V - 4, 80, "profile(for: model)")
    _message(s, V - 4, C + 4, 102, "budget and window", True)
    _message(s, C + 4, V - 4, 126, "engage(question, profile)")
    _message(s, V + 4, O - 4, 144, "embed(question)")
    _message(s, O - 4, V + 4, 162, "vector", True)
    _message(s, V + 4, I - 4, 190, "rank by words and meaning")
    _message(s, I - 4, V + 4, 208, "ranked pieces, signal", True)
    _frame(s, 250, 224, 250, 60, "opt", "[closest files are code]", V + 10)
    _message(s, V + 4, I - 4, 256, "neighbours(entry files)")
    _message(s, I - 4, V + 4, 274, "linked pieces", True)
    _self(s, V, 296, "choose route and skill,\npack the excerpts")
    _message(s, V + 4, O - 4, 334, "answer(rules, skill, excerpts, question)")
    _message(s, O - 4, V + 4, 354, "first answer", True)
    _message(s, V - 4, C + 4, 372, "words as they arrive", True)
    _self(s, V, 388, "check each file:line cited\nagainst the excerpts")
    _frame(s, 250, 426, 368, 124, "opt", "[a citation was not shown]", V + 10)
    _message(s, V + 4, O - 4, 466, "answer(same prompt + correction)")
    _message(s, O - 4, V + 4, 486, "second answer", True)
    _self(s, V, 502, "check again; keep the second\nanswer only if it is better grounded", drop=20)
    _message(s, V - 4, C + 4, 590, "EngineReply", True)
    _message(s, C - 4, P, 610, "answer, decision line", True)
    s.save()


def sequence_mcp():
    s = Sheet("sequence_mcp", 626, 540)
    X, S, T, V, I, O = 46, 178, 296, 404, 498, 584
    _lifelines(s, [(X, ":Outside model"), (S, ":MCPServer"), (T, ":VaultTools"), (V, ":Vault"), (I, ":Index"), (O, ":Ollama")], 528, half=40)
    for x, a, b in [(S, 58, 84), (S, 108, 462), (T, 128, 444), (V, 196, 390), (O, 216, 240), (I, 264, 288), (I, 328, 352)]:
        s.rect(x - 4, a, 8, b - a, z=4)

    _message(s, X, S - 4, 62, "tools/list")
    _message(s, S - 4, X, 82, "eight tool definitions", True)
    _message(s, X, S - 4, 112, "tools/call vault_prepare")
    _message(s, S + 4, T - 4, 132, "call(name, arguments)")
    _self(s, T, 146, "re-index only if\nfiles changed")
    _message(s, T + 4, V - 4, 200, "brief(task, budget)")
    _message(s, V + 4, O - 4, 220, "embed(task)")
    _message(s, O - 4, V + 4, 238, "vector", True)
    _message(s, V + 4, I - 4, 268, "rank pieces")
    _message(s, I - 4, V + 4, 286, "pieces, signal", True)
    _frame(s, 356, 300, 190, 62, "opt", "[closest files are code]", V + 10)
    _message(s, V + 4, I - 4, 334, "neighbours")
    _message(s, I - 4, V + 4, 352, "linked pieces", True)
    _message(s, V - 4, T + 4, 388, "Brief", True)
    _self(s, T, 400, "write the decision line, the method\nand the excerpts, marked as data", drop=20)
    _message(s, T - 4, S + 4, 442, "ToolResult", True)
    _message(s, S - 4, X, 460, "result as text", True)
    _self(s, X, 480, "answers with its own model;\nBurrow calls no chat model", drop=20)
    s.save()


# ---------------------------------------------------------------- design

def engine_steps():
    s = Sheet("engine_steps", 626, 306)
    steps = [("1  Decide", "Is the vault needed?\nSearch, or follow links?\nWhich skill fits?"),
             ("2  Fit", "How much can this\nmodel read? Set the\nbudget and the window."),
             ("3  Answer", "The frozen local\nmodel answers from\nthe excerpts."),
             ("4  Check", "Was every file:line\ncited really shown?\nRetry once if not."),
             ("5  Learn", "Propose notes of what\nthe person decided.\nWrite with consent.")]
    w, gap, top = 112, 14, 62
    xs = [6 + i * (w + gap) for i in range(5)]
    for x, (name, words) in zip(xs, steps):
        s.rect(x, top, w, 86)
        s.rect(x, top, w, 22, name, weight="bold", z=3)
        s.text(x + w / 2, top + 54, words, size=SMALL)
    for x in xs[:-1]:
        s.line([(x + w, top + 43), (x + w + gap, top + 43)], "fill")
    # What the proposal called each part.
    s.text(6, 12, "Named in the proposal as", ha="left", size=SMALL, style="italic")
    for i, words in [(0, "Retrieval policy"), (1, "Token budgeting\nmechanism"), (2, "Frozen small model"), (3, "Added in this study"), (4, "Write policy")]:
        s.rect(xs[i] + 6, 22, w - 12, 26, words, dashed=True, size=SMALL)
        s.line([(xs[i] + w / 2, 48), (xs[i] + w / 2, top)], dashed=True, lw=0.6)
    # What each step reads and writes.
    s.rect(6, 212, 242, 84)
    s.text(127, 224, "Index (rebuilt from the vault)", weight="bold")
    s.text(127, 262, "word index, vectors, links between files\nskills and their vectors\nmodel profiles", size=SMALL)
    s.rect(390, 212, 230, 84)
    s.text(505, 224, "Vault (the person's own files)", weight="bold")
    s.text(505, 262, "Markdown notes and documents\nlinked code folders\nSkills folder", size=SMALL)
    s.line([(xs[0] + w / 2, top + 86), (xs[0] + w / 2, 212)], "open", dashed=True)
    s.text(xs[0] + w / 2 + 5, 182, "reads", size=SMALL, ha="left")
    s.line([(xs[1] + w / 2 - 20, top + 86), (xs[1] + w / 2 - 20, 212)], "open", dashed=True)
    s.text(xs[1] + w / 2 - 15, 182, "reads the\nprofile", size=SMALL, ha="left")
    s.line([(xs[4] + w / 2, top + 86), (xs[4] + w / 2, 212)], "open", dashed=True)
    s.text(xs[4] + w / 2 - 5, 182, "writes notes", size=SMALL, ha="right")
    s.line([(390, 254), (248, 254)], "open", dashed=True)
    s.text(319, 245, "indexed into", size=SMALL)
    s.save()


def architecture():
    s = Sheet("architecture", 626, 470)
    s.text(8, 12, "Surfaces", ha="left", size=SMALL, style="italic")
    tops = [(8, "Burrow.app\ndesktop app"), (132, "burrow\ncommand line"), (256, "BurrowChat\nterminal chat"), (380, "BurrowTUI\nterminal view"), (504, "BurrowMCP\nMCP server")]
    for x, words in tops:
        component(s, x, 22, 114, 46, words)
    component(s, 256, 110, 362, 40, "BurrowTools: eight vault tools, defined once")
    for x in (313, 437, 561):
        s.line([(x, 68), (x, 110)], "open", dashed=True)
    s.rect(8, 192, 610, 150, z=1)
    s.text(16, 205, "«component»  BurrowCore", ha="left", weight="bold")
    s.rect(18, 218, 590, 50, z=2)
    s.text(26, 229, "Engine", ha="left", weight="bold", size=SMALL)
    for x, words in [(26, "Decide"), (142, "Fit"), (258, "Answer rules"), (374, "Check"), (490, "Learn")]:
        s.rect(x, 238, 108, 24, words, size=7.3, z=3)
    for x, words in [(18, "Retrieval\nsearch and walk"), (140, "Skills"), (262, "Vault and\nindex"), (384, "Vector index"), (506, "Ollama client")]:
        s.rect(x, 286, 102, 44, words, z=3)
    s.line([(65, 68), (65, 192)], "open", dashed=True)
    s.line([(189, 68), (189, 192)], "open", dashed=True)
    s.line([(437, 150), (437, 192)], "open", dashed=True)
    for x, w, words in [(18, 224, "Vault folder\nMarkdown notes, Skills, linked code"), (262, 224, ".burrow folder\nindex.sqlite, vectors.bin, models.json")]:
        s.rect(x, 400, w, 54, words)
    s.line([(313, 330), (313, 400)], "open", dashed=True)
    s.line([(280, 330), (280, 372), (130, 372), (130, 400)], "open", dashed=True)
    s.rect(506, 400, 112, 54, "Ollama\n127.0.0.1:11434")
    s.line([(557, 330), (557, 400)], "open", dashed=True)
    s.text(562, 366, "HTTP", size=SMALL, ha="left")
    s.save()


def classes():
    s = Sheet("classes", 626, 566)

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

    a, b, c, d = 4, 146, 348, 502          # column left edges
    wa, wb, wc, wd = 116, 180, 126, 120
    # Column 1: what the vault stands on.
    cls(a, 10, wa, "Database", ["handle, lock"], ["rows(sql)", "transaction(work)"])
    cls(a, 100, wa, "VectorIndex", ["ids : [Int]", "dimension : Int"], ["nearest(to, limit)", "similarity(of, to)"])
    cls(a, 206, wa, "Embedder, Answerer", [], ["embed(texts)", "answer(system, user)"], "«protocol»")
    cls(a, 302, wa, "Ollama", ["base : URL"], ["embedder()", "answerer(model)", "measure(model)"])
    cls(a, 424, wa, "Lesson", ["kind : NoteKind", "text : String", "quote : String"], [])
    # Column 2: the vault and what a question becomes.
    cls(b, 10, wb, "Vault", ["root : URL", "store : URL"],
        ["refresh(embedder) : IndexReport", "retrieve(question, mode) : Retrieved", "brief(question, budget) : Brief",
         "engage(question, profile) : EngineReply", "lessons(turns) : [Lesson]", "keep(lessons) : [String]",
         "profile(for model) : ModelProfile", "skills() : [Skill]"])
    cls(b, 196, wb, "Brief", ["route : Route", "skill : Skill?", "retrieved : Retrieved", "system, user : String", "seconds : Double"], [])
    cls(b, 320, wb, "Retrieved", ["mode : Mode", "excerpts : [Excerpt]", "signal : Signal", "seconds : Double"], ["paths : [String]", "characters : Int"])
    cls(b, 456, wb, "Excerpt", ["path : String", "startLine, endLine : Int", "text : String", "reason : Reason", "isNote : Bool"], [])
    # Column 3.
    cls(c, 10, wc, "EngineSettings", ["memoryFloor = 0.40", "looseMatch = 0.52", "skillFloor = 0.55", "skillMargin = 0.10", "useSkills, check : Bool"], [])
    cls(c, 124, wc, "EngineReply", ["brief : Brief", "result : ChatResult", "citations : [Citation]", "retried : Bool", "profile : ModelProfile"], ["unverified : [Citation]"])
    cls(c, 256, wc, "Route", ["mode : Mode", "why : String"], [])
    cls(c, 334, wc, "Skill", ["name, when : String", "body : String", "needsVault : Bool", "fallbackFor : String?"], [])
    cls(c, 442, wc, "Signal", ["nearest : Float?", "wordMatches : Int"], [])
    # Column 4.
    cls(d, 10, wd, "ModelProfile", ["model : String", "contextTokens : Int", "billions : Double", "readsPerSecond", "charactersPerToken", "budgetCharacters : Int", "windowTokens : Int"],
        ["fitted(...)", "budget : Budget"])
    cls(d, 176, wd, "Budget", ["characters = 12,000", "entryFiles = 4", "hops = 2", "longestExcerpt = 3,000"], [])
    cls(d, 276, wd, "Citation", ["path : String", "line : Int", "shown : Bool"], [])
    cls(d, 366, wd, "Mode", ["none", "search", "walk"], [], "«enumeration»")

    def lab(x, y, words, ha="center"):
        s.text(x, y, words, size=6.8, ha=ha)

    # Vault and its foundations.
    s.line([(b, 40), (a + wa, 40)], "open"); lab(133, 33, "1")
    s.line([(b, 130), (a + wa, 130)], "open"); lab(133, 123, "1")
    s.line([(b, 150), (128, 150), (128, 236), (a + wa, 236)], "open", dashed=True)
    s.line([(b, 158), (136, 158), (136, 452), (a + wa, 452)], "open", dashed=True)
    s.line([(a + wa / 2, 302), (a + wa / 2, 276)], "open", dashed=True); lab(a + wa / 2 + 5, 290, "provides", "left")
    # Vault creates a brief and a reply.
    s.line([(b + 90, 164), (b + 90, 196)], "open", dashed=True); lab(b + 95, 181, "creates", "left")
    s.line([(b + wb, 40), (c, 40)], "open", dashed=True)
    s.line([(b + wb, 144), (c, 144)], "open", dashed=True)
    s.line([(c, 222), (b + wb, 222)], "open"); lab(337, 215, "1")
    s.line([(b + wb, 272), (c, 272)], "open"); lab(337, 265, "1")
    s.line([(b + wb, 284), (337, 284), (337, 356), (c, 356)], "open"); lab(334, 306, "0..1", "right")
    s.line([(b + 90, 290), (b + 90, 320)], "open"); lab(b + 95, 306, "1", "left")
    s.line([(b + 90, 426), (b + 90, 456)], "open"); lab(b + 95, 442, "0..*", "left")
    s.line([(b + wb, 412), (337, 412), (337, 462), (c, 462)], "open"); lab(334, 441, "1", "right")
    # The reply, the profile and the budget.
    s.line([(c + wc, 134), (d, 134)], "open"); lab(488, 127, "1")
    s.line([(d + wd / 2, 152), (d + wd / 2, 176)], "open", dashed=True); lab(d + wd / 2 + 5, 165, "gives", "left")
    s.line([(c + wc, 220), (488, 220), (488, 286), (d, 286)], "open"); lab(491, 269, "0..*", "left")
    s.line([(c + wc, 304), (488, 304), (488, 400), (d, 400)], "open")
    s.save()


def states():
    s = Sheet("states", 626, 250)
    s.start(20, 86)
    s.rounded(52, 60, 124, 52, "Proposed\nby the model, with a quote", radius=9, size=7.3)
    s.rounded(306, 60, 118, 52, "Offered\nshown to the person", radius=9, size=7.3)
    s.rounded(478, 30, 118, 44, "Kept\nwritten as a note", radius=9, size=7.3)
    s.rounded(478, 108, 118, 44, "Declined\nnothing written", radius=9, size=7.3)
    s.rounded(52, 186, 124, 48, "Discarded\nnever shown", radius=9, size=7.3)
    s.stop(612, 52)
    s.stop(612, 130)
    s.stop(214, 210)
    s.line([(27, 86), (52, 86)], "fill")
    s.line([(176, 86), (306, 86)], "fill")
    s.text(241, 70, "[quote is in the person's\nwords, and it is new]", size=7)
    s.line([(424, 76), (478, 54)], "fill")
    s.text(432, 30, "accept / write\nthe note, refresh\nthe index", size=7)
    s.line([(424, 98), (478, 128)], "fill")
    s.text(440, 132, "decline", size=7)
    s.line([(114, 112), (114, 186)], "fill")
    s.text(122, 149, "[quote is not in the person's words,\nor the vault already holds the note]", size=7, ha="left")
    s.line([(596, 52), (603, 52)], "fill")
    s.line([(596, 130), (603, 130)], "fill")
    s.line([(176, 210), (205, 210)], "fill")
    s.save()


def schema():
    s = Sheet("schema", 626, 300)

    def table(x, y, w, name, rows, dashed=False):
        h = 22 + 15 * len(rows) + 6
        s.rect(x, y, w, h, dashed=dashed, z=2)
        s.rect(x, y, w, 22, name, weight="bold", dashed=dashed, z=3)
        for i, row in enumerate(rows):
            s.text(x + 7, y + 34 + 15 * i, row, ha="left", size=7.3)

    table(12, 14, 170, "files", ["PK  id", "      path (unique)", "      is_note", "      cluster", "      hash"])
    table(240, 14, 160, "chunks", ["PK  id", "FK  file_id", "      start_line", "      end_line", "      body"])
    table(458, 14, 156, "vectors", ["PK, FK  chunk_id", "      vector"])
    table(240, 186, 160, "chunks_fts  (full-text index)", ["PK  rowid = chunks.id", "      path", "      body"], dashed=True)
    table(12, 186, 170, "links", ["PK  source", "PK  target", "PK  kind (imports, uses, about)", "      via"])
    table(458, 110, 156, "meta", ["PK  key", "      value"])
    s.line([(182, 60), (240, 60)])
    s.text(190, 52, "1", size=7.5)
    s.text(229, 52, "0..*", size=7.5)
    s.line([(400, 60), (458, 60)])
    s.text(408, 52, "1", size=7.5)
    s.text(446, 52, "0..1", size=7.5)
    s.line([(320, 117), (320, 186)])
    s.text(328, 127, "1", size=7.5)
    s.text(328, 176, "1", size=7.5)
    s.line([(97, 117), (97, 186)], dashed=True)
    s.text(105, 127, "1", size=7.5)
    s.text(109, 176, "0..*", size=7.5)
    s.text(90, 152, "by path", size=7.2, ha="right")
    s.rect(458, 200, 156, 78, dashed=True)
    s.text(536, 212, "Files beside the database", weight="bold", size=7.3)
    s.text(466, 234, "vectors.bin   mapped vectors", ha="left", size=7)
    s.text(466, 249, "models.json   model profiles", ha="left", size=7)
    s.text(466, 264, "skills.json   skill vectors", ha="left", size=7)
    s.line([(536, 173), (536, 200)], "open", dashed=True)
    s.text(542, 187, "generation", size=7, ha="left")
    s.save()


def deployment():
    s = Sheet("deployment", 626, 440)
    node(s, 8, 24, 452, 404, "«device» The person's computer")
    s.rect(24, 72, 130, 44, "«artifact»\nBurrow.app", z=3)
    s.rect(166, 72, 130, 44, "«artifact»\nburrow (command line,\nterminal chat, MCP server)", z=3, size=7.0)
    s.rect(330, 72, 118, 44, "«process»\nMCP client, for\nexample Claude Code", z=3, size=7.0)
    s.line([(330, 94), (296, 94)], "open")
    s.text(330, 60, "stdio, JSON-RPC", size=SMALL)
    s.rect(44, 168, 222, 84, z=2)
    s.text(52, 180, "Data on disk", ha="left")
    s.rect(50, 192, 104, 50, "Vault folder\nnotes, skills,\nlinked code", z=3, size=7.3)
    s.rect(160, 192, 100, 50, ".burrow\nindex.sqlite\nvectors.bin", z=3, size=7.3)
    s.rect(24, 318, 272, 84, z=2)
    s.text(32, 330, "«service» Local model service, 127.0.0.1", ha="left")
    s.rect(34, 342, 122, 50, "local chat model", z=3, size=7.3)
    s.rect(166, 342, 120, 50, "embedding model", z=3, size=7.3)
    s.line([(99, 116), (99, 168)], "open", dashed=True)
    s.line([(216, 116), (216, 168)], "open", dashed=True)
    s.line([(34, 116), (34, 318)], "open")
    s.line([(286, 116), (286, 318)], "open")
    s.text(160, 285, "HTTP on the loopback address only", size=SMALL, back=True)
    s.rect(330, 200, 118, 50, "«artifact»\nevaluation harness\n(Python)", z=3, size=7.2)
    s.line([(330, 225), (312, 225), (312, 108), (296, 108)], "open", dashed=True)
    s.line([(389, 250), (389, 360), (296, 360)], "open")
    node(s, 480, 24, 130, 136, "«cloud» GitHub")
    s.rect(490, 52, 110, 44, "Pages\nlanding page", z=3, size=7.3)
    s.rect(490, 106, 110, 44, "Releases\nprogram and app", z=3, size=7.3)
    s.line([(490, 128), (460, 128)], "open")
    s.text(404, 146, "HTTPS download,\nonce", size=SMALL)
    node(s, 496, 190, 112, 70, "«cloud»")
    s.text(552, 232, "Cloud model, HTTPS\nevaluation only", size=7.3)
    s.line([(448, 225), (496, 225)], "open")
    s.save()


# ---------------------------------------------------------------- wireframes

def _window(s, x, y, w, h):
    s.rect(x, y, w, h, line=1.0)
    s.rect(x, y, w, 26, line=0.8)
    for i in range(3):
        s.ax.add_patch(Ellipse((x + 12 + 11 * i, y + 13), 7, 7, facecolor="white", edgecolor=INK, lw=0.7, zorder=4))


def wire_main():
    s = Sheet("wire_main", 626, 420)
    _window(s, 8, 8, 610, 404)
    s.text(100, 21, "New   Hide sidebar", size=SMALL)
    s.text(330, 21, "Back  Forward     Vault name, counts of notes, files and links", size=SMALL)
    s.text(578, 21, "Inspector", size=SMALL)
    s.rect(8, 34, 132, 378)
    s.rect(16, 92, 116, 22, "Files | Search | Tags", size=7.2)
    s.rect(16, 42, 116, 20, "Graph", size=7.2)
    s.rect(16, 66, 116, 20, "Ask", size=7.2, line=1.6)
    s.rect(16, 122, 116, 234, "File tree\n\nMemory\nSkills\nlinked code folders", size=7.2)
    s.rect(16, 364, 116, 40, "Add: note, folder,\nlink a folder", size=7.2)
    # The Ask panel.
    s.rect(140, 34, 478, 18, z=2)
    s.text(200, 43, "Graph      Ask  ×      +", size=SMALL)
    s.rect(158, 58, 442, 22, "Question", size=7.2)
    s.rect(158, 86, 442, 96, "Answer\n\ntext with file:line citations", size=7.4)
    s.rect(158, 192, 442, 26, line=1.6)
    s.text(166, 205, "Decision line:  Read the vault: the closest files are code, so their links are followed.  Method: Explain code.", ha="left", size=6.6)
    s.rect(158, 224, 442, 22, dashed=True)
    s.text(166, 235, "Warning, only when needed:  Not among what it read: file:line", ha="left", size=6.9)
    s.rect(158, 254, 442, 52)
    s.text(166, 265, "Used", ha="left", weight="bold", size=7.2)
    s.text(166, 281, "file name, lines read, link mark when reached through a link; each row opens its file", ha="left", size=7)
    s.text(166, 295, "file name, lines read", ha="left", size=7)
    s.text(166, 320, "Seconds taken, on this device     Keep as Note     What Should Burrow Remember?", ha="left", size=7)
    s.rect(158, 332, 442, 26)
    s.text(166, 345, "Proposed note:  kind, one sentence", ha="left", size=7)
    s.rect(548, 336, 44, 18, "Keep", size=7.2)
    s.rect(158, 372, 100, 30, "Look in: Everything\nor one folder", size=6.9)
    s.rect(264, 372, 86, 30, "Model", size=7.2)
    s.rect(356, 372, 214, 30, "Ask your vault", size=7.4)
    s.rect(576, 372, 24, 30, "↑", size=8)
    s.save()


def wire_terminal():
    s = Sheet("wire_terminal", 626, 330)
    s.rect(8, 8, 610, 314, line=1.0)
    s.rect(8, 8, 610, 20, line=0.8)
    s.text(313, 18, "Terminal", size=SMALL)
    rows = [
        (44, "burrow chat   vault name  ·  model name  ·  whole vault, or one folder", "bold"),
        (58, "counts of notes and code files  ·  meaning search on  ·  searches the vault first", "normal"),
        (86, "›  the person's question", "bold"),
        (104, "   · vault_prepare(task: \"the question\")     run by Burrow before the model is asked", "normal"),
        (118, "     → the engine's decision: search or walk, number of excerpts, method chosen, seconds", "normal"),
        (140, "   The answer, streamed as it is written, naming file:line for each thing it states.", "normal"),
        (176, "›  /keep", "bold"),
        (194, "   decision: one sentence that stands alone", "normal"),
        (208, "   Keep it? [y/N]   y", "normal"),
        (222, "   kept in Memory/the new note", "normal"),
        (258, "›  _", "bold"),
    ]
    for y, words, weight in rows:
        s.text(22, y, words, ha="left", size=7.3, weight=weight)
    s.line([(8, 290), (618, 290)], lw=0.6)
    s.text(22, 306, "Commands:  /folders   /folder NAME   /keep   /new   /help   /quit", ha="left", size=7.2)
    # Callouts.
    s.note(452, 74, 156, 26, "decision line of the engine")
    s.line([(452, 96), (420, 114)], lw=0.6)
    s.note(452, 186, 156, 34, "consent is asked for\neach note, one at a time")
    s.line([(452, 204), (128, 208)], lw=0.6)
    s.save()


ALL = (use_cases, activity, sequence_engine, sequence_mcp, engine_steps, architecture, classes, states, schema, deployment, wire_main, wire_terminal)

if __name__ == "__main__":
    wanted = set(sys.argv[1:])
    for draw in ALL:
        if not wanted or draw.__name__ in wanted:
            draw()
