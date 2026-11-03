"""The ten Chapter 4 diagrams in standard notation (UML 2.5 and Gane–Sarson), drawn with kit.py.

    python3 docs/thesis/uml/diagrams.py <canvas folder> <page folder>

writes each one as a Design-canvas artboard (<canvas folder>/project/<Name>.dc.html, plus canvas.json) and as a plain
page (<page folder>/<file>.html) that is captured as docs/thesis/diagrams/<file>.png for the Word chapter.

Sizes are chosen for the printed page: a diagram up to about 1,100 px wide sits on a portrait page and a wider one on
a landscape page, so 15 px text prints at 6.5 to 8 pt.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from kit import INK, MUTED, Box, Diagram


def lab(d: Diagram, x, y, w, t, align="center", size=14, bg=None):
    d.text(round(x), round(y), round(w), t, size=size, color=MUTED, align=align, bg=bg)


def small(t: str) -> str:
    return f'<span style="font-size:13px;color:{MUTED}">{t}</span>'


# --------------------------------------------------------------------- 4.1 context
def context() -> Diagram:
    d = Diagram("Context", "Context diagram of CAMR (Gane–Sarson)", 1500, 930,
                "Solid: both versions or CAMR v2 · dashed: CAMR v1 only · in CAMR v2 nothing leaves the Mac after the "
                "first model download")
    p = d.gs_process(600, 280, 300, 620, "0", '<span style="font-size:22px"><b>CAMR</b></span><br>Capability-Adaptive'
                     '<br>Memory Retrieval<br><br>' + small("v1: research engine<br>v2: deployed engine"))

    def left(cy, name, into, out, v1=False):
        d.gs_entity(40, cy - 50, 280, 100, name)
        d.path([(320, cy - 20), (p.x, cy - 20)], dashed=v1)
        lab(d, 330, cy - 28 - 18 * (into.count("<br>") + 1), 260, into)
        d.path([(p.x, cy + 20), (320, cy + 20)], dashed=v1)
        lab(d, 330, cy + 28, 260, out)

    def right(cy, name, out, into, v1=True, out_first=True):
        d.gs_entity(1180, cy - 50, 280, 100, name)
        top, bottom = (out, into) if out_first else (into, out)
        if out_first:
            d.path([(p.x + p.w, cy - 20), (1186, cy - 20)], dashed=v1)
            d.path([(1186, cy + 20), (p.x + p.w, cy + 20)], dashed=v1)
        else:
            d.path([(1186, cy - 20), (p.x + p.w, cy - 20)], dashed=v1)
            d.path([(p.x + p.w, cy + 20), (1186, cy + 20)], dashed=v1)
        lab(d, 910, cy - 28 - 18 * (top.count("<br>") + 1), 266, top)
        lab(d, 910, cy + 28, 266, bottom)

    left(430, "User of an<br>on-device assistant", "moments, notes, files,<br>questions, errands, feedback",
         "answers, tool calls,<br>recalled moments, Brain replay")
    left(750, "Researcher<br>" + small("student, supervisor, examiner"),
         "configurations, persona and seed,<br>contender, commands", "test records, tables,<br>charts, logs")

    d.gs_entity(440, 120, 280, 90, "Public benchmark files (v1)<br>" + small("PopQA · HotpotQA ·<br>2WikiMultiHopQA · GSM8K"))
    d.path([(630, 210), (630, p.y)], dashed=True)
    lab(d, 642, 227, 190, "questions, gold answers,<br>supporting documents", align="left")
    d.gs_entity(780, 130, 260, 70, "Model hub<br>" + small("Hugging Face"))
    d.path([(850, 200), (850, p.y)])
    lab(d, 862, 222, 160, "model weights<br>(first run only)", align="left")

    right(360, "Local model runtime<br>" + small("Ollama, same machine (v1)"), "prompts",
          "generated text,<br>token counts, timings")
    right(510, "Cloud reference model<br>" + small("Kimi K3, Moonshot API (v1)"),
          "prompts: ceiling, ceiling_rag,<br>escalated questions", "answers, token counts")
    right(660, "Automation platform<br>" + small("n8n workflows (v1)"), "answers, cost meter",
          "teach, forget, ask<br>(HTTP on localhost)", out_first=False)
    right(810, "Web lookup (v1)<br>" + small("DuckDuckGo · Wikipedia"),
          "subject of a general question<br>(never a personal one)", "page text and its link")
    return d


# --------------------------------------------------------------------- 4.2 use cases
def use_cases() -> Diagram:
    d = Diagram("UseCases", "Use case diagram of CAMR", 1500, 1020,
                "(v1) only in CAMR v1 · (v2) only in CAMR v2 · unmarked: both versions · an italic name is abstract")
    d.band(330, 120, 930, 880, "CAMR", style="boundary")

    def uc(cx, cy, name, italic=False):
        label = f"<i>{name}</i>" if italic else name
        return d.card(cx - 125, cy - 38, 250, 76, label, kind="usecase", size=16, pad=16)

    L, M, R = 470, 795, 1115
    ask = uc(L, 200, "Ask a question<br>from memory")
    tell = uc(L, 500, "Tell or teach something<br>to remember")
    errand = uc(L, 610, "Give an errand,<br>one tool call (v2)")
    inspect = uc(L, 720, "Inspect what an<br>answer leaned on")
    life = uc(L, 860, "Watch a simulated<br>life (v2)")
    escalate = uc(M, 200, "Escalate to the<br>cloud model (v1)")
    recall = uc(M, 470, "Recall from memory")
    evaluate = uc(M, 680, "Run an evaluation", italic=True)
    grade = uc(M, 920, "Grade answers<br>by rule")
    bench = uc(R, 300, "Run benchmark conditions<br>and ablations (v1)")
    run = uc(R, 490, "Run a contender<br>through a life (v2)")
    repro = uc(R, 640, "Regenerate tables<br>and charts")
    speed = uc(R, 780, "Measure speed and<br>memory use")
    record = uc(R, 920, "Write a test record")

    def actor(cx, top, name, right=False):
        d.actor(cx, top, name)
        return cx - 26 if right else cx + 26, top + 40

    user = actor(70, 540, "User")
    n8n = actor(255, 430, "n8n (v1)")
    researcher = actor(1400, 500, "Researcher", right=True)
    cloud = actor(1400, 150, "Cloud model<br>Kimi K3 (v1)", right=True)

    def assoc(who, case: Box, aim=0):  # aim: how far right of the centre the line is aimed
        d.path([who, case.hit(*who, case.cx + aim, case.cy)], head=None)

    for c in (ask, tell, errand, inspect, life):
        assoc(user, c)
    assoc(n8n, ask, aim=60)
    assoc(n8n, tell, aim=20)
    for c in (bench, run, repro, speed):
        assoc(researcher, c)
    for c in (escalate, bench):
        assoc(cloud, c)

    def rel(src: Box, dst: Box, label, side=1, at=0.5, head="open"):
        p, q = src.toward(dst.cx, dst.cy), dst.toward(src.cx, src.cy)
        d.path([p, q], head=head, dashed=label is not None)
        if label:
            d.along(p, q, label, side=side, at=at)

    rel(ask, recall, "«include»", side=-1, at=0.45)
    rel(errand, recall, "«include»", side=1)
    rel(evaluate, recall, "«include»", side=-1)
    rel(evaluate, grade, "«include»", side=-1)
    rel(evaluate, record, "«include»", side=1)
    rel(speed, record, "«include»", side=-1)
    rel(escalate, ask, "«extend»", side=-1)
    for child in (life, bench, run):  # generalization: a hollow triangle towards the parent
        rel(child, evaluate, None, head="triangle")
    return d


# --------------------------------------------------------------------- 4.3 activity
def activity() -> Diagram:
    d = Diagram("Activity", "Activity diagram of the evaluation pipelines", 1060, 1320,
                "Two partitions, one per version · ◆ decision or merge · ▬ fork or join")
    for x, w, name in ((40, 520, "CAMR v1: public benchmarks"), (560, 460, "CAMR v2: scripted lives")):
        d.band(x, 120, w, 1180, None, style="package")
        d.card(x, 120, w, 44, f"<b>{name}</b>", kind="head", size=15)

    def act(cx, y, w, h, label, size=15):
        return d.card(cx - w / 2, y, w, h, label, kind="round", size=size, pad=8)

    def down(x, y1, y2):
        d.path([(x, y1), (x, y2)], head="open")

    # CAMR v1
    X = 300
    d.deco(X - 12, 182, 24, 24, "initial")
    steps = ["Load the official benchmark files<br>PopQA · HotpotQA · 2WikiMultiHopQA · GSM8K",
             "Draw a fixed sample per benchmark<br>(seed 13; question ids + file hash)",
             "Split: validation questions for tuning,<br>held-out questions for confirmation",
             "Holdout guard: no evaluation<br>question enters memory",
             "Write path: documents become<br>screened notes in one SQLite file"]
    y, prev = 230, 206
    for s in steps:
        down(X, prev, y)
        act(X, y, 420, 60, s)
        prev, y = y + 60, y + 90
    d.deco(80, 680, 440, 7, "bar")
    down(X, prev, 680)
    conds = ["floor:<br>small model<br>alone", "treatment:<br>small model<br>+ CAMR", "ceiling:<br>Kimi K3<br>alone",
             "ceiling_rag:<br>Kimi K3 +<br>same notes"]
    for cx, s in zip((126, 248, 370, 492), conds):
        down(cx, 687, 717)
        act(cx, 717, 112, 84, s, size=14)
        down(cx, 801, 831)
    d.deco(80, 831, 440, 7, "bar")
    steps = ["Log every query: prompt, notes,<br>tokens, latencies, answer",
             "Score: contains, exact match,<br>F1, final number",
             "Analyse: gap closed with bootstrap CI;<br>ablation, budget sweep, device profile",
             "Write tables, figures<br>and FINDINGS.md"]
    y, prev = 868, 838
    for s in steps:
        down(X, prev, y)
        act(X, y, 420, 60, s)
        prev, y = y + 60, y + 90
    down(X, prev, 1230)
    d.deco(X - 14, 1230, 28, 28, "final")

    # CAMR v2
    X, S = 735, 950
    d.deco(X - 12, 182, 24, 24, "initial")
    down(X, 206, 230)
    act(X, 230, 240, 60, "Make a scripted life from<br>a persona and a seed")
    down(X, 290, 320)
    d.deco(650, 320, 350, 7, "bar")
    down(X, 327, 357)
    act(X, 357, 240, 60, "Load a contender<br>(one embedder, 1.7B reader)")
    down(S, 327, 357)
    act(S, 357, 130, 100, "Measure speed:<br>one room of 250<br>to 3,000 words,<br>notes vs words", size=14)
    down(X, 417, 452)
    d.decision(X, 470, 36, 36)
    down(X, 488, 520)
    act(X, 520, 240, 60, "Observe the day's<br>moments, then save")
    down(X, 580, 612)
    d.decision(X, 630, 36, 36)
    down(X, 648, 690)
    lab(d, X + 10, 660, 130, "[end of a week]", align="left")
    act(X, 690, 240, 60, "Weekly quiz: the same 100<br>questions, graded by rule")
    d.path([(X + 18, 630), (900, 630), (900, 800), (X + 18, 800)], head="open")
    lab(d, X + 30, 604, 110, "[otherwise]")
    down(X, 750, 782)
    d.decision(X, 800, 36, 36)
    down(X, 818, 852)
    d.decision(X, 870, 36, 36)
    d.path([(X - 18, 870), (590, 870), (590, 470), (X - 18, 470)], head="open")
    lab(d, 598, 844, 110, "[more days]")
    down(X, 888, 930)
    lab(d, X + 10, 899, 130, "[day 84 done]", align="left")
    act(X, 930, 240, 84, "Run 100 errands,<br>one tool call each,<br>graded by rule")
    down(X, 1014, 1044)
    down(S, 457, 1044)
    d.deco(650, 1044, 350, 7, "bar")
    down(X, 1051, 1081)
    act(X, 1081, 240, 60, "Write a dated test record:<br>machine, code, every answer")
    down(X, 1141, 1171)
    act(X, 1171, 240, 60, "Draw growth charts<br>and README tables")
    down(X, 1231, 1251)
    d.deco(X - 14, 1251, 28, 28, "final")
    return d


# --------------------------------------------------------------------- 4.4 architecture v1
def architecture_v1() -> Diagram:
    d = Diagram("ArchitectureV1", "Component diagram of CAMR v1, the research engine", 1080, 1440,
                "Solid arrow: data passed on · dashed arrow: reads or depends on")
    ui = d.component(200, 120, 680, 80, "Interfaces",
                     "camr CLI · CAMR Personal (web app on 127.0.0.1) · Inspector · automation gateway")
    d.band(50, 250, 980, 800, None, style="package")
    d.text(360, 260, 440, "«subsystem» CAMR v1 memory engine (camr.memory)", size=16, weight=600,
           align="left", color=INK, layer=0)
    d.band(70, 300, 340, 730, "Write path (teach, ingest)", style="region")
    d.band(670, 300, 340, 730, "Read path (ask)", style="region")
    write = [("Write policy", "verbatim chunks | structured notes", 70),
             ("Screener", "empty · duplicate · injection-like", 70),
             ("Importance score", "+ timestamp", 70),
             ("Embedder", "bge-small-en-v1.5 (384-d);<br>nomic-embed-text in the app", 90)]
    y = 350
    for i, (name, det, h) in enumerate(write):
        if i:
            d.path([(240, y - 40), (240, y)])
        d.component(90, y, 300, h, name, det)
        y += h + 40
    d.path([(240, 770), (240, 850)])
    d.cylinder(90, 850, 300, 150, "<b>One SQLite file + sqlite-vec</b><br>notes · vectors · provenance ·<br>"
                                  "rejections · runs · query logs")
    read = [("Embed the question", "the same embedder"), ("kNN search, k = 20", "sqlite-vec, exact"),
            ("Retrieval policy", "similarity | composite (Eq. 4.1)"),
            ("Gate (Eq. 4.2)", "abstain below τ · admit within δ"),
            ("Entity bridging", "second hop through named entities"),
            ("Token budgeter", "note tokens ≤ B (default 512)")]
    for i, (name, det) in enumerate(read):
        y = 350 + 110 * i
        if i:
            d.path([(840, y - 40), (840, y)])
        d.component(690, y, 300, 70, name, det)
    d.path([(330, 200), (330, 350)])
    lab(d, 340, 216, 60, "teach", align="left")
    d.path([(840, 200), (840, 350)])
    lab(d, 850, 216, 60, "ask", align="left")
    d.path([(390, 485), (450, 485), (450, 880), (390, 880)], head="open", dashed=True)
    lab(d, 460, 640, 100, "rejections,<br>with source", align="left")
    d.path([(390, 925), (560, 925), (560, 505), (690, 505)], head="open", dashed=True)
    lab(d, 495, 760, 57, "vectors", align="right")
    d.path([(390, 965), (600, 965), (600, 825), (690, 825)], head="open", dashed=True)
    lab(d, 398, 973, 196, "notes on named entities", align="left")
    d.path([(840, 970), (840, 1100)])
    d.component(690, 1100, 300, 70, "Prompt template", "fixed, recorded verbatim")
    d.path([(840, 1170), (840, 1210)])
    d.component(690, 1210, 300, 80, "Frozen small model", "0.5B to 3B, through Ollama,<br>loopback only")
    d.path([(990, 1250), (1050, 1250), (1050, 160), (ui.x + ui.w, 160)])
    lab(d, 892, 116, 150, "answer +<br>cited notes")
    d.component(90, 1100, 300, 100, "Harness", "camr.harness, camr.eval: benchmarks,<br>conditions, scoring, ablation,"
                                               "<br>budget sweep, profile")
    d.path([(240, 1100), (240, 1050)], head="open", dashed=True)
    lab(d, 250, 1066, 60, "«use»", align="left")
    d.path([(240, 1200), (240, 1300)])
    lab(d, 250, 1241, 120, "ceiling runs", align="left")
    d.component(90, 1300, 300, 80, "Cloud reference model", "Kimi K3 (Moonshot API)")
    d.component(690, 1330, 300, 80, "Learned router", "grounding cascade; escalates")
    d.path([(840, 1330), (840, 1290)], dashed=True)
    d.path([(690, 1355), (390, 1355)], dashed=True)
    lab(d, 490, 1329, 100, "escalate")
    return d


# --------------------------------------------------------------------- 4.5 architecture v2
def architecture_v2() -> Diagram:
    d = Diagram("ArchitectureV2", "Component diagram of CAMR v2, the deployed engine", 1370, 960,
                "Solid arrow: calls or passes data · dashed arrow: the CAMR v1 baseline, used only by the ruler")
    d.band(700, 232, 600, 528, "Memory engine", style="package", label_side="right")

    def comp(x, y, name, det, w=240, h=80, stereo=None):
        return d.component(x, y, w, h, name, det, stereo=stereo, size=14)

    comp(350, 130, "Layout", "view/layout.py: t-SNE<br>positions of moments")
    comp(40, 270, "Browser page", "index.html: Simulation ·<br>Chat · Errands · Brain", w=210)
    comp(40, 660, "Ruler command line", "run · errands · speed ·<br>chart · life", w=210)
    comp(350, 270, "App server", "server.py · 127.0.0.1:8765 ·<br>host, origin, token checks")
    comp(350, 400, "Simulation", "sim.py: a life day by day,<br>in its own memory")
    comp(350, 530, "Agent", "agent.py: ten tools, one<br>call, parse, grade")
    comp(350, 660, "Ruler", "ruler/: lives, contenders,<br>harness, grade, speed, chart")
    comp(720, 122, "Reader", "Qwen3-1.7B-4bit · frozen,<br>greedy, thinking off", h=96, stereo="MLX model")
    comp(720, 270, "Memory", "memory.py<br>remember · choose ·<br>recall · answer", h=470)
    comp(1040, 270, "Notebook", "notes.py: write notes, lay the<br>desk, turn keys (RoPE)")
    comp(1040, 400, "Rooms", "rooms.py: place (Eq. 4.3),<br>add, fetch, save")
    comp(1040, 530, "Event log + Looks", "events.py: attention at layers<br>12–24; used if share ≥ 0.10")
    comp(720, 800, "Embedder", "Qwen3-Embedding-0.6B-<br>4bit-DWQ · frozen", h=96, stereo="MLX model")
    comp(1040, 800, "CAMR v1 engine", "a library: the baseline<br>contender, unchanged", h=96)

    d.path([(250, 300), (350, 300)])
    lab(d, 255, 256, 90, "JSON over<br>HTTP")
    d.path([(250, 700), (350, 700)])
    d.path([(470, 270), (470, 210)])
    lab(d, 480, 231, 60, "Brain", align="left")
    d.path([(470, 350), (470, 400)])
    d.path([(350, 335), (315, 335), (315, 570), (350, 570)])
    for y, t in ((300, "remember ·<br>answer"), (440, "its own<br>memory"), (570, "answer<br>with tools"),
                 (700, "contender")):
        d.path([(590, y), (720, y)])
        lab(d, 596, y - 8 - 18 * (t.count("<br>") + 1), 100, t)
    for y in (310, 440, 570):
        d.path([(960, y), (1040, y)])
    d.path([(840, 270), (840, 218)])
    lab(d, 850, 238, 100, "generate", align="left")
    d.path([(1160, 270), (1160, 170), (960, 170)])
    lab(d, 975, 144, 180, "read once to write notes")
    d.path([(840, 740), (840, 800)])
    lab(d, 850, 769, 60, "embed", align="left")
    d.path([(1040, 848), (960, 848)], head="open", dashed=True)
    d.path([(1280, 848), (1330, 848), (1330, 104), (800, 104), (800, 122)], head="open", dashed=True)
    d.path([(470, 740), (470, 930), (1160, 930), (1160, 896)], head="open", dashed=True)
    lab(d, 560, 904, 90, "contender")
    return d


# --------------------------------------------------------------------- 4.6 sequence
def sequence() -> Diagram:
    d = Diagram("Sequence", "Sequence diagram: one question answered by CAMR v2", 1480, 1200,
                "Solid line, filled head: a call · dashed line, open head: its return · bars: while a part is working")
    d.frame(30, 112, 1420, 1070, "sd Answer one question")
    xs = [100, 310, 520, 730, 940, 1150, 1360]
    d.actor(xs[0], 150, "User")
    heads = ["<b>Browser page</b><br>" + small("Chat tab"), "<b>App server</b><br>" + small("server.py"),
             "<b>Memory</b><br>" + small("memory.py"), "<b>Rooms</b><br>" + small("rooms.py, on the SSD"),
             "<b>Notebook</b><br>" + small("notes.py"), "<b>MLX models</b><br>" + small("embedder · reader")]
    for x, h in zip(xs[1:], heads):
        d.card(x - 90, 160, 180, 56, h, kind="head", size=15, pad=6)
    msgs = [(0, 1, "1. types a question and presses Send"), (1, 2, "2. POST /api/chat {text} + X-Engram-Token"),
            (2, 2, "3. check host, origin, JSON and token; take the lock"), (2, 3, "4. answer(question, today)"),
            (3, 3, "5. prompt(): the header, whose notes stay in RAM"), (3, 6, "6. embed the question"),
            (6, 3, "7. unit vector q"), (3, 3, "8. choose(): the closest moment's room and the 4 closest moments"),
            (3, 4, "9. fetch([room])"), (4, 4, "10. read the whole file in 1 MB pieces, cache bypassed"),
            (4, 3, "11. the room's notes (bytes)"), (3, 5, "12. desk([room notes])"),
            (5, 3, "13. cache: header + room, already read"),
            (3, 6, "14. generate(the 4 closest as words + the question, cache = desk)"),
            (6, 6, "15. read the new words, then write at most 40 tokens"),
            (6, 3, "16. words, time to first word, attention per word"),
            (3, 3, "17. used(): share ≥ 0.10 means used; one line to events.jsonl"), (3, 2, "18. reply"),
            (2, 1, "19. {reply, event, wait_s}"), (1, 0, "20. the answer, with its wait")]
    returns = {6, 10, 12, 15, 17, 18, 19}
    ys, y = [], 292
    for a, b, _ in msgs:
        ys.append(y)
        y += 58 if a == b else 38
    bottom = y + 10
    for x in xs:
        d.path([(x, 230 if x == xs[0] else 216), (x, bottom)], head=None, dashed=True, color="#8a94a0")
    spans = {1: [(0, 19)], 2: [(1, 18)], 3: [(3, 17)], 6: [(5, 6), (13, 15)], 4: [(8, 10)], 5: [(11, 12)]}
    for lane, ranges in spans.items():
        for i, j in ranges:
            d.card(xs[lane] - 6, ys[i] - 4, 12, ys[j] - ys[i] + 8 + (26 if msgs[j][0] == msgs[j][1] else 0), "",
                   kind="act")
    for i, ((a, b, t), y) in enumerate(zip(msgs, ys)):
        w = 7.4 * len(t) + 8
        if a == b:
            x = xs[a] + 6
            d.path([(x, y), (x + 34, y), (x + 34, y + 24), (x + 2, y + 24)])
            if a == 6:
                lab(d, xs[a] - 16 - w, y + 3, w, t, align="right", bg="#ffffff")
            else:
                lab(d, x + 44, y + 3, w, t, align="left", bg="#ffffff")
            continue
        x1 = xs[a] + (6 if b > a else -6) * (a != 0)
        x2 = xs[b] - (6 if b > a else -6) * (b != 0)
        d.path([(x1, y), (x2, y)], head="open" if i in returns else "filled", dashed=i in returns)
        lab(d, (x1 + x2) / 2 - w / 2, y - 24, w, t, bg="#ffffff")
    return d


# --------------------------------------------------------------------- 4.7 state machines
def states() -> Diagram:
    d = Diagram("States", "State machine diagrams: a moment and its room (CAMR v2)", 1060, 1500,
                "Rounded box: a state · ● initial state · ◆ choice · [guard] · trigger / effect")

    def st(x, y, w, h, label):
        return d.card(x, y, w, h, label, kind="state", size=15, pad=8)

    def go(pts):
        d.path(pts, head="open")

    d.frame(40, 120, 980, 990, "stm A moment")
    d.deco(289, 157, 22, 22, "initial")
    go([(300, 179), (300, 230)])
    lab(d, 312, 180, 260, "a Chat message, a life's day,<br>or the simulation", align="left")
    st(180, 230, 240, 64, "<b>Told</b><br>“[date] text” arrives")
    go([(300, 294), (300, 354)])
    lab(d, 312, 315, 160, "encode_one(text)", align="left")
    st(180, 354, 240, 64, "<b>Embedded</b><br>one unit vector")
    go([(300, 418), (300, 460)])
    lab(d, 312, 430, 80, "place()", align="left")
    d.decision(300, 478, 36, 36)
    go([(282, 478), (175, 478), (175, 570)])
    lab(d, 60, 434, 215, "[some moment ≥ 0.80 similar<br>has a room with space]")
    go([(318, 478), (445, 478), (445, 570)])
    lab(d, 455, 505, 110, "[otherwise]", align="left")
    st(60, 570, 230, 64, "<b>Placed in an<br>existing room</b>")
    st(330, 570, 230, 64, "<b>Placed in<br>a new room</b>")
    go([(175, 634), (175, 694)])
    go([(445, 634), (445, 694)])
    st(140, 694, 320, 84, "<b>Written</b><br>notes made by reading it once,<br>after the header and the room so far")
    go([(300, 778), (300, 838)])
    lab(d, 312, 799, 240, "append to room-NNNNNN.notes", align="left")
    st(140, 838, 320, 84, "<b>Stored</b><br>notes appended to its room file;<br>words, day and vector in the index")
    go([(460, 870), (640, 870)])
    lab(d, 470, 844, 160, "a question / recall()")
    st(640, 838, 320, 84, "<b>On the desk</b><br>in the opened room,<br>or among the 4 closest")
    go([(700, 922), (700, 990)])
    lab(d, 586, 938, 106, "answer ends<br>[share ≥ 0.10]", align="right")
    go([(880, 922), (880, 990)])
    lab(d, 890, 938, 120, "answer ends<br>[share < 0.10]", align="left")
    st(560, 990, 200, 64, "<b>Used</b><br>share ≥ 0.10")
    st(780, 990, 200, 64, "<b>Picked up only</b><br>share < 0.10")
    go([(560, 1022), (300, 1022), (300, 922)])
    lab(d, 390, 996, 80, "logged")
    go([(880, 1054), (880, 1080), (260, 1080), (260, 922)])
    lab(d, 530, 1086, 80, "logged")
    d.note(60, 950, 180, 114, "No final state:<br>CAMR v2 never<br>deletes a moment.<br>Fading belongs to<br>sleep (future work).",
           size=14)
    d.path([(150, 950), (150, 922)], head=None, dashed=True)

    d.frame(40, 1150, 980, 330, "stm A room")
    d.deco(59, 1299, 22, 22, "initial")
    go([(81, 1310), (250, 1310)])
    lab(d, 85, 1266, 160, "a moment joins no room<br>/ create the file")
    st(250, 1268, 280, 84, "<b>Growing</b><br>one file on the SSD,<br>at most 512 tokens")
    go([(330, 1268), (330, 1220), (450, 1220), (450, 1268)])
    lab(d, 250, 1176, 280, "a moment joins [similarity ≥ 0.80<br>and tokens + n ≤ 512] / append")
    go([(530, 1290), (720, 1290)])
    lab(d, 535, 1246, 180, "holds the closest<br>moment / fetch")
    st(720, 1268, 280, 84, "<b>On the desk</b><br>whole file read in one burst,<br>keys not turned")
    go([(720, 1330), (530, 1330)])
    lab(d, 535, 1338, 180, "answer ends / desk copy<br>dropped, file unchanged")
    d.note(250, 1400, 750, 60, "A moment that would overflow this room joins the next-closest room with space, or starts "
                               "a new room.<br>A room is never closed, split or rewritten.", size=14)
    d.path([(390, 1400), (390, 1352)], head=None, dashed=True)
    return d


# --------------------------------------------------------------------- 4.8 schema v1
def schema_v1() -> Diagram:
    d = Diagram("SchemaV1", "Logical schema of the CAMR v1 store (UML class notation)", 1100, 1310,
                "Each box is one SQLite table · PK primary key · FK foreign key · numbers: how many rows on each side")

    def mult(x, y, t, align="left", w=40):
        d.text(x, y, w, t, size=14, color=INK, align=align)

    d.band(30, 120, 1040, 570, "Memory tables (camr.memory.store)", style="package")
    d.klass(50, 170, 280, "source", ["<b>PK</b> source_id", "dataset", "doc_id", "note_type", "title", "ingested_at",
                                     "screener_verdict", "<i>UNIQUE(dataset, doc_id, note_type)</i>"], stereo="table")
    d.klass(50, 440, 280, "rejection", ["<b>PK</b> rejection_id", "<b>FK</b> source_id → source, may be null",
                                        "note_type", "reason", "text", "created_at"], stereo="table")
    d.klass(410, 170, 340, "note", ["<b>PK</b> note_id", "<b>FK</b> source_id → source", "note_type", "text",
                                    "token_count", "importance", "created_at", "last_accessed_at", "access_count",
                                    "<b>UQ</b> checksum"], stereo="table")
    d.klass(410, 480, 280, "meta", ["<b>PK</b> key", "value: schema version,", "embedder, dimension"], stereo="table")
    d.klass(810, 170, 240, "note_embedding", ["<b>PK, FK</b> note_id → note", "embedding (float32 vector)",
                                              "<i>ON DELETE CASCADE</i>"], stereo="table")
    d.klass(810, 350, 240, "note_vec", ["rowid = note_id", "note_type", "embedding (cosine distance)"],
            stereo="virtual table · sqlite-vec")
    d.path([(330, 270), (410, 270)], head=None)
    mult(336, 246, "1")
    mult(366, 246, "0..*", align="right")
    d.path([(190, 384), (190, 440)], head=None)
    mult(198, 386, "0..1")
    mult(198, 414, "0..*")
    d.raw(750, 233, 22, 14, f"background:{INK};clip-path:polygon(0 50%, 50% 0, 100% 50%, 50% 100%)", layer=2)
    d.path([(772, 240), (810, 240)], head=None)
    mult(752, 214, "1")
    mult(766, 214, "1", align="right")
    d.path([(810, 410), (750, 410)], head="open", dashed=True)
    d.path([(725, 420), (725, 710), (930, 710), (930, 780)], head=None, dashed=True)
    mult(733, 424, "1")
    mult(938, 752, "0..*")
    lab(d, 735, 560, 240, "logical reference: the harness<br>does not import the engine", align="left")

    d.band(30, 730, 1040, 560, "Harness tables (camr.eval.logger)", style="package")
    d.klass(50, 780, 280, "run", ["<b>PK</b> run_id", "label", "condition ∈ {floor, ceiling,",
                                  "&nbsp;&nbsp;treatment, ceiling_rag}", "benchmark · task_type",
                                  "model_name · model_version", "config_json · config_hash", "template_id · seed",
                                  "started_at · finished_at", "status"], stereo="table")
    d.klass(410, 780, 340, "query_log", ["<b>PK</b> query_id", "<b>FK</b> run_id → run",
                                         "question_id · dataset · task_type", "question · prompt · answer_text",
                                         "status ∈ {ok, failed} · error", "context, prompt and generated tokens",
                                         "retrieval, generation, end-to-end latency",
                                         "budget · abstained · top_similarity", "prefill_ms · decode_ms · served_model",
                                         "logged_at"], stereo="table")
    d.klass(810, 780, 240, "retrieved_note", ["<b>PK, FK</b> query_id → query_log", "<b>PK</b> note_id (logical)",
                                              "rank · tokens · admitted", "similarity · recency_score",
                                              "importance_score", "composite_score", "via_note_id (bridged from)"],
            stereo="table")
    d.klass(410, 1100, 340, "score", ["<b>PK</b> score_id", "<b>FK</b> query_id → query_log", "metric · value"],
            stereo="table")
    d.path([(330, 850), (410, 850)], head=None)
    mult(336, 826, "1")
    mult(366, 826, "0..*", align="right")
    d.path([(750, 850), (810, 850)], head=None)
    mult(754, 826, "1")
    mult(766, 826, "0..*", align="right")
    d.path([(580, 1030), (580, 1100)], head=None)
    mult(588, 1034, "1")
    mult(588, 1076, "0..*")
    return d


# --------------------------------------------------------------------- 4.9 files v2
def files_v2() -> Diagram:
    d = Diagram("FilesV2", "File and data design of CAMR v2 (UML artifacts)", 1080, 1340,
                "Dashed arrow: a field that points into another file")

    def icon(x, y):
        d.deco(x, y, 13, 17, "doc_out", layer=3)
        d.deco(x + 1.5, y + 1.5, 10, 14, "doc_in", layer=3)

    d.band(30, 120, 1020, 900, "~/.engram/default/ · one memory (each simulation gets its own folder)", style="package")
    d.card(70, 170, 940, 170, "", kind="box")
    icon(982, 180)
    d.text(84, 180, 880, small("«artifact»") + "<br><b>room-000042.notes</b> · append-only; written and read with "
           "F_NOCACHE", size=15, align="left", color=INK)
    for x, w, t, k in ((84, 170, "token 0", "cell"), (254, 170, "token 1", "cell"), (424, 130, "…", "box"),
                       (554, 200, "token n − 1", "cell"), (754, 242, "next moment →", "cell_next")):
        d.card(x, 232, w, 40, t, kind=k, size=14)
    d.text(84, 284, 900, "moment k fills tokens start … start + tokens − 1 (positions from index.json); n ≤ 512",
           size=14, align="left", color=INK)
    d.text(84, 306, 900, "read whole, in 1 MB pieces, eight at once (preadv)", size=14, align="left", color=INK)
    d.path([(339, 340), (339, 410)], head="open", dashed=True)
    lab(d, 349, 364, 100, "each token", align="left")
    d.card(300, 410, 710, 160, "", kind="box")
    d.text(314, 420, 680, "<b>one token's notes = 114,688 bytes</b>", size=15, align="left", color=INK)
    for x, w, t in ((314, 200, "layer 0<br>K: 8 heads × 128<br>V: 8 heads × 128"), (514, 140, "layer 1<br>K · V"),
                    (654, 110, "…"), (764, 232, "layer 27<br>K · V")):
        d.card(x, 450, w, 70, t, kind="cell" if t != "…" else "box", size=14, pad=4)
    d.text(314, 532, 680, "28 layers × 2 (K, V) × 8 KV heads × 128 numbers × 2 bytes (Eq. 4.4)", size=14,
           align="left", color=INK)
    d.klass(70, 630, 440, "index.json", ["token_bytes (114,688) · room_tokens (512) · join (0.80)",
                                         "moments[ ]: mid · room · day · text · start · tokens",
                                         "rooms[ ]: rid · members[ ] · tokens"], stereo="artifact")
    d.klass(590, 630, 420, "vectors.npy", ["float32 matrix, one unit row per moment", "row i is moment mid = i"],
            stereo="artifact")
    d.klass(70, 830, 440, "events.jsonl", ["one JSON object per line; each has type and at",
                                           "remember: moment · room · day · tokens · new_room",
                                           "answer, agent: question · room · closest · nodes ·",
                                           "&nbsp;&nbsp;&nbsp;&nbsp;share · used · words · looks · wait_s · seconds",
                                           "tool: task · tool · args · result", "verdict: event · verdict · expected"],
            stereo="artifact")
    d.klass(590, 830, 420, "layout.json", ["moments (how many were laid out)", "xy[ ]: one [x, y] per moment"],
            stereo="artifact")
    d.path([(180, 630), (180, 340)], head="open", dashed=True)
    lab(d, 66, 470, 106, "start, tokens:<br>byte offsets", align="right")
    d.path([(510, 690), (590, 690)], head="open", dashed=True)
    lab(d, 512, 664, 76, "mid = row")
    d.path([(290, 830), (290, 753)], head="open", dashed=True)
    lab(d, 300, 774, 180, "nodes, closest, used:<br>moment ids", align="left")
    d.path([(800, 830), (800, 734)], head="open", dashed=True)
    lab(d, 810, 773, 190, "xy[i] from row i (t-SNE)", align="left")

    d.band(30, 1060, 1020, 260, "repository records/ · written by the ruler", style="package")
    d.klass(70, 1110, 940, "records/YYYY-MM-DD/HHMMSS-persona-sS-contender.json", [
        "kind · persona · seed · questions · weeks_planned · started · finished",
        "contender{ }: name · reader · room_tokens · join · closest · token_bytes",
        "environment{ }: machine · chip · memory_gb · power · load_1m · python · commit · dirty · source sha · mlx · "
        "mlx_lm · numpy",
        "weeks[ ]: week · date · notes_so_far · quiz_s · peak_ram_gb · disk_mb",
        "&nbsp;&nbsp;&nbsp;&nbsp;summary{ }: knows · told · honest · false_memories · stale · missed · wrong · "
        "wait_median_s · wait_p90_s",
        "&nbsp;&nbsp;&nbsp;&nbsp;answers[ ]: qid · kind · question · expected · answer · verdict · ttft_s · gen_tps · "
        "prompt_tokens"], stereo="artifact")
    return d


# --------------------------------------------------------------------- 4.10 deployment
def deployment() -> Diagram:
    d = Diagram("Deployment", "Deployment diagram of the CAMR v2 app on the Mac", 1560, 960,
                "3-D boxes: nodes (devices and execution environments) · lines: communication paths")
    d.node(40, 170, 1200, 760, small("«device»") + "<br><b>MacBook Pro M5 Pro (Mac17,9)</b> · macOS · 24 GB unified "
           "memory", depth=20)
    env = "#f7f9fb"
    d.node(80, 280, 300, 260, small("«executionEnvironment»") + "<br><b>Web browser</b>", depth=12, fill=env)
    d.artifact(100, 360, 260, 150, "index.html", "Simulation · Chat ·<br>Errands · Brain;<br>carries the launch key")
    d.node(480, 280, 380, 280, small("«executionEnvironment»") + "<br><b>Python 3.12 virtual environment</b>",
           depth=12, fill=env)
    for x, y, n, t in ((500, 350, "App server", "127.0.0.1:8765"),
                       (680, 350, "Memory engine", "Memory · Rooms ·<br>Notebook · Events"),
                       (500, 450, "Ruler", "run from a terminal"), (680, 450, "CAMR v1 engine", "baseline only")):
        d.component(x, y, 160, 80, n, t, size=14)
    d.node(960, 280, 250, 280, small("«executionEnvironment»") + "<br><b>MLX</b> on the Apple-silicon<br>GPU (Metal)",
           depth=12, fill=env)
    d.artifact(980, 375, 210, 80, "Qwen3-1.7B-4bit", "reader, frozen")
    d.artifact(980, 465, 210, 80, "Qwen3-Embedding-0.6B", "4bit-DWQ · embedder, frozen")
    d.node(480, 700, 730, 200, small("«device»") + "<br><b>Internal SSD</b>", depth=12, fill=env)
    d.artifact(500, 770, 220, 110, "~/.engram/", "default/: your memory ·<br>simulations/: one per run")
    d.artifact(740, 770, 210, 110, "records/", "dated test records (JSON),<br>in the repository")
    d.artifact(970, 770, 220, 110, "~/.cache/huggingface/", "model weights,<br>about 1.3 GB")
    d.node(1310, 280, 220, 220, small("«device»") + "<br><b>GitHub Actions</b><br>ubuntu-latest, external<br><br>"
           + small("tests of lives, grading,<br>records and charts on<br>every push; no MLX"), depth=14)
    d.node(1310, 720, 220, 130, small("«device»") + "<br><b>Hugging Face Hub</b><br>external<br>"
           + small("«HTTPS», first run only;<br>then HF_HUB_OFFLINE=1"), depth=14)
    d.path([(380, 420), (480, 420)], head=None)
    lab(d, 385, 358, 90, "«HTTP»<br>JSON on<br>loopback")
    lab(d, 385, 428, 90, "Host, Origin,<br>launch key")
    d.path([(860, 420), (960, 420)], head=None)
    lab(d, 865, 376, 90, "generate,<br>encode")
    lab(d, 865, 428, 90, "in-process")
    d.path([(670, 560), (670, 688)], head=None)
    lab(d, 680, 606, 200, "append, burst read<br>(F_NOCACHE), records", align="left")
    d.path([(1080, 688), (1080, 560)], head=None)
    lab(d, 1090, 615, 100, "load weights", align="left")
    d.path([(1310, 785), (1222, 785)], head=None)
    return d


DIAGRAMS = {"context": context, "use_cases": use_cases, "evaluation_pipeline": activity,
            "architecture_v1": architecture_v1, "architecture_v2": architecture_v2,
            "sequence_question_v2": sequence, "state_moment_room": states, "schema_v1": schema_v1,
            "files_v2": files_v2, "deployment_mac": deployment}


def main(canvas: Path, pages: Path) -> None:
    (canvas / "project").mkdir(parents=True, exist_ok=True)
    pages.mkdir(parents=True, exist_ok=True)
    boards, order, x, y, row_h = {}, [], 0, 0, 0
    for file, make in DIAGRAMS.items():
        d = make()
        name = f"{d.name}.dc.html"
        (canvas / "project" / name).write_text(d.dc_html())
        (pages / f"{file}.html").write_text(d.plain_html())
        if x and x + d.w > 6000:
            x, y, row_h = 0, y + row_h + 240, 0
        boards[name] = {"x": x, "y": y, "w": d.w, "h": d.h}
        order.append(name)
        x, row_h = x + d.w + 240, max(row_h, d.h)
    meta = {"v": 3, "createdOnFiles": {"v": 1, "at": dt.datetime.now(dt.timezone.utc).isoformat()},
            "title": "CAMR Chapter 4 Diagrams", "launch": {"view": "canvas"}, "pages": [], "boards": boards,
            "order": order, "notes": {}, "designSystems": []}
    (canvas / "project" / "canvas.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
