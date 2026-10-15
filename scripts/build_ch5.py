"""Chapter 5 (System Implementation, Testing and Evaluation), rewritten around what was found.

Same template and Word styles as before (`build_chapter5.py` supplies the document helpers and a few sections that
did not change). Every number is read from a results file at build time or quoted from docs/FINDINGS.md, which names
the file behind it; nothing is estimated.

    python scripts/build_ch5.py --template proposal.docx --out docs/report/Chapter5_CAMR
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("build_chapter5", HERE / "build_chapter5.py")
old = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(old)

Chapter, pct, ROOT = old.Chapter, old.pct, old.ROOT
FIG, DIAGRAMS, REPORT = old.FIG, old.DIAGRAMS, old.REPORT
REPO_URL = old.REPO_URL
RES = ROOT / "results"
AG = RES / "agentic"
RB = RES / "ragbench"


# ----------------------------------------------------------------- results, read at build time


def J(rel: str):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


def p1(x: float | None) -> str:
    """A share as a percentage with one decimal ("60.5%")."""
    return "–" if x is None else f"{100 * x:.1f}%"


def usd(x: float | None, digits: int = 2) -> str:
    return "–" if x is None else f"${x:,.{digits}f}"


READER_NAMES = {"qwen2_5_0_5b": "Qwen 2.5 0.5B", "llama3_2_3b": "Llama 3.2 3B", "kimi-k3": "Kimi K3"}
PIPE_NAMES = {"dense": "Dense (naive RAG)", "bm25": "BM25", "hybrid": "Hybrid (RRF)", "rerank": "Hybrid + reranker",
              "hyde": "HyDE", "crag": "Corrective RAG", "abstain": "Reranker + abstain", "check": "Reranker + CAMR check",
              "camr": "CAMR (verified)"}
PIPE_ORDER = list(PIPE_NAMES)


def rag_runs() -> dict[tuple[str, str], dict]:
    """(pipeline, reader tag) -> run file; the judged summary when the judge has run."""
    out = {}
    for f in sorted(RB.glob("run_*.json")):
        d = json.loads(f.read_text())
        tag = d["reader"].replace(":", "_").replace(".", "_")
        out[(d["pipeline"], tag)] = d
    return out


def rag_summary(d: dict) -> dict:
    """The run's summary (judged when the judge has run), with CAMR's answers about a named other meaning counted
    apart from wrong ones: they state which meaning they are about, which a plain RAG answer never does."""
    s = dict(d.get("summary_judged") or d["summary"])
    judged = d.get("judged", {})
    rows = d["per_question"]
    n = len(rows) or 1
    ok = lambda r: judged.get(str(r["i"]), r["exact"])  # noqa: E731
    s["other_meaning"] = sum(r["stated"] and not ok(r) and bool(r.get("ambiguous")) for r in rows) / n
    s["wrong_exact"] = sum(r["stated"] and not ok(r) and not r.get("ambiguous") for r in rows) / n
    return s


DESK_SYSTEMS = [("llm_qwen2_5_0_5b", "Qwen 0.5B alone"), ("llm_llama3_2_3b", "Llama 3B alone"),
                ("stuff_llama3_2_3b", "Llama 3B + context stuffing"), ("rag_llama3_2_3b", "Llama 3B + RAG"),
                ("camr_qwen2_5_0_5b", "Qwen 0.5B + CAMR"), ("camr_llama3_2_3b", "Llama 3B + CAMR"),
                ("llm_kimi-k3", "Kimi K3 alone"), ("stuff_kimi-k3", "Kimi K3 + context stuffing"),
                ("rag_kimi-k3", "Kimi K3 + RAG"), ("camr_kimi-k3", "Kimi K3 + CAMR")]
AGENT_CONFIGS = [("llama3_2_3b__none", "Llama 3B, no memory"), ("llama3_2_3b__rag", "Llama 3B + RAG"),
                 ("llama3_2_3b__camr", "Llama 3B + CAMR"), ("kimi-k3__none", "Kimi K3, no memory"),
                 ("kimi-k3__rag", "Kimi K3 + RAG"), ("kimi-k3__camr", "Kimi K3 + CAMR")]
FRESH_SYSTEMS = [("llm_llama3_2_3b", "Llama 3B alone"), ("rag_llama3_2_3b", "Llama 3B + RAG"),
                 ("camr_llama3_2_3b", "Llama 3B + CAMR"), ("llm_kimi-k3", "Kimi K3 alone"),
                 ("stuff_kimi-k3", "Kimi K3 + stuffing"), ("rag_kimi-k3", "Kimi K3 + RAG"),
                 ("camr_kimi-k3", "Kimi K3 + CAMR")]


def loaded(prefix: str, systems: list[tuple[str, str]]) -> list[tuple[str, str, dict]]:
    out = []
    for tag, name in systems:
        d = J(f"results/agentic/{prefix}_{tag}.json")
        if d:
            out.append((tag, name, d))
    return out


def heldout_readers() -> list[tuple[str, dict, dict]]:
    """Per reader on the held-out set: judged outcome of the chosen verified pipeline, and its timing."""
    judged = (J("results/verified/judged_heldout.json") or {}).get("files", {})
    rows = []
    for tag, name in (("_sa", "qwen2.5:0.5b"), ("_sa_qwen2_5_1_5b", "qwen2.5:1.5b"),
                      ("_sa_llama3_2_3b", "llama3.2:3b"), ("_sa_phi4-mini", "phi4-mini (3.8B)"),
                      ("_sa_qwen2_5_7b", "qwen2.5:7b")):
        j = judged.get(f"answers_heldout{tag}.json", {}).get("facts+compress+reader")
        a = J(f"results/verified/answers_heldout{tag}.json")
        if not j or not a:
            continue
        v = a["variants"]["facts+compress+reader"]
        rows.append((name, j, v))
    return rows


def _row(prefix: str, tag: str, key: str, item: str) -> dict:
    d = J(f"results/agentic/{prefix}_{tag}.json") or {}
    rows = d.get("per_ticket") or d.get("per_question") or d.get("per_task") or []
    return next((r for r in rows if r.get("ticket", r.get("id", r.get("task"))) == item), {})


def n8n_shots() -> list[tuple[str, str]]:
    """The n8n screenshots (docs/figures/n8n) with captions whose numbers come from the same runs' result files."""
    desk = (J("results/agentic/helio_camr_kimi-k3.json") or {}).get("per_ticket", [])
    acts = [r.get("action") for r in desk]
    t20 = _row("helio", "camr_kimi-k3", "ticket", "T020")
    agent = (J("results/agentic/agent_kimi-k3__camr.json") or {}).get("summary", {})
    fa, fc = _row("fresh", "llm_kimi-k3", "id", "F012"), _row("fresh", "camr_kimi-k3", "id", "F012")
    fs = (J("results/agentic/fresh_camr_kimi-k3.json") or {}).get("summary", {})
    n_tasks = agent.get("tasks", 20)
    handed = round(agent.get("escalated", 0) * n_tasks)

    def secs(r):
        return f"{(r.get('model_ms') or 0) / 1000:.1f} s"

    return [
        ("desk_canvas.png", f"A support-desk run in n8n (Kimi K3 + CAMR): {len(desk)} tickets answered, "
         f"{acts.count('reply')} replies sent, {acts.count('escalate')} escalated, with the resolutions a person gave "
         "taught back and 3 policy changes applied; each link shows how many items passed (screenshot)"),
        ("desk_t013_escalated.png", "Inside that run, day 2, ticket T013 *How much is the bird mesh kit?*: nothing in "
         "memory, so the answer is not stated (`stated: false`) and the ticket goes to a person; the input (left) "
         "carries the resolution the person gives, which the workflow then teaches (screenshot)"),
        ("desk_t020_answered.png", f"Day 3, ticket T020 *Price of the Helio bird mesh kit please*: answered "
         f"*{t20.get('answer', '')}* from the taught resolution, with the evidence sentence and its source; one model "
         f"call, {usd(t20.get('cost_usd'), 4)} (screenshot)"),
        ("fresh_canvas.png", f"A current-events run in n8n (Kimi K3 + CAMR): {fs.get('pages_live', 30)} pages "
         f"fetched live from Wikipedia and taught ({fs.get('items_taught', 0)} items), {fs.get('questions', 50)} "
         "questions answered, one score (screenshot)"),
        ("fresh_fetch.png", "The fetch node's output: the raw wikitext of one day's *Current events* page as fetched "
         "live (the node retries once and continues on error, D-36) (screenshot)"),
        ("fresh_answer_alone.png", f"Question F012 to Kimi K3 alone: a confident answer from its training data that "
         f"is wrong for this news (*2M0437b*); {secs(fa)} of model time, {usd(fa.get('cost_usd'), 4)} (screenshot)"),
        ("fresh_answer.png", f"The same question to Kimi K3 + CAMR: *{fc.get('answer', '')}*, with the news item it "
         f"came from as evidence; {secs(fc)}, {usd(fc.get('cost_usd'), 4)} (screenshot)"),
        ("agent_canvas.png", f"An operations-agent run in n8n (Kimi K3 + CAMR): {n_tasks} tasks, "
         f"{n_tasks - handed} completed by the agent, {handed} handed to a person (screenshot)"),
        ("agent_a20_alone.png", "Task A20 (*20 HS-400 panels on a single Volta-2 inverter?*) given to Kimi K3 without "
         "memory: escalated, *cannot answer without inventing facts* (screenshot)"),
        ("agent_a20_camr.png", "The same task with CAMR: the agent searches memory, reads that a Volta-2 inverter "
         "takes at most 18 panels, and replies with the limit and two options (screenshot)"),
    ]


def speed() -> dict:
    return (J("results/models/speed.json") or {}).get("models", {})


# Machine each sweep model ran on (sweep_results/machine-*.sqlite and their notes); unlisted models ran on E.
SWEEP_MACHINE = {"gemma3:1b": "C", "smollm2:1.7b": "C", "granite3.3:2b": "C", "falcon3:3b": "C", "phi4-mini:3.8b": "C",
                 "qwen2.5:7b": "B", "llama3.1:8b": "B", "gemma2:9b": "B", "qwen2.5:14b": "B",
                 "mistral:7b": "D", "olmo2:7b": "D", "granite3.3:8b": "D", "gemma3:12b": "D",
                 "yi:6b": "F", "falcon3:10b": "F", "olmo2:13b": "F"}
SIZE_BANDS = [(0, 1.3, "About 1B"), (1.3, 2.9, "1.5–2.5B"), (2.9, 5.0, "3–4B"), (5.0, 10.0, "6–9B"),
              (10.0, 99, "10–15B")]


def sweep_models() -> list[dict]:
    """Every model of the size sweep, smallest first: accuracy alone and with CAMR per benchmark, parameters and
    quantisation from the Ollama registry, decode speed and mean seconds per answer with CAMR (PopQA), and the
    benchmarks whose latest run had failed queries."""
    import sqlite3

    rows = J("results/pilot/tables/model_sweep.json") or []
    meta = J("docs/model_registry_metadata.json") or {}
    db = sqlite3.connect(f"file:{RES / 'pilot/camr.sqlite'}?mode=ro", uri=True)
    latest = {(lab, cond, b): rid for lab, cond, b, rid in db.execute(
        "SELECT label, condition, benchmark, MAX(run_id) FROM run WHERE status='completed' AND label LIKE 'm:%' "
        "GROUP BY label, condition, benchmark")}
    out: dict[str, dict] = {}
    for r in rows:
        m = r["model"]
        size = meta.get(m, {}).get("parameter_size", "0B")
        d = out.setdefault(m, {"model": m, "machine": SWEEP_MACHINE.get(m, "E"), "failed": set(),
                               "params": float(size[:-1]) / 1000 if size.endswith("M") else float(size.rstrip("B")),
                               "quant": meta.get(m, {}).get("quantization", "?")})
        d[r["benchmark"]] = (r["floor"], r["with_memory"])
        if r["benchmark"] == "popqa":
            d["tok_s"] = r.get("decode_tok_s_memory")
        for cond in ("floor", "treatment"):
            rid = latest.get((f"m:{m}", cond, r["benchmark"]))
            if rid and db.execute("SELECT COUNT(*) FROM query_log WHERE run_id=? AND status!='ok'", (rid,)).fetchone()[0]:
                d["failed"].add(r["benchmark"])
        rid = latest.get((f"m:{m}", "treatment", "popqa"))
        if rid and r["benchmark"] == "popqa":
            d["secs"] = db.execute("SELECT AVG(e2e_latency_ms)/1000 FROM query_log WHERE run_id=? AND status='ok'",
                                   (rid,)).fetchone()[0]
    return sorted(out.values(), key=lambda d: d["params"])


def sweep_kimi() -> dict[str, float]:
    rows = J("results/pilot/tables/model_sweep.json") or []
    return {r["benchmark"]: r["ceiling_kimi"] for r in rows if r.get("ceiling_kimi") is not None}


def missing_sizes(sw: list[dict]) -> list[str]:
    return [f"{s}B" for s, lo, hi in ((5, 4.5, 6.0), (10, 9.5, 11.5), (13, 12.5, 14.0))
            if not any(lo <= r["params"] < hi for r in sw)]


def _band(sw: list[dict]) -> list[tuple[str, list[dict]]]:
    return [(name, [r for r in sw if lo <= r["params"] < hi]) for lo, hi, name in SIZE_BANDS
            if any(lo <= r["params"] < hi for r in sw)]


def size_bands(sw: list[dict], kimi: dict) -> list[list[str]]:
    out = []
    for name, ms in _band(sw):
        def mean(b, i):
            v = [r[b][i] for r in ms if b in r]
            return statistics.mean(v) if v else 0.0
        hop = [r["hotpotqa"][1] for r in ms if "hotpotqa" in r]
        at = sum(t >= kimi.get("hotpotqa", 9) - 1e-6 for t in hop)
        gs = [r["gsm8k"] for r in ms if "gsm8k" in r]
        secs = [r["secs"] for r in ms if r.get("secs") and r["machine"] != "C"]  # one CPU class (2.1 GHz)
        out.append([name, str(len(ms)), f"{100 * mean('popqa', 0):.1f} → {100 * mean('popqa', 1):.1f}%",
                    f"{100 * mean('hotpotqa', 0):.1f} → {100 * mean('hotpotqa', 1):.1f}%", f"{at} of {len(hop)}",
                    f"{sum(t > f + 1e-6 for f, t in gs)} / {sum(t < f - 1e-6 for f, t in gs)}",
                    f"{statistics.median(secs):.1f}" if secs else "–"])
    return out


def costs() -> dict | None:
    return J("results/costs/kimi_costs.json")


def git_count() -> tuple[int, int]:
    hist = old.git_history()
    return len(hist), len({h[1][:11] for h in hist})


# ================================================================= 5.1 Introduction


def introduction(c: Chapter) -> None:
    c.h2("Introduction")
    c.p("This chapter reports what was built, how it was tested, and what the measurements showed, including where "
        "the system failed. The project follows the AI and machine learning route of the departmental guidelines, "
        "with one difference that shapes the whole chapter: the language models are **not** trained. They run with "
        "frozen weights, and everything the system learns is stored outside them, in a memory engine called CAMR "
        "(Capability-Adaptive Memory Retrieval). The parts that *are* fitted to data, a router and an escalation "
        "cascade, were tuned by cross-validation on training questions only, and two fine-tuned models (LoRA) were "
        "trained as baselines to test the proposal's claim that memory beats retraining.")
    c.p("Four things were built. (1) The **memory engine**: a write path that turns documents into screened notes in "
        "one SQLite file, and a read path that decides per question how much memory a small model should read. (2) "
        "**Verified answering**: an answer is stated as fact only when a stored sentence supports it; otherwise it is "
        "withheld or handed on. (3) **Learning without training**: looking things up when memory has nothing, and "
        "learning formulas from corrections. (4) **Applications**: CAMR Personal, a desktop assistant, and a gateway "
        "that lets workflow automations (n8n) and tool-using agents call the engine.")
    c.p("Each was evaluated against named baselines: the same model without memory, a frontier cloud model (Kimi K3), "
        "eight modern retrieval-augmented generation (RAG) pipelines, context stuffing, and fine-tuning. Every number "
        "in this chapter comes from a results file in the repository, and the file is named. Results are reported "
        "the way they came out. Section ⟦sec_scorecard⟧ opens the results with a scorecard that marks each claim as "
        "met in full, met in part, or not met, and section ⟦sec_flaws⟧ lists every flaw found, with its cause.")
    c.table("Where each part of the system is described and evaluated",
            ["Component", "What it does", "Implemented in", "Evaluated in"],
            [["Memory engine (write and read paths)", "Stores documents as notes; per question: retrieve, gate, "
              "bridge, pack under a token budget", "⟦sec_impl⟧", "⟦sec_retrieval⟧, ⟦sec_gap⟧"],
             ["Verified answering", "States an answer only when a stored sentence supports it", "⟦sec_verify_impl⟧",
              "⟦sec_verified⟧, ⟦sec_ragresult⟧"],
             ["Learning without training", "Looks up what memory lacks; learns formulas from corrections",
              "⟦sec_learn_impl⟧", "⟦sec_learning⟧"],
             ["Large data and device limits", "Bulk ingest that is searchable at once; a governor that stops at "
              "the device's limits", "⟦sec_bulk_impl⟧", "⟦sec_bulk⟧"],
             ["Learned routing", "Chooses memory budget or cloud per question", "⟦sec_policy_impl⟧", "⟦sec_policy⟧"],
             ["CAMR Personal", "Desktop assistant with memory", "⟦sec_app⟧", "⟦sec_apptest⟧, ⟦sec_appres⟧"],
             ["Automation gateway", "n8n workflows and agents call any system through one interface",
              "⟦sec_gateway⟧", "⟦sec_agentic⟧, ⟦sec_cost⟧"]],
            [3.6, 5.6, 2.8, 3.9], size=9.5)
    c.p(f"The work was done in increments, each ending with a measured result that decided the next step. "
        f"{c.next_fig()} shows the sequence as recorded in the repository's history.")
    c.figure(REPORT / "timeline.png", "Development increments reconstructed from the git history; each marked step is "
             "a commit that added an implemented or measured increment", key="timeline")


# ================================================================= 5.2 Environment


