"""Architecture and process diagrams for the report (Graphviz), drawn from the implemented code paths.

    python scripts/make_diagrams.py --out docs/figures/diagrams
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BLUE, ORANGE, GREEN, INK, INK2, SURF, LINE = "#2a78d6", "#eb6834", "#1baf7a", "#111111", "#52514e", "#f3f5f9", "#9aa3b2"
BASE = f'''graph [fontname="Helvetica" fontsize=11 bgcolor="white" pad=0.25 nodesep=0.35 ranksep=0.45 newrank=true]
node [fontname="Helvetica" fontsize=10.5 shape=box style="rounded,filled" fillcolor="{SURF}" color="{LINE}" penwidth=1.1 fontcolor="{INK}" margin="0.14,0.07"]
edge [fontname="Helvetica" fontsize=9 color="{INK2}" fontcolor="{INK2}" arrowsize=0.7 penwidth=1.0]
'''

DIAGRAMS: dict[str, str] = {}

DIAGRAMS["architecture"] = f'''digraph G {{ rankdir=TB; {BASE}
user [label="User / Researcher" shape=ellipse fillcolor="white"];
ui [label="Interfaces: camr CLI · CAMR Personal (web UI) · Inspector (read-only)" fillcolor="#e9f1fb" color="{BLUE}"];
subgraph cluster_engine {{ label="CAMR memory engine (camr.memory) — on the device"; fontname="Helvetica-Bold"; color="{GREEN}"; style="rounded"; penwidth=1.4;
  subgraph cluster_write {{ label="Write path (teach)"; color="{LINE}"; style="rounded,dotted";
    wp [label="Write policy\nverbatim chunks | structured"]; sc [label="Screener\nempty · duplicate · injection"];
    im [label="Importance score"]; emb1 [label="Embedder\nBGE-small / nomic-embed"]; }}
  subgraph cluster_read {{ label="Read path (ask)"; color="{LINE}"; style="rounded,dotted";
    emb2 [label="Embed question"]; knn [label="kNN search (k = 20)"]; gate [label="Gate: abstain below τ,\nadmit within 0.15 of best" fillcolor="#e8f7f0" color="{GREEN}"];
    bridge [label="Entity bridging" fillcolor="#e8f7f0" color="{GREEN}"]; budg [label="Token budgeter (≤ B)"]; }}
  store [label="SQLite + sqlite-vec (one file)\nnotes · vectors · provenance · logs" shape=cylinder fillcolor="#e9f1fb" color="{BLUE}"];
}}
prompt [label="Prompt template (fixed, hashed)"];
slm [label="Frozen small model via Ollama (loopback only)" fillcolor="#fdeee6" color="{ORANGE}"];
router [label="Learned router + grounding cascade" fillcolor="#e8f7f0" color="{GREEN}"];
cloud [label="Cloud model (Kimi K3): ceiling / escalation only" fillcolor="#fdeee6" color="{ORANGE}" style="rounded,filled,dashed"];
harness [label="Harness: conditions · scoring · bootstrap · tables"];
user -> ui;
ui -> wp [label="teach"]; wp -> sc; sc -> im; im -> emb1; emb1 -> store;
ui -> emb2 [label="ask"]; emb2 -> knn; store -> knn [style=dashed label="vectors"]; knn -> gate; gate -> bridge; bridge -> budg;
budg -> prompt; prompt -> slm; slm -> ui [label="answer + cited notes" constraint=false];
router -> slm [style=dashed]; router -> cloud [style=dashed label="escalate"]; harness -> ui [style=dotted arrowhead=none];
}}'''

DIAGRAMS["pipeline"] = f'''digraph G {{ rankdir=TB; {BASE}
data [label="Public benchmarks (real data)\\nPopQA · HotpotQA · 2WikiMultiHopQA · GSM8K" fillcolor="#e9f1fb" color="{BLUE}"];
sample [label="Fixed sample per benchmark\\nseed 13 · persisted ids + file hash"];
split [label="Disjoint splits\\npilot (validation) · learn-train 144 · n = 200 test"];
guard [label="Holdout guard\\nno evaluation question enters memory"];
ingest [label="Ingest documents → notes\\n(write path)"];
subgraph cluster_c {{ label="Conditions (same questions, same store)"; color="{LINE}"; style="rounded,dotted"; fontname="Helvetica-Bold";
  floor [label="floor\\nsmall model alone"]; treat [label="treatment\\nsmall model + CAMR" fillcolor="#e8f7f0" color="{GREEN}"];
  ceil [label="ceiling\\nlarge model alone"]; crag [label="ceiling_rag\\nlarge model + same notes"]; }}
rec [label="Per-query records\\nprompt · notes · tokens · timings · answer"];
score [label="Scoring\\ncontains · EM · F1 · final number"];
ana [label="Analysis\\ngap closed + bootstrap CI · residual gap\\nablation · budget · sweep · learned policy"];
out [label="Tables · figures · FINDINGS.md · Chapter 5" fillcolor="#e9f1fb" color="{BLUE}"];
data -> sample -> split -> guard -> ingest; ingest -> {{floor treat ceil crag}}; {{floor treat ceil crag}} -> rec -> score -> ana -> out;
}}'''

DIAGRAMS["query_flow"] = f'''digraph G {{ rankdir=TB; {BASE}
q [label="User types a message" shape=ellipse fillcolor="white"];
rem [label="Starts with\\n\\"remember that\\"?" shape=diamond fillcolor="white"];
store1 [label="Store as memory\\n(no model call)" fillcolor="#e8f7f0" color="{GREEN}"];
recall [label="Recall: embed → kNN → gate → bridge → budget"];
abst [label="Best similarity ≥ τ ?" shape=diamond fillcolor="white"];
cards [label="Show \\"Recalled N memories\\"\\n(before the answer streams)" fillcolor="#e9f1fb" color="{BLUE}"];
none [label="Show \\"No matching memories\\"\\n(model answers alone)" fillcolor="#fdeee6" color="{ORANGE}"];
gen [label="Stream answer from the\\nchosen Ollama model"];
log [label="Log turn: answer · sources ·\\ngrounded % · timings"];
chat [label="Store what the user said\\nas memory (chat)" fillcolor="#e8f7f0" color="{GREEN}"];
fb [label="👍 → answer stored as memory\\n👎 → recorded" fillcolor="#e8f7f0" color="{GREEN}"];
q -> rem; rem -> store1 [label="yes"]; rem -> recall [label="no"]; recall -> abst; abst -> cards [label="yes"]; abst -> none [label="no"];
cards -> gen; none -> gen; gen -> log -> chat; log -> fb [style=dashed label="user feedback"];
}}'''

DIAGRAMS["policy"] = f'''digraph G {{ rankdir=TB; {BASE}
q [label="Question" shape=ellipse fillcolor="white"];
feat [label="Pre-answer features (11)\\ntask type · best similarity ·\\nmargin · near-best notes · length"];
router [label="Learned router\\nridge per action (offline)\\nLinUCB (bandit feedback)" fillcolor="#e8f7f0" color="{GREEN}"];
local [label="Answer locally\\nalone · +128 · +512 · +1024 tokens"];
cloud [label="Escalate to cloud\\n(Kimi K3)" fillcolor="#fdeee6" color="{ORANGE}"];
check [label="Grounded?\\nanswer words in notes ·\\nabstention-like · length" shape=diamond fillcolor="white"];
done [label="Return local answer\\n(71% of questions)" fillcolor="#e9f1fb" color="{BLUE}"];
q -> feat -> router; router -> local [label="local arm"]; router -> cloud [label="maths →"];
local -> check; check -> done [label="yes"]; check -> cloud [label="no (escalate)"];
}}'''

DIAGRAMS["ui_components"] = f'''digraph G {{ rankdir=LR; {BASE}
subgraph cluster_browser {{ label="Browser (single-page app: index.html · app.css · app.js, no framework)"; fontname="Helvetica-Bold"; color="{BLUE}"; style="rounded"; penwidth=1.3;
  side [label="Sidebar\\nmemory ring · new chat · search\\nchat history · Memory · Teach · Settings"];
  thread [label="Thread\\nuser bubbles · recall card (before the answer)\\nstreamed answer · grounded % · 👍/👎 · timings" fillcolor="#e9f1fb" color="{BLUE}"];
  composer [label="Composer\\nmessage box · Remember toggle\\nmodel picker · file drop · send"];
  panel [label="Memory panel\\nThis answer · All memory (search, Forget)\\nGrowth (counts, share from memory)"];
  dialogs [label="Dialogs\\nTeach (text, .txt/.md/.pdf) · Settings\\n(budget, history, privacy export)"];
  setup [label="Setup screen\\nOllama missing / memory model missing\\n→ one-click download with progress" fillcolor="#fdeee6" color="{ORANGE}"];
}}
subgraph cluster_server {{ label="Local server (127.0.0.1 only; Host and Origin checked)"; fontname="Helvetica-Bold"; color="{GREEN}"; style="rounded"; penwidth=1.3;
  api [label="JSON API\\n/api/state · conversations · memory\\nteach · settings · feedback · export"];
  sse [label="/api/chat\\nServer-Sent Events:\\nrecall → token… → done" fillcolor="#e8f7f0" color="{GREEN}"];
  asst [label="Assistant\\n(CAMR engine + chat memory)" fillcolor="#e8f7f0" color="{GREEN}"];
}}
ollama [label="Ollama on the same machine\\nchat model + nomic-embed-text" fillcolor="#fdeee6" color="{ORANGE}"];
store [label="memory-ollama-nomic-embed-text.sqlite\\n(one file in the user's home)" shape=cylinder fillcolor="#e9f1fb" color="{BLUE}"];
composer -> sse [label="message"]; sse -> thread [label="events"]; side -> api; panel -> api; dialogs -> api; setup -> api;
api -> asst; sse -> asst; asst -> ollama [label="embed · generate"]; asst -> store;
}}'''

DIAGRAMS["rag_vs_camr"] = f'''digraph G {{ rankdir=TB; {BASE} compound=true;
subgraph cluster_rag {{ label="Standard RAG (retrieve-then-read)"; fontname="Helvetica-Bold"; color="{ORANGE}"; style="rounded"; penwidth=1.4;
  r_docs [label="Fixed document corpus\\n(indexed once, offline)" shape=cylinder fillcolor="#fdeee6" color="{ORANGE}"];
  r_q [label="Question" shape=ellipse fillcolor="white"];
  r_emb [label="Embed question"];
  r_top [label="Top-k most similar chunks\\n(always k, however weak)"];
  r_cat [label="Concatenate all k into the prompt"];
  r_llm [label="Model answers"];
  r_q -> r_emb -> r_top -> r_cat -> r_llm; r_docs -> r_top [style=dashed];
}}
subgraph cluster_camr {{ label="CAMR (capability-adaptive memory)"; fontname="Helvetica-Bold"; color="{GREEN}"; style="rounded"; penwidth=1.4;
  c_write [label="Write path: documents, chat statements,\\nremember-that, 👍 answers → screen,\\ndeduplicate, provenance" fillcolor="#e8f7f0" color="{GREEN}"];
  c_store [label="Growing personal memory\\n(one SQLite file)" shape=cylinder fillcolor="#e9f1fb" color="{BLUE}"];
  c_q [label="Question" shape=ellipse fillcolor="white"];
  c_route [label="Router: memory budget\\nor cloud? (learned)" fillcolor="#e8f7f0" color="{GREEN}"];
  c_emb [label="Embed question → top-20 candidates"];
  c_gate [label="Gate: abstain if best < τ;\\nadmit only within δ of best" fillcolor="#e8f7f0" color="{GREEN}"];
  c_bridge [label="Entity bridging:\\nfollow named entities (2nd hop)" fillcolor="#e8f7f0" color="{GREEN}"];
  c_pack [label="Pack under token budget B"];
  c_llm [label="Model answers"];
  c_check [label="Grounded in the notes?\\nelse escalate" shape=diamond fillcolor="white"];
  c_q -> c_route -> c_emb -> c_gate -> c_bridge -> c_pack -> c_llm -> c_check;
  c_store -> c_emb [style=dashed]; c_write -> c_store;
  c_llm -> c_write [style=dashed label="what the user says\\nbecomes memory" constraint=false];
}}
}}'''


DIAGRAMS["external_weights"] = f'''digraph G {{ rankdir=LR; {BASE} compound=true; ranksep=0.55;
q [label="Question" shape=ellipse fillcolor="white"];
subgraph cluster_compute {{ label="Compute: frozen weights"; fontname="Helvetica-Bold"; color="{ORANGE}"; style="rounded"; penwidth=1.4;
  slm [label="Small model (0.5B–3B)\\nweights never change\\n≈0.4–2 GB in RAM" fillcolor="#fdeee6" color="{ORANGE}"];
}}
subgraph cluster_memory {{ label="Memory: external weights that grow (on disk)"; fontname="Helvetica-Bold"; color="{GREEN}"; style="rounded"; penwidth=1.4;
  vec [label="Note vectors\\nN × d numbers + text + source\\n(read: only what a question needs)" shape=cylinder fillcolor="#e9f1fb" color="{BLUE}"];
  ivf [label="Learned index\\nC centroids (k-means)\\nprobe a few clusters" fillcolor="#e8f7f0" color="{GREEN}"];
  ad [label="Query adapter\\n2·d·r numbers (InfoNCE)" fillcolor="#e8f7f0" color="{GREEN}"];
  rt [label="Router weights\\n(ridge / LinUCB)" fillcolor="#e8f7f0" color="{GREEN}"];
}}
subgraph cluster_grow {{ label="How memory grows"; fontname="Helvetica-Bold"; color="{BLUE}"; style="rounded,dashed"; penwidth=1.2;
  teach [label="Teach: notes, files,\\n'remember that', 👍"];
  web [label="Eager lookup on a miss\\n(DuckDuckGo → Wikipedia)\\nnever for personal questions" fillcolor="#e6f6f8" color="#0a6670"];
  pack [label="Knowledge packs\\n(vectors precomputed)"];
  sleep [label="Sleep (idle): tidy · curiosity ·\\nre-index · train adapter\\n(kept only if recall rises)" fillcolor="#e8f7f0" color="{GREEN}"];
}}
q -> rt [lhead=cluster_memory]; rt -> ad -> ivf -> vec;
vec -> slm [label="admitted notes\\n(gated, ≤ B tokens)"]; q -> slm [style=dashed];
slm -> ans [label=""]; ans [label="Answer + cited sources" shape=ellipse fillcolor="white"];
teach -> vec; web -> vec; pack -> vec; sleep -> ivf; sleep -> ad; sleep -> vec [style=dashed];
}}'''

DIAGRAMS["eager_loop"] = f'''digraph G {{ rankdir=TB; {BASE}
q [label="Question" shape=ellipse fillcolor="white"];
recall [label="Recall from memory\\n(gate + entity gate)"];
d1 [label="Memory has it?" shape=diamond fillcolor="white"];
d2 [label="About the user?\\n(my, I, we …)" shape=diamond fillcolor="white"];
d3 [label="Learning online on?" shape=diamond fillcolor="white"];
look [label="Look up the subject\\nDuckDuckGo → Wikipedia lead\\n(cached, rate-limit aware)" fillcolor="#e6f6f8" color="#0a6670"];
learn [label="Write path: screen, dedupe,\\nstore with its link" fillcolor="#e8f7f0" color="{GREEN}"];
recall2 [label="Recall again"];
ans [label="Answer from notes\\n(cite sources)" fillcolor="#e9f1fb" color="{BLUE}"];
teachme [label="“I don't know that yet,\\ntell me and I'll remember”\\n+ Teach me button" fillcolor="#fdeee6" color="{ORANGE}"];
alone [label="Model alone\\n(general knowledge)"];
q -> recall -> d1; d1 -> ans [label="yes"]; d1 -> d2 [label="no"];
d2 -> teachme [label="yes"]; d2 -> d3 [label="no"]; d3 -> look [label="yes"]; d3 -> alone [label="no"];
look -> learn -> recall2 -> ans; look -> alone [label="nothing found" style=dashed];
}}'''


def render(out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, dot in DIAGRAMS.items():
        p = out / f"{name}.png"
        subprocess.run(["dot", "-Tpng", "-Gdpi=170", "-o", str(p)], input=dot.encode(), check=True)
        paths.append(p)
    return paths


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/figures/diagrams")
    for p in render(Path(ap.parse_args().out)):
        print(p)
