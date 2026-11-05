"""The Chapter 4 diagrams of CAMR as built (4 November 2026), in standard notation (UML 2.5 and Gane–Sarson).

They reuse the kit of the earlier Chapter 4 diagrams (v2/docs/thesis/uml/kit.py, read only), so the notation, fonts
and strokes are the same. Each diagram is written as a plain page and captured with headless Chrome at twice its
size; the top 104 px (the diagram's own title, which the thesis caption replaces) are left out, as before.

    python3 docs/thesis/diagrams/src/final_diagrams.py            # every diagram
    python3 docs/thesis/diagrams/src/final_diagrams.py context    # one
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
UML = HERE.parents[3] / "v2" / "docs" / "thesis" / "uml"
sys.path.insert(0, str(UML))

from kit import INK, LINE, MUTED, Box, Diagram  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TOP = 104  # the title band left out of the capture


def lab(d: Diagram, x, y, w, t, align="center", size=14, bg=None):
    d.text(round(x), round(y), round(w), t, size=size, color=MUTED, align=align, bg=bg)


def small(t: str) -> str:
    return f'<span style="font-size:13px;color:{MUTED}">{t}</span>'


def gs_store(d: Diagram, x, y, w, h, sid: str, label: str, duplicate=False) -> Box:
    """A Gane–Sarson data store: an open-ended box, its id in a cell at the left (a second line marks a copy)."""
    d.raw(x, y, w, h, f"background:#ffffff;border:1.5px solid {LINE};border-right:none")
    d.raw(x, y, 48, h, f"background:#f1f4f7;border:1.5px solid {LINE}")
    if duplicate:
        d.raw(x + 8, y, 1.5, h, f"background:{LINE}")
    d.card(x + (6 if duplicate else 0), y, 48 - (6 if duplicate else 0), h, f"<b>{sid}</b>", kind="bare", size=15, pad=2)
    d.card(x + 48, y, w - 48, h, label, kind="bare", size=15, align="left", pad=10)
    return Box(x, y, w, h)


def diamond(d: Diagram, p, q, filled=True):
    """A UML aggregation (hollow) or composition (filled) diamond at p, on the straight line p→q; returns where the
    line should start (the diamond's far tip)."""
    (x1, y1), (x2, y2) = p, q
    L, W = 22, 13
    if y1 == y2:  # horizontal
        s = 1 if x2 > x1 else -1
        left = x1 if s > 0 else x1 - L
        box = (left, y1 - W / 2, L, W)
        tip = (x1 + s * L, y1)
    else:
        s = 1 if y2 > y1 else -1
        top = y1 if s > 0 else y1 - L
        box = (x1 - W / 2, top, W, L)
        tip = (x1, y1 + s * L)
    bx, by, bw, bh = box
    poly = "clip-path:polygon(50% 0, 100% 50%, 50% 100%, 0 50%)"
    d.raw(bx, by, bw, bh, f"background:{LINE};{poly}", layer=3)
    if not filled:
        d.raw(bx + 2.2, by + 2.2, bw - 4.4, bh - 4.4, f"background:#ffffff;{poly}", layer=3)
    return tip


def rel(d: Diagram, pts, start=None, head="open", dashed=False):
    """A class-diagram line: ``start`` 'comp' or 'agg' puts a diamond at the first point; ``head`` at the last."""
    pts = [tuple(p) for p in pts]
    if start:
        pts[0] = diamond(d, pts[0], pts[1], filled=start == "comp")
    d.path(pts, head=head, dashed=dashed)


def klass3(d: Diagram, x, y, w, name, attrs, ops, stereo=None, size=13) -> Box:
    """A UML class with its three compartments: name (and «stereotype»), attributes, operations. ``attrs`` None
    leaves the attribute compartment out (a «module» of functions)."""
    head_h = 46 if stereo else 30
    label = (f'<span style="font-size:12px;color:{MUTED}">«{stereo}»</span><br><b>{name}</b>' if stereo
             else f"<b>{name}</b>")
    d.card(x, y, w, head_h, label, kind="class_name", size=15, pad=4)
    yy = y + head_h
    for rows in ([attrs] if attrs is not None else []) + [ops]:
        hh = round(12 + size * 1.3 * max(1, len(rows)))
        d.card(x, yy, w, hh, "<br>".join(rows), kind="class_body", size=size, align="left", pad=7, valign="top")
        yy += hh
    return Box(x, y, w, yy - y)


# --------------------------------------------------------------------- context
def context() -> Diagram:
    d = Diagram("Context", "Context diagram of CAMR (Gane–Sarson)", 1100, 1265,
                "Solid: CAMR · dashed: the CAMR v1 baseline only")
    p = d.gs_process(430, 300, 230, 920, "0", '<span style="font-size:22px"><b>CAMR</b></span><br>the memory engine,'
                     '<br>its app and its<br>benchmarks,<br>on the Mac')
    LW = 176  # the width of a flow's label, between an entity and the process

    def left(cy, name, into, out, h=100):
        d.gs_entity(30, cy - h / 2, 210, h, name)
        d.path([(240, cy - 20), (p.x, cy - 20)])
        lab(d, 247, cy - 28 - 18 * (into.count("<br>") + 1), LW, into)
        d.path([(p.x, cy + 20), (240, cy + 20)])
        lab(d, 247, cy + 28, LW, out)

    def right(cy, name, out, into, dashed=False, out_first=True, h=100):
        d.gs_entity(860, cy - h / 2, 210, h, name)
        top, bottom = (out, into) if out_first else (into, out)
        if out_first:
            d.path([(p.x + p.w, cy - 20), (866, cy - 20)], dashed=dashed)
            d.path([(866, cy + 20), (p.x + p.w, cy + 20)], dashed=dashed)
        else:
            d.path([(866, cy - 20), (p.x + p.w, cy - 20)], dashed=dashed)
            d.path([(p.x + p.w, cy + 20), (866, cy + 20)], dashed=dashed)
        lab(d, 670, cy - 28 - 18 * (top.count("<br>") + 1), 190, top)
        lab(d, 670, cy + 28, 190, bottom)

    left(480, "User<br>" + small("of the Mac app<br>(Chat)"),
         "moments and files to<br>remember, questions,<br>research, memory mode<br>(CAMR, RAG or off)",
         "answers (from memory,<br>the model or the web)<br>with code blocks, what<br>each answer read")
    left(780, "Wikipedia<br>" + small("public API,<br>for research"), "a search for<br>the question",
         "the best page's<br>plain text")
    left(1080, "Researcher<br>" + small("student, supervisor,<br>examiner"),
         "contender, model, cut,<br>seed, benchmark<br>commands", "dated records, tables,<br>charts, cost ledger")

    d.gs_entity(170, 130, 300, 100, "Hugging Face Hub<br>" + small("model weights · benchmark datasets"))
    d.path([(455, 230), (455, p.y)])
    lab(d, 230, 246, 216, "weights and datasets<br>(first download only)", align="right")
    d.gs_entity(620, 130, 300, 100, "Public benchmark files<br>" + small("PopQA · HotpotQA · 2Wiki · GSM8K<br>"
                                                                          "(baseline)"))
    d.path([(770, 230), (770, 264), (630, 264), (630, p.y)], dashed=True)
    lab(d, 780, 240, 200, "questions, documents", align="left")

    right(430, "Ollama<br>" + small("a separate program<br>on the Mac"), "a chat with recalled<br>notes as words",
          "the streamed answer,<br>its timings")
    right(670, "Anthropic API<br>" + small("Claude Haiku, Sonnet,<br>Opus 5.5: the yardstick,<br>benchmarks only"),
          "the scripted history<br>and its questions", "answers, tokens, cost<br>(kept in the ledger)", h=120)
    right(910, "Cloud model<br>(baseline)<br>" + small("Kimi K3, Moonshot API"), "prompts: ceiling,<br>escalations",
          "answers, token counts", dashed=True, h=110)
    right(1140, "Automation platform<br>" + small("n8n workflows<br>(baseline)"), "answers", "teach, forget, ask",
          dashed=True, out_first=False)
    return d


# --------------------------------------------------------------------- use cases
def use_cases() -> Diagram:
    d = Diagram("UseCases", "Use case diagram of CAMR", 1100, 1330,
                "An italic name is abstract · dashed arrows: «include» and «extend» · hollow triangle: generalisation")
    d.band(160, 120, 790, 1180, "CAMR", style="boundary")

    def uc(cx, cy, name, italic=False):
        label = f"<i>{name}</i>" if italic else name
        return d.card(cx - 115, cy - 38, 230, 76, label, kind="usecase", size=16, pad=16)

    L, M, R = 300, 555, 810
    chat = uc(L, 390, "Chat: ask, or<br>research online")
    tell = uc(L, 215, "Tell or attach<br>something to remember")
    code = uc(L, 550, "Ask for code<br>in Chat")
    watch = uc(L, 705, "Watch what an<br>answer reads")
    vault = uc(L, 850, "Browse the vault<br>(Obsidian)")
    pair = uc(L, 1150, "Pair Ollama<br>with memory")
    switch = uc(M, 190, "Choose memory:<br>CAMR, RAG or off")
    compare = uc(M, 480, "Compare CAMR,<br>RAG and off")
    reach = uc(M, 320, "Choose a reach<br>or a shelf")
    recall = uc(515, 650, "Recall from memory")
    bench = uc(M, 900, "Run a benchmark", italic=True)
    grade = uc(M, 1220, "Grade answers<br>by rule")
    claude = uc(R, 330, "Ask Claude alone<br>(the yardstick)")
    haul = uc(R, 640, "Run the Long Haul")
    suites = uc(R, 790, "Run the Hugging<br>Face suites")
    speed = uc(R, 1020, "Measure speed<br>and RAM")
    record = uc(R, 1220, "Write a dated record")

    def actor(cx, top, name, right=False):
        d.actor(cx, top, name, width=140)
        return cx - 26 if right else cx + 26, top + 40

    user = actor(80, 560, "User")
    ollama = actor(80, 1160, "«system»<br>Ollama")
    researcher = actor(1025, 760, "Researcher", right=True)
    api = actor(1025, 280, "«system»<br>Claude API", right=True)

    def assoc(who, case: Box, aim=0):
        d.path([who, case.hit(*who, case.cx + aim, case.cy)], head=None)

    for c in (chat, tell, code, watch, vault, pair):  # aimed at the near end, so no line crosses another case
        assoc(user, c, aim=-95)
    assoc(ollama, pair)
    for c in (haul, suites, speed):
        assoc(researcher, c)
    assoc(api, claude)

    def rel(src: Box, dst: Box, label, side=1, at=0.5, head="open", pos=None):
        p, q = src.toward(dst.cx, dst.cy), dst.toward(src.cx, src.cy)
        d.path([p, q], head=head, dashed=label is not None)
        if label and pos:  # placed by hand where the lines are close together
            d.text(pos[0], pos[1], 70, label, size=14, color=MUTED)
        elif label:
            d.along(p, q, label, side=side, at=at)

    rel(switch, chat, "«extend»", side=1, at=0.55)
    rel(reach, chat, "«extend»", pos=(424, 374))
    rel(compare, chat, "«extend»", pos=(372, 437))
    rel(compare, recall, "«include»", side=-1, at=0.5)
    rel(chat, recall, "«include»", pos=(294, 471))
    rel(code, recall, "«include»", pos=(318, 610))
    rel(pair, recall, "«include»", pos=(468, 772))
    rel(bench, recall, "«include»", pos=(548, 712))
    rel(bench, grade, "«include»", side=-1)
    rel(bench, record, "«include»", side=1)
    rel(speed, record, "«include»", side=-1, at=0.6)
    rel(claude, bench, "«extend»", side=1, at=0.5)
    for child in (haul, suites):
        rel(child, bench, None, head="triangle")
    return d


# --------------------------------------------------------------------- activity
def activity() -> Diagram:
    d = Diagram("Activity", "Activity diagram of the Long Haul pipeline", 1100, 1500,
                "◆ decision or merge · ▬ fork or join · [guard] · ⊗ flow final")
    d.card(40, 120, 1020, 44, "<b>act Run the Long Haul</b>", kind="head", size=15)

    def act(cx, y, w, h, label, size=15):
        return d.card(cx - w / 2, y, w, h, label, kind="round", size=size, pad=8)

    def down(x, y1, y2):
        d.path([(x, y1), (x, y2)], head="open")

    X = 550
    d.deco(X - 12, 182, 24, 24, "initial")
    steps = [("Build the script from its seed: one project, 110 working days,<br>17,786 events, 2.01M tokens, "
              "probes planted early, asked late", 64),
             ("Extend it to 220 days and 4.01M tokens with noise only<br>(every probe and event kept as it was)", 64),
             ("Cut it at 64K · 256K · 1M · 2M · 3M · 4M tokens", 44),
             ("Draw each cut's checkpoint: 10 questions per family (seed 0),<br>216 in all; 3M and 4M ask the 2M "
              "cut's 73 again", 64)]
    y, prev = 230, 206
    for s, h in steps:
        down(X, prev, y)
        act(X, y, 600, h, s)
        prev, y = y + h, y + h + 34
    down(X, prev, y)
    d.decision(X, y + 18, 36, 36)
    merge_y = y + 18
    down(X, y + 36, y + 70)
    fork = y + 70
    d.deco(70, fork, 900, 7, "bar")
    cols = [(150, "<b>engine:</b> 1.7B · 4B · 8B<br>" + small("rooms, core, tiers,<br>vault; project reach")),
            (330, "<b>bare:</b> model alone<br>" + small("the newest 32K or<br>64K tokens that fit")),
            (510, "<b>words:</b> Qwen 27B<br>" + small("the engine's rooms,<br>pasted in as text")),
            (690, "<b>ollama:</b> paired, bare<br>" + small("memory as words<br>through the proxy")),
            (870, "<b>Claude alone</b><br>" + small("Haiku · Sonnet ·<br>Opus 5.5, no memory"))]
    top = fork + 37
    for cx, t in cols:
        down(cx, fork + 7, top)
        act(cx, top, 170, 84, t, size=14)
    tell_y = top + 84 + 30
    for cx, _ in cols[:4]:
        down(cx, top + 84, tell_y)
    d.card(60, tell_y, 720, 64, "Tell the history up to the cut, one event at a time: tell(text, day)", kind="round",
           size=15, pad=8)
    cx = 870
    down(cx, top + 84, tell_y)
    act(cx, tell_y, 170, 64, "Hold the call's worst<br>cost in the ledger", size=14)
    dy = tell_y + 64 + 40
    down(cx, tell_y + 64, dy - 18)
    d.decision(cx, dy, 36, 36)
    d.path([(cx + 18, dy), (1010, dy)], head="open")
    d.raw(1010, dy - 13, 26, 26, "border:2px solid #36424f;border-radius:50%;background:#ffffff")
    d.text(1010, dy - 12, 26, "✕", size=16, color=INK)
    lab(d, 950, dy - 60, 110, "[over $60 less<br>$2] / refused", size=13)
    ask_y = dy + 18 + 36
    down(cx, dy + 18, ask_y)
    lab(d, cx + 8, dy + 20, 120, "[within the cap]", align="left", size=13)
    act(cx, ask_y, 170, 84, "Read the newest part<br>that fits 1M tokens;<br>answer as JSON", size=14)
    down(420, tell_y + 64, ask_y)
    d.card(60, ask_y, 720, 84, "Ask the checkpoint's questions, read-only:<br>nothing an answer reads is kept (E-31)",
           kind="round", size=15, pad=8)
    join = ask_y + 84 + 34
    down(420, ask_y + 84, join)
    down(cx, ask_y + 84, join)
    d.deco(70, join, 900, 7, "bar")
    g = join + 7 + 30
    down(X, join + 7, g)
    act(X, g, 620, 64, "Grade every answer by rule: right · wrong · stale · declined ·<br>false_memory "
                       "(a decline is right only for a never-said question)")
    r = g + 64 + 30
    down(X, g + 64, r)
    act(X, r, 620, 64, "Write a dated record after the checkpoint: machine, load, commit,<br>camr_source_sha, "
                       "process footprint, every answer and its metrics")
    dz = r + 64 + 40
    down(X, r + 64, dz - 18)
    d.decision(X, dz, 36, 36)
    d.path([(X - 18, dz), (52, dz), (52, merge_y), (X - 18, merge_y)], head="open")
    lab(d, 62, dz - 26, 140, "[another cut]", align="left")
    down(X, dz + 18, dz + 60)
    lab(d, X + 12, dz + 22, 140, "[last cut done]", align="left")
    d.deco(X - 14, dz + 60, 28, 28, "final")
    d.band(40, 120, 1020, dz + 60 + 28 + 24 - 120, None, style="package")
    d.h = dz + 60 + 28 + 40
    return d


# --------------------------------------------------------------------- architecture
def architecture() -> Diagram:
    d = Diagram("Architecture", "Component diagram of CAMR", 1100, 1500,
                "Solid arrow: calls or passes data · dashed arrow: the CAMR v1 baseline, used only by the benchmarks")

    def comp(x, y, w, h, name, det, stereo=None):
        return d.component(x, y, w, h, name, det, stereo=stereo, size=14)

    # the app and its server
    comp(30, 130, 330, 120, "CAMR Mac app", "Chat · CAMR / RAG / off ·<br>Compare; starts the engine<br>"
                                            "with its own token", stereo="SwiftUI")
    comp(450, 130, 320, 120, "App server", "server.py · 127.0.0.1 · Host,<br>Origin and X-CAMR-Token checks")
    d.path([(360, 172), (450, 172)])
    lab(d, 362, 116, 86, "HTTP,<br>loopback,<br>token", size=13)
    d.path([(450, 214), (360, 214)], head="open", dashed=True)
    lab(d, 362, 222, 86, "answer,<br>live events", size=13)

    # the memory engine
    d.band(30, 300, 760, 660, "«subsystem» Memory engine (camr_engine)", style="package")
    comp(50, 345, 720, 72, "Session", "reach.py: reads several reaches (session · project · agent · global),<br>"
                                     "writes one; memory on or off")
    d.path([(610, 250), (610, 345)])
    lab(d, 530, 262, 72, "say,<br>settings", align="right", size=13)
    d.card(50, 460, 720, 480, "", kind="box")
    d.text(64, 470, 640, "<b>Memory</b> · memory.py: remember · choose · recall · answer · fade", size=15,
           align="left", color=INK)
    ix, iy = 50 + 720 - 24, 468
    d.deco(ix, iy, 14, 18, "icon", layer=3)
    d.deco(ix - 4, iy + 3, 9, 5, "icon", layer=3)
    d.deco(ix - 4, iy + 10, 9, 5, "icon", layer=3)
    d.path([(410, 417), (410, 460)])
    lab(d, 420, 426, 200, "one Memory per reach", align="left", size=13)
    parts = [("Core", "«subconscious» core.py:<br>≤ 256 tokens of core<br>notes, kept in RAM"),
             ("Rooms", "«conscious» rooms.py:<br>≤ 512-token rooms,<br>join 0.80, burst read"),
             ("Tiers", "swap.py: hot rooms in<br>RAM, awake on the SSD,<br>asleep past the budget"),
             ("Vault", "«archive» vault.py: one<br>Markdown note a moment,<br>doors, fades 5% a day"),
             ("Notebook", "notes.py: writes notes,<br>lays the desk, turns<br>keys (RoPE)"),
             ("Event log", "events.py: one line an<br>answer; attention<br>per written word"),
             ("Metrics", "metrics.py: first word,<br>retrieval, tier, GB/s,<br>RAM, disk"),
             ("Live", "live.py: weights loading,<br>the room read, words,<br>layer activity")]
    for i, (name, det) in enumerate(parts):
        x, y = 66 + 233 * (i % 3), 505 + 142 * (i // 3)
        d.card(x, y, 220, 130, f"<b>{name}</b><br>" + small(det), kind="box", size=14, pad=8)

    # the models, beside the engine
    comp(875, 470, 195, 120, "Reader", "Qwen3 1.7B · 4B · 8B,<br>4-bit; frozen,<br>thinking off", stereo="MLX model")
    comp(875, 650, 195, 110, "Embedder", "Qwen3-Embedding-<br>0.6B; frozen", stereo="MLX model")
    d.path([(770, 530), (875, 530)])
    lab(d, 778, 488, 92, "generate,<br>write notes", size=13)
    d.path([(770, 705), (875, 705)])
    lab(d, 778, 682, 92, "embed", size=13)

    # Ollama, paired
    comp(30, 1020, 260, 90, "ollama CLI", "OLLAMA_HOST=<br>127.0.0.1:11435")
    comp(30, 1170, 260, 90, "Ollama pairing", "pair/ollama.py · proxy on<br>127.0.0.1:11435")
    comp(30, 1330, 260, 80, "Ollama", "127.0.0.1:11434", stereo="program")
    d.path([(160, 1110), (160, 1170)])
    d.path([(160, 1260), (160, 1330)])
    lab(d, 170, 1272, 190, "the chat, notes in front<br>of the last message", align="left", size=13)
    d.path([(290, 1200), (340, 1200), (340, 940)])
    lab(d, 350, 972, 80, "recall<br>as words", align="left", size=13)

    # the benchmarks
    comp(420, 1020, 280, 90, "Benchmark command line", "python -m<br>camr_engine.bench.…")
    comp(420, 1170, 280, 130, "Benchmark runners", "bench/: longhaul · local ·<br>ollama_run · suite_run ·<br>"
                                                   "reach_run · ram · throughput")
    comp(420, 1370, 280, 80, "CAMR v1 engine", "the baseline, as a library")
    comp(875, 1330, 195, 110, "Claude client", "bench/claude.py;<br>ledger with a<br>$60 cap")
    # the Code benchmark's agent: driven by the runners, never by the app
    comp(875, 810, 195, 150, "Code agent", "agentic/: workspace,<br>tools, MCP servers,<br>skills")
    d.note(880, 990, 185, 46, "benchmark only: used<br>by the Code benchmark", size=13)
    d.path([(970, 990), (970, 960)], head=None, dashed=True)
    d.path([(875, 880), (770, 880)])
    lab(d, 778, 838, 92, "brain with<br>memory", size=13)
    d.path([(700, 1220), (840, 1220), (840, 930), (875, 930)])
    lab(d, 848, 1070, 150, "code tasks", align="left", size=13)
    d.path([(560, 1110), (560, 1170)])
    d.path([(560, 1300), (560, 1370)], head="open", dashed=True)
    lab(d, 570, 1322, 80, "baseline", align="left", size=13)
    d.path([(700, 1195), (735, 1195), (735, 940)])
    lab(d, 745, 972, 90, "contender:<br>tell, ask", align="left", size=13)
    d.path([(700, 1280), (960, 1280), (960, 1330)])
    lab(d, 750, 1240, 130, "Claude alone,<br>the yardstick", size=13)
    return d


# --------------------------------------------------------------------- sequence
def sequence() -> Diagram:
    W = 1100
    d = Diagram("Sequence", "Sequence diagram: one question answered in Chat", W, 1500,
                "Solid line, filled head: a call · dashed line, open head: its return · bars: while a part is working")
    xs = [60, 185, 340, 490, 635, 765, 885, 1005]  # wider gaps where the labels are long
    d.actor(xs[0], 150, "User", width=100)
    heads = ["<b>Mac app</b><br>" + small("Chat"), "<b>App server</b><br>" + small("server.py,<br>routes/chat.py"),
             "<b>Session</b><br>" + small("reach.py"), "<b>Memory</b><br>" + small("memory.py"),
             "<b>Tiers, Rooms</b><br>" + small("swap.py,<br>rooms.py"), "<b>Core,<br>Notebook</b><br>" +
             small("core.py,<br>notes.py"), "<b>MLX models</b><br>" + small("embedder ·<br>reader")]
    for x, h in zip(xs[1:], heads):
        d.card(x - 53, 150, 106, 92, h, kind="head", size=14, pad=4)
    # long messages are written on two or three lines, so each fits between its lifelines
    msgs = [(0, 1, "1. types a<br>question,<br>presses Send"),
            (1, 2, "2. POST /api/chat/<br>message {text, ask}<br>+ X-CAMR-Token"),
            (2, 2, "3. check host, origin, token; start a job"), (2, 1, "4. {id}"),
            (2, 3, "5. answer(question,<br>today)"), (3, 7, "6. embed the question, once"), (7, 3, "7. unit vector q"),
            (3, 3, "8. choose(): the closest moment<br>in every reach read"), (3, 4, "9. recall(question,<br>chosen)"),
            (4, 5, "10. fetch(room)"),
            (5, 5, "11. [hot] RAM · [awake] one SSD<br>burst · [asleep] words"),
            (5, 4, "12. notes, tier,<br>bytes, seconds"), (4, 6, "13. desk(header, core, room)"),
            (6, 4, "14. cache: header | core | room,<br>already read"),
            (4, 7, "15. generate(4 closest moments, date,<br>question as words; cache = desk)"),
            (7, 7, "16. read the new words,<br>then write the answer"),
            (1, 2, "17. GET /api/live?<br>id=&amp;from=N,<br>again and again"),
            (2, 1, "18. events: room,<br>each word, each<br>layer's activity"),
            (7, 4, "19. words, first word, attention per word"),
            (4, 4, "20. one metrics record;<br>one line to events.jsonl"), (4, 3, "21. reply"), (3, 2, "22. reply"),
            (1, 0, "23. the answer,<br>the room it read,<br>its wait")]
    returns = {3, 6, 11, 13, 17, 18, 20, 21}
    lines = [t.count("<br>") + 1 for _, _, t in msgs]
    ys, end = [], 262  # each message starts 10px below where the one before it ends (its label included)
    for (a, b, _), n in zip(msgs, lines):
        y = end + 10 + (6 if a == b else 6 + 18 * n)
        ys.append(y)
        end = max(y + 24, y + 3 + 18 * n) if a == b else y
    bottom = end + 24
    d.frame(30, 112, W - 60, bottom + 24 - 112, "sd Answer one question")
    for x in xs:
        d.path([(x, 258 if x == xs[0] else 242), (x, bottom)], head=None, dashed=True, color="#8a94a0")
    spans = {1: [(1, 22)], 2: [(1, 21)], 3: [(4, 21)], 4: [(8, 20)], 5: [(9, 11)], 6: [(12, 13)], 7: [(5, 6), (14, 18)]}
    for lane, ranges in spans.items():
        for i, j in ranges:
            d.card(xs[lane] - 6, ys[i] - 4, 12, ys[j] - ys[i] + 8 + (26 if msgs[j][0] == msgs[j][1] else 0), "",
                   kind="act")
    for i, ((a, b, t), y) in enumerate(zip(msgs, ys)):
        n = lines[i]
        tb = f'<span style="background:#ffffff;padding:0 2px">{t}</span>'  # white only behind the words
        w = 7.3 * max(len(s) for s in t.replace("&amp;", "&").split("<br>")) + 10
        if a == b:
            x = xs[a] + 6
            d.path([(x, y), (x + 34, y), (x + 34, y + 24), (x + 2, y + 24)])
            if a == 7:
                lab(d, xs[a] - 16 - w, y + 3, w, tb, align="right")
            else:
                lab(d, x + 44, y + 3, w, tb, align="left")
            continue
        x1 = xs[a] + (6 if b > a else -6) * (a != 0)
        x2 = xs[b] - (6 if b > a else -6) * (b != 0)
        d.path([(x1, y), (x2, y)], head="open" if i in returns else "filled", dashed=i in returns)
        lx = min(max((x1 + x2) / 2 - w / 2, 40), W - 40 - w)
        lab(d, lx, y - 6 - 18 * n, w, tb)
    d.h = bottom + 40
    return d


# --------------------------------------------------------------------- states
def states() -> Diagram:
    d = Diagram("States", "State machine diagrams: a moment, its room and its vault note", 1060, 1680,
                "Rounded box: a state · ● initial state · [guard] · trigger / effect")

    def st(x, y, w, h, label):
        return d.card(x, y, w, h, label, kind="state", size=15, pad=8)

    def go(pts):
        d.path(pts, head="open")

    # a moment
    d.frame(40, 120, 980, 570, "stm A moment")
    d.deco(219, 157, 22, 22, "initial")
    go([(230, 179), (230, 215)])
    lab(d, 242, 172, 320, "a Chat message, a code note, a Long Haul event", align="left", size=13)
    st(110, 215, 240, 64, "<b>Told</b><br>“[date, day] text” arrives")
    go([(230, 279), (230, 400)])
    lab(d, 242, 296, 400, "embed; place(): [similarity ≥ 0.80 and space in an<br>awake room] join it, else start a "
                          "room /<br>read once with the room so far, append its notes", align="left", size=13)
    st(60, 400, 340, 110, "<b>Stored</b><br>notes in its room's file; words,<br>day and vector in the index;<br>"
                          "one note in the vault")
    go([(400, 440), (600, 440)])
    lab(d, 410, 414, 190, "a question / recall()")
    st(600, 400, 380, 84, "<b>On the desk</b><br>in the room read, or among<br>the 4 closest moments as words")
    go([(700, 484), (700, 550)])
    lab(d, 586, 500, 106, "[share ≥ 0.10]", align="right", size=13)
    go([(880, 484), (880, 550)])
    lab(d, 890, 500, 110, "[share < 0.10]", align="left", size=13)
    st(600, 550, 190, 60, "<b>Used</b><br>its vault note +1.0")
    st(800, 550, 180, 60, "<b>Picked up only</b>")
    go([(600, 580), (330, 580), (330, 510)])
    lab(d, 400, 554, 160, "answer logged", size=13)
    go([(890, 610), (890, 640), (250, 640), (250, 510)])
    lab(d, 500, 646, 160, "answer logged", size=13)

    # a room
    d.frame(40, 730, 980, 620, "stm A room")
    d.deco(79, 829, 22, 22, "initial")
    go([(101, 840), (220, 840)])
    lab(d, 56, 856, 160, "no room joined /<br>a new file", size=13)
    st(220, 800, 300, 96, "<b>Awake on the SSD</b><br>one .notes file of at most<br>512 tokens")
    go([(260, 800), (260, 772), (360, 772), (360, 800)])
    lab(d, 370, 758, 140, "a moment joins /<br>append", align="left", size=13)
    st(680, 800, 300, 96, "<b>Hot in RAM</b><br>kept as arrays the desk<br>takes, no SSD read")
    go([(520, 830), (680, 830)])
    lab(d, 522, 770, 156, "a question needs it /<br>one burst read,<br>kept hot", size=13)
    go([(680, 870), (520, 870)])
    lab(d, 522, 878, 156, "[RAM budget full;<br>least recently used] /<br>let go, file kept", size=13)
    go([(900, 800), (900, 772), (960, 772), (960, 800)])
    lab(d, 760, 758, 132, "a question /<br>no read", align="right", size=13)
    st(220, 1080, 300, 110, "<b>Asleep</b><br>.notes deleted; its moments<br>kept as words in the index<br>"
                            "and the vault")
    go([(300, 896), (300, 1080)])
    lab(d, 60, 950, 232, "[awake files over the disk<br>budget; weakest room first,<br>then least recently used] /<br>"
                         "delete .notes, log sleep", align="right", size=13)
    go([(440, 1080), (440, 896)])
    lab(d, 452, 960, 230, "[wake on] a question /<br>notes written again from<br>its words, log wake", align="left",
        size=13)
    go([(520, 1160), (560, 1160), (560, 1214), (480, 1214), (480, 1190)])
    lab(d, 572, 1150, 250, "a question [wake off] /<br>its moments read as words", align="left", size=13)
    d.note(620, 1230, 380, 96, "No final state: sleep removes notes, never<br>words. The engine never deletes a "
                               "moment;<br>a person deletes a vault note's file.", size=14)

    # a vault note's strength
    d.frame(40, 1390, 980, 270, "stm A vault note")
    d.deco(79, 1509, 22, 22, "initial")
    go([(101, 1520), (220, 1520)])
    lab(d, 100, 1476, 120, "kept / s = 1.0", size=13)
    st(220, 1480, 300, 84, "<b>Remembered</b><br>strength s ≥ 0.1")
    go([(300, 1480), (300, 1450), (440, 1450), (440, 1480)])
    lab(d, 456, 1440, 300, "a day unused [not pinned] / s × 0.95", align="left", size=13)
    go([(300, 1564), (300, 1600), (440, 1600), (440, 1564)])
    lab(d, 456, 1590, 300, "used in an answer / s + 1.0", align="left", size=13)
    go([(520, 1510), (680, 1510)])
    lab(d, 522, 1484, 156, "[s < 0.1]", size=13)
    st(680, 1480, 300, 84, "<b>Faded</b><br>words kept; never<br>deleted by the engine")
    go([(680, 1550), (520, 1550)])
    lab(d, 522, 1558, 156, "used / s + 1.0", size=13)
    return d


# --------------------------------------------------------------------- files
def files() -> Diagram:
    d = Diagram("Files", "File and data design of CAMR (UML artifacts)", 1080, 1700,
                "Dashed arrow: a field that points into another file")

    d.band(30, 120, 1020, 120, "~/.camr/ · one folder per reach", style="package")
    for i, (n, t) in enumerate((("session/&lt;id&gt;/", "one conversation"), ("project/&lt;name&gt;/", "one project"),
                                ("agent/&lt;name&gt;/", "one agent"), ("global/", "facts for everywhere"))):
        d.artifact(50 + 248 * i, 160, 236, 64, n, t, stereo=None)

    top = 270
    L, R, W = 50, 590, 440
    y0 = top + 50
    room = d.klass(L, y0, W, "room-NNNNNN.notes", ["raw 16-bit keys and values, token by token:",
                                                  "tokens × layers × (K, V) × KV heads × head size;",
                                                  "append-only; read whole in 1 MB pieces, eight",
                                                  "at once, F_NOCACHE; deleted when it sleeps"],
                   stereo="artifact")
    index = d.klass(R, y0, W, "index.json", ["token_bytes · room_tokens (512) · join (0.80)",
                                            "moments[ ]: mid · room · day · text · start ·",
                                            "&nbsp;&nbsp;&nbsp;&nbsp;tokens",
                                            "rooms[ ]: rid · members[ ] · tokens"], stereo="artifact")
    y1 = room.y + room.h + 70
    tiers = d.klass(L, y1, W, "tiers.json", ["tick · used{ room: the tick it was last read }",
                                            "(with tiers on: the hot rooms come first)"], stereo="artifact")
    vec = d.klass(R, y1, W, "vectors.npy", ["float32 matrix, one unit row per moment;", "row i is moment mid = i"],
                  stereo="artifact")
    y2 = max(tiers.y + tiers.h, vec.y + vec.h) + 40
    events = d.klass(L, y2, W, "events.jsonl", ["one JSON object per line, each with type and at:",
                                               "remember: moment · room · day · tokens · new_room",
                                               "answer, agent: question · room · closest · nodes ·",
                                               "&nbsp;&nbsp;&nbsp;&nbsp;share · used · words · wait_s",
                                               "sleep, wake: rooms[ ] · moment ids are mids"], stereo="artifact")
    metrics = d.klass(R, y2, W, "metrics.jsonl", ["one record per answer: first_word_s · total_s ·",
                                                 "prefill_tps · decode_tps · retrieval_ms{ choose,",
                                                 "&nbsp;&nbsp;&nbsp;&nbsp;core, fetch, wake, desk, total } · tier ·",
                                                 "read_bytes · gbps · read_share · context_tokens ·",
                                                 "history_tokens · new_tokens · peak_ram_bytes ·",
                                                 "peak_mlx_bytes · disk_bytes · question · room"],
                      stereo="artifact")
    y3 = max(events.y + events.h, metrics.y + metrics.h) + 40
    vault = d.klass(L, y3, W, "vault/&lt;reach&gt;-NNNNNN.md", ["front matter: id · day · date · room · reach ·",
                                                            "moment (its mid) · tags · strength · pinned ·",
                                                            "asleep · used · as_of · links[ [[note-id]] ] · doors[ ]",
                                                            "then the moment's words; opens in Obsidian;",
                                                            "vault/.camr-index.json saves reading every file"],
                    stereo="artifact")
    lock = d.klass(R, y3, W, ".lock", ["held (flock) while one process has the folder open;",
                                      "a second process gets ReachBusy"], stereo="artifact")
    pair = d.klass(R, lock.y + lock.h + 30, W, "ollama/ · the pairing's own notes",
                   ["notes.jsonl · vectors.f32 · vault/ollama-NNNNNN.md ·", "metrics.jsonl"], stereo="artifact")
    bottom = max(vault.y + vault.h, pair.y + pair.h) + 30
    d.band(30, top, 1020, bottom - top, "one memory folder, e.g. ~/.camr/project/kitchen/", style="package")
    d.path([(R, y0 + 100), (L + W, y0 + 100)], head="open", dashed=True)
    lab(d, L + W + 4, y0 + 52, R - L - W - 8, "start,<br>tokens", size=13)
    d.path([(R + W / 2, y1), (R + W / 2, index.y + index.h)], head="open", dashed=True)
    lab(d, R + W / 2 + 10, index.y + index.h + 20, 120, "mid = row", align="left", size=13)
    d.path([(L + W / 2, y1), (L + W / 2, room.y + room.h)], head="open", dashed=True)
    lab(d, L + W / 2 + 10, room.y + room.h + 20, 200, "used{ }: room ids", align="left", size=13)

    t2 = bottom + 40
    d.klass(50, t2 + 50, 980, "&lt;YYYY-MM-DD&gt;/&lt;HHMMSS&gt;-&lt;task&gt;-&lt;contender&gt;.json", [
        "kind · task · contender{ }: name · model · reach · core · ram_bytes · disk_bytes · wake · room_tokens · join",
        "environment{ }: machine · chip · memory_gb · power · load_1m · python · commit · dirty · camr_source_sha · mlx",
        "haul{ }: seed · tokens · events · script_sha · checkpoints[ ]: name · tokens · events · footprint_gb · summary",
        "&nbsp;&nbsp;&nbsp;&nbsp;answers[ ]: id · family · question · expected · answer · verdict · reason · metrics{ }"],
            stereo="artifact")
    led = d.klass(50, t2 + 50 + 48 + 20 + 76 + 24, 980, "claude-ledger.jsonl", [
        "one line per hold, call or count: model · purpose · effort · tokens in, cached and out · cost_usd · time"],
                  stereo="artifact")
    end = led.y + led.h + 24
    d.band(30, t2, 1020, end - t2, "records/bench/ in the repository · written by the benchmark runners",
           style="package")
    d.h = end + 30
    return d


# --------------------------------------------------------------------- deployment
def deployment() -> Diagram:
    d = Diagram("Deployment", "Deployment diagram of CAMR on the Mac", 1100, 1600,
                "3-D boxes: nodes (devices and execution environments) · lines: communication paths")
    # outside the Mac, above it
    d.node(520, 140, 250, 160, small("«device»") + "<br><b>Anthropic API</b><br>external<br><br>"
           + small("«HTTPS», benchmarks<br>only: Claude Haiku,<br>Sonnet, Opus 5.5"), depth=14)
    d.node(820, 140, 230, 160, small("«device»") + "<br><b>GitHub Actions</b><br>ubuntu-latest,<br>external<br>"
           + small("tests that need no<br>MLX, on every push"), depth=14)

    d.node(30, 370, 1030, 1050, small("«device»") + "<br><b>MacBook Pro M5 Pro (Mac17,9)</b> · macOS · 24 GB unified "
           "memory", depth=20)
    env = "#f7f9fb"
    d.node(60, 470, 270, 250, small("«executionEnvironment»") + "<br><b>CAMR Mac app</b> (SwiftUI)", depth=12,
           fill=env)
    d.artifact(80, 550, 230, 140, "CAMR.app", "Chat · CAMR / RAG /<br>off; its own launch<br>token; picks the model")
    d.node(420, 470, 590, 330, small("«executionEnvironment»") + "<br><b>Python 3.12 virtual environment</b>",
           depth=12, fill=env)
    for x, y, n, t in ((440, 545, "App server", "127.0.0.1, a free port<br>picked by the app"),
                       (725, 545, "Memory engine", "Session · Memory · Core ·<br>Rooms · Tiers · Vault"),
                       (440, 670, "Ollama pairing", "127.0.0.1:11435"),
                       (725, 670, "Benchmarks", "bench/ runners,<br>Claude client")):
        d.component(x, y, 265, 108, n, t, size=14)
    d.node(60, 870, 270, 160, small("«executionEnvironment»") + "<br><b>Ollama</b>", depth=12, fill=env)
    d.artifact(80, 930, 230, 80, "ollama serve", "127.0.0.1:11434 · qwen3")
    d.node(600, 870, 410, 230, small("«executionEnvironment»") + "<br><b>MLX</b> on the Apple-silicon GPU (Metal)",
           depth=12, fill=env)
    d.artifact(615, 950, 185, 120, "Reader", "Qwen3 1.7B · 4B ·<br>8B, 4-bit, frozen")
    d.artifact(812, 950, 185, 120, "Embedder", "Qwen3-Embedding-<br>0.6B, frozen")
    d.node(60, 1170, 950, 220, small("«device»") + "<br><b>Internal SSD</b>", depth=12, fill=env)
    for i, (n, t) in enumerate((("~/.camr/", "memories: one folder<br>per reach, rooms,<br>index, vault"),
                                ("records/", "dated records<br>(JSON) and<br>claude-ledger.jsonl"),
                                ("~/.cache/<br>huggingface/", "model weights<br>and datasets"),
                                ("~/.config/camr/<br>anthropic.env", "the key, read only<br>by the Claude client"))):
        d.artifact(80 + 232 * i, 1225, 215, 150, n, t)
    d.node(560, 1490, 260, 100, small("«device»") + "<br><b>Hugging Face Hub</b> · external<br>"
           + small("«HTTPS», first run only;<br>then HF_HUB_OFFLINE=1"), depth=14)

    # communication paths
    d.path([(330, 610), (420, 610)], head=None)
    lab(d, 332, 548, 86, "«HTTP»<br>loopback,<br>token", size=13)
    lab(d, 332, 618, 86, "starts it:<br>--model<br>--live", size=13)
    d.path([(440, 724), (390, 724), (390, 950), (330, 950)], head=None)
    lab(d, 120, 790, 262, "chat with notes as words", align="right", size=13)
    d.path([(860, 800), (860, 870)], head=None)
    lab(d, 690, 818, 160, "generate, encode", align="right", size=13)
    lab(d, 870, 818, 120, "in-process", align="left", size=13)
    d.path([(480, 800), (480, 1170)], head=None)
    lab(d, 340, 1096, 132, "append, burst read<br>(F_NOCACHE),<br>records", align="right", size=13)
    d.path([(805, 1100), (805, 1170)], head=None)
    lab(d, 815, 1120, 120, "load weights", align="left", size=13)
    d.path([(690, 300), (690, 470)], head=None)
    lab(d, 700, 318, 260, "«HTTPS» the Long Haul, questions", align="left", size=13)
    d.path([(690, 1390), (690, 1490)], head=None)
    return d


# --------------------------------------------------------------------- the assistant
def assistant() -> Diagram:
    d = Diagram("Assistant", "Component diagram of the CAMR assistant", 1100, 1460,
                "Solid arrow: calls or passes data · dashed arrow: events the app watches · «external»: off the Mac")

    def comp(x, y, w, h, name, det, stereo=None):
        return d.component(x, y, w, h, name, det, stereo=stereo, size=14)

    comp(30, 130, 360, 140, "CAMR Mac app", "Chat: Ask · Remember · Research online<br>· Attach a file; Code; "
         "the live<br>weights view", stereo="SwiftUI")
    comp(520, 140, 340, 120, "App server", "routes/chat.py · 127.0.0.1;<br>launch token; one job at a time")
    d.path([(390, 180), (520, 180)])
    lab(d, 400, 126, 110, "HTTP, loopback,<br>token", size=13)
    d.path([(520, 235), (390, 235)], head="open", dashed=True)
    lab(d, 400, 242, 110, "answers,<br>live events", size=13)

    # the server's three doors
    files = comp(40, 370, 230, 140, "Files", "media.py: PDF pages<br>as text; images and<br>video via the eyes")
    router = comp(310, 370, 230, 140, "Router", "assistant.route: one<br>word, MEMORY or<br>GENERAL")
    research = comp(580, 370, 230, 140, "Research", "assistant.research:<br>the page as marked<br>data, "
                                                "never orders")
    comp(880, 380, 190, 120, "Wikipedia", "search, then the<br>page's plain text", stereo="external")
    d.path([(690, 260), (690, 310), (155, 310), (155, 370)])
    d.path([(425, 310), (425, 370)])
    d.path([(690, 310), (695, 310), (695, 370)])
    lab(d, 163, 318, 110, "Attach a file", align="left", size=13)
    lab(d, 433, 318, 60, "Ask", align="left", size=13)
    lab(d, 703, 318, 140, "Research online", align="left", size=13)
    d.path([(810, 415), (880, 415)])
    lab(d, 812, 374, 66, "HTTPS<br>search", size=13)
    d.path([(880, 465), (810, 465)])
    lab(d, 812, 472, 66, "page<br>text", size=13)

    # the models
    comp(40, 640, 230, 130, "Eyes", "Qwen3-VL-4B-Thinking:<br>sees and reasons;<br>images, video frames",
         stereo="MLX vision model")
    comp(310, 640, 230, 130, "Reader", "Qwen3 1.7B · 4B · 8B,<br>4-bit; frozen", stereo="MLX model")
    comp(860, 640, 210, 130, "Embedder", "Qwen3-Embedding-<br>0.6B; frozen", stereo="MLX model")
    d.path([(155, 510), (155, 640)])
    lab(d, 50, 534, 98, "images and<br>video frames<br>described", align="right", size=13)
    d.path([(350, 510), (350, 640)])
    lab(d, 358, 584, 170, "GENERAL: the model's<br>own knowledge", align="left", size=13)
    d.path([(510, 510), (510, 545), (575, 545), (575, 860)])
    lab(d, 583, 600, 80, "MEMORY", align="left", size=12)
    d.path([(255, 510), (255, 530), (290, 530), (290, 860)])
    lab(d, 120, 784, 162, "kept on a shelf", align="right", size=13)
    d.path([(745, 510), (745, 860)])
    lab(d, 753, 760, 100, "kept on a shelf<br>(marked as<br>from the web)", align="left", size=13)

    # the engine: one Memory per shelf
    d.band(30, 815, 1040, 615, None, style="package")  # named at its foot: the lines into it cross its top
    d.text(44, 1396, 600, "«subsystem» Memory engine (camr_engine)", size=15, weight=600, align="left", color=INK,
           layer=0)
    d.card(50, 860, 1000, 312, "", kind="box")
    d.text(64, 870, 900, "<b>Memory</b> · memory.py, one per shelf: remember · choose · recall · answer · fade",
           size=14, align="left", color=INK)
    parts = [("Core", "core.py: standing<br>facts, in RAM"),
             ("Rooms (notes)", "rooms.py: the<br>model's keys and<br>values, on the SSD"),
             ("Tiers", "swap.py: RAM,<br>SSD, asleep<br>as words"),
             ("Vault", "vault.py: a note<br>a moment, doors"),
             ("Revision", "revise.py: SAME,<br>UPDATE or NEW; old<br>note kept, superseded"),
             ("Event log", "events.py: what<br>an answer read"),
             ("Metrics", "metrics.py: first<br>word, tier, GB/s"),
             ("Live", "live.py: layers<br>loading, firing")]
    for i, (name, det) in enumerate(parts):
        x, y = 66 + 247 * (i % 4), 905 + 132 * (i // 4)
        d.card(x, y, 233, 120, f"<b>{name}</b><br>" + small(det), kind="box", size=14, pad=6)
    d.card(50, 1192, 1000, 188, "", kind="box")
    d.text(64, 1202, 970, "<b>Shelves</b> · shelves.py: each shelf a reach; Auto files a moment by meaning; every "
           "question reads all four;<br>warm() builds the kernels and reads the newest notes into RAM", size=14,
           align="left", color=INK)
    for i, (name, det) in enumerate([("Projects", "global reach:<br>the project"),
                                     ("Coding", "project:coding:<br>what Code learns"),
                                     ("Research", "project:research:<br>from the web"),
                                     ("Personal", "project:personal:<br>the user's life")]):
        d.card(66 + 247 * i, 1255, 233, 110, f"<b>{name}</b><br>" + small(det), kind="box", size=14, pad=6)

    # the engine and the models
    d.path([(440, 860), (440, 770)])
    lab(d, 448, 790, 80, "the desk", align="left", size=13)
    d.path([(965, 860), (965, 770)])
    lab(d, 973, 790, 80, "embed", align="left", size=13)
    return d


# --------------------------------------------------------------------- class diagram of the engine
def class_engine() -> Diagram:
    """The engine's classes as built (v2/camr_engine), each with a few of its real attributes and operations."""
    d = Diagram("ClassEngine", "Class diagram of the CAMR engine (camr_engine)", 1100, 1700,
                "◆ composition · ◇ aggregation · → association · ⇢ dependency · underlined: a class method")
    X, CW = [30, 303, 577, 850], 220
    ind = "&nbsp;&nbsp;&nbsp;&nbsp;"

    def k(col, y, name, attrs, ops, stereo=None):
        return klass3(d, X[col], y, CW, name, attrs, ops, stereo=stereo)

    def m(x, y, t, align="left", w=120):  # a multiplicity or role name, small, beside a line's end
        d.text(round(x if align == "left" else x - w), round(y), w, t, size=12, color=MUTED, align=align)

    y1 = 180
    reach = k(0, y1, "Reach", ["kind: str", "name: str", "/label: str"], ["path(root): Path",
                                                                         "<u>parse(text): Reach</u>"],
              stereo="dataclass")
    session = k(1, y1, "Session", ["on: bool", "home: Reach", "memories: dict[Reach,", ind + "Memory]"],
                ["switch(on)", "memory(reach): Memory", "remember(text, day)", "recall(question)",
                 "answer(question, today)", "plain(question, today)"])
    shelf = k(2, y1, "Shelf", ["name: str", "label: str", "reach: str", "about: str", "like: tuple[str, ...]"], [],
              stereo="dataclass, frozen")
    sorter = k(3, y1, "Sorter", ["shelves: list[Shelf]", "vecs: ndarray"], ["scores(text)", "sort(text)"])
    y2 = max(b.y + b.h for b in (reach, session, shelf, sorter)) + 80
    vault = k(0, y2, "Vault", ["path: Path", "reach: str | None", "prefix: str"],
              ["write(text, …)", "link(a, b, by)", "use(nids, day)", "fade(today): int", "pin(nid, on)",
               "neighbours(nid, n)"])
    memory = k(1, y2, "Memory", ["path: Path", "reach: str | None", "closest: int = 4", "allowance: int"],
               ["remember(text, day)", "choose(question)", "recall(question)", "answer(question, today)",
                "use(moments, today, day)", "fade(today)"])
    tiers = k(2, y2, "Tiers", ["disk_budget: int | None", "wake: bool", "sleeping: set[int]", "used: dict",
                               "tick: int"],
              ["bind(rooms, …)", "load(rid): Read", "touch(rid)", "enforce(keep): list[int]", "sleep(rid)",
               "wake_room(rid): bytes"])
    embedder = k(3, y2, "Embedder", ["model", "tok", "name: str", "dim: int"], ["encode(texts)", "encode_one(text)"],
                 stereo="MLX model")
    y3 = max(b.y + b.h for b in (vault, memory, tiers, embedder)) + 80
    core = k(0, y3, "Core", ["budget: int", "members: list", "tokens: int", "/bytes: int"],
             ["candidates()", "refresh(): bool", "text(): str"])
    notebook = k(1, y3, "Notebook", ["header: list[int]", "shape: Shape", "core: list"],
                 ["write(ids, after)", "desk(rooms)"])
    rooms = k(2, y3, "Rooms", ["token_bytes: int", "room_tokens: int", "join: float", "moments: list[Moment]",
                               "rooms: list[Room]", "vectors: ndarray"],
              ["place(vec, tokens): int | None", "add(text, day, vec,", ind + "notes, rid): Moment",
               "fetch(rids): dict", "disk_bytes(): int", "save()"])
    revise = k(3, y3, "revise", None, ["revise(memory, reader,", ind + "embedder, text, source)",
                                       "judge(reader, old, new)", "mark(memory, old, new)",
                                       "closest(memory, text,", ind + "embedder, source)"], stereo="module")
    y4 = max(b.y + b.h for b in (core, notebook, rooms, revise)) + 80
    assistant = k(0, y4, "assistant", None, ["route(reader, question,", ind + "turns, closest)", "research(question)",
                                             "named_in(question, notes)", "chat_ids(reader, system,", ind +
                                             "turns, question)"], stereo="module")
    reader = k(1, y4, "Reader", ["repo: str", "max_tokens: int", "model", "tok"],
               ["chat_ids(system, user, tools)", "generate(ids, cache,", ind + "max_tokens): Reply",
                "new_cache(ids)", "<u>rewind(cache, length)</u>"], stereo="MLX model")
    live = k(2, y4, "Live", ["kind: str", "events: list[dict]", "done: bool", "stopped: bool"],
             ["add(kind, **data): dict", "finish(**data)", "since(i): dict"])
    seer = k(3, y4, "Seer", ["repo: str", "model", "processor"], ["see(images, system, user)",
                                                                 "describe(image, ask): str"], stereo="MLX vision model")
    bottom = max(b.y + b.h for b in (assistant, reader, live, seer))

    def right(b):
        return b.x + b.w

    # row 1: a session reads reaches; a shelf names one; the sorter holds the shelves
    yy = session.y + 40
    rel(d, [(session.x, yy), (right(reach), yy)])
    m(right(reach) + 3, yy - 18, "reaches", w=52)
    m(right(reach) + 3, yy + 3, "1..*", w=52)
    rel(d, [(shelf.cx, shelf.y), (shelf.cx, 140), (reach.cx, 140), (reach.cx, reach.y)], dashed=True)
    d.text(round(session.x), 118, CW, "«names» (reach: str)", size=12, color=MUTED)
    yy = sorter.y + 40
    rel(d, [(sorter.x, yy), (right(shelf), yy)])
    m(sorter.x - 3, yy - 18, "shelves", align="right", w=52)
    m(right(shelf) + 3, yy + 3, "1..*", w=52)
    xs_ = embedder.x + 0.7 * CW
    rel(d, [(xs_, sorter.y + sorter.h), (xs_, embedder.y)])
    m(xs_ + 6, embedder.y - 22, "1")

    # Session ◇— Memory, one per reach
    rel(d, [(memory.cx, session.y + session.h), (memory.cx, memory.y)], start="agg")
    m(memory.cx + 8, memory.y - 22, "1..*")
    m(memory.cx - 8, session.y + session.h + 26, "memories<br>{one per reach}", align="right", w=130)
    # Memory → Embedder, over the gap between rows 1 and 2
    gx, gy = memory.x + 0.85 * CW, memory.y - 26
    rel(d, [(gx, memory.y), (gx, gy), (embedder.x + 0.3 * CW, gy), (embedder.x + 0.3 * CW, embedder.y)])
    m(embedder.x + 0.3 * CW - 6, embedder.y - 22, "embedder 1", align="right")

    # Memory ◆— Vault, ◆— Tiers (row 2)
    yy = memory.y + 60
    rel(d, [(memory.x, yy), (right(vault), yy)], start="comp", head=None)
    m(right(vault) + 4, yy + 4, "0..1")
    rel(d, [(right(memory), yy), (tiers.x, yy)], start="comp", head=None)
    m(tiers.x - 4, yy + 4, "0..1", align="right", w=40)

    # Memory ◇— Notebook (shared by every reach), ◇— Core
    rel(d, [(memory.cx, memory.y + memory.h), (memory.cx, notebook.y)], start="agg", head=None)
    m(memory.cx + 8, notebook.y - 22, "1")
    m(memory.cx + 8, memory.y + memory.h + 24, "shared", w=80)
    by = notebook.y - 34
    cx0, cxc = memory.x + 0.15 * CW, core.x + 0.7 * CW
    rel(d, [(cx0, memory.y + memory.h), (cx0, by), (cxc, by), (cxc, core.y)], start="agg", head=None)
    m(cxc + 6, core.y - 22, "0..1")
    # Core → Vault (vaults 1..*), Core → Notebook
    vx = core.x + 0.3 * CW
    rel(d, [(vx, core.y), (vx, vault.y + vault.h)])
    m(vx - 6, vault.y + vault.h + 4, "vaults<br>1..*", align="right", w=60)
    yy = notebook.y + 50
    rel(d, [(right(core), yy), (notebook.x, yy)])
    m(notebook.x - 4, yy + 3, "1", align="right", w=20)

    # Memory ◆— Rooms and Memory → Reader, down the gap between columns 2 and 3
    xa, xb = right(memory) + 16, right(memory) + 34
    ya, yb = memory.y + memory.h - 30, memory.y + memory.h - 12
    rel(d, [(right(memory), ya), (xb, ya), (xb, rooms.y + 40), (rooms.x, rooms.y + 40)], start="comp", head=None)
    m(rooms.x - 3, rooms.y + 22, "1", align="right", w=12)
    rel(d, [(right(memory), yb), (xa, yb), (xa, reader.y + 30), (right(reader), reader.y + 30)])
    m(right(reader) + 3, reader.y + 34, "reader 1", w=52)
    # Tiers → Rooms (bind)
    rel(d, [(rooms.cx, tiers.y + tiers.h), (rooms.cx, rooms.y)])
    m(rooms.cx + 6, rooms.y - 22, "rooms 0..1")
    # Notebook → Reader
    rel(d, [(notebook.cx, notebook.y + notebook.h), (notebook.cx, reader.y)])
    m(notebook.cx + 6, reader.y - 22, "reader 1")

    # revise ⇢ Rooms, ⇢ Embedder
    yy = rooms.y + 90
    rel(d, [(revise.x, yy), (right(rooms), yy)], dashed=True)
    m(revise.x - 4, yy - 18, "«use»", align="right", w=50)
    rel(d, [(revise.cx, revise.y), (revise.cx, embedder.y + embedder.h)], dashed=True)
    m(revise.cx + 6, revise.y - 26, "«use»")
    # assistant ⇢ Reader, ⇢ Live; Reader ⇢ Live
    yy = reader.y + 60
    rel(d, [(right(assistant), yy), (reader.x, yy)], dashed=True)
    m(right(assistant) + 2, yy - 18, "«use»", w=40)
    yy = reader.y + 110
    rel(d, [(right(reader), yy), (live.x, yy)], dashed=True)
    m(right(reader) + 3, yy + 4, "«reports<br>to»", w=52)
    ly = bottom + 30
    rel(d, [(assistant.cx, assistant.y + assistant.h), (assistant.cx, ly), (live.cx, ly),
            (live.cx, live.y + live.h)], dashed=True)
    m(live.cx + 6, live.y + live.h + 4, "«use» (reporting)", w=130)
    d.h = ly + 40
    return d


# --------------------------------------------------------------------- DFD level 0
def dfd0() -> Diagram:
    """Process 0 of the context diagram, opened into its five processes and five data stores (Gane–Sarson). Every
    flow that crosses the boundary in the context diagram appears here, split where two processes share it."""
    d = Diagram("DFD0", "Level 0 data flow diagram of CAMR (Gane–Sarson)", 1100, 1665,
                "Dashed: the CAMR v1 baseline only · a second line: a store or entity drawn twice")

    def f(pts, label=None, at=None, w=150, align="center", dashed=False):
        d.path(pts, dashed=dashed)
        if label:
            lab(d, at[0], at[1], w, label, align=align, size=13)

    def copy_mark(x, y, w, h):  # Gane–Sarson: an entity drawn a second time has a stroke across its corner
        d.raw(x + w - 22, y + h - 11.5, 26, 1.8, f"background:{LINE};transform:rotate(-45deg)", layer=3)

    # external entities
    d.gs_entity(30, 130, 610, 100, "User<br>" + small("of the Mac app (Chat, Code)"))
    d.gs_entity(830, 130, 240, 100, "Hugging Face Hub<br>" + small("model weights ·<br>benchmark datasets"))
    d.gs_entity(90, 300, 170, 100, "Wikipedia<br>" + small("public API"))
    d.gs_entity(800, 1040, 230, 100, "Ollama<br>" + small("a separate program<br>on the Mac"))
    d.gs_entity(30, 1225, 175, 115, "Researcher<br>" + small("student, supervisor,<br>examiner"))
    d.gs_entity(900, 1225, 170, 125, "Anthropic API<br>" + small("Claude Haiku,<br>Sonnet, Opus 5.5"))
    EY = 1540
    d.gs_entity(30, EY, 190, 95, "Cloud model<br>(baseline)<br>" + small("Kimi K3, Moonshot"))
    d.gs_entity(360, EY, 200, 95, "Automation<br>platform<br>" + small("n8n (baseline)"))
    d.gs_entity(590, EY, 170, 95, "Public benchmark<br>files " + small("(baseline)"))
    d.gs_entity(780, EY, 180, 95, "Hugging Face Hub<br>" + small("benchmark<br>datasets"))
    copy_mark(786, EY + 6, 174, 89)

    # processes
    d.gs_process(370, 290, 250, 140, "3", "Research online,<br>read a file", size=15)
    d.gs_process(30, 520, 220, 340, "1", "Remember<br>a moment<br>" + small("revise · place in a<br>room · write notes<br>"
                                                                       "and a vault note"), size=15)
    d.gs_process(720, 520, 310, 420, "2", "Answer a question<br>" + small("route · choose · recall ·<br>"
                                                                      "lay the desk · generate"), size=15)
    d.gs_process(30, 920, 220, 225, "4", "Fade and sleep<br>" + small("5% a day; rooms past<br>the disk budget "
                                                                   "sleep"), size=15)
    d.gs_process(320, 1210, 470, 250, "5", "Run a benchmark<br>" + small("Long Haul · Hugging Face suites ·<br>"
                                                                    "speed and RAM · Claude alone"), size=15)

    # data stores, and the copies that process 4 uses
    for sid, y, name in (("D1", 580, "Room files (.notes)"), ("D2", 660, "Index and vectors"),
                         ("D3", 740, "Vault (Markdown)"), ("D4", 820, "Event, metrics logs")):
        gs_store(d, 380, y, 230, 50, sid, name)
    for sid, y, name in (("D3", 925, "Vault (Markdown)"), ("D1", 1015, "Room files (.notes)"),
                         ("D2", 1095, "Index and vectors")):
        gs_store(d, 380, y, 230, 45, sid, name, duplicate=True)
    gs_store(d, 30, 1413, 175, 45, "D5", "Run records")

    # the user, research and the web
    f([(60, 230), (60, 520)], "moments to remember", (68, 252), 200, "left")
    f([(430, 230), (430, 290)], "research requests,<br>files to remember", (270, 236), 152, "right")
    f([(560, 290), (560, 230)], "answers from<br>the web", (568, 236), 130, "left")
    f([(370, 335), (260, 335)], "a search for<br>the question", (262, 299), 106)
    f([(260, 375), (370, 375)], "the best page's<br>plain text", (262, 381), 106)
    f([(400, 430), (400, 470), (180, 470), (180, 520)], "page and file text,<br>marked by source", (190, 476), 200,
      "left")
    f([(620, 400), (690, 400), (690, 545), (720, 545)], "the page,<br>as marked<br>data", (698, 418), 76, "left")
    f([(640, 160), (800, 160), (800, 520)], "questions, code tasks,<br>approvals, memory<br>on or off", (808, 250), 185,
      "left")
    f([(780, 520), (780, 200), (640, 200)], "answers (from memory<br>or the model), code<br>changes, what each<br>"
                                            "answer read", (628, 282), 145, "right")
    f([(1000, 230), (1000, 520)], "model weights<br>(first download only)", (830, 400), 162, "right")

    # 1 and the stores
    f([(250, 600), (380, 600)], "notes: keys<br>and values", (254, 562), 122)
    f([(250, 675), (380, 675)], "moment, room,<br>vector", (254, 637), 122)
    f([(380, 695), (250, 695)], "closest<br>moments", (254, 699), 122)
    f([(250, 765), (380, 765)], "a vault note", (254, 745), 122)
    f([(250, 845), (380, 845)], "remember event", (254, 825), 122)
    # 2 and the stores
    f([(610, 605), (720, 605)], "a room's notes<br>(burst read)", (612, 567), 106)
    f([(610, 685), (720, 685)], "closest<br>moment, room", (612, 647), 106)
    f([(610, 755), (720, 755)], "core notes", (612, 735), 106)
    f([(720, 775), (610, 775)], "used: +1.0", (612, 779), 106)
    f([(720, 832), (610, 832)], "events, metrics", (612, 812), 106)
    f([(610, 858), (720, 858)], "what each<br>answer read", (612, 862), 106)
    # 2 and Ollama
    f([(880, 940), (880, 1046)], "a chat with<br>recalled notes<br>as words", (774, 950), 98, "right")
    f([(1000, 1046), (1000, 940)], "the streamed<br>answer, its<br>timings", (894, 950), 98, "right")
    # 4 and its copies of the stores
    f([(380, 935), (250, 935)], "strength, last use", (254, 915), 122)
    f([(250, 958), (380, 958)], "× 0.95 a day", (254, 962), 122)
    f([(250, 1037), (380, 1037)], "sleep: deleted;<br>wake: rewritten", (254, 999), 122)
    f([(380, 1117), (250, 1117)], "a room's moments<br>as words", (254, 1079), 122)

    # 5: the benchmark and its parts
    f([(735, 940), (735, 1210)], "answers and<br>their metrics", (628, 960), 100, "right")
    f([(765, 1210), (765, 940)], "checkpoint<br>questions", (773, 1150), 100, "left")
    f([(340, 1210), (340, 1180), (15, 1180), (15, 700), (30, 700)], "the scripted history: tell(text, day)",
      (40, 1158), 290, "left")
    f([(205, 1262), (320, 1262)], "contender, model,<br>cut, seed,<br>commands", (207, 1203), 112)
    f([(320, 1312), (205, 1312)], "dated records,<br>tables, charts,<br>cost ledger", (207, 1316), 112)
    f([(320, 1425), (205, 1425)], "dated records,<br>ledger lines", (207, 1387), 112)
    f([(205, 1448), (320, 1448)], "past records", (207, 1452), 112)
    f([(790, 1262), (906, 1262)], "the scripted<br>history and its<br>questions", (792, 1203), 112)
    f([(906, 1320), (790, 1320)], "answers, tokens,<br>cost (kept in<br>the ledger)", (792, 1324), 112)
    f([(340, 1460), (340, 1485), (100, 1485), (100, EY + 6)], "prompts: ceiling, escalations", (110, 1489), 220,
      "left", dashed=True)
    f([(160, EY + 6), (160, 1517), (380, 1517), (380, 1460)], "answers, token counts", (170, 1521), 200, "left",
      dashed=True)
    f([(440, 1460), (440, EY + 6)], "answers", (384, 1466), 50, "right", dashed=True)
    f([(520, EY + 6), (520, 1460)], "teach, forget,<br>ask", (528, 1466), 90, "left", dashed=True)
    f([(680, EY + 6), (680, 1460)], "questions,<br>documents", (594, 1505), 80, "right", dashed=True)
    f([(870, EY + 6), (870, 1485), (770, 1485), (770, 1460)], "benchmark<br>datasets", (878, 1490), 90, "left")
    d.card(622, 1010, 104, 122, "Dashed: CAMR v1<br>baseline only.<br>Second line in a<br>store, or stroke<br>"
           "across a corner:<br>drawn twice.", kind="box", size=12, align="left", pad=5)  # the key
    return d


DIAGRAMS = {"context": context, "use_cases": use_cases, "evaluation_pipeline": activity,
            "architecture": architecture, "sequence_question": sequence, "state_room": states, "files": files,
            "deployment": deployment, "assistant": assistant, "class_engine": class_engine, "dfd0": dfd0}

try:  # the two baseline diagrams, drawn by the earlier generator (read only) at the same scale
    import diagrams as _v1  # noqa: E402
    DIAGRAMS.update({"architecture_v1": _v1.architecture_v1, "schema_v1": _v1.schema_v1})
except Exception:  # noqa: BLE001
    pass


def render(name: str, d: Diagram) -> Path:
    html = d.plain_html().replace("<style>body{margin:0}</style>",
                                  f"<style>body{{margin:0;margin-top:-{TOP}px;overflow:hidden}}</style>")
    out = OUT / f"{name}.png"
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / f"{name}.html"
        page.write_text(html)
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=3",
                        f"--window-size={d.w},{d.h - TOP}", "--virtual-time-budget=5000",
                        f"--user-data-dir={tmp}/profile", f"--screenshot={out}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)
    return out


def main(names: list[str]) -> None:
    for name in names or list(DIAGRAMS):
        print(render(name, DIAGRAMS[name]()))


if __name__ == "__main__":
    main(sys.argv[1:])