def environment(c: Chapter) -> None:
    profile = json.loads((old.PILOT / "profile.json").read_text())
    hw = profile["hardware"]
    sp = speed()
    c.h2("Implementation Environment", key="sec_env")
    c.p("Development, every experiment and every automation run took place on Linux machines with x86-64 CPUs and no "
        "GPU: four cores and 16 GB of memory, the consumer-laptop class that NFR-01 targets. The system is a local "
        "research prototype. CAMR Personal is distributed as downloadable files, but nothing was deployed as a public "
        "service. The n8n automations ran headless on the same machine; no workflow was exposed to the internet.")
    c.h3("Hardware and Deployment Environment")
    ram = []
    for m in ("qwen2.5:0.5b", "qwen2.5:1.5b", "llama3.2:3b", "phi4-mini", "qwen2.5:7b"):
        s = sp.get(m)
        if s and s.get("rss_mb"):
            ram.append(f"{m} {s['rss_mb'] / 1024:.1f} GB")
    ram_txt = ("Measured resident memory of the model runtime after loading: " + ", ".join(ram) + ".") if ram else \
        "Model runtime 0.7 GB (0.5B) to 4.3 GB (3B), measured after one answer (`results/eager/ram.json`)."
    c.table("Implementation environment and minimum requirements",
            ["Item or layer", "Tested specification or version", "Purpose and justification", "Evidence"],
            [["Primary machine (A)", f"{hw['cpu']}, {hw['logical_cpus']} logical CPUs, {hw['memory_gb']:.1f} GB RAM "
              "(14.3 GB usable by processes), no GPU, Linux x86-64", "All development; every experiment in this "
              "chapter except the 19-model sweep; the n8n automations", "`results/pilot/tables/profile.json`"],
             ["Sweep machines (B–E)", "Same class: 4 vCPU Intel Xeon (2.10 GHz; machine C 2.80 GHz), 16 GB RAM",
              "The 19-model sweep, one model family per machine, merged afterwards", "FINDINGS F10"],
             ["Minimum to run the engine", "4 cores, 16 GB RAM. Engine process "
              f"{profile['peak_rss_mb_engine_process']:.0f} MB peak; store {profile['store_file_mb']:.1f} MB (pilot); "
              "557 MB peak while bulk-ingesting 123,301 paragraphs", "A 0.5–3B model and the engine fit with headroom on "
              "a 16 GB device", "TC-14; `results/bulk/ingest.json`"],
             ["Local models", ram_txt + " A 7B model needs about 5 GB; a 20B model was killed for lack of memory "
              "until its weights were memory-mapped, then slowed to 0.4 tokens/s under pressure", "Which model sizes a "
              "16 GB device can run beside other software", "`results/models/speed.json`; F6, F8"],
             ["Cloud model", "Moonshot Kimi K3 (and K2.6 in the pilot) over an OpenAI-compatible HTTPS API",
              "Frontier reference, escalation target, second reader, judge; never required to run CAMR",
              "`results/costs/kimi_costs.json`"],
             ["End-user devices (CAMR Personal)", "Windows 10/11 (x64, ARM64), macOS (Apple Silicon, Intel), Linux "
              "(x64, ARM64) with Ollama; ≥ 4 GB RAM for a 1.5B model", "The application talks only to Ollama on the same "
              "machine", "CI build and launch test on all six (⟦ci⟧)"],
             ["Specialised hardware", "None: no GPU, NPU or accelerator anywhere", "The study targets CPU-only "
              "consumer devices; every timing is a CPU timing", "Profiles; CI runner labels"]],
            [3.0, 4.8, 4.6, 3.5], size=9.5)
    c.h3("Software, Services and Configuration")
    c.table("Software and services used (versions as tested)",
            ["Component", "Version", "Role in the system"],
            [["Python", "3.11.15", "Engine, harness, gateway, experiment scripts"],
             ["Ollama", "0.35.0", "Local model runtime on the loopback interface; quantised GGUF weights (Q4_K_M)"],
             ["Local models", "qwen2.5 0.5B / 1.5B / 7B, llama3.2 3B, phi4-mini 3.8B (+14 more in the sweep)",
              "Frozen readers; greedy decoding, temperature 0, seed 13"],
             ["SQLite / sqlite-vec", "3.45.1 / 0.1.9", "One-file store: notes, vectors (exact kNN), provenance, "
              "keyword index (FTS5), run logs"],
             ["sentence-transformers / PyTorch (CPU)", "6.1.0 / 2.14.1", "BGE-small-en-v1.5 embedder (384-d); "
              "cross-encoder ms-marco-MiniLM-L-6-v2 for the RAG baselines"],
             ["transformers / PEFT", "5.19.0 / 0.21.2", "The two LoRA fine-tuning baselines (CPU, fp32)"],
             ["n8n / Node.js", "2.43.6 / 24.22.0", "Workflow automation: support desk, agent tasks, live news "
              "workflows, run headless with `n8n execute`"],
             ["Moonshot API", "kimi-k3 (list price $3 per million input tokens, $15 per million output tokens)",
              "Cloud reference; the key is read from the `MOONSHOT_API_KEY` environment variable only"],
             ["Streamlit, Playwright, axe-core", "1.64.0, 1.63.0, 4.10", "Read-only inspector; browser tests, "
              "screenshots and the accessibility audit"],
             ["pytest", "9.1.1", "203 automated tests (section ⟦sec_testing⟧)"]],
            [4.2, 4.2, 7.5], size=9.5)
    c.p("Each experiment is configured by one YAML file loaded into typed dataclasses that reject unknown keys, so a "
        "misspelt setting fails instead of silently using a default (NFR-07). Every run records the hash of its full "
        "configuration and is resumable. Docker was not used: the experiments ran directly on the hosts, and the "
        "application ships as one self-contained executable per platform. No password, key or personal data appears "
        "in the repository, the logs or any screenshot. The cloud key existed only in an environment variable, and "
        "it is to be rotated after the study.")
    c.h3("Deployment and Reproducibility")
    c.p("Everything in this chapter can be rerun from the repository. The commands below were run as shown on "
        "machine A. Only the Kimi conditions need the cloud key; every other step runs offline once the models and "
        "data are downloaded.")
    c.code("""git clone https://github.com/Satasdin/CAMR.git && cd CAMR
python -m venv .venv && source .venv/bin/activate
pip install -e ".[vec,embed,dev,inspect]"
python -m pytest -q                                   # health check: 203 tests, no network
ollama pull qwen2.5:0.5b && ollama pull qwen2.5:1.5b && ollama pull llama3.2:3b
python scripts/fetch_data.py                          # PopQA, HotpotQA, 2Wiki, GSM8K (prints a hash per file)
export MOONSHOT_API_KEY=...                           # only for the Kimi conditions""")
    c.p("**One command re-checks the key results.** `scripts/reproduce.py` recomputes them from the frozen caches "
        "(every web response and model answer is stored by its exact request) and compares every number with the "
        "committed one; it exits with status 0 only if all match. It needs no key and no network.")
    c.code("""python scripts/reproduce.py --twice                  # 8 checks, run twice: 16/16 must pass""")
    c.p("**The experiments of this chapter**, each resumable:")
    c.code("""python scripts/verified_qa.py answer --set heldout     # verified answering (F24); judge, report
python scripts/rag_bench.py run --reader qwen2.5:0.5b  # nine RAG pipelines and CAMR (F28)
python scripts/math_learning.py run --model qwen2.5:0.5b --mode calc   # formulas from corrections (F27)
python scripts/large_data.py corpus && python scripts/large_data.py ingest && python scripts/large_data.py limits
python scripts/agentic/gateway.py &                    # automation gateway on 127.0.0.1:8765
python scripts/agentic/n8n_workflows.py run --systems camr:kimi-k3   # n8n support desk (F29)
python scripts/kimi_costs.py                           # US dollars spent on the cloud model
python scripts/make_ch5_figures.py && python scripts/build_ch5.py --template proposal.docx""")
    c.p("**The application only:** download the file for the platform from the release page, or "
        "`pip install \"camr[app] @ git+https://github.com/Satasdin/CAMR.git\"`, then `camr app`, which opens "
        "http://127.0.0.1:8502.")


# ================================================================= 5.3 Datasets


def datasets(c: Chapter) -> None:
    corpus = J("results/ragbench/corpus.json") or {}
    fresh = J("data/agentic/fresh.json") or {}
    helio = J("data/agentic/helio.json") or {}
    counts = helio.get("counts", {})
    c.h2("Dataset Description", key="sec_data")
    c.p("Two kinds of data were used: public benchmarks with reference answers, and data built for this study where "
        "no benchmark could test the question. Nothing in either is generated by the system under test. "
        f"{c.next_tab()} lists the public benchmarks and {c.next_tab(2)} the data built for the study.")
    c.h3("Public Benchmarks")
    c.table("Public benchmarks",
            ["Benchmark", "Source and licence", "Size used", "Task", "Metric"],
            [["PopQA", "Mallen et al. (2023); templates over Wikidata facts", "14,267 questions; three sets of "
              "200 drawn for this study (below)", "Single-hop, long-tail facts", "Answer contained; judged"],
             ["HotpotQA (dev, distractor)", "Yang et al. (2018); crowd-written over Wikipedia; CC BY-SA",
              "7,405 questions, 10 paragraphs each", "Multi-hop", "Exact match, F1"],
             ["2WikiMultiHopQA (dev)", "Ho et al. (2020); Wikipedia and Wikidata", "12,576 questions",
              "Multi-hop (retrieval)", "Full-support recall"],
             ["GSM8K", "Cobbe et al. (2021); human-written; MIT", "1,319 test; 7,473 train", "Arithmetic "
              "reasoning (control)", "Final-number accuracy"]],
            [3.0, 4.4, 3.6, 2.6, 2.3], size=9.5)
    c.table("Data built for this study",
            ["Data", "What one record is", "Size", "Why it was needed"],
            [["PopQA development, test and held-out sets", "A PopQA question; ids and subjects disjoint across sets",
              "200 + 200 + 200 questions", "Choose methods on one set, test once on another (section ⟦sec_prep⟧)"],
             ["Frozen web cache", "Every page the lookups read, stored by exact request", f"{corpus.get('pages', 972)} "
              "pages", "The web changes; a frozen copy makes every lookup replayable"],
             ["RAG benchmark corpus", "The cached pages as notes: lead sentences and one note per infobox fact",
              f"{corpus.get('documents', 9989):,} documents → {corpus.get('notes', 10443):,} notes, "
              f"{corpus.get('store_mb', 46.9):.1f} MB", "One store that every RAG pipeline and CAMR search"],
             ["Formula families", "A problem from one of ten formula families; four are invented (zorbit, glim, "
              "Kessler fee, Vantor score)", "10 × (6 train + 6 held-out + 6 reworded + 4 derived)", "Test learning "
              "from corrections on knowledge no model can have"],
             ["Helio Solar (invented company)", "A product sheet or policy; a customer ticket with its gold answer; an "
              "operations task with checks on the tool calls", f"{len(helio.get('kb', [])) or 14} documents, "
              f"{len(helio.get('updates', [])) or 3} policy changes, {len(helio.get('tickets', [])) or 60} tickets over "
              "8 days, 20 agent tasks", "Automations need private, changing knowledge that no model was trained on"],
             ["Wikipedia Current events", "One news item (a sentence) from a daily page; a question whose answer is "
              f"copied from it", f"{fresh.get('items', 555)} items over 30 days "
              f"({fresh.get('days', ['2026-09-15'])[0]} to {fresh.get('days', ['', '2026-10-14'])[-1]}); "
              f"{len(fresh.get('questions', [])) or 50} questions", "Real events after every model's training data"],
             ["Bulk corpus", "Every paragraph of HotpotQA dev and 2Wiki dev, deduplicated", "123,301 paragraphs → "
              "195,735 notes", "Large-data ingest and retrieval at scale"]],
            [3.3, 4.6, 3.9, 4.1], size=9)
    c.p("The Helio tickets were written in four kinds, in the proportions a support desk meets: answerable from the "
        f"knowledge base ({counts.get('kb', 26)}), answerable only after a human agent has resolved the question once "
        f"and the resolution has been taught ({counts.get('learned', 18)}), affected by a policy change "
        f"({counts.get('update', 7)}), and unanswerable from anything the company published "
        f"({counts.get('unknown', 9)}). The news questions were written by Kimi K3 from single items, with a rule "
        "that the answer must be copied exactly from the item; 50 of the first 100 sampled items passed it, at a cost "
        f"of {usd(fresh.get('generation_cost_usd', 0.24))}. {c.next_tab()} shows one record of each kind, verbatim.")
    q = (fresh.get("questions") or [{}])[3] if fresh.get("questions") else {}
    c.table("One record of each kind (verbatim)",
            ["Data", "Record", "Reference answer"],
            [["PopQA (held-out)", "Who was the screenwriter for Mississippi Burning?", "Chris Gerolmo"],
             ["HotpotQA", "Were Scott Derrickson and Ed Wood of the same nationality?", "yes"],
             ["GSM8K", "Janet's ducks lay 16 eggs per day. She eats three for breakfast … sells the remainder … for "
              "$2 per fresh duck egg. How much in dollars does she make every day?", "18"],
             ["Formula (invented, derived)", "A Kessler fee of $30.20 was charged on an order of 6 items. What was the "
              "order value? (Kessler fee = 4% of the order plus $2.50 per item)", "380"],
             ["Helio ticket (learned)", "Which cable connects the Lumen LB-13 battery?", "CB-3 (taught after the "
              "first time a person answered it)"],
             ["Helio agent task", "Customer Amina Odhiambo orders 12 HS-400 panels with installation. Create her "
              "invoice.", "Invoice total $5,640"],
             ["Current events", q.get("question", "–"), (q.get("gold") or ["–"])[0] + f" (from the item of "
              f"{q.get('date', '–')})"]],
            [3.2, 9.0, 3.7], size=9)
    c.h3("Data Preparation and Partitioning", key="sec_prep")
    c.p("**Draws.** Every sample was drawn once from a fixed seed after sorting by question id, and saved with the hash "
        "of the source file, so every condition answered the same questions (paired comparisons). The PopQA "
        "development set (200) was used to choose every method of verified answering; the test set (200) is the "
        "learning stream of the earlier increment; the **held-out set** (200) was drawn only after every choice was "
        "made, and answered once. The code asserts that ids and subjects do not overlap between the three. The "
        "formula problems come from two seeds: seed 31 for development and seed 47 for the reported test, with no "
        "problem shared.")
    c.p("**Leakage guards.** Memory was built from documents only, never from question–answer records, and a guard "
        "refused any document containing an evaluation question verbatim (DR-04). Thresholds of the RAG baselines "
        "(abstention, corrective RAG) were chosen on the development questions only, then applied to the held-out "
        "questions. The cross-encoder and embedder were used as published, without training.")
    c.p("**Frozen external data.** Web lookups were made once (`fetch`) and stored by exact request; answering never "
        "went online. The first reproducibility run caught answer runs that had fetched pages an earlier run had "
        "missed, so two variants saw slightly different pages; freezing fixed this. Wikipedia's Current events pages "
        "were fetched live by the n8n workflow and also cached, so the questions refer to exactly the text the "
        "systems were taught.")
    c.p("**Preparation of a record.** A document is normalised (Unicode NFKC, whitespace), split into notes with "
        f"its title as a prefix, and each infobox line becomes its own note (*Directed by: Walter West*). "
        f"{c.next_tab()} follows one record from the raw files to what the model reads.")
    c.table("One PopQA record before and after preparation",
            ["Stage", "Content"],
            [["Raw question", "id 5939255 · subject *The Loudwater Mystery* · property *director* · answers "
              "[\"Walter West\", \"Walter Alabaster West\"]"],
             ["Raw document", "*The Loudwater Mystery is a 1921 British silent crime film directed by Walter West and "
              "starring Gregory Scott, Pauline Peters and Clive Brook …*"],
             ["Stored note (pilot)", "*The Loudwater Mystery (film): The Loudwater Mystery is a 1921 British silent "
              "crime film directed by Walter West …* (47 tokens, 384-d vector, provenance). Pages read by the later "
              "lookups also give one note per infobox line, e.g. *Directed by: Walter West*"],
             ["Read at question time", "Best similarity 0.77, next 0.62: only one note admitted (47 tokens instead "
              "of a 512-token budget)"],
             ["Answer", "0.5B alone: *John Sturges* (wrong). 0.5B with CAMR: *Walter West* (correct)"]],
            [3.4, 12.5], size=9.5)


# ================================================================= 5.4 Implementation


