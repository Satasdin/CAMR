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

from kit import INK, MUTED, Box, Diagram  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TOP = 104  # the title band left out of the capture


def lab(d: Diagram, x, y, w, t, align="center", size=14, bg=None):
    d.text(round(x), round(y), round(w), t, size=size, color=MUTED, align=align, bg=bg)


def small(t: str) -> str:
    return f'<span style="font-size:13px;color:{MUTED}">{t}</span>'


# --------------------------------------------------------------------- context
def context() -> Diagram:
    d = Diagram("Context", "Context diagram of CAMR (Gane–Sarson)", 1500, 1000,
                "Solid: CAMR · dashed: the CAMR v1 baseline only")
    p = d.gs_process(600, 300, 300, 660, "0", '<span style="font-size:22px"><b>CAMR</b></span><br>the memory engine,'
                     '<br>its app and its<br>benchmarks, on the Mac')

    def left(cy, name, into, out):
        d.gs_entity(40, cy - 50, 280, 100, name)
        d.path([(320, cy - 20), (p.x, cy - 20)])
        lab(d, 330, cy - 28 - 18 * (into.count("<br>") + 1), 260, into)
        d.path([(p.x, cy + 20), (320, cy + 20)])
        lab(d, 330, cy + 28, 260, out)

    def right(cy, name, out, into, dashed=False, out_first=True):
        d.gs_entity(1180, cy - 50, 280, 100, name)
        top, bottom = (out, into) if out_first else (into, out)
        if out_first:
            d.path([(p.x + p.w, cy - 20), (1186, cy - 20)], dashed=dashed)
            d.path([(1186, cy + 20), (p.x + p.w, cy + 20)], dashed=dashed)
        else:
            d.path([(1186, cy - 20), (p.x + p.w, cy - 20)], dashed=dashed)
            d.path([(p.x + p.w, cy + 20), (1186, cy + 20)], dashed=dashed)
        lab(d, 910, cy - 28 - 18 * (top.count("<br>") + 1), 266, top)
        lab(d, 910, cy + 28, 266, bottom)

    left(470, "User<br>" + small("of the Mac app (Chat, Code)"),
         "moments to remember, questions,<br>code tasks, approvals,<br>memory on or off, reach",
         "answers, code changes,<br>what each answer read,<br>vault notes")
    left(800, "Researcher<br>" + small("student, supervisor, examiner"),
         "contender, model, cut, seed,<br>benchmark commands", "dated records, tables,<br>charts, cost ledger")

    d.gs_entity(440, 130, 300, 100, "Hugging Face Hub<br>" + small("model weights · benchmark datasets"))
    d.path([(590, 230), (590, p.y)])
    lab(d, 600, 244, 200, "weights and datasets<br>(first download only)", align="left")
    d.gs_entity(800, 130, 280, 100, "Public benchmark files<br>" + small("PopQA · HotpotQA · 2Wiki · GSM8K<br>"
                                                                          "(baseline)"))
    d.path([(950, 230), (950, 268), (860, 268), (860, p.y)], dashed=True)
    lab(d, 870, 274, 200, "questions, documents", align="left")

    right(390, "Ollama<br>" + small("a separate program on the Mac"), "a chat with recalled<br>notes as words",
          "the streamed answer,<br>its timings")
    right(560, "Anthropic API<br>" + small("Claude Haiku, Sonnet, Opus 5.5:<br>the yardstick, benchmarks only"),
          "the scripted history<br>and its questions", "answers, tokens, cost<br>(kept in the ledger)")
    right(730, "Cloud model (baseline)<br>" + small("Kimi K3, Moonshot API"), "prompts: ceiling,<br>escalations",
          "answers, token counts", dashed=True)
    right(880, "Automation platform<br>" + small("n8n workflows (baseline)"), "answers", "teach, forget, ask",
          dashed=True, out_first=False)
    return d