def implementation(c: Chapter) -> None:
    c.h2("System Implementation", key="sec_impl")
    c.p("The implementation follows the package structure of Chapter 4: `camr.memory` (the engine, verification, "
        "learning, bulk ingest), `camr.models` (runners and prompts), `camr.harness` and `camr.eval` (experiments and "
        "scoring), `camr.learn` (the learned policy), `camr.device` (the governor), `camr.app` (CAMR Personal), and "
        f"`scripts/agentic` (the automation gateway). {c.next_fig()} shows how they fit together. A test enforces the "
        "package rules: the engine imports nothing from the harness, the interfaces or the scripts.")
    c.figure(DIAGRAMS / "architecture.png", "Implemented architecture: write path, one-file store, adaptive read path "
             "(green), frozen local model and optional cloud model", 11.0)
    c.h3("Write Path: From Documents to Notes")
    c.p("Ingestion turns a document into notes, screens them, scores their importance, embeds them and commits note, "
        "vector and provenance in one SQLite transaction, so the store never holds a note without its vector or its "
        "source (FR-01–FR-05). The screener rejects empty, degenerate, duplicate, over-length and injection-like text "
        "and logs why. Duplicates are caught by a checksum under a UNIQUE constraint. Two additions came from the "
        "evaluation. Each line of an infobox (*Directed by: Walter West*) became a note of its own, because a short "
        "labelled fact can be read without a model (section ⟦sec_verify_impl⟧). And when a large file arrives, notes "
        "are stored at once without vectors, findable through a keyword index, and their vectors are added in the "
        "background (section ⟦sec_bulk_impl⟧).")
    c.h3("Read Path: Deciding How Much Memory a Model Reads")
    c.p("For each question the engine embeds it, finds the 20 nearest notes by exact search, and then applies the "
        "capability-adaptive steps that distinguish it from plain retrieval. Each step is switchable in configuration, "
        "and each was kept or dropped on measured evidence:")
    c.items(["**Gating** abstains when even the best note is weak, and admits only notes close to the best one. It "
             "keeps irrelevant text away from a small reader.",
             "**Entity gate** abstains when the question names something no admitted note mentions. Similarity alone "
             "cannot tell a note about *this* film from a note about a similar one.",
             "**Entity bridging** follows a name mentioned in an admitted note to that entity's own note: the second "
             "hop of a multi-hop question, without building a graph.",
             "**One note per source** (optional) admits at most one note per source title, so six near-copies of one "
             "correction do not fill the context.",
             "**Hybrid order** (large stores) adds keyword (BM25) hits to the vector hits and lifts exact word matches.",
             "**The token budget** packs notes in rank order until the next would exceed *B* tokens."])
    old.formal_model(c)
    c.p("Hybrid order, used for large stores, ranks by similarity plus a bounded bonus for the keyword match, scaled "
        "to the best match among the candidates; the gate still uses the plain similarity:")
    c.eq(r"h(q,n)=s(q,n)+\beta\,\frac{\text{bm25}(q,n)}{\underset{m\in C(q)}{\text{max}}\;\text{bm25}(q,m)},\qquad\beta=0.10", key="eq_hybrid")

    # ---------------------------------------------------------- verified answering
    c.h3("Verified Answering", key="sec_verify_impl")
    c.p("A small model that reads the right note can still answer wrongly, and a model that reads nothing will "
        "answer anyway. Verified answering removes the second failure and exposes the first: an answer is stated "
        f"as fact only if a stored sentence supports it. {c.next_fig()} shows the flow.")
    c.figure(DIAGRAMS / "verified_flow.png", "Verified answering: the fact reader answers without a model when a "
             "labelled fact matches; otherwise the model reads and four checks decide whether its answer is stated", 10.5)
    c.p("Let *a* be an answer, *w(a)* its claim words (the words of its first sentence that are not in the question "
        "and are not framing words such as *directed by*), and *U* the units (sentences and fact lines) memory read. "
        "The answer is stated only when one unit satisfies all four checks:")
    c.eq(r"V(a,q)=\exists\,u\in U:\;w(a)\subseteq\text{tok}(u)\;\wedge\;\text{about}(u,q)\;\wedge\;\text{rel}(u,q)\;\wedge\;\text{kind}(a,q)", key="eq_verify")
    c.where([(r"w(a)\subseteq\text{tok}(u)", "grounding: every claim word occurs in that one unit;"),
             (r"\text{about}(u,q)", "subject: the unit is about what the question names (titled with the name, or "
              "mentions it); when memory holds a note titled with the name, only such notes count;"),
             (r"\text{rel}(u,q)", "relation: a labelled fact supports only its own relation (*Directed by* is no "
              "evidence for *producer*), and a plain sentence must state the asked relation;"),
             (r"\text{kind}(a,q)", "the answer is the kind asked for (a year is no answer to *who*).")])
    c.p("A question that names nothing (*What hours is the support desk open?*) cannot pass the subject check, and "
        "the first automation runs showed this withheld correct answers (defect D-33, section ⟦sec_agentic⟧). Such a "
        "question is now anchored by its topic words *T(q)*, its content words of three or more letters other than "
        "question words, matched on their first five letters. The rule applies only when the question names no "
        "entity, asks no known relation, and no note is about its lookup phrase; every PopQA question asks a known "
        "relation, so the benchmark results are untouched (a first version also applied it to *What is the religion "
        "of refuge?* and let a wrong answer through; the replay check caught it):")
    c.eq(r"\text{about}(u,q)=\mathbb{1}\left[\left|T(q)\cap\text{tok}_5(u)\right|\ge\tfrac{1}{2}\left|T(q)\right|\right]\quad\text{when }q\text{ names nothing and asks no known relation}", key="eq_topic")
    c.p("Three further rules complete the answerer. **The fact reader**: when a fact line about the subject carries "
        "the asked relation, its value is the answer and no model is called. **Knowing a subject**: memory counts as "
        "knowing a subject only if a note is titled with it; a note that merely mentions it does not stop a lookup "
        "(this round-2 change added 3.5 points on the development set). **Several meanings**: a name that means "
        "several things is never resolved silently; the answer names the meaning it is about, or gives each. What "
        "fails the checks is offered as an unverified lead, or, in an automation, handed to a person.")
    c.p("**Worked examples (held-out set, Qwen 0.5B).** *Who was the screenwriter for Mississippi Burning?* Memory "
        "held the film's page with the fact line *Written by: Chris Gerolmo*. The asked relation matched the label, so "
        "the fact reader answered *Chris Gerolmo* with no model call, and the answer was stated with that line as its "
        "source. *Who is the author of The Disk?* has no labelled author, so the model read the compressed lead and "
        "answered *Jorge Luis Borges is the author of \"The Disk\"*; the claim words occur in the sentence *\"The "
        "Disk\" is a 1975 short story written by Argentine writer Jorge Luis Borges*, which is in the note titled "
        "*The Disk* and states the relation (*written by*), so all four checks passed. The checks also fail correct "
        "answers: *al-Ghazali* for *Who is the author of The Incoherence of the Philosophers?* was right, but the kind "
        "check expects a person's name to start with a capital letter, so it was withheld (section ⟦sec_flaws⟧).")

    # ---------------------------------------------------------- learning
    c.h3("Learning Without Training", key="sec_learn_impl")
    c.p("Two mechanisms let a frozen model gain knowledge as it is used. Neither changes a weight.")
    c.p(f"**Looking up what memory lacks (eager learning).** When recall finds nothing about the question's subject "
        f"and the question is not about the user, the engine looks the subject up (DuckDuckGo, then the Wikipedia "
        f"lead and infobox), stores what it read through the write path with its link, and answers from memory. "
        f"Questions about the user (*my*, *I*, *we*) are never sent to the web; the assistant asks to be taught "
        f"instead. {c.next_fig()} shows the loop.")
    c.figure(DIAGRAMS / "eager_loop.png", "Eager learning: look up on a miss, store with the source, answer from memory; "
             "never for personal questions", 8.5)
    c.p(f"**Learning formulas from corrections.** The model writes the formula as an expression, or as an equation "
        f"with one unknown letter; a calculator evaluates or solves it. When an answer in a training round is wrong, "
        f"one correction is stored: the rule and that problem worked through. Later problems recall the correction "
        f"({c.next_fig()}). An answer is **grounded** only if its expression uses every number the problem gives:")
    c.figure(DIAGRAMS / "math_loop.png", "Learning a formula from corrections: the model sets the problem up, the "
             "calculator does the arithmetic, and a wrong answer in training stores the rule with a worked example", 8.0)
    c.eq(r"\text{grounded}(e,p)=\mathbb{1}\left[\text{nums}(p)\subseteq\text{nums}(e)\right]", key="eq_ground")
    c.p("A number the problem marks as a percentage may appear in the expression as a fraction (7% as 0.07). That rule "
        "is itself a correction: an earlier version also accepted *4 items* as *4%* (found on the development draw). **Sleep** (when the device is idle) tidies duplicates, looks up names memory mentions but "
        "lacks, rebuilds the index and trains a query adapter, which is kept only if held-out recall rises; on the "
        "evidence of section ⟦sec_learning⟧ it never did.")

    # ---------------------------------------------------------- large data
    c.h3("Large Data and the Device Governor", key="sec_bulk_impl")
    c.p("On a CPU, embedding is the cost of ingestion: 30–47 notes per second for BGE-small on four cores, which "
        "would leave a 120,000-paragraph corpus unusable for over an hour. Memory therefore has two tiers. Notes are "
        "committed at once **without** vectors and indexed by SQLite's FTS5 keyword index, kept in step by triggers, "
        "so they are searchable immediately through hybrid order (Equation ⟦eq_hybrid_n⟧). A background `drain` adds "
        "the vectors a batch at a time, pauses while other work keeps the CPU busy, and stops at the device's limits; "
        "the queue is its state, so it resumes after any stop.")
    c.p("A **governor** probes the device (free disk, available RAM, CPU load), calibrates it (embedding rate, search "
        "time per 100,000 notes, prompt-reading and generation speed) and enforces limits: a disk reserve, a RAM "
        "reserve, a store cap and a process cap. Every job checks it before each batch and stops cleanly, resumable, "
        "at the first limit. It also sets the read plan, choosing the largest token budget *B* whose expected time "
        "meets the latency target *L*:")
    c.eq(r"B^{*}=\underset{B\in\{512,256,128,64\}}{\text{max}}\;\left\{B:\;t_{\text{search}}(N)+30+\frac{B+60}{r_{\text{read}}}\cdot1000+\frac{16}{r_{\text{gen}}}\cdot1000\le L\right\}", key="eq_plan")
    c.where([(r"t_{\text{search}}(N)", "exact-search time in ms for N notes, linear in N from the calibration;"),
             (r"r_{\text{read}},\,r_{\text{gen}}", "the measured prompt-reading and generation speeds in tokens per "
              "second (285 and 50.7 for the 0.5B model on machine A).")])

    # ---------------------------------------------------------- runners and routing
    c.h3("Model Runners and the Learned Routing Policy", key="sec_policy_impl")
    c.p("Every runner exposes one operation, `generate`, and none can change model weights (FR-09). The Ollama runner "
        "uses greedy decoding and refuses any host but loopback unless configured as a ceiling (IR-01, NFR-06). The "
        "cloud runner pins the model name, retries with backoff, and logs a failure instead of scoring it (IR-02, "
        "IR-07). Kimi accepts only temperature 1, so its answers are single samples. Every answer from any model is "
        "cached by its exact request, which is what makes the results replayable without a key. Ollama aborts some "
        "generations with *token repeat limit reached*; the runner now records that as an empty answer instead of "
        "crashing the run (found in the formula experiment).")
    c.p("The learned policy chooses per question among five actions: the small model alone, with 128, 512 or 1,024 "
        "tokens of memory, or escalation to the cloud. No neural network is trained; the learned parameters are a "
        "ridge-regression vector per action and the cascade's grounding model.")
    old.policy_math(c)
    c.figure(DIAGRAMS / "policy.png", "Learned routing: a router chooses a memory budget or the cloud, and a grounding "
             "check escalates local answers the notes do not support", 7.5)

    # ---------------------------------------------------------- application
    c.h3("CAMR Personal: the Engine as a Desktop Assistant", key="sec_app")
    c.p("CAMR Personal gives any model the user has in Ollama a long-term memory. The user teaches it notes and files "
        "(.txt, .md, .pdf), states facts with *remember that …*, and approves good answers with a thumbs-up; what the "
        "user states in chat is remembered too, so a fact mentioned weeks ago is recalled after it has left the "
        "context window. Before the answer streams, a card shows which memories were read. Version 0.4 adds verified "
        "answers: a fact is shown as *Verified* with its source, or as an unverified lead. The server is a "
        "standard-library Python process bound to 127.0.0.1 that refuses foreign hosts and cross-site writes; the "
        "front end is a single page with no framework. Self-contained downloads are built by continuous integration "
        f"for six platforms. {c.next_fig()} and {c.next_fig(2)} show it in use.")
    for name, cap, w in (("dark_7_verified.png", "CAMR Personal 0.4: an answer stated as verified with its source, and "
                          "a lead that could not be verified", 14.5),
                         ("dark_3_panel_recall.png", "CAMR Personal: a remembered fact recalled, its grounding, and an "
                          "abstention, with the memory panel open", 14.5)):
        if (FIG / "app" / name).exists():
            c.figure(FIG / "app" / name, cap, w)
    old.interface_design(c)

    # ---------------------------------------------------------- automation gateway
    c.h3("Automation Gateway, n8n Workflows and the Agent", key="sec_gateway")
    c.p("To test whether the engine is needed in the automations companies actually build, it was put behind a "
        "small HTTP gateway that any workflow tool can call, next to the alternatives such a workflow would otherwise "
        f"use ({c.next_fig()}). The gateway serves four systems behind one interface (*reset, teach, forget, ask*): "
        "the model **alone**; **context stuffing**, which pastes the whole knowledge base into every prompt; **modern "
        "RAG**, hybrid search with a cross-encoder reranker and LangChain's standard RAG prompt; and **CAMR**, "
        "verified memory. Each answer records its model calls, tokens, seconds and, for the cloud model, its cost in "
        "US dollars at Moonshot's list price:")
    c.figure(DIAGRAMS / "automation.png", "Automation set-up: n8n workflows call the gateway over HTTP; the gateway "
             "serves four answering systems on a local or a cloud model and meters each answer")
    c.eq(r"\text{cost}=\frac{3.00\,T_{\text{in}}+15.00\,T_{\text{out}}}{10^{6}}\;\text{USD}", key="eq_cost")
    c.where([(r"T_{\text{in}},T_{\text{out}}", "prompt and generated tokens reported by the API (Kimi K3 reasoning "
              "tokens count as output); cached-input discounts were not applied, so costs are upper bounds.")])
    c.p("Three n8n workflows were built with standard nodes only (Manual Trigger, HTTP Request, Loop Over Items, IF, "
        "No Operation) and run headless with `n8n execute`; one workflow file per system is in "
        f"`results/agentic/n8n/`. The **support desk** ({c.next_fig()}) replays eight days of Helio Solar: each event "
        "is either a policy change, which withdraws the old document and publishes the new one, or a ticket, which "
        "is answered and then either sent or escalated. When a person resolves an escalated ticket, the resolution "
        "is taught, so the next customer who asks gets it automatically. The **current-events digest** fetches 30 "
        "daily Wikipedia pages live, teaches every item, and answers 50 questions about them; when Wikimedia refused "
        "a fetch (it began to after repeated runs, D-36), the gateway taught the same page as cached when the "
        "questions were written. The **operations "
        "agent** workflow hands each of 20 tasks to an agent and records whether it completed it or handed it to a "
        "person.")
    c.figure(DIAGRAMS / "n8n_desk.png", "Support-desk workflow as built in n8n (node names as in the workflow file)")
    for name, cap in n8n_shots():
        # detail views: the input and output panels side by side (scripts/agentic/n8n_screens.py crop)
        path = next((q for q in (FIG / "n8n" / "panels" / name, FIG / "n8n" / name) if q.exists()), None)
        if path:
            c.figure(path, re.sub(r"\*([^*]+)\*", "\u201c\\1\u201d", cap).replace("`", ""), 15.8)
    c.p(f"The agent ({c.next_fig()}) is a tool-using loop in the ReAct style: each turn the model writes one line, "
        "*ACTION <tool> <json>* or *DONE*; the tool runs and its result is appended. Its tools are `search_memory` "
        "(absent without memory), `calculate`, `create_invoice`, `reply` and `escalate`. A task succeeds only when "
        "every check on the tool calls holds; an invoice or reply with a number or fact that is not the company's "
        "counts as a **hallucinated action**. The first runs with the 3B model showed it answering *DONE* at once or "
        "never consulting memory, so the agent now searches memory with the task before the first turn, and the "
        "prompt ends with an explicit cue for the next line.")
    c.figure(DIAGRAMS / "agent_loop.png", "The operations agent: one tool call per turn, at most eight turns, checked "
             "on what it did, not on what it said", 9.5)


# ================================================================= 5.5 Model selection and evaluation protocol


def selection(c: Chapter) -> None:
    th = J("results/ragbench/thresholds.json") or {}
    c.h2("Model Training, Selection and Evaluation Protocol", key="sec_selection")
    c.h3("Baselines and Candidate Models")
    c.p("Because CAMR's answering models are frozen, *model selection* meant two things: which frozen model to "
        "recommend for the engine, and which engine configuration to use. Both were chosen on evidence kept apart "
        f"from the final tests. {c.next_tab()} lists every baseline the engine was compared with.")
    c.table("Baselines",
            ["Baseline", "What it is", "Used in"],
            [["Model alone (floor)", "The same frozen model, no memory", "Every experiment"],
             ["Kimi K3 closed-book", "Frontier cloud model answering from its weights", "⟦sec_verified⟧, ⟦sec_gap⟧, "
              "⟦sec_agentic⟧"],
             ["Kimi K3 with the same notes", "The cloud model reading what CAMR retrieved (ceiling_rag)", "⟦sec_gap⟧"],
             ["Eight modern RAG pipelines", "Dense, BM25, hybrid, reranked, HyDE, corrective, abstaining, and reranked "
              "with CAMR's check (section ⟦sec_rag_def⟧)", "⟦sec_ragresult⟧"],
             ["Context stuffing", "The whole knowledge base in every prompt", "⟦sec_agentic⟧"],
             ["LoRA fine-tuning (facts)", "Qwen2.5-0.5B trained on the 237 documents CAMR stores", "⟦sec_learning⟧"],
             ["LoRA fine-tuning (formulas)", "The same model trained on the same corrections memory stores",
              "⟦sec_learning⟧"],
             ["Token memory (kNN-LM)", "22,554 (hidden state, next token) pairs beside the frozen model",
              "⟦sec_learning⟧"]],
            [3.6, 7.6, 4.7], size=9.5)
    c.p("**Candidate models.** Nineteen quantised models from 0.5B to 14.8B parameters across ten families were each "
        "run with the same store, questions and prompts (greedy decoding, seed 13). The pilot questions served as "
        "validation evidence; the 200-question HotpotQA study then served as a held-out test, with its configuration "
        "written before it ran. For verified answering, five readers (0.5B, 1.5B, 3B, 3.8B, 7B) answered the "
        "held-out set with the pipeline that had been chosen on the development set with the 0.5B model.")
    c.h3("What Was Trained, and How It Was Selected", key="sec_tune_read")
    c.p("No weight of an answering model changes in CAMR. Four components were fitted to data, and each was selected "
        f"on data its final test never saw ({c.next_tab()}).")
    c.table("Trained and tuned components and how each was selected",
            ["Component", "Search space", "Selected on", "Chosen", "Tested on"],
            [["Router (ridge per action)", "λ ∈ {0.01 … 100} × 3 feature sets", "5-fold CV, 144 training questions",
              "task-only features, λ = 0.01", "72 held-out questions, once"],
             ["LinUCB (online router)", "α ∈ {0 … 2}, 1–10 passes", "same", "α = 1, one pass", "same"],
             ["Grounding cascade", "threshold θ ∈ [0, 1], step 0.05", "same", "θ = 0.05", "same"],
             ["Read path (gate margin δ, budget B)", "δ ∈ {None, 0.05 … 0.25}, B ∈ {256, 512, 1024}",
              "validation half of 1,000 retrieval questions", "δ = None, B = 1,024 (retrieval only)", "other half"],
             ["LoRA on documents", "format × lr × epoch", "60 validation questions", "raw, 3e-4, epoch 1",
              "60 held-out questions"],
             ["LoRA on corrections", "epoch 1–6", "2 problems per family", "epoch 6", "fresh draw (seed 47)"],
             ["RAG abstain and CRAG thresholds", "cross-encoder score", "200 development questions",
              f"abstain {th.get('abstain_threshold', 5.3)}; CRAG {th.get('crag_lower', 4.77)} / "
              f"{th.get('crag_upper', 7.57)}", "200 held-out questions"],
             ["Verified answering (methods)", "infobox facts, fact reader, compression, strict checks, subject "
              "look-up, second readers, hybrid", "200 development questions", "facts + compression + strict + "
              "subject look-up, 0.5B reader", "200 held-out questions, once"]],
            [3.4, 3.7, 3.3, 3.0, 2.5], size=9)
    c.p("The two LoRA baselines were trained on CPU in full precision (rank 16; micro-batch 2 with 4-step gradient "
        "accumulation and gradient checkpointing after batch 8 ran out of memory at 13.9 GB). Their training and "
        "validation curves are in section ⟦sec_learning⟧.")
    c.h3("Evaluation Protocol and Measures")
    old.metrics_section(c)
    c.p("For verified answering every answer falls in one of four outcomes: **correct**; **wrong, stated as fact** "
        "(the hallucination rate); **about another meaning, named** (a true statement about a meaning the answer "
        "names, e.g. the 2011 film when the question meant the 1992 one); and **not confirmed** (withheld or offered "
        "as a lead). Exact matching misses aliases (*Garowe* for *Garoowe*), so every answer exact matching marked "
        "wrong was judged again by Kimi K3 with a fixed prompt, and both scores are kept. For a system that may "
        "decline, the precision of what it states is reported beside its accuracy:")
    c.eq(r"\text{precision}=\frac{\#\{\text{stated and correct}\}}{\#\{\text{stated}\}},\qquad\text{coverage}=\frac{\#\{\text{stated}\}}{\#\{\text{questions}\}}", key="eq_prec")
    c.p("In the automations, each of the *N* tickets ends in exactly one outcome: a correct reply, a wrong reply "
        "(including a superseded value after a policy change) or an escalation to a person. Unknowable tickets (and "
        "the first occurrence of a question nobody has answered yet) should be escalated; all others should be "
        "answered:")
    c.eq(r"R=\frac{n_{\text{correct}}}{N},\quad W=\frac{n_{\text{wrong}}}{N},\quad E=\frac{n_{\text{escalated}}}{N},\quad R+W+E=1;\qquad c_{1000}=\frac{1000}{N}\sum_{t=1}^{N}\text{cost}_t", key="eq_desk")
    c.p("An agent task *succeeds* only if every check on its tool calls holds. With 200 questions one question is 0.5 "
        "points; with 60 tickets, 1.7 points; with 20 tasks, 5 points.")
    c.h3("The Modern RAG Pipelines Compared", key="sec_rag_def")
    c.p("CAMR's verified pipeline was compared with eight retrieval-augmented generation pipelines in current use. All "
        "nine read the same store (the RAG corpus of section ⟦sec_data⟧), retrieve from the same notes, and are scored "
        "on the same 200 held-out questions. Every RAG pipeline uses LangChain's standard RAG prompt (*rlm/rag-prompt*) "
        f"and five passages. {c.next_fig()} shows what each one does.")
    c.figure(DIAGRAMS / "rag_pipelines.png", "The nine pipelines: what each retrieves, how it decides whether to "
             "answer, and what reads the result")
    c.p("Hybrid search fuses the dense and BM25 rankings by reciprocal rank (Cormack et al., 2009), and the reranker "
        "rescores the fused top 20 with a cross-encoder (Nogueira & Cho, 2019):")
    c.eq(r"\text{RRF}(n)=\sum_{r\in\{\text{dense},\text{bm25}\}}\frac{1}{k+\text{rank}_r(n)},\qquad k=60", key="eq_rrf")
    c.p("HyDE (Gao et al., 2022) embeds a passage the reader writes instead of the question. Corrective RAG (Yan et "
        "al., 2024) grades retrieval with the cross-encoder's best score: above the upper threshold it keeps the "
        "relevant sentences; below the lower one it searches the web (here, the same frozen lookups CAMR uses); in "
        "between it does both. The abstaining pipeline answers only when the best score clears its threshold. The "
        "*check* pipeline is a hybrid: modern RAG retrieval and reading, followed by CAMR's verification check, which "
        "separates the value of CAMR's check from the value of its retrieval.")


# ================================================================= 5.6 Testing


TEST_CASES = [
    ["TC-01–06", "FR-01–FR-08, IR-03/04", "Write path, screener, store, ranking, budget (fixtures)",
     "Notes with provenance; rejects logged; kNN equal to NumPy; budget never exceeded", "Pass"],
    ["TC-07–08", "FR-09/10, IR-01/02", "Runner interface; non-loopback host; failing cloud transport",
     "Only `generate`; remote host refused; bounded retries then a logged failure", "Pass"],
    ["TC-09–13", "FR-11–FR-15, DR-02", "Sampling, scoring, records, ablation plan, bootstrap",
     "Same sample after shuffling; scores equal hand values; CI correct", "Pass"],
    ["TC-14", "FR-16, NFR-01", "Device profile, 3 × 10 questions", "Fits 16 GB", "Engine 712 MB + runtime 1,987 MB. Pass"],
    ["TC-17", "NFR-02", "Retrieval share of answer time, 0.5B", "≤ 10%", "56% (contention). **Fail** (D-05)"],
    ["TC-19", "NFR-05", "Same configuration twice", "Byte-identical prompts", "30/30 prompts; 0.5B answers 20/30 (D-02)"],
    ["TC-20–22", "NFR-06, DR-04, IR-07", "Sockets blocked; leaked question; runtime down mid-run",
     "No external connection; ingestion refused; failures logged, run continues", "Pass"],
    ["TC-23–36", "Application", "Teach, ask, remember, 👍, forget, export; empty input; foreign host; path "
     "traversal; six platform builds", "As specified in Chapter 4", "Pass (13 + 6 server tests, CI on six platforms)"],
    ["TC-37–58", "Learning (0.3)", "Lookups, privacy of personal questions, rate limits, packs, harvest, sleep",
     "Personal questions never sent; caches replay offline; packs install without a model", "Pass (27 + 15 tests)"],
    ["TC-59", "Verified answering", "A claim in memory about another subject / relation / of the wrong kind",
     "Not stated", "Pass (25 tests)"],
    ["TC-60", "Verified answering", "A fact line answers the question", "Answered without a model call", "Pass"],
    ["TC-61", "Verified answering (D-33)", "Questions that name nothing (*What hours is the support desk open?*)",
     "Stated only from a sentence sharing the topic words", "Failed first in the n8n desk; fixed. Pass"],
    ["TC-62", "Large data", "Bulk ingest; search before any vector exists", "Searchable at once through keywords",
     "123,301 paragraphs in 335 s; hybrid recall@10 74.3% with no vectors. Pass"],
    ["TC-63", "Governor", "Store cap, disk reserve, RAM reserve; resume", "Stops before each limit; resumes with no "
     "duplicate", "Stopped at all three; 0 duplicates in 14,104 notes. Pass (11 tests)"],
    ["TC-64", "Formulas", "A wrong training answer; a correction stored; held-out problems",
     "Correction recalled; calculator evaluates or solves; grounding flagged", "Pass (replayed offline)"],
    ["TC-65", "Entities (D-31, D-32, D-37)", "Instructions at the start of a sentence; terse ticket phrasing; "
     "titles with *St.*, *A.I.*, *Hello*", "Instructions not taken for names; titles kept whole", "D-37 found by "
     "the replay check; fixed. Pass (4 regression tests)"],
    ["TC-66", "Runner", "Ollama aborts with *token repeat limit*", "Empty answer recorded; run continues", "Pass"],
    ["TC-67", "Automation gateway", "n8n workflows: 60 tickets, 20 tasks, 30 live pages",
     "Every workflow completes (exit 0); every answer metered", "Failed when Wikimedia refused fetches (D-36); fixed. Pass (n8n 2.43.6)"],
    ["TC-68", "Reproducibility (NFR-04/05)", "`reproduce.py --twice` without key or network",
     "Every recomputed number equals the committed one", "16/16. Pass"],
]


def testing(c: Chapter) -> None:
    c.h2("Testing", key="sec_testing")
    c.h3("Test Strategy and Acceptance Criteria")
    c.p("Testing worked at four levels, each answering a different question. **Unit and integration tests** (203, "
        "pytest, white-box, fully offline with test doubles for models and the web) check that each component does "
        "what its requirement says. **System tests** run the real pipeline on real data with real models. **Replay "
        "tests** recompute the key results from frozen caches and require every number to match. **Measurements** "
        "check the non-functional requirements against thresholds fixed before the runs: retrieval ≤ 10% of answer "
        "time (NFR-02), byte-identical prompts on a repeat (NFR-05), fits in 16 GB (NFR-01). Browser tests "
        "(Playwright) and an accessibility audit (axe-core, WCAG AA contrast) cover the interface. A verdict is "
        f"assigned only by comparing an observed result with an expected one written in advance. {c.next_tab()} shows "
        "where the 203 automated tests sit.")
    files = [["test_memory.py", 48, "Write and read paths, gate, entity gate, bridging, budget, per-title limit"],
             ["test_learning.py", 27, "Lookups, rate limits, privacy rule, packs, harvest, sleep"],
             ["test_verify.py", 25, "Grounding, subject, relation, kind, fact reader, topic anchoring, replay"],
             ["test_harness.py", 22, "Conditions, records, failures, resume, runner errors"],
             ["test_bridging.py", 16, "Entity bridging and its budget interaction"],
             ["test_app_learning.py", 15, "Application learning features"],
             ["test_app.py / test_app_server.py", 19, "Assistant core; server API, host and origin checks"],
             ["test_device.py", 11, "Governor limits, resume, read plan"],
             ["test_app_e2e.py", 11, "Browser tests with Chromium"],
             ["test_architecture.py / test_learn.py", 9, "Package dependency rules; learned policy"]]
    c.table("Automated tests by file (pytest 9.1.1, 203 tests, all passing)", ["File", "Tests", "What they cover"],
            [[f"`{a}`", b, d] for a, b, d in files], [5.0, 1.6, 9.3], size=9.5)
    c.h3("Test Cases and Results", key="sec_tests")
    c.p("The test cases are summarised by requirement below. Detailed cases for the earlier increments (TC-01 to "
        "TC-58) are in the test files and the repository's earlier chapter; TC-59 to TC-68 cover this increment.")
    c.table("Test cases and results", ["Test ID", "Traceability", "Scenario and data", "Expected result",
                                       "Actual result and verdict"],
            TEST_CASES, [1.6, 2.6, 4.3, 3.6, 3.8], size=8.5)
    c.h3("Defects Found and Retests", key="sec_defects")
    c.p("Every defect below was found by a test or a real run, and every one was either fixed and retested or is "
        "reported as open. Failed results were kept, not deleted. Most defects were found by running the system on "
        "real data, not by the unit tests, which is why the system tests matter.")
    defects = [
        ["D-01", "Screener rejected a real song title (*I Can't Get Next to You*) as a model refusal", "Refusal check "
         "only on model-written notes", "Pass"],
        ["D-02", "0.5B answers differed on 10/30 questions between identical runs (wrong → wrong)", "Engine shown "
         "deterministic; floors reported as a range", "Open (runtime)"],
        ["D-03", "20B model killed for lack of memory at 13.3 GB", "Memory-mapped weights", "Pass"],
        ["D-04", "A configuration field added mid-study changed the hash; resume re-ran finished runs", "Schema "
         "frozen before final runs", "Pass"],
        ["D-05", "Retrieval took 56% of the 0.5B model's answer time (NFR-02)", "Diagnosed as CPU contention; thread "
         "partitioning", "Open for 0.5B"],
        ["D-06", "Recency + importance (Eq. 4.1) lowered full-support recall by 4.6 points", "Similarity + gating + "
         "bridging", "Pass"],
        ["D-07", "A run whose model server died mid-sweep was still marked complete", "Resume re-runs runs with "
         "failed queries", "Pass"],
        ["D-08", "gemma2:9b killed three times at 13.4 GB (prompt cache)", "Prompt cache capped at 1 GiB", "Pass"],
        ["D-09", "App: store used across threads; file watcher crashed", "Lock; watcher off", "Pass"],
        ["D-10", "App warm-up loaded the model with other options, so it loaded twice", "Same options", "Pass"],
        ["D-11, D-12", "Interface contrast below WCAG AA; no top-level heading", "Tokens per theme; hidden heading",
         "Pass (0 axe violations)"],
        ["D-13, D-16", "App over-refused general questions (*capital of Australia*)", "Prompt chosen on held-out "
         "cases (21/21)", "Pass"],
        ["D-14", "Chat memory stored plain questions", "Only statements kept", "Pass"],
        ["D-15", "Entity gate: possessive normalised differently in question and note", "One normalisation", "Pass"],
        ["D-17, D-18", "Lookups: *The* stripped mid-title; an empty reply (rate limit) cached as *nothing known*",
         "Article kept; empty replies never cached", "Pass; stream re-run"],
        ["D-19", "*Ask to be taught* prompt led with *I don't know* although the notes answered", "Prompt F", "Pass"],
        ["D-20, D-21", "Pack harvest drifted off topic; lookups sent no User-Agent, so Wikimedia refused them",
         "Relevance floor; CAMR User-Agent", "Pass"],
        ["D-22, D-23", "Sleep read names across sentence ends; two chips below AA contrast", "Names within a "
         "sentence; darker green", "Pass"],
        ["D-24, D-29", "Ambiguous names: the wrong meaning fetched first; for *Spain* a list instead of the country",
         "Meanings named exactly as asked first; the name's own article first", "Pass"],
        ["D-25, D-26", "Searched for *director of Emma* (finds people called Emma); fetched fragments of a name",
         "Relation phrases look up their subject; fragments skipped", "Pass"],
        ["D-27, D-30", "Rate-limited search and summary APIs cost two minutes a question", "Ordinary search page and "
         "article page instead", "Pass"],
        ["D-28", "*genre is Covers* searched as a name", "The phrase only when no name exists", "Pass"],
        ["D-31", "Entity gate read instructions (*Give the amount…*, *Find its area*) as names, withholding the right "
         "correction for 33 of 60 reworded problems", "Instructions at any sentence start are not names", "Pass; "
         "verified replays identical"],
        ["D-32", "Entity gate read terse ticket phrasing (*Recommended cleaning interval?*, *E57. Any idea?*) as "
         "names, so the agent's memory returned nothing", "Sentence openers are not names; a name ends with its "
         "sentence", "Pass; agent 80% → 100%"],
        ["D-33", "Verified answering withheld correct answers to questions that name nothing: 14 of 45 answerable "
         "desk tickets escalated", "Topic anchoring (Eq. ⟦eq_topic_n⟧)", "Pass; desk 51.7% → 75.0%, still 0 "
         "wrong"],
        ["D-34", "The news workflow reused the support persona, so the cloud model refused news questions as off "
         "topic", "Persona per scenario", "Pass; re-run"],
        ["D-35", "The decline detector missed *I can't identify …*, so a RAG decline was sent as a reply", "Pattern "
         "widened; every desk system re-run", "Pass"],
        ["D-38", "Kimi K3 writes *I don’t know* with a curly apostrophe, which the decline detector missed, so 13 of "
         "its honest declines on the news questions were scored as wrong answers", "Apostrophes normalised before "
         "detection (gateway and RAG benchmark)", "Every result file re-checked: only that run was affected; re-run"],
        ["D-37", "The D-32 fix itself cut titles at abbreviations and greetings (*St. Louis Blues* → *Louis Blues*, "
         "*A.I. Artificial Intelligence*, *the composer of Hello*), and its opener rule dropped names that start a "
         "statement (*Josh decides to …*), so PopQA questions and the GSM8K interference check recalled different "
         "notes", "Abbreviations, dotted initials and ellipses do not end a sentence; greetings are openers only at a "
         "sentence start; the opener rule applies only to a sentence that asks", "Found by the replay check; extraction "
         "identical to before D-32 on all 600 PopQA questions and 440 formula problems; replays re-run"],
        ["D-36", "After repeated runs Wikimedia refused the workflow's live page fetches (HTTP 403), and the news "
         "workflow stopped", "The fetch node continues on error; the gateway then uses the page as cached when the "
         "questions were written, and records which pages came live", "Pass; re-run"],
        ["D-39", "In the news workflow a loop's *done* output fed all 30 looped pages to the next node, which n8n runs "
         "once per item: each question was asked 30 times and 1,500 score requests reset the gateway's connection, "
         "so n8n marked the runs as failed", "The nodes after a loop run once (*Execute Once*)", "Found in the "
         "screenshots; scores and costs unchanged (answers per question, repeats were cache hits); re-run clean"],
        ["D-40", "The D-37 opener rule applied only to sentences ending in *?*, so the desk request *Price of the "
         "Helio bird mesh kit please* read *Price of the Helio* as a name and the ticket was escalated", "Requests "
         "(*please*) and fragments without a full stop also open with a common word; the test uses the ticket as "
         "written", "Found by re-running the desk on the final code; every CAMR desk answer identical to the reported "
         "run; PopQA and formula extraction unchanged"],
    ]
    c.table("Defects found and retests", ["ID", "Defect", "Correction", "Retest"], defects,
            [1.7, 7.4, 4.3, 2.5], size=8.5)
    c.h3("Application and Interface Testing", key="sec_apptest")
    c.p("CAMR Personal was tested as a user meets it: valid, empty, out-of-scope and unsupported input, the runtime "
        "missing, a foreign host. Browser tests (Chromium, Playwright) cover remember-then-ask with the recall card, "
        "an empty message, thumbs-up teaching, theme and panel, phone width without horizontal scrolling, and a "
        "keyboard-only path with accessible names. The axe-core audit first reported a *serious* contrast violation "
        "and a missing page heading (D-11, D-12); after the fixes it reported **0 violations** in both themes at "
        "desktop and phone width, with every colour pair at WCAG AA or better. These tests show that the application "
        "behaves correctly and fails safely. They do not show that people find it useful: no user study was run "
        "(section ⟦sec_limits⟧).")
    if (FIG / "app" / "dark_0_setup_ollama_down.png").exists():
        c.figure(FIG / "app" / "dark_0_setup_ollama_down.png", "Failing safely: with Ollama not running, the "
                 "application says what is missing and offers the download", 13.0)
    old.ui_testing(c)


# ================================================================= 5.7 Version control, 5.8 AI declaration


def version_control(c: Chapter) -> None:
    n_commits, _ = git_count()
    c.h2("Version Control and Implementation Evidence", key="sec_vc")
    c.p(f"Project repository: **{REPO_URL}**. The repository holds the README, a setup walkthrough "
        "(`docs/SETUP.md`), the findings log naming the results file behind every number (`docs/FINDINGS.md`), the "
        "dependency file (`pyproject.toml`), every experiment configuration (`configs/`), the test suite, the n8n "
        "workflow files, and the scripts that regenerate every figure and this chapter. Results that are small enough "
        "(summaries, per-question records, answer and web caches) are committed so that the replay checks run from a "
        "fresh clone; downloaded datasets and large databases are excluded by `.gitignore` and regenerated by the "
        f"scripts. The history holds {n_commits} commits, each an implemented or measured step whose message names "
        "what it added.")
    c.p("The work followed GitHub flow: one branch per round of work, merged through a pull request that describes "
        "the change and its test plan. Merged so far: Satasdin/CAMR#2 (engine, harness, findings), Satasdin/CAMR#3 "
        "(CAMR Personal 0.2 and the n = 200 study), Satasdin/CAMR#4 (application speed), Satasdin/CAMR#5 (0.2.1), "
        "Satasdin/CAMR#6 (GitHub evidence), Satasdin/CAMR#7 (equations, RAG comparison, tuning, LoRA, interface "
        "tests) and Satasdin/CAMR#8 (CAMR 0.3, learning as it goes). The work in this chapter (verified answering, "
        "large data, the governor, formulas, RAG pipelines, automations) is on branch "
        "`claude/engine-build-docs-yfw9u0`. The sweep machines pushed results to their own branches, which were "
        "merged into the results database rather than into the code. Continuous integration builds and "
        "launch-tests the application on six platforms for every change to it; releases v0.2.0 and v0.2.1 attach the "
        "six downloads. The code is MIT-licensed.")
    for name, cap in (("1_repository.png", "Project repository on GitHub"),
                      ("2_pull_requests.png", "Pull requests that merged each round of work"),
                      ("3_actions_run.png", "Continuous integration: tests, build and launch test on six platforms")):
        if (FIG / "repo" / name).exists():
            c.figure(FIG / "repo" / name, cap + " (screenshot)", 14.5)
    c.table("Continuous-integration evidence (GitHub Actions run 36899712846, release v0.2.1)",
            ["Target", "Runner", "Tests", "Build", "Launch test"],
            [["Windows x64", "windows-2025", "pass", "pass", "pass"],
             ["Windows ARM64", "windows-11-arm", "pass", "pass", "pass"],
             ["macOS Apple Silicon", "macos-15", "pass", "pass", "pass"],
             ["macOS Intel", "macos-15-intel", "pass", "pass", "pass"],
             ["Linux x64", "ubuntu-24.04", "pass", "pass", "pass"],
             ["Linux ARM64", "ubuntu-24.04-arm", "pass", "pass", "pass"]],
            [4.0, 3.6, 2.6, 2.6, 3.1], size=9.5, key="ci")
    c.p("**Secrets.** The Moonshot key was supplied only through an environment variable, masked in every log, and "
        "never written to a configuration file, a commit or a screenshot. Cached cloud answers are stored by request "
        "text, which contains no key.")