# --------------------------------------------------------------------- use cases
def use_cases() -> Diagram:
    d = Diagram("UseCases", "Use case diagram of CAMR", 1500, 1100,
                "An italic name is abstract · dashed arrows: «include» and «extend» · hollow triangle: generalisation")
    d.band(330, 120, 930, 960, "CAMR", style="boundary")

    def uc(cx, cy, name, italic=False):
        label = f"<i>{name}</i>" if italic else name
        return d.card(cx - 125, cy - 38, 250, 76, label, kind="usecase", size=16, pad=16)

    L, M, R = 470, 795, 1115
    chat = uc(L, 210, "Chat with memory")
    tell = uc(L, 340, "Tell something<br>to remember")
    code = uc(L, 470, "Code with a<br>local agent")
    watch = uc(L, 600, "Watch what an<br>answer reads")
    vault = uc(L, 730, "Browse the vault<br>(Obsidian)")
    pair = uc(L, 900, "Pair Ollama<br>with memory")
    switch = uc(M, 190, "Switch memory<br>on or off")
    reach = uc(M, 320, "Choose a reach")
    recall = uc(M, 520, "Recall from memory")
    bench = uc(M, 760, "Run a benchmark", italic=True)
    grade = uc(M, 990, "Grade answers<br>by rule")
    claude = uc(R, 200, "Ask Claude alone<br>(the yardstick)")
    haul = uc(R, 560, "Run the Long Haul")
    suites = uc(R, 700, "Run the Hugging<br>Face suites")
    speed = uc(R, 850, "Measure speed<br>and RAM")
    record = uc(R, 1000, "Write a dated record")

    def actor(cx, top, name, right=False):
        d.actor(cx, top, name)
        return cx - 26 if right else cx + 26, top + 40

    user = actor(80, 470, "User")
    ollama = actor(200, 900, "«system»<br>Ollama")
    researcher = actor(1400, 640, "Researcher", right=True)
    api = actor(1400, 150, "«system»<br>Claude API", right=True)

    def assoc(who, case: Box, aim=0):
        d.path([who, case.hit(*who, case.cx + aim, case.cy)], head=None)

    for c in (chat, tell, code, watch, vault, pair):
        assoc(user, c)
    assoc(ollama, pair)
    for c in (haul, suites, speed):
        assoc(researcher, c)
    assoc(api, claude)

    def rel(src: Box, dst: Box, label, side=1, at=0.5, head="open"):
        p, q = src.toward(dst.cx, dst.cy), dst.toward(src.cx, src.cy)
        d.path([p, q], head=head, dashed=label is not None)
        if label:
            d.along(p, q, label, side=side, at=at)

    rel(switch, chat, "«extend»", side=1)
    rel(reach, chat, "«extend»", side=-1, at=0.45)
    rel(chat, recall, "«include»", side=1, at=0.6)
    rel(code, recall, "«include»", side=-1, at=0.55)
    rel(pair, recall, "«include»", side=-1, at=0.6)
    rel(bench, recall, "«include»", side=-1)
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
    d = Diagram("Architecture", "Component diagram of CAMR", 1560, 1100,
                "Solid arrow: calls or passes data · dashed arrow: the CAMR v1 baseline, used only by the benchmarks")

    def comp(x, y, w, h, name, det, stereo=None):
        return d.component(x, y, w, h, name, det, stereo=stereo, size=14)

    comp(40, 150, 250, 120, "CAMR Mac app", "Chat · Code; starts the<br>engine with its own token", stereo="SwiftUI")
    comp(40, 520, 250, 90, "ollama CLI", "OLLAMA_HOST=<br>127.0.0.1:11435")
    comp(40, 660, 250, 80, "Ollama", "127.0.0.1:11434", stereo="program")
    comp(40, 800, 250, 90, "Benchmark command line", "python -m<br>camr_engine.bench.…")
    comp(360, 150, 250, 120, "App server", "server.py · 127.0.0.1 · Host,<br>Origin and X-CAMR-Token checks")
    comp(360, 330, 250, 120, "Code agent", "agentic/: workspace, tools,<br>MCP servers, skills; every<br>"
                                          "command waits for approval")
    comp(360, 520, 250, 90, "Ollama pairing", "pair/ollama.py · proxy on<br>127.0.0.1:11435")
    comp(360, 780, 250, 130, "Benchmark runners", "bench/: longhaul · local ·<br>ollama_run · suite_run ·<br>"
                                                  "reach_run · ram · throughput")
    comp(360, 980, 250, 80, "CAMR v1 engine", "the baseline, as a library")

    d.band(680, 130, 840, 560, "«subsystem» Memory engine (camr_engine)", style="package", label_side="right")
    comp(700, 175, 800, 64, "Session", "reach.py: reads several reaches (session · project · agent · global), "
                                       "writes one; memory on or off")
    d.card(700, 280, 800, 390, "", kind="box")
    d.text(714, 290, 600, "<b>Memory</b> · memory.py: remember · choose · recall · answer · fade", size=15,
           align="left", color=INK)
    ix, iy = 700 + 800 - 24, 288
    d.deco(ix, iy, 14, 18, "icon", layer=3)
    d.deco(ix - 4, iy + 3, 9, 5, "icon", layer=3)
    d.deco(ix - 4, iy + 10, 9, 5, "icon", layer=3)
    parts = [("Core", "«subconscious» core.py:<br>≤ 256 tokens of core<br>notes, kept in RAM"),
             ("Rooms", "«conscious» rooms.py:<br>≤ 512-token rooms,<br>join 0.80, burst read"),
             ("Tiers", "swap.py: hot rooms in<br>RAM, awake on the SSD,<br>asleep past the budget"),
             ("Vault", "«archive» vault.py: one<br>Markdown note a moment,<br>doors, fades 5% a day"),
             ("Notebook", "notes.py: writes notes,<br>lays the desk, turns<br>keys (RoPE)"),
             ("Event log", "events.py: one line an<br>answer; attention<br>per written word"),
             ("Metrics", "metrics.py: first word,<br>retrieval, tier, GB/s,<br>RAM, disk"),
             ("Live", "live.py: weights loading,<br>the room read, words,<br>layer activity")]
    for i, (name, det) in enumerate(parts):
        x, y = 715 + 195 * (i % 4), 330 + 160 * (i // 4)
        d.card(x, y, 185, 140, f"<b>{name}</b><br>" + small(det), kind="box", size=14, pad=8)

    comp(700, 760, 300, 110, "Reader", "Qwen3 1.7B · 4B · 8B, 4-bit;<br>frozen, thinking off", stereo="MLX model")
    comp(1040, 760, 250, 110, "Embedder", "Qwen3-Embedding-0.6B;<br>frozen", stereo="MLX model")
    comp(1320, 760, 200, 110, "Claude client", "bench/claude.py; ledger<br>with a $60 cap")

    d.path([(290, 200), (360, 200)])
    lab(d, 292, 130, 66, "HTTP,<br>loopback,<br>token", size=13)
    d.path([(360, 230), (290, 230)], head="open", dashed=True)
    lab(d, 292, 238, 66, "answer,<br>live events", size=13)
    d.path([(610, 195), (700, 195)])
    lab(d, 612, 152, 64, "say,<br>settings", size=13)
    d.path([(1100, 239), (1100, 280)])
    lab(d, 1110, 246, 200, "one Memory per reach", align="left", size=13)
    d.path([(485, 270), (485, 330)])
    lab(d, 495, 286, 80, "code runs", align="left")
    d.path([(610, 390), (650, 390), (650, 225), (700, 225)])
    lab(d, 614, 398, 80, "brain with<br>memory", align="left")
    d.path([(290, 565), (360, 565)])
    d.path([(485, 610), (485, 700), (290, 700)])
    lab(d, 300, 706, 180, "the chat, notes in front<br>of the last message", align="left")
    d.path([(610, 565), (700, 565)])
    lab(d, 612, 524, 64, "recall<br>as words", size=13)
    d.path([(290, 845), (360, 845)])
    d.path([(610, 830), (660, 830), (660, 640), (700, 640)])
    lab(d, 614, 838, 120, "contender:<br>tell, ask", align="left")
    d.path([(485, 910), (485, 980)], head="open", dashed=True)
    lab(d, 495, 930, 80, "baseline", align="left")
    d.path([(610, 890), (1420, 890), (1420, 870)])
    lab(d, 1080, 896, 230, "Claude alone, the yardstick")
    d.path([(850, 670), (850, 760)])
    lab(d, 860, 700, 130, "generate,<br>write notes", align="left")
    d.path([(1165, 670), (1165, 760)])
    lab(d, 1175, 708, 60, "embed", align="left")
    return d


# --------------------------------------------------------------------- sequence
def sequence() -> Diagram:
    d = Diagram("Sequence", "Sequence diagram: one question answered in Chat", 1560, 1460,
                "Solid line, filled head: a call · dashed line, open head: its return · bars: while a part is working")
    xs = [90, 270, 455, 640, 825, 1010, 1195, 1400]
    d.actor(xs[0], 150, "User")
    heads = ["<b>Mac app</b><br>" + small("Chat"), "<b>App server</b><br>" + small("server.py, routes/chat.py"),
             "<b>Session</b><br>" + small("reach.py"), "<b>Memory</b><br>" + small("memory.py"),
             "<b>Tiers, Rooms</b><br>" + small("swap.py, rooms.py"), "<b>Core, Notebook</b><br>" +
             small("core.py, notes.py"), "<b>MLX models</b><br>" + small("embedder · reader")]
    for x, h in zip(xs[1:], heads):
        d.card(x - 88, 160, 176, 56, h, kind="head", size=15, pad=6)
    msgs = [(0, 1, "1. types a question, presses Send"),
            (1, 2, "2. POST /api/chat/message {text, ask} + X-CAMR-Token"),
            (2, 2, "3. check host, origin, token; start a job"), (2, 1, "4. {id}"),
            (2, 3, "5. answer(question, today)"), (3, 7, "6. embed the question, once"), (7, 3, "7. unit vector q"),
            (3, 3, "8. choose(): the closest moment in every reach read"), (3, 4, "9. recall(question, chosen)"),
            (4, 5, "10. fetch(room)"),
            (5, 5, "11. [hot] RAM · [awake] one SSD burst · [asleep] words"),
            (5, 4, "12. notes, tier, bytes, seconds"), (4, 6, "13. desk(header, core, room)"),
            (6, 4, "14. cache: header | core | room, already read"),
            (4, 7, "15. generate(4 closest moments, date, question as words; cache = desk)"),
            (7, 7, "16. read the new words, then write the answer"),
            (1, 2, "17. GET /api/live?id=&from=N, again and again"),
            (2, 1, "18. events: room, each word, each layer's activity"),
            (7, 4, "19. words, first word, attention per word"),
            (4, 4, "20. one metrics record; one line to events.jsonl"), (4, 3, "21. reply"), (3, 2, "22. reply"),
            (1, 0, "23. the answer, the room it read, its wait")]
    returns = {3, 6, 11, 13, 17, 18, 20, 21}
    ys, y = [], 292
    for a, b, _ in msgs:
        ys.append(y)
        y += 58 if a == b else 42
    bottom = y + 10
    d.frame(30, 112, 1500, bottom + 24 - 112, "sd Answer one question")
    for x in xs:
        d.path([(x, 230 if x == xs[0] else 216), (x, bottom)], head=None, dashed=True, color="#8a94a0")
    spans = {1: [(1, 22)], 2: [(1, 21)], 3: [(4, 21)], 4: [(8, 20)], 5: [(9, 11)], 6: [(12, 13)], 7: [(5, 6), (14, 18)]}
    for lane, ranges in spans.items():
        for i, j in ranges:
            d.card(xs[lane] - 6, ys[i] - 4, 12, ys[j] - ys[i] + 8 + (26 if msgs[j][0] == msgs[j][1] else 0), "",
                   kind="act")
    for i, ((a, b, t), y) in enumerate(zip(msgs, ys)):
        w = 7.4 * len(t) + 8
        if a == b:
            x = xs[a] + 6
            d.path([(x, y), (x + 34, y), (x + 34, y + 24), (x + 2, y + 24)])
            if a == 7:
                lab(d, xs[a] - 16 - w, y + 3, w, t, align="right", bg="#ffffff")
            else:
                lab(d, x + 44, y + 3, w, t, align="left", bg="#ffffff")
            continue
        x1 = xs[a] + (6 if b > a else -6) * (a != 0)
        x2 = xs[b] - (6 if b > a else -6) * (b != 0)
        d.path([(x1, y), (x2, y)], head="open" if i in returns else "filled", dashed=i in returns)
        lab(d, (x1 + x2) / 2 - w / 2, y - 24, w, t, bg="#ffffff")
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
    d = Diagram("Deployment", "Deployment diagram of CAMR on the Mac", 1560, 1060,
                "3-D boxes: nodes (devices and execution environments) · lines: communication paths")
    d.node(40, 170, 1200, 860, small("«device»") + "<br><b>MacBook Pro M5 Pro (Mac17,9)</b> · macOS · 24 GB unified "
           "memory", depth=20)
    env = "#f7f9fb"
    d.node(80, 290, 260, 240, small("«executionEnvironment»") + "<br><b>CAMR Mac app</b> (SwiftUI)", depth=12,
           fill=env)
    d.artifact(100, 370, 220, 130, "CAMR.app", "Chat · Code;<br>its own launch token;<br>picks the model")
    d.node(440, 290, 370, 330, small("«executionEnvironment»") + "<br><b>Python 3.12 virtual environment</b>",
           depth=12, fill=env)
    for x, y, n, t in ((455, 360, "App server", "127.0.0.1:8790<br>(8765 alone)"),
                       (635, 360, "Memory engine", "Session · Memory ·<br>Core · Rooms ·<br>Tiers · Vault"),
                       (455, 480, "Ollama pairing", "127.0.0.1:11435"),
                       (635, 480, "Benchmarks", "bench/ runners,<br>Claude client")):
        d.component(x, y, 165, 100, n, t, size=14)
    d.node(900, 290, 300, 330, small("«executionEnvironment»") + "<br><b>MLX</b> on the Apple-silicon<br>GPU (Metal)",
           depth=12, fill=env)
    d.artifact(920, 390, 260, 96, "Reader", "Qwen3 1.7B · 4B · 8B,<br>4-bit, frozen")
    d.artifact(920, 500, 260, 96, "Embedder", "Qwen3-Embedding-0.6B,<br>frozen")
    d.node(80, 640, 260, 160, small("«executionEnvironment»") + "<br><b>Ollama</b>", depth=12, fill=env)
    d.artifact(100, 700, 220, 80, "ollama serve", "127.0.0.1:11434 · qwen3")
    d.node(420, 720, 780, 280, small("«device»") + "<br><b>Internal SSD</b>", depth=12, fill=env)
    d.artifact(440, 800, 175, 170, "~/.camr/", "memories: one<br>folder per reach,<br>rooms, index,<br>vault")
    d.artifact(630, 800, 175, 170, "records/", "dated records<br>(JSON) and<br>claude-ledger<br>.jsonl")
    d.artifact(820, 800, 175, 170, "~/.cache/<br>huggingface/", "model weights<br>and datasets")
    d.artifact(1010, 800, 175, 170, "~/.config/camr/<br>anthropic.env", "the key, read<br>only by the<br>"
                                                                          "Claude client")
    d.node(1310, 190, 220, 170, small("«device»") + "<br><b>Anthropic API</b><br>external<br><br>"
           + small("«HTTPS», benchmarks<br>only: Claude Haiku,<br>Sonnet, Opus 5.5"), depth=14)
    d.node(1310, 460, 220, 160, small("«device»") + "<br><b>GitHub Actions</b><br>ubuntu-latest, external<br><br>"
           + small("tests that need no<br>MLX, on every push"), depth=14)
    d.node(1310, 780, 220, 150, small("«device»") + "<br><b>Hugging Face Hub</b><br>external<br>"
           + small("«HTTPS», first run only;<br>then HF_HUB_OFFLINE=1"), depth=14)
    d.path([(340, 420), (440, 420)], head=None)
    lab(d, 354, 350, 82, "«HTTP»<br>loopback,<br>token", size=13)
    lab(d, 354, 428, 82, "starts it:<br>--model<br>--live", size=13)
    d.path([(810, 440), (900, 440)], head=None)
    lab(d, 824, 400, 74, "generate,<br>encode", size=13)
    lab(d, 824, 448, 74, "in-process", size=13)
    d.path([(455, 560), (400, 560), (400, 690), (340, 690)], head=None)
    lab(d, 150, 580, 242, "chat with notes as words", align="right", size=13)
    d.path([(620, 620), (620, 708)], head=None)
    lab(d, 630, 640, 200, "append, burst read<br>(F_NOCACHE), records", align="left")
    d.path([(1050, 708), (1050, 620)], head=None)
    lab(d, 1060, 650, 100, "load weights", align="left")
    d.path([(760, 278), (760, 240), (1310, 240)], head=None)
    lab(d, 900, 214, 260, "«HTTPS» the Long Haul, questions")
    d.path([(1200, 860), (1310, 860)], head=None)
    return d


DIAGRAMS = {"context": context, "use_cases": use_cases, "evaluation_pipeline": activity,
            "architecture": architecture, "sequence_question": sequence, "state_room": states, "files": files,
            "deployment": deployment}


def render(name: str, d: Diagram) -> Path:
    html = d.plain_html().replace("<style>body{margin:0}</style>",
                                  f"<style>body{{margin:0;margin-top:-{TOP}px;overflow:hidden}}</style>")
    out = OUT / f"{name}.png"
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / f"{name}.html"
        page.write_text(html)
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                        f"--window-size={d.w},{d.h - TOP}", "--virtual-time-budget=5000",
                        f"--user-data-dir={tmp}/profile", f"--screenshot={out}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)
    return out


def main(names: list[str]) -> None:
    for name in names or list(DIAGRAMS):
        print(render(name, DIAGRAMS[name]()))


if __name__ == "__main__":
    main(sys.argv[1:])