def ai_declaration(c: Chapter, declaration: str | None) -> None:
    c.h2("Author Oversight and Use of AI-Assisted Tools")
    c.p(declaration or (
        "Claude Code, an AI coding assistant provided by Anthropic, was used during implementation and evaluation. "
        "Under the student's direction it helped write the engine, the gateway, the experiment scripts and their "
        "tests; ran the experiments on the cloud machines; produced the figures and screenshots; and drafted this "
        "chapter from the logged results. Kimi K3 (Moonshot AI) was used as a measured system and as the judge of "
        "answers that exact matching marked wrong; its role in each experiment is stated where it appears. The "
        "student defined the problem, objectives, requirements and design (Chapters 1–4), chose which experiments "
        "to run, including the comparison with modern RAG pipelines, the automation scenarios and the cloud-cost "
        "accounting, and set the budget for cloud use."))
    c.p("The output was checked against the source code, the automated tests (203), the per-question records and "
        "the replay harness, which recomputes the key results and fails if any number differs. The student required "
        "that only experiments actually run be reported, and that failures be reported as measured; an earlier draft "
        "written before results existed was discarded for that reason. The student made the final decisions and "
        "takes full responsibility for the submitted work.")


# ================================================================= 5.9 Results (sections whose data is complete)


def res_retrieval(c: Chapter) -> None:
    c.h3("Getting the Evidence to the Model (Objective ii)", key="sec_retrieval")
    c.p("Before any model answers, the first question is whether the right text reaches it. This was measured with "
        "no language model at all: 500 questions per benchmark over one store of 38,054 notes from 23,524 real "
        f"paragraphs, counting a question as served only if **every** gold paragraph reached the context (Equation "
        f"⟦eq_sr_n⟧). {c.next_tab()} gives the result.")
    c.table("Full-support recall by read path, 500 questions each (`results/retrieval_eval/tables/retrieval_eval.json`)",
            ["Read path (512 tokens unless stated)", "2Wiki: all gold", "Tokens", "HotpotQA: all gold", "Tokens"],
            [["Similarity only (baseline)", "35.8%", "471", "70.8%", "470"],
             ["+ recency and importance (proposal's Eq. 4.1)", "34.6%", "470", "65.4%", "467"],
             ["+ gating", "33.4%", "408", "64.6%", "384"],
             ["+ entity bridging", "75.2%", "472", "70.0%", "470"],
             ["**Similarity + gating + bridging (CAMR)**", "**78.4%**", "**439**", "70.8%", "420"],
             ["Standard RAG, top 10", "39.2%", "767", "78.6%", "800"],
             ["CAMR at 1,024 tokens", "**84.0%**", "821", "**83.0%**", "728"]],
            [6.4, 2.4, 1.7, 2.6, 1.7], size=9.5)
    c.p("**Where it was strong.** On 2WikiMultiHopQA, entity bridging lifted full-support recall from 35.8% to 78.4% "
        "at the same budget with 7% fewer tokens: twice the recall of top-10 RAG with 43% fewer tokens. These questions "
        "are compositional (*Who is the father of the director of film X?*); the second paragraph shares almost no "
        "words with the question, so similarity cannot find it, but the first paragraph names it, and bridging follows "
        "the name; section ⟦sec_examples⟧ follows two real questions through it.")
    c.p("**Where it was not.** On HotpotQA, where both entities are usually named in the question, CAMR is plain RAG "
        "with a token cap (70.8% against 68.2% for top-5 RAG at equal precision), and top-10 RAG finds more (78.6%) "
        "by reading twice the text. The proposal's composite score (Equation 4.1, recency and importance) **lowered** "
        "recall on both benchmarks (−1.2 and −5.4 points), because benchmark questions are independent and recency "
        "carries no information about them; it was dropped (D-06). Bridging also costs recall at a 256-token budget "
        "(−6.4 points), where bridged notes crowd out direct hits.")


def res_verified(c: Chapter) -> None:
    jf = (J("results/verified/judged_heldout.json") or {})
    sa = jf.get("files", {}).get("answers_heldout_sa.json", {})
    v = sa.get("facts+compress+reader", {}).get("verified", {})
    vk = sa.get("+kimi+cross", {}).get("verified", {})
    cl = jf.get("closed", {})
    c.h3("Answers That Are Verified or Not Stated (No Hallucination)", key="sec_verified")
    c.p("A small model with memory still states wrong facts: in the earlier pipeline the 0.5B model read memory and "
        "answered every question, and half of its answers were wrong. Verified answering (section ⟦sec_verify_impl⟧) "
        "was built to change that, and every method was chosen on the 200 development questions "
        f"({c.next_tab()}).")
    c.table("Development set: each step of verified answering (200 questions, judged; `results/verified/answers_dev*.json`)",
            ["Pipeline", "Correct", "Wrong, stated", "Other meaning (named)", "Not confirmed"],
            [["Before: 0.5B reads, every answer stated", "45.0%", "**51.5%**", "–", "–"],
             ["The same answers, checked", "42.0%", "9.0%", "20.5%", "28.5%"],
             ["+ infobox facts as notes", "48.0%", "5.0%", "20.0%", "27.0%"],
             ["+ fact reader and compression", "55.5%", "3.5%", "18.0%", "23.0%"],
             ["+ strict checks (kind, relation)", "55.5%", "2.5%", "17.5%", "24.5%"],
             ["**+ look up the subject when no note is titled with it (chosen)**", "**59.0%**", "**2.5%**", "20.5%",
              "18.0%"],
             ["chosen + Kimi K3 second reader and cross-check", "60.0%", "3.0%", "21.0%", "16.0%"],
             ["strict + 3B second reader", "57.0%", "3.0%", "18.0%", "22.0%"],
             ["chosen + hybrid (keyword) recall", "59.0%", "2.5%", "20.5%", "18.0%"]],
            [7.0, 1.8, 2.2, 2.6, 2.3], size=9)
    c.p("Two findings from development shaped the design. A larger second reader (3B or Kimi K3) added at most one "
        "point of correct answers and up to 1.5 points of wrong ones: when the answer is not in what memory read, a "
        "stronger reader cannot find it either. And *knowing* a subject had to mean having a note titled with it; "
        "notes that merely mention it had stopped lookups (+3.5 points once fixed). The chosen pipeline was then run "
        f"**once** on the held-out set ({c.next_fig()}, {c.next_tab()}).")
    c.figure(REPORT / "verified_outcomes.png", "Held-out set (200 questions no choice was made on): outcomes of each "
             "system, judged", 15.5)
    rows = [["**0.5B + verified memory (CAMR)**", f"**{p1(v.get('correct'))}**", f"**{p1(v.get('hallucinated'))}**",
             p1(v.get("other_meaning")), p1(v.get("unconfirmed"))],
            ["0.5B + verified memory, Kimi K3 cross-check", p1(vk.get("correct")), p1(vk.get("hallucinated")),
             p1(vk.get("other_meaning")), p1(vk.get("unconfirmed"))],
            ["Before: 0.5B reads, every answer stated", "47.0%", "52.0%", "–", "–"]]
    for m, name in (("kimi-k3", "Kimi K3 alone (cloud)"), ("llama3.2:3b", "Llama 3B alone"),
                    ("qwen2.5:0.5b", "Qwen 0.5B alone")):
        if m in cl:
            rows.append([name, p1(cl[m]["correct"]), p1(cl[m]["wrong"]), "–", p1(1 - cl[m]["correct"] - cl[m]["wrong"])])
    c.table("Held-out set: verified memory against the models alone (`results/verified/judged_heldout.json`)",
            ["System", "Correct", "Wrong, stated as fact", "Other meaning (named)", "Not confirmed"], rows,
            [6.6, 1.9, 2.6, 2.6, 2.2], size=9.5)
    c.p(f"**What this shows.** On questions no choice was made on, the frozen 0.5B model with verified memory states a "
        f"wrong fact about once in thirty-three answers ({p1(v.get('hallucinated'))}), against about once in three for "
        f"the cloud model answering from its weights ({p1(cl.get('kimi-k3', {}).get('wrong'))}), and it is correct "
        f"{p1(v.get('correct'))} of the time against the cloud model's {p1(cl.get('kimi-k3', {}).get('correct'))}. "
        "That is the trade the design makes: less coverage for far fewer wrong statements. Of the correct answers, 102 "
        "were read straight from a fact line with no model call, and 19 were read by the model and confirmed by the "
        "checks.")
    c.p(f"**Where it was not perfect.** {c.next_tab()} shows one real case of every outcome.")
    c.table("One held-out case of each outcome (Qwen 0.5B, verbatim)",
            ["Outcome", "Question", "What was stated", "Why"],
            [["Correct, no model call", "Who was the screenwriter for Mississippi Burning?", "Chris Gerolmo",
              "Fact line *Written by: Chris Gerolmo*"],
             ["Correct, model read", "Who is the author of The Disk?", "Jorge Luis Borges is the author of \"The Disk\"",
              "Sentence *\"The Disk\" is a 1975 short story written by … Jorge Luis Borges*"],
             ["Other meaning, named", "Who was the producer of Happy? (gold: Allu Aravind)", "Happy (Pharrell Williams "
              "song): Pharrell Williams; Happy (2011 film): …", "The name has many meanings; each answer names its own"],
             ["Wrong, stated", "In what country is Almedina? (gold: Portugal)", "Spain",
              "The stored line *Almedina: Country: Spain* is about another Almedina"],
             ["Wrong, stated", "What is Hermann Ahlwardt's occupation? (gold: journalist)", "Teacher, opinion writer",
              "Quoted from the infobox; the benchmark's answer differs"],
             ["Correct, withheld", "Who is the author of The Incoherence of the Philosophers?", "– (lead: al-Ghazali)",
              "The kind check expects a capitalised name"],
             ["Wrong, withheld", "Who was the screenwriter for Boring?", "– (lead: Steven Spielberg)", "Not in memory: the "
              "model guessed, and the check stopped it"]],
            [2.8, 4.3, 4.0, 4.8], size=8.5)
    c.p("All six wrong stated answers on the held-out set repeat a stored line word for word: the model did not invent "
        "them. They come from a page about another meaning of the name, or from a source that disagrees with the "
        "benchmark. The check guarantees that a stated answer is *supported by memory*, not that memory is right. "
        "The other costs are coverage: 19% of questions got no stated answer, and 3.5% of those had a correct lead that "
        "the checks were too strict to accept. On the 200-question test stream (seen once before round 2) the same "
        "pipeline scored 52.5% correct with 5.0% wrong; Kimi K3 alone scored 68.0% with 31.0% wrong.")


def res_multihop(c: Chapter) -> None:
    c.h3("Multi-Hop Questions and the Residual Gap (Objectives iii and iv)", key="sec_gap")
    h = old.hotpot200()
    c.p("The pilot (30 questions per task) showed what memory can and cannot close. With the same notes, the gap "
        "between a 0.5B model and a 20B model was 10.0 points on single facts, 23.3 on multi-hop questions and 83.3 on "
        "arithmetic reasoning: **memory closes knowledge gaps, not reasoning gaps**. Most of the remaining multi-hop "
        "gap was reading: 16 of the 0.5B model's 21 misses (76%) had the answer in its context. The multi-hop result "
        "was then confirmed on 200 HotpotQA questions with the configuration fixed in advance.")
    if h:
        c.table("HotpotQA, 200 held-out questions: exact match alone and with CAMR, paired bootstrap 95% CI "
                "(`results/hotpot200/camr.sqlite`)", ["Model", "Alone", "With CAMR", "Gain (95% CI)", "s / answer"],
                h["rows"], [3.4, 1.8, 2.2, 5.4, 2.1], size=9.5)
    c.p("With CAMR, a 3B model (54.0%) matched the cloud model closed-book (51.8%) at 5.8 s instead of 18.4 s per "
        "answer, and every gain excluded zero. The cloud model with the same notes reached 66.3%: the 12-point residual "
        "is what a larger reader still buys when both read the same evidence. Gains grew with the reader (+23, +30.5, "
        "+34.5 points), which is the first argument against the smallest model for multi-hop work (section "
        "⟦sec_models⟧).")
    c.figure(REPORT / "residual_gap.png", "Residual gap: the 0.5B model and a 20B model reading the same notes, per task "
             "type (pilot)", 13.0)
    c.p("**Budget (objective v).** For the 0.5B model, 128 tokens of memory was best for single facts (76.7%, against "
        "66.7% at 512 and 1,024): more notes distracted it. Multi-hop peaked at 512 tokens. Arithmetic never benefited "
        "from memory at any budget, and worked examples **lowered** the 0.5B model's GSM8K score from 33.3% to 16.7%.")


def res_learning(c: Chapter) -> None:
    c.h3("Learning Without Changing the Weights", key="sec_learning")
    c.p("The proposal argued that external memory is a better way for a small model to gain knowledge than retraining. "
        "Four experiments tested it: looking things up, learning formulas from corrections, fine-tuning on the same "
        "material, and storing knowledge as weights beside the model.")
    c.p("**Looking things up.** Starting from an empty memory and looking up what it did not know, the 0.5B model "
        "answered 43.5% of 200 new questions, against 10.0% for itself closed-book, 19.0% for a 3B model and 20.5% for "
        "a 20B model whose process needed 13.2 GB of RAM against 0.7 GB. Asked again offline in other words, it kept "
        "41.5% (90.8% of what it had answered right). The lookup sets the ceiling: the answer was in the fetched text "
        "for 52% of questions, and when it was, the 0.5B model was right 76% of the time.")
    if (REPORT / "learning_curve.png").exists():
        c.figure(REPORT / "learning_curve.png", "The learning stream: running accuracy of the frozen 0.5B model with "
                 "eager learning against the closed-book models", 14.0)
    mt = J("results/math/run_qwen2.5_0.5b_calc.json")
    c.p("**Learning formulas from corrections.** Ten formula families, four of them invented so no model could know "
        "them, were taught by correction only: one training problem per family per round, corrected only when wrong. "
        "The method was developed on one draw of problems (seed 31) and reported on a fresh draw (seed 47) that shares "
        f"no problem with it, run once after the method was frozen ({c.next_tab()}).")
    c.table("Formulas learned from corrections, fresh draw (`results/math/run_*.json`)",
            ["Model, mode", "Corrections", "Held-out", "Reworded", "Derived", "Invented, held-out", "Seen − unseen"],
            [["Qwen 0.5B, calculator: before", "–", "15.0%", "15.0%", "2.5%", "0.0%", "–"],
             ["**Qwen 0.5B, calculator: after**", "34", "**50.0%**", "**48.3%**", "**22.5%**", "**70.8%**", "+18.3"],
             ["Qwen 0.5B, reasoning itself: after", "40", "35.0%", "20.0%", "7.5%", "33.3%", "+18.3"],
             ["Kimi K3, calculator: before", "–", "60.0%", "60.0%", "60.0%", "0.0%", "–"],
             ["**Kimi K3, calculator: after**", "**4**", "**100%**", "**100%**", "**100%**", "**100%**", "**0.0**"]],
            [4.6, 1.9, 1.7, 1.7, 1.6, 2.4, 1.9], size=9)
    c.p("**Where it was perfect.** Kimi K3 was corrected once on each invented formula and then solved every "
        "held-out, reworded and derived problem, including ones no correction showed: it inverted the Kessler fee "
        "(`0.04*x + 2.50*6 = 30.20`) and nested the zorbit operation. **Where it was not.** The 0.5B model went from "
        "15% to 50% held-out and from 0% to 70.8% on invented formulas, but it cannot apply the arithmetic series or "
        "Heron's formula even with its own corrected solution in front of it (it rewrites `n/2 * (2a + (n-1)d)` as "
        "`n * (a + (n-1)d)`), and on combinations it got worse after correction (50% → 0%) by copying the prompt's "
        f"sample equation. {c.next_fig()} shows held-out accuracy as corrections accumulate: it rises with the first "
        "correction and does not fall as more are stored, the opposite of overfitting.")
    c.figure(REPORT / "math_learning_curve.png", "Held-out accuracy as corrections accumulate (fresh draw), and seen "
             "against unseen problems after learning", 15.5)
    c.p(f"Three checks show that this is learning a rule, not memorising answers. New numbers: every held-out problem "
        f"has numbers no correction contains, and an answer counts only within 0.2% of the truth. No copying: 3 of 61 "
        f"wrong answers equalled a stored training answer. And derived problems need the rule ({c.next_fig()}): a "
        f"worked example alone lifted held-out accuracy to 40% but derived problems not at all (2.5%), while the rule "
        f"alone lifted derived problems to 20%.")
    c.figure(REPORT / "math_ablation.png", "One correction per formula stored as the rule, the worked example, or both "
             "(Qwen 0.5B, calculator)", 13.5)
    c.p(f"{c.next_tab()} shows how answers changed once a correction was stored (fresh draw, Qwen 0.5B, calculator "
        "mode, verbatim from `results/math/examples_qwen2.5_0.5b_calc.json`).")
    c.table("Answers before and after one correction (Qwen 0.5B; what the model wrote, and what the calculator did)",
            ["Problem (answer)", "Before", "After one correction"],
            [["What is 5 zorbit 7? (36)", "`5 * 7 + 5` → 40", "`3*5 - 2*7 + 5*7` → 36"],
             ["Convert 28 glims into poms. (2352)", "`28 * 12` → 336", "`28 * 84` → 2352"],
             ["A Vantor score of 16 and h = 4: what is w? (6)", "`16 = 4*w` → solved: 4",
              "`2*w + 4**2/4 = 16` → solved: 6"],
             ["12 kg with kinetic energy 1536 J: how fast? (16)", "`12 * 9.81 + 1536 / 1536` → 118.7",
              "`1536 = 1/2 * 12 * v**2` → solved: 16"],
             ["Kinetic energy of 8 kg at 23 m/s (2116)", "`0.5 * 8 * 23 ** 2 / 2` → 1058", "`1/2 * 8 * 23**2` → 2116"]],
            [5.6, 4.7, 5.6], size=9)
    c.p("The model also wrote its own result after each expression (*= 10* for 5 zorbit 7, *v = 25.33* for the speed); "
        "those were wrong, and the calculator, which evaluates or solves what the model set up, made them irrelevant. "
        "The invented Vantor and kinetic-energy cases show the solver at work: the model wrote an equation with the "
        "unknown, not the inverted formula, and the engine solved it.")
    c.p(f"**Fine-tuning on the same corrections** ({c.next_fig()}). A LoRA adapter trained on the same problems "
        "beat memory on the trained wording (88.3% against 50.0% held-out) and was well fitted by the usual test "
        "(95% seen, 88% unseen, epoch chosen on validation). But reworded problems fell to 48.3%, derived problems "
        "were pushed through the forward formula (17.5% against memory's 25.0%), and unrelated GSM8K problems fell from "
        "13.3% to **0%**: every answer now came out in the trained *Formula: … ####* form. Memory left GSM8K unchanged "
        "and is undone by deleting a note.")
    c.figure(REPORT / "math_lora_vs_memory.png", "LoRA by epoch against memory on the same corrections", 14.5)
    c.p("**Fine-tuning on facts, and weights beside the model.** On the 237 PopQA documents CAMR stores, LoRA reached "
        "13.3% on held-out questions after a 3.5-hour search, against 71.7% for the same model reading memory, which "
        "stored the documents in 6 s. Training loss fell to 0.16 while accuracy never passed 13.3%: the adapter "
        "learned to reproduce the documents, not to answer questions about them. A token-level memory beside the "
        "frozen model (kNN-LM, 22,554 entries) also reached 13.3%. Knowledge works as text the model reads, not as "
        "numbers inside or beside it.")
    c.figure(REPORT / "token_memory.png", "Held-out accuracy by where the frozen model's knowledge lives", 12.5)
    c.p("**What did not work.** The query adapter trained during sleep never beat the untrained identity on unseen "
        "questions (recall@1 88% → 83% when trained regardless), so sleep keeps it only when held-out recall rises, "
        "which has not happened. The learned index first looked much faster than exact search, but that was measured "
        "with queries that were near copies of stored notes; with real questions over 196,000 notes it needed a quarter of its clusters "
        "to stay within 1.3 points of exact recall, and then was no faster than exact search in RAM.")


def res_bulk(c: Chapter) -> None:
    c.h3("Large Data and the Device's Limits", key="sec_bulk")
    c.table("Large data (`results/bulk/ingest.json`, `scale.json`, `limits.json`)", ["Measure", "Result"],
            [["Ingest, keyword tier", "123,301 paragraphs → 195,735 notes in 335 s (368 paragraphs/s); 187 MB store; "
              "peak process memory 557 MB"],
             ["Search with no vectors yet", "Hybrid recall@10 74.3% (all gold for 49.5% of questions), median 1.3 s "
              "under full CPU load; dense search alone finds nothing"],
             ["Recall as memory grows (all vectors)", "Exact recall@10 83.7% at 8k notes, 77.3% at 100k, 75.4% at 196k; "
              "10.7 ms a question in RAM (287 MB of vectors)"],
             ["Hybrid recall at 196k notes", "84.3% recall@10 against 75.4% for vectors alone; every gold paragraph in "
              "the top 10 for 68.0% against 51.8%; 248 ms median"],
             ["Governor", "Stopped at a 4 MB store cap, a disk reserve of 2,026 MB and a RAM reserve set above what was "
              "free, each before any write past it; resumed each time: 8,656 paragraphs as 14,104 notes, 0 duplicates"],
             ["Embedding speed", "30–47 notes/s on 4 cores; int8 ONNX was 1.8× faster but agreed with fp32 on only 86% "
              "of top-10 results, so it was rejected"]],
            [4.2, 11.7], size=9.5)
    c.p("**Perfect:** the governor stopped at every limit and the store held no duplicate after five interrupted "
        "runs. **Not perfect:** exact recall drops 8.3 points as memory grows 24-fold with distractors; hybrid order "
        "recovers it at 23 times the search time (248 ms against 10.7 ms), which is still small next to a model's "
        "answer time.")
    if (REPORT / "index_scaling.png").exists():
        c.figure(REPORT / "index_scaling.png", "Search time and resident memory as memory grows: exact search against "
                 "the learned index", 13.5)


def res_policy(c: Chapter) -> None:
    c.h3("Routing Between the Device and the Cloud", key="sec_policy")
    c.p("The learned router was tuned by 5-fold cross-validation on 144 training questions and scored once on 72 "
        f"held-out questions ({c.next_tab()}).")
    c.table("Tuned policies on 72 held-out questions (`results/learn/tables/policy_tuning.json`)",
            ["Policy", "Accuracy", "Δ vs always-cloud (95% CI)", "Sent to cloud", "s / answer"],
            [["Always Kimi K3", "63.9%", "–", "100%", "12.6"],
             ["Tuned router", "62.5%", "−1.4 (−13.9 to +11.1)", "17%", "2.3"],
             ["Tuned LinUCB (bandit feedback only)", "55.6%", "−8.3 (−20.8 to +4.2)", "17%", "2.0"],
             ["**Tuned router + grounding cascade**", "**66.7%**", "+2.8 (−8.3 to +13.9)", "**25%**", "**2.9**"],
             ["Oracle (best action in hindsight)", "79.2%", "–", "24%", "2.6"]],
            [5.2, 1.9, 3.8, 2.2, 1.8], size=9.5)
    c.p("The router learned on its own to send every arithmetic question to the cloud and to answer facts locally. "
        "With the cascade it matched the cloud model's accuracy (the difference is within noise) while three questions "
        "in four stayed on the device and the mean time per answer fell from 12.6 s to 2.9 s. Cross-validation chose "
        "the simplest router (task type only); the retrieval features did not help on 144 questions. The oracle's "
        "79.2% shows the features are the bottleneck, mostly on multi-hop questions.")
    c.figure(REPORT / "heldout_policies.png", "Tuned policies on the held-out questions: accuracy with paired 95% "
             "intervals against always-cloud, and the share sent to the cloud", 14.0)


def res_app(c: Chapter) -> None:
    lat = old.app_latency()
    c.h3("CAMR Personal in Use", key="sec_appres")
    c.p("What a user waits for is the first word. With the model loaded in the background at launch, the first word "
        "came after 0.6 s (0.5B), 0.9 s (1.5B) and 1.7 s (3B) on the 4-core CPU; without warm-up the first answer "
        "after a reboot took 2.4 s, 16.8 s and 172.7 s. A 21-fold larger memory (282 to 5,976 notes) added about 10 ms "
        "to the lookup, and a repeated question's lookup takes 2.8 ms from the query cache instead of 189 ms. In live "
        "scenarios the application answered from what the user had taught, recalled a fact after it had left the "
        "context window, asked to be taught when a personal fact was missing, and never sent a personal question to "
        "the web.")
    if lat and (REPORT / "app_latency.png").exists():
        c.figure(REPORT / "app_latency.png", "Time to the first word: cold start, after warm-up, and a typical answer",
                 13.5)


def res_repro(c: Chapter) -> None:
    c.h3("Reproducibility", key="sec_repro")
    c.p("`python scripts/reproduce.py --twice` recomputes the key results from the committed caches and compares every "
        "number with the committed one: the test suite; every development-set lookup; every variant of verified "
        "answering on the development, test and held-out sets (each question's status, claim, correctness and first "
        "answer); bulk ingest with real embeddings and recall on 600 questions (83.67% dense, 95.13% hybrid); the "
        "governor tests; and every formula run and ablation. The last run passed **16 of 16 checks (8 checks, twice "
        "in a row) with no API key in the environment and no network**: the cloud model's answers were replayed by a "
        "stand-in that builds the identical request. The harness also caught a real fault: two answer runs had seen "
        "slightly different web pages because one had fetched what the other missed; freezing the web cache fixed it. "
        "It caught a second fault in this increment: the replays after D-32 failed on the test, held-out and formula "
        "checks because the D-32 fix had cut titles such as *St. Louis Blues* (D-37). After that was fixed, entity "
        "extraction was identical to the pre-D-32 code on all 600 PopQA questions and 440 formula problems, and the "
        "replays were rerun.")


# ================================================================= 5.9 Results (model choice, RAG, automations, cost)


def res_models(c: Chapter) -> None:
    c.h3("Which Model to Run CAMR With", key="sec_models")
    sw = sweep_models()
    kimi = sweep_kimi()
    miss = missing_sizes(sw)
    c.p(f"Two experiments answer this. The {len(sw)}-model sweep measured what memory adds to each model on three "
        "task types; the held-out re-test swapped the reader inside the verified pipeline, keeping everything else "
        f"fixed. The sweep covers {len(sw)} models from {sw[0]['params']:.2f}B to {sw[-1]['params']:.1f}B parameters, "
        f"every one on the same store and the same questions. {c.next_tab()} lists all of them, smallest first, and "
        f"{c.next_tab(2)} sums them up by size class."
        + (f" No {' or '.join(miss) if len(miss) < 3 else ', '.join(miss[:-1]) + ' or ' + miss[-1]} model was in "
           "the sweep; the size classes cover those sizes by their neighbours."
           if miss else ""))
    rows = []
    for r in sw:
        cells = []
        for b in ("popqa", "hotpotqa", "gsm8k"):
            if b not in r:
                cells.append("–")
                continue
            f, t = r[b]
            at_kimi = kimi.get(b) is not None and t >= kimi[b] - 1e-6
            cells.append(f"{100 * f:.1f} → " + (f"**{100 * t:.1f}%**" if at_kimi else f"{100 * t:.1f}%")
                         + (" †" if b in r["failed"] else ""))
        rows.append([f"{r['model']} ({r['params']:.{2 if r['params'] < 1 else 1}f}B, {r['quant']})", *cells,
                     f"{r['tok_s']:.1f}" if r.get("tok_s") else "–", f"{r['secs']:.1f}" if r.get("secs") else "–",
                     r["machine"]])
    rows.append(["*Kimi K3 (cloud), no memory*",
                 *[f"*{100 * kimi[b]:.1f}%*" if kimi.get(b) is not None else "–" for b in ("popqa", "hotpotqa", "gsm8k")],
                 "–", "*7.7*", "cloud"])
    c.table(f"All {len(sw)} models of the size sweep: accuracy alone → with CAMR (bold: at or above Kimi K3), decode "
            "speed with CAMR and seconds per answer with CAMR (`results/pilot/tables/model_sweep.json`; F10, F10b)",
            ["Model (parameters, quantisation)", "Long-tail facts (30 q)", "Multi-hop (30 q)", "Arithmetic (12 q)",
             "Decode tok/s", "s / answer", "Machine"], rows, [4.0, 2.3, 2.3, 2.3, 1.3, 1.3, 1.6], size=8)
    fast = ", ".join(sorted({r["machine"] for r in sw} - {"C"}))
    c.p(f"Machine is the 4-core cloud machine the model ran on ({fast}: Xeon at 2.1 GHz; C: Xeon at 2.8 GHz). "
        "Accuracy is comparable across machines, speed only within one. One question is 3.3 points on the facts and "
        "multi-hop sets and 8.3 points on arithmetic, so a gap of one or two questions between two models is noise. "
        "† One to three questions of that run failed with a runtime error; accuracy is over the answered ones (F10).")
    c.table("The sweep by size class: mean accuracy alone → with CAMR, models at Kimi K3's level, and time per answer",
            ["Size class", "Models", "Facts", "Multi-hop", "At Kimi on multi-hop", "Arithmetic helped / hurt",
             "s / answer (median, 2.1 GHz)"], size_bands(sw, kimi), [1.9, 1.5, 2.4, 2.4, 2.1, 2.3, 2.0], size=8)
    c.figure(REPORT / "model_sizes.png", "Every model of the sweep by name and size: accuracy alone (grey) and with "
             "CAMR (blue helps, orange hurts) on three task types, and time per answer", 16.0)
    c.p(SIZES_TEXT(sw, kimi))
    rows = []
    sp = speed()
    for name, j, v in heldout_readers():
        key = name.split(" ")[0]
        s = sp.get(key, {})
        rows.append([name, p1(j["verified"]["correct"]), p1(j["verified"]["hallucinated"]),
                     p1(j["verified"]["other_meaning"]), p1(j["verified"]["unconfirmed"]),
                     f"{s['s_per_answer_median']:.2f}" if s.get("s_per_answer_median") else "–",
                     f"{s['rss_mb'] / 1024:.1f}" if s.get("rss_mb") else "–"])
    if rows:
        c.table("Held-out set, verified pipeline with the reader swapped (judged); speed and memory measured alone on "
                "the 4-core CPU (`results/models/speed.json`)",
                ["Reader", "Correct", "Wrong, stated", "Other meaning", "Not confirmed", "s / answer", "RAM, GB"],
                rows, [3.4, 1.8, 2.1, 2.1, 2.2, 1.9, 1.7], size=9)
    if (REPORT / "model_choice.png").exists():
        c.figure(REPORT / "model_choice.png", "The verified pipeline with five readers: accuracy and wrong statements, "
                 "speed and memory", 15.5)
    c.p(MODELS_TEXT(sp))


def res_rag(c: Chapter) -> None:
    runs = rag_runs()
    c.h3("CAMR Against Modern RAG Pipelines", key="sec_ragresult")
    c.p("All nine pipelines of section ⟦sec_rag_def⟧ answered the 200 held-out questions from the same store of "
        "10,443 notes. Correct and wrong are judged as in section ⟦sec_verified⟧; *declined* means the pipeline "
        "said it did not know (or, for CAMR and the check, did not state an answer). Gold in context is whether the "
        "reference answer appears anywhere in what the reader was given.")
    for tag, name in (("qwen2_5_0_5b", "Qwen 2.5 0.5B"), ("llama3_2_3b", "Llama 3.2 3B"), ("kimi-k3", "Kimi K3")):
        rows = []
        for pipe in PIPE_ORDER:
            d = runs.get((pipe, tag))
            if not d:
                continue
            s = rag_summary(d)
            rows.append([PIPE_NAMES[pipe], p1(s["correct_exact"]), p1(s["wrong_exact"]),
                         p1(s["other_meaning"]) if s["other_meaning"] else "–", p1(s["declined"]),
                         p1(s["gold_in_context"]), f"{s['prompt_tokens']:.0f}", f"{s['calls']:.2f}",
                         f"{s['model_s']:.2f}", f"{s['cpu_ms']:.0f}"])
        if rows:
            c.table(f"RAG pipelines and CAMR, 200 held-out questions, reader {name} "
                    f"(`results/ragbench/run_*_{tag}.json`)",
                    ["Pipeline", "Correct", "Wrong, stated", "Other meaning (named)", "Declined", "Gold in context",
                     "Prompt tokens", "Model calls", "Model s", "Retrieval CPU ms"], rows,
                    [3.4, 1.4, 1.5, 1.6, 1.4, 1.5, 1.4, 1.3, 1.2, 1.4], size=8)
    for name, cap in (("rag_outcomes.png", "Outcomes of every pipeline per reader: correct, wrong but stated, "
                       "declined"),
                      ("rag_tradeoff.png", "Accuracy against wrong statements, and accuracy against model time, for "
                       "every pipeline and reader"),
                      ("rag_errors.png", "Where the wrong answers come from: the answer was in what the reader got "
                       "(misread) or it was not (answered anyway)"),
                      ("rag_cost.png", "What each pipeline reads and what reading costs (0.5B reader): answer in "
                       "context, prompt tokens, retrieval CPU time")):
        if (REPORT / name).exists():
            c.figure(REPORT / name, cap, 15.8)
    c.p(RAG_TEXT(runs))
    ex = rag_examples(runs)
    if ex:
        c.table("The same held-out questions through three pipelines (reader in brackets; verbatim, shortened)",
                ["Question (gold)", "Hybrid + reranker", "Corrective RAG", "CAMR"], ex, [4.0, 4.0, 4.0, 3.9],
                size=8)


def rag_examples(runs: dict) -> list[list[str]]:
    """Three real questions: one where RAG stated a wrong answer and CAMR declined, one where CAMR was right and RAG
    wrong, one where RAG was right and CAMR declined (its cost)."""
    tag = "kimi-k3" if ("camr", "kimi-k3") in runs else "qwen2_5_0_5b"
    need = [("rerank", tag), ("crag", tag), ("camr", tag)]
    if not all(k in runs for k in need):
        return []
    rows = {k: {r["i"]: r for r in runs[k]["per_question"]} for k in need}
    judged = {k: runs[k].get("judged", {}) for k in need}
    ok = lambda k, r: judged[k].get(str(r["i"]), r["exact"])  # noqa: E731
    gold = {x["i"]: x for x in json.loads((RES / "verified/heldout.json").read_text())["items"]}
    picks, out = [], []
    for want in (("wrong", "declined"), ("wrong", "right"), ("right", "declined")):
        for i, r in rows[need[0]].items():
            c = rows[need[2]].get(i)
            if not c or i in picks:
                continue
            rs = "right" if r["stated"] and ok(need[0], r) else "wrong" if r["stated"] else "declined"
            cs = "right" if c["stated"] and ok(need[2], c) else "wrong" if c["stated"] else "declined"
            if (rs, cs) == want:
                picks.append(i)
                break
    short = lambda s: (s or "").replace("\n", " ")[:110]  # noqa: E731
    for i in picks:
        g = gold[i]
        cells = [f"{g['question']} (*{g['answers'][0]}*)"]
        for k in need:
            r = rows[k][i]
            mark = "✓" if r["stated"] and ok(k, r) else "✗" if r["stated"] else "declined"
            cells.append(f"{short(r['answer'])} [{mark}]")
        out.append(cells)
    return out


def res_agentic(c: Chapter) -> None:
    c.h3("Automations and Agents: Where an Engine Is Needed", key="sec_agentic")
    c.p("The three n8n scenarios (section ⟦sec_gateway⟧) test what benchmarks cannot: knowledge that is private, "
        "that changes, that arrives after a model was trained, and an automation that acts on its answers.")
    desk = loaded("helio", DESK_SYSTEMS)
    if desk:
        rows = []
        for tag, name, d in desk:
            s = d["summary"]
            ms = [r.get("model_ms") or 0 for r in d["per_ticket"]]
            rows.append([name, p1(s["auto_resolved_correct"]), p1(s["wrong_replies"]), p1(s["escalated"]),
                         p1(s["answerable_correct"]), p1(s["unanswerable_escalated"]),
                         f"{statistics.mean(ms) / 1000:.1f}", usd(s.get("cost_usd_per_1000_tickets"))
                         if "kimi" in tag else "$0 (local)"])
        c.table("n8n support desk, 60 tickets over 8 days (`results/agentic/helio_*.json`)",
                ["System", "Correct reply", "Wrong reply", "Escalated", "Answerable resolved", "Unknowable escalated",
                 "Model s / ticket", "Cloud cost per 1,000"], rows, [3.9, 1.5, 1.4, 1.5, 1.8, 1.8, 1.5, 2.0], size=8.5)
        if (REPORT / "agentic_desk.png").exists():
            c.figure(REPORT / "agentic_desk.png", "What reached the customer, per system, and the cloud cost per 1,000 "
                     "tickets", 15.8)
    c.p(DESK_TEXT(desk))
    ex = desk_examples(desk)
    if ex:
        c.table("One learned fact through the desk: *Which cable connects the Lumen LB-13 battery?* (Kimi K3 as the "
                "reader; verbatim, shortened)", ["System", "First time (day 3)", "What happened next", "Later asked again"],
                ex, [3.0, 4.6, 3.6, 4.7], size=8)
    agents = loaded("agent", AGENT_CONFIGS)
    if agents:
        rows = []
        for tag, name, d in agents:
            s = d["summary"]
            rows.append([name, p1(s["success"]), p1(s["hallucinated_actions"]), p1(s["escalated"]),
                         f"{s['steps_per_task']:.1f}", usd(s.get("cost_usd_per_1000_tasks")) if "kimi" in tag
                         else "$0 (local)"])
        c.table("Operations agent, 20 tasks (`results/agentic/agent_*.json`)",
                ["Agent", "Task succeeded", "Hallucinated action", "Escalated", "Tool calls / task",
                 "Cloud cost per 1,000"], rows, [4.4, 2.2, 2.4, 1.9, 2.1, 2.9], size=9)
        if (REPORT / "agentic_agent.png").exists():
            c.figure(REPORT / "agentic_agent.png", "Operations agent: tasks completed correctly and hallucinated "
                     "actions", 14.5)
        if (REPORT / "agentic_matrix.png").exists():
            c.figure(REPORT / "agentic_matrix.png", "Every agent task in every configuration: succeeded, handed to a "
                     "person, failed, or a hallucinated action", 15.8)
    c.p(AGENT_TEXT(agents))
    tr = agent_trace(agents)
    if tr:
        c.p("One task end to end, as the agent ran it (Kimi K3 with CAMR's memory, verbatim):")
        c.code(tr)
    fresh = loaded("fresh", FRESH_SYSTEMS)
    if fresh:
        rows = []
        for tag, name, d in fresh:
            s = d["summary"]
            rows.append([name, p1(s["correct"]), p1(s["wrong_stated"]), p1(s["declined"]),
                         usd(s.get("cost_usd_per_1000_questions")) if "kimi" in tag else "$0 (local)"])
        c.table("Current events: 30 days of Wikipedia fetched live by n8n, 50 questions (`results/agentic/fresh_*.json`)",
                ["System", "Correct", "Wrong, stated", "Declined", "Cloud cost per 1,000"], rows,
                [5.4, 2.2, 2.6, 2.2, 3.5], size=9)
        if (REPORT / "agentic_fresh.png").exists():
            c.figure(REPORT / "agentic_fresh.png", "Questions about news after the models' training data: what each "
                     "system answered, and the cloud cost", 15.5)
    c.p(FRESH_TEXT(fresh))


def desk_examples(desk) -> list[list[str]]:
    want = {"stuff_kimi-k3": "Kimi K3 + context stuffing", "rag_kimi-k3": "Kimi K3 + RAG",
            "camr_kimi-k3": "Kimi K3 + CAMR"}
    out = []
    for tag, _, d in desk:
        if tag not in want:
            continue
        rows = [r for r in d["per_ticket"] if "cable" in r["question"].lower()]
        rows.sort(key=lambda r: r["ticket"])
        if not rows:
            continue
        first, later = rows[0], rows[1:]
        nxt = ("Escalated: a person answered *CB-3*, and the answer was taught" if first["outcome"] == "escalated"
               else "Sent to the customer; nobody was asked, so nothing was taught")
        lat = "; ".join(f"{r['answer'][:70]} [{'✓' if r['outcome'] == 'correct' else '✗' if r['outcome'] == 'wrong' else 'escalated'}]"
                        for r in later)
        out.append([want[tag], f"{first['answer'][:90]} [{first['outcome']}]", nxt, lat])
    return out


def agent_trace(agents) -> str:
    for tag, _, d in agents:
        if tag == "kimi-k3__camr":
            for t in d["per_task"]:
                if t["task"] == "A12":
                    return "\n".join(line[:118] for line in t.get("transcript", "").strip().splitlines()[:14])
    return ""


def res_cost(c: Chapter) -> None:
    d = costs()
    c.h3("What It Costs: Device Time and Cloud Dollars", key="sec_cost")
    c.p("Every local answer cost no money beyond the machine; every cloud answer was metered (Equation ⟦eq_cost_n⟧). "
        f"{c.next_tab()} gives the whole project's cloud spend, from the logged token counts.")
    if d:
        rows = [[r["what"], f"{r['calls']:,}", f"{r['input_tokens']:,}", f"{r['output_tokens']:,}", usd(r["usd"])]
                for r in d["rows"]]
        tot = d["total"]
        rows.append(["**Total**", f"**{tot['calls']:,}**", f"**{tot['input_tokens']:,}**",
                     f"**{tot['output_tokens']:,}**", f"**{usd(tot['usd'])}**"])
        c.table("Cloud spend by experiment at list price (`results/costs/kimi_costs.json`)",
                ["Experiment", "Calls", "Input tokens", "Output tokens", "USD"], rows, [7.4, 1.6, 2.3, 2.3, 2.3],
                size=8.5)
        if (REPORT / "kimi_costs.png").exists():
            c.figure(REPORT / "kimi_costs.png", "Kimi K3 spend across the project", 14.5)
    if (REPORT / "cost_compare.png").exists():
        c.figure(REPORT / "cost_compare.png", "What the same cloud model costs per 1,000 answers with each kind of "
                 "memory, in every scenario measured (log scale)", 15.8)
    c.p(COST_TEXT(d))


def res_flaws(c: Chapter) -> None:
    c.h3("What Failed, and Why", key="sec_flaws")
    c.p("The flaws below were found by the measurements in this chapter. Fixed ones stay listed because they show "
        "how the system failed before the fix; open ones are the boundaries of what the evidence supports.")
    rows = [
        ["Memory does not close reasoning gaps", "GSM8K residual 83.3 points between 0.5B and 20B reading the same "
         "notes; worked examples lowered the 0.5B model from 33.3% to 16.7%", "Arithmetic questions need a stronger "
         "model or a calculator", "Open: routed to the cloud by the learned policy; calculator for formulas"],
        ["A small reader wastes good evidence", "76% of the 0.5B model's multi-hop misses had the answer in context; "
         "gains grow with the reader (+23 to +34.5 points)", "Multi-hop answers need ≥ 3B", "Open: choose the reader "
         "by task (section ⟦sec_models⟧)"],
        ["The check guarantees support, not truth", "All 6 wrong stated held-out answers quote a stored line about "
         "another meaning or a source that disagrees with the benchmark", "A wrong page in memory gives a wrong, "
         "sourced answer", "Open: the source is shown with every answer"],
        ["Checks too strict for some correct answers", "*al-Ghazali* withheld (kind check expects a capital); 14 of "
         "45 answerable desk tickets withheld before D-33", "Lower coverage", "D-33 fixed; the kind check is open"],
        ["CAMR's recall has no reranker", "Answer in what the reader got: 64% with CAMR against 72% with reranked "
         "RAG on the same corpus (section ⟦sec_ragresult⟧)", "Lower coverage than the best RAG pipeline",
         "Open: add the cross-encoder to CAMR's recall"],
        ["The check trusts a claim that only names the subject or another of its attributes", "0.5B desk replies "
         "*Lumen LB-13* for *Which cable …?* and *10-year firmware* for the latest firmware were stated; no known "
         "relation covers *cable* or *firmware*", "4 wrong desk replies with the 0.5B reader (none with 3B or Kimi K3)",
         "Open: require a claim word beyond the subject's own name"],
        ["Small readers hedge under the standard RAG prompt", "Llama 3B: *I don't know where RMA numbers start, but "
         "… they start with HLX-*", "14 answerable desk tickets escalated by the 3B + RAG system", "Reported; "
         "prompt-specific"],
        ["The lookup sets the ceiling", "Answer in the fetched text for 52% (stream) to 72–73% (held-out, "
         "development) of questions", "Up to a quarter of questions cannot be answered from memory", "Open"],
        ["Retrieval share of answer time (NFR-02)", "56% for the 0.5B model in the pilot profile; about 20% after "
         "core partitioning", "Target ≤ 10% met only for models whose generation takes ≥ 450 ms", "Open for 0.5B"],
        ["Recency and importance scoring", "−1.2 and −5.4 points of full-support recall", "Proposal's Eq. 4.1 "
         "harmful on independent questions", "Removed (D-06); untested on conversations"],
        ["Learned retrieval components", "Query adapter never beat the identity on unseen questions; the learned "
         "index was no faster than exact search at equal recall", "No benefit from training retrieval here",
         "Kept off; accepted only if held-out recall rises"],
        ["Some formulas beyond the 0.5B model", "Arithmetic series and Heron's formula never applied; combinations "
         "50% → 0% after correction (copied the prompt's sample)", "Small models need the rule and the arithmetic "
         "done for them", "Open; the grounding check flags most copied answers"],
        ["Fine-tuning wins on the trained wording", "LoRA 88.3% against memory 50.0% held-out on formulas", "Memory "
         "is weaker on exactly the trained format", "Reported; LoRA lost GSM8K (13.3% → 0%) and derived problems"],
        ["Entity gate is rule-based", "D-15, D-31, D-32, D-37, D-40: possessives, instructions, terse phrasing, abbreviations and requests; "
         "HotpotQA −1.2 points", "Wrongly withheld notes", "Fixed cases; a learned recogniser is future work"],
        ["Run-to-run variation of the 0.5B runtime", "Answers differed on 10 of 30 questions between identical runs "
         "(wrong → wrong)", "Small-model floors vary by a few points", "Open (runtime); engine prompts are identical"],
        ["Evaluation defects in the automations", "D-34: the news workflow used the support persona; D-35: a decline "
         "phrased *I can't identify* was sent as a reply; D-36: Wikimedia refused repeated live fetches; D-38: a curly "
         "apostrophe hid declines; D-39: a loop asked each news question 30 times",
         "Baselines would have been scored unfairly; a workflow stopped", "Fixed and every affected run repeated "
         "before reporting"],
    ]
    c.table("Flaw catalogue", ["Flaw", "Evidence", "Consequence", "Status"], rows, [3.3, 5.6, 3.6, 3.4], size=8.5)


def res_limits(c: Chapter) -> None:
    c.h3("Limitations, Delimitations and Threats to Validity", key="sec_limits")
    c.p("**Limitations** are weaknesses of the evidence; each is stated with its likely effect.")
    c.items([
        "**Sample sizes.** Headline results use 200 questions (one question = 0.5 points), the desk 60 tickets (1.7 "
        "points), the agent 20 tasks (5 points) and the pilot 30 questions (3.3 points). Differences of a few points "
        "between systems on the desk or the agent are not significant.",
        "**One cloud sample.** Kimi K3 accepts only temperature 1, so each cloud answer is one sample; repeated runs "
        "would move its scores by a few points.",
        "**The judge is a cloud model.** Kimi K3 judged answers that exact matching marked wrong. It also appears as a "
        "system under test, so it could favour its own phrasing; the exact-match scores, which give the same ordering, "
        "are kept beside every judged score.",
        "**Data written for this study.** The Helio company, its tickets and agent tasks were written by the researcher, "
        "and the news questions by Kimi K3 from single items. They test the mechanism (private, changing knowledge; "
        "events after training), not the difficulty of a real company's support queue.",
        "**Timings.** Machines were 4-core cloud containers, not a physical laptop, and some runs shared the CPU with "
        "others; timings are reported only from runs that had the CPU to themselves, and cached answers keep their "
        "original timing.",
        "**Costs** are computed at Moonshot's list price without cached-input discounts, so they are upper bounds; the "
        "local runs' electricity and hardware were not costed.",
        "**No user study.** The application was tested for behaviour and accessibility, not for usefulness to people.",
    ])
    c.p("**Delimitations** are boundaries chosen for the study: CPU-only consumer devices (no GPU, no phones); "
        "English questions; frozen, quantised open models served by Ollama, with fine-tuning used only as a baseline; "
        "text only; self-hosted n8n run headless, with no workflow exposed to the internet; no real customer or "
        "personal data; a research prototype, not a production service.")
    c.p("**Threats to validity.** *Internal:* answer caching makes replays exact, but a cached cloud answer is the "
        "answer of the day it was asked; methods were chosen on development data only, and the held-out set was "
        "answered once. *Construct:* *hallucination* here means a wrong answer stated as fact, judged against the "
        "benchmark's gold answers, which are themselves sometimes disputable (section ⟦sec_verified⟧). *External:* "
        "PopQA's templated questions and an invented company are cleaner than real traffic. *Conclusion:* intervals "
        "are reported where they matter, and several differences in this chapter lie within them.")


def scorecard(c: Chapter) -> None:
    """The results at a glance: each claim, its evidence, and whether it was met."""
    jv = ((J("results/verified/judged_heldout.json") or {}).get("files", {}).get("answers_heldout_sa.json", {})
          .get("facts+compress+reader", {}).get("verified", {}))
    desk = {t: d["summary"] for t, _, d in loaded("helio", DESK_SYSTEMS)}
    agents = {t: d["summary"] for t, _, d in loaded("agent", AGENT_CONFIGS)}
    rows = [
        ["Long-tail facts: a small model with memory matches the cloud model", "19-model sweep; PopQA",
         "18 of 19 models reach or beat Kimi K3 closed-book (66.7%) with memory", "**Met**"],
        ["Multi-hop: memory closes part of the gap", "HotpotQA, n = 200", "3B + CAMR 54.0% vs Kimi K3 51.8%; "
         "0.5B gains +23 points but stays far below", "**Met for ≥ 3B; partial for 0.5B**"],
        ["Second hop found without a graph", "2Wiki retrieval, n = 500", "Full-support recall 35.8% → 78.4% at the "
         "same budget", "**Met**"],
        ["Reasoning gaps closed by memory", "GSM8K", "No: residual 83.3 points; worked examples hurt the 0.5B model",
         "**Not met**"],
        ["Few wrong facts stated", "Held-out PopQA, n = 200, judged", f"{p1(jv.get('hallucinated'))} wrong stated "
         f"(Kimi K3 alone 31.5%), {p1(jv.get('correct'))} correct (Kimi 67.5%)", "**Met, at a cost in coverage**"],
    ]
    if "camr_kimi-k3" in desk:
        s = desk["camr_kimi-k3"]
        rows.append(["Automations: no wrong reply to a customer", "n8n desk, 60 tickets, Kimi K3 + CAMR",
                     f"{p1(s['answerable_correct'])} of answerable tickets resolved, {p1(s['wrong_replies'])} wrong "
                     f"replies, {p1(s['unanswerable_escalated'])} of unknowable tickets escalated",
                     "**Met (after D-33)**" if s["wrong_replies"] == 0 else "**Partial**"])
    if "kimi-k3__camr" in agents:
        s = agents["kimi-k3__camr"]
        rows.append(["Agents act only on company facts", "20 operations tasks, Kimi K3 + CAMR",
                     f"{p1(s['success'])} success, {p1(s['hallucinated_actions'])} hallucinated actions",
                     "**Met**" if s["success"] == 1 and s["hallucinated_actions"] == 0 else "**Partial**"])
    rows += [
        ["Learning without training: formulas", "Fresh draw, invented formulas", "Kimi K3 100% after 4 corrections; "
         "0.5B 0% → 70.8% on invented formulas, 50% overall", "**Met for Kimi; partial for 0.5B**"],
        ["Memory beats fine-tuning", "Same documents / same corrections", "Facts: 71.7% vs 13.3%. Formulas: LoRA "
         "higher on trained wording (88.3% vs 50.0%), lower on derived problems and lost GSM8K",
         "**Met for facts; mixed for formulas**"],
        ["Large data within device limits", "123,301 paragraphs; governor", "Searchable in 335 s; stops at every "
         "limit; 0 duplicates", "**Met**"],
        ["Retrieval ≤ 10% of answer time (NFR-02)", "Device profile", "56% for 0.5B (contention); met only for "
         "≥ 1.5B models", "**Not met for 0.5B**"],
        ["Reproducible on demand", "`reproduce.py --twice`", "16/16 checks, no key, no network", "**Met**"],
    ]
    c.table("Scorecard: each claim, its evidence and whether it was met", ["Claim", "Evidence", "Result", "Verdict"],
            rows, [4.4, 3.2, 5.3, 3.0], size=8.5, key="tab_scorecard")


# ----------------------------------------------------------------- narrative written from the results


def SIZES_TEXT(sw: list[dict], kimi: dict) -> str:  # noqa: N802
    """What the size classes show, every number from the sweep."""
    bands = _band(sw)

    def mean(ms, b, i):
        v = [r[b][i] for r in ms if b in r]
        return 100 * statistics.mean(v) if v else 0.0

    def med_s(ms):  # one CPU class only (machines B, D, E at 2.1 GHz): speed is comparable within a class
        v = [r["secs"] for r in ms if r.get("secs") and r["machine"] != "C"]
        return statistics.median(v) if v else 0.0

    def of(k, n):
        return f"all {n}" if k == n else f"{k} of {n}"

    facts = [mean(ms, "popqa", 1) for _, ms in bands]
    hop = [mean(ms, "hotpotqa", 1) for _, ms in bands]
    secs = [med_s(ms) for _, ms in bands]
    small = bands[0][1]
    hurt_small = sum(r["gsm8k"][1] < r["gsm8k"][0] - 1e-6 for r in small if "gsm8k" in r)
    above = [r for r in sw if r["params"] >= 5 and r.get("secs") and r["machine"] != "C"]
    slower = sum(r["secs"] > 7.7 for r in above)
    k_f, k_h = 100 * kimi.get("popqa", 0), 100 * kimi.get("hotpotqa", 0)
    reach_f = sum(r["popqa"][1] >= kimi.get("popqa", 9) - 1e-6 for r in sw if "popqa" in r)
    return (
        f"**Facts stop improving at about 1.5B; reading across documents keeps improving; time grows fastest.** "
        f"Memory lifts every model on long-tail facts, from a mean of {mean(small, 'popqa', 0):.0f}% alone to "
        f"{facts[0]:.0f}% for the smallest class, and from 1.5B upwards every class averages "
        f"{min(facts[1:]):.0f}–{max(facts[1:]):.0f}% with CAMR: {of(reach_f, len(sw))} models reach or beat Kimi K3's "
        f"{k_f:.1f}%, and a 14B model with memory is no better than a 1.5B one. Multi-hop reading is different: the "
        f"class means with CAMR climb {' → '.join(f'{h:.0f}' for h in hop)}%, and only "
        f"{sum(r['hotpotqa'][1] >= kimi.get('hotpotqa', 9) - 1e-6 for r in sw if 'hotpotqa' in r)} of {len(sw)} "
        f"models reach Kimi K3's {k_h:.1f}% (none below 3B). Time per answer climbs faster than either: on the "
        f"2.1 GHz machines the class medians are {' → '.join(f'{s:.1f}' for s in secs)} s, and {of(slower, len(above))} "
        f"models of 6B and above measured there took longer than Kimi K3's 7.7 s. **Where small models fall short:** "
        f"worked examples lowered arithmetic for {of(hurt_small, len(small))} models of about 1B, and the 0.5B model "
        "gains least on multi-hop. **Where large models fall short:** speed. Their extra parameters paid off on "
        "multi-hop reading and arithmetic, not on facts. ")


def MODELS_TEXT(sp: dict) -> str:  # noqa: N802
    rows = heldout_readers()
    corr = [j["verified"]["correct"] for _, j, _ in rows]
    hall = [j["verified"]["hallucinated"] for _, j, _ in rows]
    text = (f"**What the reader swap shows.** Every reader from 0.5B to 7B landed within "
            f"{100 * (max(corr) - min(corr)):.1f} points on correct answers ({p1(min(corr))}–{p1(max(corr))}) and "
            f"within {100 * (max(hall) - min(hall)):.1f} points on wrong stated ones ({p1(min(hall))}–{p1(max(hall))}). "
            "The reason is structural: 140 of the 200 questions were answered from a fact line with no model call, "
            "whatever the reader. Of the other 60 (with the 0.5B reader), 19 were answered correctly, and 36 of the remaining "
            "41 had no answer anywhere in what memory read, which no reader can fix. In this pipeline a bigger model buys nothing but time and memory. ")
    s05, s3, s7 = sp.get("qwen2.5:0.5b", {}), sp.get("llama3.2:3b", {}), sp.get("qwen2.5:7b", {})
    if s05.get("s_per_answer_median") and s7.get("s_per_answer_median"):
        text += (f"Measured alone on the 4-core CPU, a short answer took {s05['s_per_answer_median']:.2f} s with the "
                 f"0.5B model, {s3.get('s_per_answer_median', 0):.2f} s with the 3B model and "
                 f"{s7['s_per_answer_median']:.2f} s with the 7B model, whose runtime held "
                 f"{s7.get('rss_mb', 0) / 1024:.1f} GB of RAM against {s05.get('rss_mb', 0) / 1024:.1f} GB. ")
    text += ("**The choice therefore depends on the task.** For verified fact answering, the smallest model is enough "
             "(0.5B or 1.5B). For multi-hop reading, 3B is the smallest model that matched the cloud model, and the "
             "gain from memory grows with the reader (section ⟦sec_gap⟧). For arithmetic, phi4-mini (3.8B) with "
             "worked examples reached 91.7%, but memory helps arithmetic only in some model families, so it is a "
             "per-model choice. Above 7B, every model with memory answered more slowly than the cloud model on this "
             "hardware. The recommended configuration for a 16 GB CPU-only device is a **1.5B model for facts and a "
             "3B model when questions need reading across documents**, with the cloud model reserved for what memory "
             "cannot close.")
    return text


def RAG_TEXT(runs: dict) -> str:  # noqa: N802
    def s(pipe, tag):
        d = runs.get((pipe, tag))
        return rag_summary(d) if d else None
    out = []
    for tag, name in (("kimi-k3", "Kimi K3"), ("qwen2_5_0_5b", "the 0.5B model"), ("llama3_2_3b", "the 3B model")):
        rag = {p: s(p, tag) for p in PIPE_ORDER if p != "camr" and s(p, tag)}
        cm = s("camr", tag)
        if not rag:
            continue
        best = max(rag, key=lambda p: rag[p]["correct_exact"])
        b = rag[best]
        text = (f"**With {name} as the reader**, the most accurate RAG pipeline was {PIPE_NAMES[best].lower()} "
                f"({p1(b['correct_exact'])} correct), but it also stated a wrong answer to {p1(b['wrong_exact'])} of "
                "questions")
        if cm:
            text += (f"; CAMR was correct on {p1(cm['correct_exact'])}, stated a wrong answer to "
                     f"{p1(cm['wrong_exact'])}, gave an answer about a named other meaning for "
                     f"{p1(cm['other_meaning'])}, and declined {p1(cm['declined'])}, with "
                     f"{cm['calls']:.2f} model calls and {cm['prompt_tokens']:.0f} prompt tokens per question against "
                     f"{b['calls']:.2f} and {b['prompt_tokens']:.0f}")
        out.append(text + ".")
    ck, rr = s("check", "kimi-k3"), s("rerank", "kimi-k3")
    if ck and rr:
        d = runs[("check", "kimi-k3")]
        jd = d.get("judged", {})
        dec = [r for r in d["per_question"] if not r["stated"]]
        dec_ok = sum(bool(jd.get(str(r["i"]), r["exact"])) for r in dec)
        out.append(f"**CAMR's check bolted onto RAG** cut Kimi K3's wrong answers from {p1(rr['wrong_exact'])} to "
                   f"{p1(ck['wrong_exact'])} but declined {p1(ck['declined'])}, and {dec_ok} of those {len(dec)} "
                   "declined answers were correct: under the "
                   "standard RAG prompt the model answers in full sentences (*… is al-Ghazali, a Muslim polymath and "
                   "student of the Asharite school …*), and the check requires every word of the claim in one stored "
                   "sentence. The check is built for the short answers CAMR's own prompt asks for; it is not a filter "
                   "for any answer.")
    out.append("**What the comparison means.** Modern RAG answers more questions, and with a strong reader it answers "
               "more of them correctly. It does so by stating whatever its reader concludes, so roughly one answer in "
               "five from the cloud model, and one in two from a small model, is wrong but presented as fact. CAMR "
               "answers fewer questions and states very few wrong ones, because it reads labelled facts directly and "
               "states nothing a stored sentence does not support; its remaining errors are answers about another "
               "meaning that it names, which a reader can see. Where a wrong answer costs more than an unanswered "
               "one (a customer reply, an invoice, an agent's action), that trade is the point; where coverage "
               "matters most, a reranked RAG pipeline is the better choice. Part of CAMR's lower coverage is "
               "retrieval, not caution: the answer was in what the reader received for "
               f"{p1(rr['gold_in_context']) if rr else '–'} of questions with reranked RAG and "
               f"{p1(s('camr', 'kimi-k3')['gold_in_context']) if s('camr', 'kimi-k3') else '–'} with CAMR, the same "
               "as plain dense retrieval; CAMR has no reranker, and adding one is an obvious next step. Corrective "
               "RAG's web fallback added nothing on this corpus, because the corpus already held the pages the "
               "lookups would fetch.")
    return " ".join(out)


def DESK_TEXT(desk) -> str:  # noqa: N802
    s = {t: d["summary"] for t, _, d in desk}
    pt = {t: d["summary"]["prompt_tokens"] / max(1, d["summary"]["tickets"]) for t, _, d in desk}
    if not {"camr_kimi-k3", "rag_kimi-k3", "stuff_kimi-k3", "llm_kimi-k3"} <= set(s):
        return ""
    cm, rg, st, lm = s["camr_kimi-k3"], s["rag_kimi-k3"], s["stuff_kimi-k3"], s["llm_kimi-k3"]
    text = ("**What the desk shows.** A model alone is useless here and dangerous when small. Kimi K3 knew nothing "
            f"about Helio and escalated {p1(lm['escalated'])} of tickets, but it still told two customers to clean their "
            "panels *once or twice a year*, a plausible answer that is not the company's (every 6 months). The 0.5B "
            f"model alone answered almost everything and sent wrong replies to "
            f"{p1(s.get('llm_qwen2_5_0_5b', {}).get('wrong_replies'))} of tickets"
            + (f"; the 3B model alone was no better ({p1(s['llm_llama3_2_3b']['wrong_replies'])} of tickets, fluent and "
               "invented: *the error code E21 on your Volta-2 indicates a fault in the solar panel's voltage "
               "regulator*)" if "llm_llama3_2_3b" in s else "")
            + ". Given the company's documents, all three Kimi systems answered the knowledge-base "
            f"and policy tickets correctly. They differ in what they did when the answer was **not** known: CAMR sent "
            f"{p1(cm['wrong_replies'])} wrong replies, context stuffing {p1(st['wrong_replies'])} and RAG "
            f"{p1(rg['wrong_replies'])}. CAMR resolved every answerable ticket ({p1(cm['answerable_correct'])}) and "
            f"escalated every one it could not know ({p1(cm['unanswerable_escalated'])}).")
    text += (" **Why escalation matters more than it looks.** In a desk that learns, a question reaches a person only "
             "if the system admits it does not know, and only then is the answer taught. A wrong reply is not just one "
             "error: it stops the learning. The next table follows one fact through the eight days.")
    text += (f" **Cost.** Stuffing sends the whole knowledge base with every ticket ({pt['stuff_kimi-k3']:.0f} prompt "
             f"tokens per ticket against {pt['rag_kimi-k3']:.0f} for RAG and {pt['camr_kimi-k3']:.0f} for CAMR) and "
             f"cost {usd(st['cost_usd_per_1000_tickets'])} per 1,000 tickets against {usd(rg['cost_usd_per_1000_tickets'])} "
             f"for RAG and {usd(cm['cost_usd_per_1000_tickets'])} for CAMR; with 14 documents that is affordable, but "
             "it grows with every document added, while retrieval does not. Most of every bill is the cloud model's "
             "output, including its reasoning tokens.")
    text += (" **Before the D-33 fix**, CAMR with Kimi K3 sent 0 wrong replies but escalated 48.3% of tickets, "
             "including 14 it could answer: questions such as *What hours is the support desk open?* name no product, "
             "so the subject check had nothing to anchor to. After the fix (topic anchoring, Equation ⟦eq_topic_n⟧) "
             f"it resolved {p1(cm['auto_resolved_correct'])} of all tickets, still with 0 wrong.")
    for tag, name in (("camr_qwen2_5_0_5b", "the 0.5B model"), ("camr_llama3_2_3b", "the 3B model")):
        if tag in s:
            x = s[tag]
            text += (f" With {name} as the reader, CAMR resolved {p1(x['auto_resolved_correct'])} with "
                     f"{p1(x['wrong_replies'])} wrong replies and {p1(x['escalated'])} escalated.")
    return text


def AGENT_TEXT(agents) -> str:  # noqa: N802
    s = {t: d["summary"] for t, _, d in agents}
    if not {"kimi-k3__none", "kimi-k3__rag", "kimi-k3__camr"} <= set(s):
        return ""
    kn, kr, kc = s["kimi-k3__none"], s["kimi-k3__rag"], s["kimi-k3__camr"]
    text = (f"**What the agent shows.** Without memory, Kimi K3 behaved well and achieved little: told never to invent "
            f"a price, it escalated all 20 tasks (*I do not have the unit price for HS-400 panels … I must not invent "
            f"prices*), which is correct only for the three tasks nobody could do ({p1(kn['success'])} success). With "
            f"either memory it completed every task ({p1(kr['success'])} with RAG, {p1(kc['success'])} with CAMR) and "
            "took no hallucinated action: every invoice total and every reply was the company's. It computed totals "
            "with the calculator tool (*12*420 + 180 + 35*12 = 5640*), combined a learned resolution with a price "
            "(task A08: two Volta-2 inverters at 18 panels each, 36 panels, $15,120), applied the 45-day return rule to "
            "a 50-day-old purchase, and handed the HS-700 warranty, financing and Volta-X price requests to a person. "
            f"Memory cost little: {usd(kr['cost_usd_per_1000_tasks'])} per 1,000 tasks with RAG and "
            f"{usd(kc['cost_usd_per_1000_tasks'])} with CAMR, against {usd(kn['cost_usd_per_1000_tasks'])} for an agent "
            "that does nothing useful. CAMR's run cost slightly more because the agent made more tool calls "
            f"({kc['steps_per_task']:.2f} per task against {kr['steps_per_task']:.2f}). With a strong model, RAG and "
            "CAMR were equally good here; the difference is what memory returns when nothing is relevant (CAMR returns "
            "nothing, RAG returns its top five regardless), and a strong model was not misled by irrelevant passages.")
    text += (" **Before D-32**, the Kimi K3 + CAMR agent succeeded on 80% of tasks: terse task phrasing "
             "(*Recommended cleaning interval?*) was read as a name that no note mentions, so the entity gate returned "
             "nothing and the agent escalated tasks memory could answer. The fix brought it to 100%.")
    l3 = [s.get(k) for k in ("llama3_2_3b__none", "llama3_2_3b__rag", "llama3_2_3b__camr")]
    if all(l3):
        text += (f" **With the 3B model**, the agent succeeded on {p1(l3[0]['success'])} of tasks without memory, "
                 f"{p1(l3[1]['success'])} with RAG and {p1(l3[2]['success'])} with CAMR, with "
                 f"{p1(l3[0]['hallucinated_actions'])}, {p1(l3[1]['hallucinated_actions'])} and "
                 f"{p1(l3[2]['hallucinated_actions'])} hallucinated actions.")
    return text


def FRESH_TEXT(fresh) -> str:  # noqa: N802
    s = {t: d["summary"] for t, _, d in fresh}
    if "llm_kimi-k3" not in s or "camr_kimi-k3" not in s:
        return ""
    lm, cm = s["llm_kimi-k3"], s["camr_kimi-k3"]
    text = (f"**What the news shows.** Asked about events after its training data, Kimi K3 alone was right on "
            f"{p1(lm['correct'])} of questions and stated a wrong answer to {p1(lm['wrong_stated'])}: *four* "
            "journalists arrested where the item says six, *Tropical Storm Fred* where it says Fay, *at least 54* "
            "killed in an airstrike where it says seven. With the workflow teaching each day's page as it arrives, "
            f"the same model with CAMR was right on {p1(cm['correct'])} and declined {p1(cm['declined'])}, questions "
            "whose answers it had read but could not confirm. "
            + (f"Its one answer scored wrong ({p1(cm['wrong_stated'])}) is not an invention: *Which town in North "
               "Kordofan did the Sudanese Armed Forces announce they had recaptured?* has two true answers in the "
               "pages (Sodri on 25 September, al-Mazroub on 2 October); the question was written from the first, and "
               "CAMR gave the second, with its evidence. An earlier run gave Sodri: between the two runs a Wikipedia "
               "editor changed one item on another day's page, which was enough to change which of the two items "
               "memory read first. Live data moves results." if cm["wrong_stated"] else
               f"It stated nothing wrong ({p1(cm['wrong_stated'])})."))
    if "rag_kimi-k3" in s and "stuff_kimi-k3" in s:
        rg, st = s["rag_kimi-k3"], s["stuff_kimi-k3"]
        text += (f" Modern RAG over the same items reached {p1(rg['correct'])} with {p1(rg['wrong_stated'])} wrong; "
                 f"pasting all 30 days into every prompt reached {p1(st['correct'])}, the best accuracy, at "
                 f"{usd(st['cost_usd_per_1000_questions'])} per 1,000 questions against "
                 f"{usd(rg['cost_usd_per_1000_questions'])} for RAG and {usd(cm['cost_usd_per_1000_questions'])} for "
                 f"CAMR: {st['prompt_tokens'] / max(1, st['questions']):,.0f} prompt tokens per question, because "
                 "every question carries 556 news items. On a stream that grows every day, stuffing's cost grows with "
                 "it; a memory's does not.")
    loc = [(n, s[t]) for t, n in (("llm_llama3_2_3b", "Llama 3B alone"), ("rag_llama3_2_3b", "Llama 3B + RAG"),
                                  ("camr_llama3_2_3b", "Llama 3B + CAMR")) if t in s]
    if loc:
        rows = {t: {r["id"]: r for r in d["per_question"]} for t, _, d in fresh}
        declined = [i for i, r in rows.get("rag_llama3_2_3b", {}).items() if r["outcome"] == "declined"]
        rescued = sum(rows.get("camr_llama3_2_3b", {}).get(i, {}).get("outcome") == "correct" for i in declined)
        text += (" **On the device** the gap is wider: " + "; ".join(f"{n} {p1(x['correct'])} correct, "
                                                               f"{p1(x['wrong_stated'])} wrong" for n, x in loc)
                 + ". With the standard RAG prompt the 3B model hedged (*I don't know the specific number of "
                 f"journalists ..., but according to the context ...*), and {rescued} of its {len(declined)} declines "
                 "were answered correctly with CAMR; CAMR's two answers scored wrong are *Tabuk* for *Tabuk, Saudi Arabia* (right, "
                 "missed by the exact match) and the two-answer question above.")
    pages = [d["summary"].get("pages_live") for _, _, d in fresh if d["summary"].get("pages_live") is not None]
    if pages:
        live = "all 30 pages were" if min(pages) >= 30 else f"at least {min(pages)} of the 30 pages were"
        text += (f" In the reported runs {live} fetched live by n8n. The first news runs were marked as failed by "
                 "n8n: a loop's *done* output carries every item it looped over, so the question list was fetched 30 "
                 "times, each question was asked 30 times and 1,500 score requests reset the connection (D-39). "
                 "Answers are kept per question and every repeat was an answer-cache hit, so scores and costs were "
                 "unaffected; the nodes after a loop now run once, and Kimi K3 alone and with CAMR were repeated on "
                 "the fixed workflow.")
    return text


def COST_TEXT(d) -> str:  # noqa: N802
    if not d:
        return ""
    desk = {t: x["summary"] for t, _, x in loaded("helio", DESK_SYSTEMS)}
    fresh = {t: x["summary"] for t, _, x in loaded("fresh", FRESH_SYSTEMS)}
    agents = {t: x["summary"] for t, _, x in loaded("agent", AGENT_CONFIGS)}
    runs = rag_runs()
    rows = []
    def per(s, key):
        return s.get(key) if s else None
    for name, k in (("Kimi K3 alone", "llm_kimi-k3"), ("Kimi K3 + context stuffing", "stuff_kimi-k3"),
                    ("Kimi K3 + RAG", "rag_kimi-k3"), ("Kimi K3 + CAMR", "camr_kimi-k3")):
        rows.append(f"{name}: desk {usd(per(desk.get(k), 'cost_usd_per_1000_tickets'))}, news "
                    f"{usd(per(fresh.get(k), 'cost_usd_per_1000_questions'))}")
    rb = []
    for pipe in ("dense", "rerank", "crag", "camr"):
        r = runs.get((pipe, "kimi-k3"))
        if r:
            s = r["summary"]
            rb.append(f"{PIPE_NAMES[pipe]} {usd((s['prompt_tokens'] * 3 + s['gen_tokens'] * 15) / 1e6 * 1000)}")
    top = sorted(d["rows"], key=lambda r: -r["usd"])[:3]
    big = "; ".join(f"{r['what'].split(': ', 1)[-1]} ({usd(r['usd'])})" for r in top)
    stuff_news = fresh.get("stuff_kimi-k3", {}).get("cost_usd")
    text = (f"The whole study spent {usd(d['total']['usd'])} on {d['total']['calls']:,} cloud calls. The three largest "
            f"items were: {big}." + (f" Context stuffing on the news questions alone cost {usd(stuff_news)} for 50 "
                                    "questions." if stuff_news else "") +
            " Per 1,000 answers, at list price: " + "; ".join(rows) + ". On the RAG benchmark: " + "; ".join(rb) + ". ")
    a = agents.get("kimi-k3__camr")
    if a:
        text += f"The agent with CAMR's memory cost {usd(a['cost_usd_per_1000_tasks'])} per 1,000 tasks. "
    text += ("**Cheaper or more expensive?** CAMR was the cheapest way to make the cloud model useful in every "
             "scenario where it applied, because it sends the fewest prompt tokens and, for labelled facts, often no "
             "prompt at all; context stuffing was the most expensive, and its cost grows with the knowledge base. Most "
             "of every cloud bill is output, and Kimi K3 bills its reasoning as output, so a short answer still costs "
             "more than its length suggests. Local models cost nothing per answer but CPU time: with CAMR the 3B "
             "model's desk answers took about 2 s of model time against 32–37 s with RAG or stuffing, whose prompts "
             "were 2–4 times longer (timings from runs that shared the CPU; section ⟦sec_models⟧ gives clean speeds).")
    return text


# ================================================================= build


def results(c: Chapter) -> None:
    c.h2("Evaluation Results, Discussion and Limitations", key="sec_results")
    c.p("The results are organised by what the study set out to show, not by the order of the experiments. Each "
        "subsection gives the measurement, what it permits the study to conclude, and where the system fell short. "
        "Sources are in `results/`; every table is also in `docs/FINDINGS.md`.")
    c.h3("Results at a Glance: Where It Was Perfect and Where It Was Not", key="sec_scorecard")
    scorecard(c)
    c.p("Three patterns run through the table. Memory works when the gap is **knowledge** (facts, private documents, "
        "recent events, invented formulas) and does not when the gap is **reasoning**. Verification turns a small "
        "model's confident errors into withheld answers, at the price of answering less. And a stronger model reading "
        "the same memory does better wherever reading is the hard part, which is why the engine is more useful beside "
        "a strong model than a replacement for one.")
    res_retrieval(c)
    res_verified(c)
    res_models(c)
    res_rag(c)
    res_multihop(c)
    old.worked_examples(c)
    res_learning(c)
    res_agentic(c)
    res_cost(c)
    res_bulk(c)
    res_policy(c)
    res_app(c)
    old.scenarios_section(c)
    old.learning_scenarios(c)
    res_repro(c)
    res_flaws(c)
    res_limits(c)


def build(template: Path, out: Path, declaration: str | None) -> Path:
    c = Chapter(template)
    c.h1("System Implementation, Testing and Evaluation")
    introduction(c)
    environment(c)
    datasets(c)
    implementation(c)
    selection(c)
    testing(c)
    version_control(c)
    ai_declaration(c, declaration)
    results(c)
    return c.save(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", default="docs/report/Chapter5_CAMR")
    ap.add_argument("--declaration", default=None, help="replace the AI-use declaration text")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    path = build(Path(a.template), Path(a.out), a.declaration)
    print("wrote", path)
    if not a.no_pdf:
        print("wrote", old.to_pdf(path))


if __name__ == "__main__":
    main()
