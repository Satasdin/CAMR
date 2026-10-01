"""Build Chapter 5 (Implementation, Testing and Evaluation) as .docx and .pdf.

The proposal document is used as the template, so headings, captions, fonts,
spacing, margins and the "Chapter N:" numbering are the proposal's own Word
styles. The body is cleared and replaced with Chapter 5 only.

Every number in the chapter comes from a results file in this repository
(results/*/tables, docs/FINDINGS.md) or is read from them here; nothing is
estimated.

    python scripts/build_chapter5.py --template proposal.docx --out build/Chapter5
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "docs" / "figures"
DIAGRAMS = FIG / "diagrams"
REPORT = FIG / "report"
PILOT = ROOT / "results" / "pilot" / "tables"
LEARN = ROOT / "results" / "learn" / "tables"
REGISTRY = json.loads((ROOT / "docs" / "model_registry_metadata.json").read_text())
REPO_URL = "https://github.com/Satasdin/CAMR"
TEXT_WIDTH_CM = 15.9


class Chapter:
    def __init__(self, template: Path, number: int = 5):
        self.n = number
        self.doc = docx.Document(str(template))
        self._clear_body()
        self._start_at_chapter(number)
        self.fig_n = 0
        self.tab_n = 0
        self.labels: dict[str, str] = {}  # key -> "Table 5.n" / "Figure 5.n", resolved in text as ⟦key⟧

    # ------------------------------------------------------------ template

    def _clear_body(self) -> None:
        body = self.doc.element.body
        for el in list(body):
            if el.tag != qn("w:sectPr"):
                body.remove(el)
        # The proposal's last section carries its own header/footer and page
        # numbering; keep it, but restart page numbers at 1.
        sect = body.find(qn("w:sectPr"))
        pg = sect.find(qn("w:pgNumType"))
        if pg is None:
            pg = sect.makeelement(qn("w:pgNumType"), {})
            sect.append(pg)
        pg.set(qn("w:start"), "1")
        pg.set(qn("w:fmt"), "decimal")

    def _start_at_chapter(self, n: int) -> None:
        """Make the heading list (Chapter %1 / %1.%2 / %1.%2.%3) start at chapter n."""
        numbering = self.doc.part.numbering_part.element
        style = self.doc.styles["Heading 1"].element
        num_id = style.find(qn("w:pPr")).find(qn("w:numPr")).find(qn("w:numId")).get(qn("w:val"))
        for num in numbering.findall(qn("w:num")):
            if num.get(qn("w:numId")) == num_id:
                for old in num.findall(qn("w:lvlOverride")):
                    num.remove(old)
                ov = num.makeelement(qn("w:lvlOverride"), {qn("w:ilvl"): "0"})
                st = ov.makeelement(qn("w:startOverride"), {qn("w:val"): str(n)})
                ov.append(st)
                num.append(ov)

    # ------------------------------------------------------------ blocks

    def h1(self, text: str) -> None:
        self.doc.add_paragraph(text, style="Heading 1")

    def h2(self, text: str) -> None:
        self.doc.add_paragraph(text, style="Heading 2")

    def h3(self, text: str) -> None:
        self.doc.add_paragraph(text, style="Heading 3")

    def _runs(self, p, text: str, size: float | None = None) -> None:
        """Minimal inline markup: **bold**, *italic*, `code`, [[placeholder]] (highlighted)."""
        for part in re.split(r"(\*\*.+?\*\*|\*[^*]+?\*|`[^`]+`|\[\[.+?\]\])", text):
            if not part:
                continue
            if part.startswith("**"):
                r = p.add_run(part[2:-2]); r.bold = True
            elif part.startswith("[["):
                r = p.add_run(part[2:-2]); r.font.highlight_color = WD_COLOR_INDEX.YELLOW
            elif part.startswith("*"):
                r = p.add_run(part[1:-1]); r.italic = True
            elif part.startswith("`"):
                r = p.add_run(part[1:-1]); r.font.name = "Courier New"
                r.font.size = Pt(size - 1 if size else 11)
            else:
                r = p.add_run(part)
            if size and not part.startswith("`"):
                r.font.size = Pt(size)

    def p(self, text: str) -> None:
        para = self.doc.add_paragraph(style="Normal")
        self._runs(para, text)

    def items(self, entries: list[str], numbered: bool = True) -> None:
        roman = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]
        for i, e in enumerate(entries):
            para = self.doc.add_paragraph(style="List Paragraph")
            para.paragraph_format.left_indent = Cm(1.0)
            para.paragraph_format.first_line_indent = Cm(-0.6)
            self._runs(para, (f"{roman[i]}.\t" if numbered else "•\t") + e)

    def code(self, text: str) -> None:
        for line in text.strip("\n").splitlines():
            para = self.doc.add_paragraph(style="Normal")
            pf = para.paragraph_format
            pf.line_spacing, pf.space_after, pf.left_indent = 1.0, Pt(0), Cm(0.6)
            para.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r = para.add_run(line or " ")
            r.font.name, r.font.size = "Courier New", Pt(9.5)
        self.doc.add_paragraph(style="Normal").paragraph_format.space_after = Pt(0)

    def table(self, caption: str, header: list[str], rows: list[list], widths: list[float] | None = None,
              size: float = 10, key: str | None = None) -> str:
        self.tab_n += 1
        label = f"Table {self.n}.{self.tab_n}"
        if key:
            self.labels[key] = label
        self.doc.add_paragraph(f"{label}: {caption.replace('`', '')}", style="TabCaption")
        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = self.doc.styles["Table Grid"]
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for row_cells, values, is_head in [(t.rows[0].cells, header, True)] + [
                (t.add_row().cells, r, False) for r in rows]:
            for cell, v in zip(row_cells, values):
                para = cell.paragraphs[0]
                pf = para.paragraph_format
                pf.line_spacing, pf.space_after, pf.space_before = 1.0, Pt(2), Pt(2)
                para.alignment = WD_ALIGN_PARAGRAPH.LEFT
                self._runs(para, f"**{v}**" if is_head else str(v), size)
        # repeat header row on every page
        trpr = t.rows[0]._tr.get_or_add_trPr()
        trpr.append(trpr.makeelement(qn("w:tblHeader"), {}))
        if widths:
            t.autofit = False
            for col, w in zip(t.columns, widths):  # gridCol widths: what LibreOffice and Word lay out by
                col.width = Cm(w)
            for row in t.rows:
                for cell, w in zip(row.cells, widths):
                    cell.width = Cm(w)
        self.doc.add_paragraph(style="Normal").paragraph_format.space_after = Pt(0)
        return label

    def figure(self, path: Path, caption: str, width_cm: float = TEXT_WIDTH_CM, key: str | None = None) -> str:
        self.fig_n += 1
        label = f"Figure {self.n}.{self.fig_n}"
        if key:
            self.labels[key] = label
        para = self.doc.add_paragraph(style="Normal")
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.keep_with_next = True
        para.add_run().add_picture(str(path), width=Cm(width_cm))
        self.doc.add_paragraph(f"{label}: {caption.replace('`', '')}", style="FigCaption")
        return label

    def next_fig(self, k: int = 1) -> str:
        return f"Figure {self.n}.{self.fig_n + k}"

    def next_tab(self, k: int = 1) -> str:
        return f"Table {self.n}.{self.tab_n + k}"

    def resolve(self) -> None:
        """Replace ⟦key⟧ cross-references with the final table/figure numbers."""
        def fix(paragraphs):
            for para in paragraphs:
                for run in para.runs:
                    if "⟦" in run.text:
                        run.text = re.sub(r"⟦(\w+)⟧", lambda m: self.labels[m.group(1)], run.text)
        fix(self.doc.paragraphs)
        for t in self.doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    fix(cell.paragraphs)

    def save(self, out: Path) -> Path:
        self.resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        path = out.with_suffix(".docx")
        self.doc.save(str(path))
        return path


# ----------------------------------------------------------------- data helpers


def pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def git_history() -> list[list[str]]:
    out = subprocess.run(["git", "log", "--reverse", "--date=format:%d %b %Y %H:%M", "--format=%h|%ad|%an|%s"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [line.split("|", 3) for line in out.strip().splitlines()]


def hotpot200() -> dict | None:
    """Floor / CAMR exact match on the 200-question HotpotQA study, with paired bootstrap CIs on the gain."""
    import random
    import sqlite3

    db = ROOT / "results" / "hotpot200" / "camr.sqlite"
    if not db.exists():
        return None
    c = sqlite3.connect(db)
    q = ("SELECT r.label, r.condition, q.question_id, s.value, q.e2e_latency_ms FROM run r JOIN query_log q USING(run_id) "
         "JOIN score s USING(query_id) WHERE s.metric='em' AND q.status='ok' AND r.status='completed' AND r.run_id IN "
         "(SELECT MAX(run_id) FROM run WHERE status='completed' GROUP BY label, condition, benchmark)")
    data: dict = {}
    for label, cond, qid, v, ms in c.execute(q):
        data.setdefault(label, {}).setdefault(cond, {})[qid] = (v, ms)
    order = [("m:qwen2.5:0.5b", "floor", "treatment"), ("m:qwen2.5:1.5b", "floor", "treatment"),
             ("m:llama3.2:3b", "floor", "treatment"), ("kimi", "ceiling", "ceiling_rag")]
    rows, res, rng = [], {}, random.Random(13)
    for label, base, mem in order:
        a, b = data.get(label, {}).get(base, {}), data.get(label, {}).get(mem, {})
        ids = sorted(set(a) & set(b))
        if len(ids) < 150:
            if label == "kimi" and len(a) >= 150:  # Kimi with the same notes still running: report closed-book only
                fa = sum(v[0] for v in a.values()) / len(a)
                sa = sum(v[1] for v in a.values()) / len(a) / 1000
                res["Kimi K3 (cloud)"] = (fa, None, sa, len(a), sa)
                rows.append(["Kimi K3 (cloud)", pct(fa), "–", "–", "–"])
            continue
        diffs = [b[i][0] - a[i][0] for i in ids]
        boots = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(2000))
        fa, fb = sum(a[i][0] for i in ids) / len(ids), sum(b[i][0] for i in ids) / len(ids)
        sec = sum(b[i][1] for i in ids) / len(ids) / 1000
        sec_alone = sum(a[i][1] for i in ids) / len(ids) / 1000
        name = "Kimi K3 (cloud)" if label == "kimi" else label[2:]
        res[name] = (fa, fb, sec, len(ids), sec_alone)
        rows.append([name, pct(fa), f"**{pct(fb)}**", f"{100 * (fb - fa):+.1f} pts ({100 * boots[50]:+.1f} to {100 * boots[1949]:+.1f})", f"{sec:.1f}"])
    if not rows:
        return None
    text = H200_TEXT(res) if callable(H200_TEXT) else ""
    return {"rows": rows, "text": text}


def sweep_latency() -> dict[str, float]:
    """Mean seconds per PopQA answer with CAMR, per swept model (latest completed run)."""
    import sqlite3
    c = sqlite3.connect(ROOT / "results" / "pilot" / "camr.sqlite")
    q = ("SELECT r.label, AVG(q.e2e_latency_ms) / 1000 FROM run r JOIN query_log q USING(run_id) "
         "WHERE r.condition='treatment' AND r.benchmark='popqa' AND r.label LIKE 'm:%' AND q.status='ok' "
         "AND r.run_id IN (SELECT MAX(run_id) FROM run WHERE status='completed' GROUP BY label, condition, benchmark) "
         "GROUP BY r.label")
    return {label[2:]: s for label, s in c.execute(q)}


def sweep_rows() -> list[dict]:
    rows = json.loads((PILOT / "model_sweep.json").read_text())
    by_model: dict[str, dict] = {}
    for r in rows:
        by_model.setdefault(r["model"], {})[r["benchmark"]] = r
    out = []
    for m, b in by_model.items():
        meta = REGISTRY.get(m, {})
        size = meta.get("parameter_size", "?")
        num = float(size.rstrip("MB")) / (1000 if size.endswith("M") else 1) if size != "?" else 0
        out.append({"model": m, "params": size, "quant": meta.get("quantization", "?"), "num": num, **b})
    return sorted(out, key=lambda r: (r["num"], r["model"]))


# ----------------------------------------------------------------- the chapter


def build(template: Path, out: Path, declaration: str | None) -> Path:
    c = Chapter(template)
    profile = json.loads((PILOT / "profile.json").read_text())
    rl = json.loads((LEARN / "rl_report.json").read_text())
    sweep = sweep_rows()
    n_models = len(sweep)
    hist = git_history()

    c.h1("System Implementation, Testing and Evaluation")

    # ================================================================ 5.1
    c.h2("Introduction")
    c.p("This chapter reports how the design of Chapter 4 was implemented as the CAMR memory engine and its "
        "evaluation harness, how the implementation was tested, and what the experiments measured. The project "
        "follows the AI and machine learning route of the departmental guidelines with one important difference: "
        "the language models were never trained or fine-tuned. Every model ran with frozen weights, and what "
        "changed between conditions was the external memory and the engine's policy for using it. The chapter "
        "therefore reports dataset provenance, the implemented data-to-answer pipeline, the experimental "
        "configuration, the tests that verify the requirements of section 4.2, and the measured results for each "
        "research objective.")
    c.p("Every number in this chapter was produced by the code in the project repository on real public "
        "benchmark data and real models, and each table names the results file it comes from. Where a result is "
        "weaker than expected, or a requirement was not met, it is reported as measured. Section 5.2 describes the "
        "environment, section 5.3 the datasets, section 5.4 the implementation, section 5.5 testing, section 5.6 "
        "the version-control evidence, section 5.7 the declaration of AI-assisted tools, and section 5.8 the "
        "results, discussion and limitations.")
    c.p("The work proceeded in increments, each ending with a measured result that decided the next step. The "
        "proposal's engine and harness were built and unit-tested first. The engine was then made "
        "capability-adaptive (gating, entity bridging and procedural memory), and a residual-gap condition was "
        "added. Next came a real-model pilot on a CPU-only machine, a memory-growth experiment, a model-size sweep "
        "spread across five machines, and a comparison with a frontier cloud model (Kimi K3). The engine's "
        "per-question policy was then learned from rewards, and the multi-hop result was confirmed on 200 held-out "
        "questions. Finally, the engine was packaged as a downloadable desktop application. "
        f"{c.next_fig()} shows this sequence as it appears in the repository's commit history, and {c.next_fig(2)} "
        "shows the experimental pipeline that every result in this chapter passed through.")
    c.figure(REPORT / "timeline.png", "Development process reconstructed from the git history; each marked step is a "
             "commit that added an implemented or measured increment")
    c.figure(DIAGRAMS / "pipeline.png", "Experimental pipeline: from public benchmark data to the tables and figures of "
             "this chapter", 11.5)

    # ================================================================ 5.2
    c.h2("Implementation Environment")
    c.p("All development and every experiment ran on Linux machines with x86-64 CPUs and no GPU. This is the "
        "consumer-laptop class of device that NFR-01 targets: four CPU cores and 16 GB of memory. The system is a "
        "local research prototype. It was not deployed for public access.")
    c.h3("Hardware and Deployment Environment")
    hw = profile["hardware"]
    c.table("Implementation environment and minimum requirements",
            ["Item or layer", "Tested specification or version", "Purpose and justification", "Evidence"],
            [["Primary machine (A)", f"{hw['cpu']}, {hw['logical_cpus']} logical CPUs, {hw['memory_gb']:.1f} GB RAM "
              "(14.3 GB usable by processes), no GPU, Linux x86-64", "Development, all pilot, growth, ablation, "
              "learning and Kimi runs; the stated minimum (NFR-01)", "`results/pilot/tables/profile.json`"],
             ["Sweep machines (B–E)", "Same container class: 4 vCPU Intel Xeon (2.10 GHz; machine C 2.80 GHz), "
              "16 GB RAM", "Model-size sweep run in parallel, one model family per machine, then merged",
              "`camr merge`; FINDINGS F10"],
             ["Minimum to run the engine", "4 cores, 16 GB RAM. Measured peak: engine process "
              f"{profile['peak_rss_mb_engine_process']:.0f} MB, model runtime {profile['peak_rss_mb_model_runtime']:.0f} MB "
              f"(qwen2.5:0.5b), store {profile['store_file_mb']:.1f} MB", "A 0.5B model and the engine fit in under "
              "3 GB, leaving headroom on a 16 GB device", "`camr profile` (TC-14)"],
             ["Large local model", "gpt-oss:20b (21B total, 3.6B active, MoE) with memory-mapped weights",
              "Local large-model ceiling; loads in 16 GB only with mmap (first attempt was killed at 13.3 GB)",
              "FINDINGS F6"],
             ["Cloud ceiling", "Moonshot Kimi K3 and Kimi K2.6 via an OpenAI-compatible HTTPS API", "Frontier "
              "reference model (ceiling condition only; NFR-06)", "`configs/pilot_kimi.yaml`"],
             ["End-user device (CAMR Personal)", "Windows 10/11 (x64, ARM64), macOS (Apple Silicon, Intel), Linux "
              "(x64, ARM64); Ollama installed; ≥ 4 GB RAM for a 1.5B model", "The application tested by real users; "
              "talks only to Ollama on the same machine", "CI build and launch test on all six (⟦ci⟧)"],
             ["Specialised hardware", "None: no GPU, NPU or accelerator was used anywhere", "The study targets "
              "CPU-only consumer devices; every timing is a CPU timing", "Profiles and CI runner labels"]],
            [3.0, 4.6, 4.8, 3.5])
    c.h3("Software, Services and Configuration")
    c.table("Software and services used",
            ["Component", "Version", "Role in the system"],
            [["Python", "3.11.15", "Implementation language of the engine, harness and CLI"],
             ["Ollama", "0.35.0", "Local model runtime on the loopback interface (IR-01); Q4/Q8 GGUF weights"],
             ["SQLite / sqlite-vec", "3.45.1 / 0.1.9", "Single-file store with exact kNN vector search (FR-05, IR-04, NFR-03)"],
             ["sentence-transformers / PyTorch", "6.1.0 / 2.14.1 (CPU)", "BGE-small-en-v1.5 embedder, 384 dimensions (IR-03)"],
             ["NumPy", "2.4.6", "Scoring, bootstrap confidence intervals, ridge regression and LinUCB"],
             ["Streamlit", "1.64.0", "Read-only inspection interface (FR-17, IR-06)"],
             ["Matplotlib / Playwright", "3.11.2 / 1.63.0", "Figures; automated screenshots of the inspector"],
             ["pytest", "9.1.1", "Unit and integration tests (section 5.5)"],
             ["Moonshot API", "kimi-k3, kimi-k2.6", "Cloud ceiling. The key is read from the `MOONSHOT_API_KEY` "
              "environment variable and never written to configuration, logs or the repository"]],
            [4.0, 3.4, 8.5])
    c.p("Configuration is a single YAML file per experiment (NFR-07). It is loaded into typed dataclasses that "
        "reject unknown keys, so a misspelt ablation parameter fails loudly instead of silently running the "
        "default. Each run records the hash of its full configuration. A completed run with the same label and "
        "hash is skipped, which makes every command resumable after an interruption. Containers (Docker) were "
        "not part of the solution: the experiments ran directly on the hosts above, and the application ships "
        "as a single self-contained executable per platform.")
    c.h3("Deployment and Reproducibility")
    c.p("The engine installs as a Python package and is driven by one command-line program, `camr` (IR-05). Every "
        "result in this chapter can be regenerated with the commands below. They were run as shown, on Linux with "
        "Python 3.11 and Ollama 0.35. Each block can be copied into a terminal. Steps 4 and 6 need the cloud key "
        "only for the Kimi comparisons; everything else runs offline once models and data are downloaded.")
    c.p("**Step 1: get the code and install it** (a virtual environment keeps it separate from other Python "
        "projects).")
    c.code("""git clone https://github.com/Satasdin/CAMR.git
cd CAMR
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\\Scripts\\activate
pip install -e ".[vec,embed,dev,inspect]"
python -m pytest -q                                     # health check: all tests pass, no network needed""")
    c.p("**Step 2: install the local models** with Ollama (https://ollama.com/download).")
    c.code("""ollama pull qwen2.5:0.5b        # the small model of the pilot
ollama pull gpt-oss:20b         # large local comparison model (needs ~14 GB RAM)
ollama pull qwen2.5:1.5b && ollama pull llama3.2:3b     # used in the n = 200 study""")
    c.p("**Step 3: download the real benchmark data** (PopQA, HotpotQA, 2WikiMultiHopQA, GSM8K) and the "
        "Wikipedia corpus for PopQA. The pilot corpus is already in the repository; the learning split needs its "
        "own.")
    c.code("""python scripts/fetch_data.py                            # prints a hash per file
python scripts/build_popqa_corpus.py --config configs/learn.yaml --split train --run-dir results/learn \\
       --out data/popqa/corpus_learn.jsonl""")
    c.p("**Step 4: the cloud key** (only for the Kimi conditions). It is read from an environment variable and "
        "never written to any file.")
    c.code("""export MOONSHOT_API_KEY=...                             # your own key""")
    c.p("**Step 5: run the experiments.** Each command is resumable: run it again after an interruption and it "
        "skips finished work.")
    c.code("""camr reproduce       --config configs/pilot.yaml        # pilot: ingest, conditions, ablation, budgets, profile
camr grow            --config configs/pilot.yaml --stages 0.25,0.5,1.0      # memory growth
camr sweep-models    --config configs/pilot.yaml --models qwen2.5:0.5b,llama3.2:3b,phi4-mini:3.8b   # any list
camr retrieval-eval  --config configs/retrieval_eval.yaml                   # 500 + 500 questions, no LLM
camr learn           --config configs/learn.yaml --phase all                # learned policy
camr ingest          --config configs/hotpot200.yaml                        # n = 200 study
camr sweep-models    --config configs/hotpot200.yaml --models qwen2.5:0.5b,qwen2.5:1.5b,llama3.2:3b""")
    c.p("**Step 6: the cloud comparisons.**")
    c.code("""camr run --config configs/pilot_kimi.yaml --out results/pilot --condition ceiling     --benchmark popqa --label kimi
camr run --config configs/pilot_kimi.yaml --out results/pilot --condition ceiling_rag --benchmark popqa --label kimi
camr run --config configs/hotpot200.yaml  --condition ceiling     --benchmark hotpotqa --label kimi
camr run --config configs/hotpot200.yaml  --condition ceiling_rag --benchmark hotpotqa --label kimi""")
    c.p("**Step 7: regenerate the tables, figures and this chapter** from the logged results alone (NFR-04).")
    c.code("""camr analyse --run-dir results/pilot
python scripts/make_figures.py && python scripts/make_report_figures.py && python scripts/make_diagrams.py
camr inspect --run-dir results/pilot                    # read-only web view at http://localhost:8501
python scripts/build_chapter5.py --template proposal.docx --out build/Chapter5""")
    c.p("**The application only** (no experiments): download the file for the platform from the v0.2.0 release "
        "page, or install it with Python:")
    c.code("""pip install "camr[app] @ git+https://github.com/Satasdin/CAMR.git"
ollama pull qwen2.5:1.5b
camr app                                                # opens http://127.0.0.1:8502""")
    c.p(f"{c.next_fig()} shows the CLI's command surface and {c.next_fig(2)} the test-suite health check, both "
        "captured from real runs.")
    c.figure(FIG / "setup" / "terminal_help.png", "The camr command-line interface (captured output)", 13.5)
    c.figure(FIG / "setup" / "terminal_tests.png", "Health check: the offline test suite passing (captured output)", 13.5)

    # ================================================================ 5.3
    c.h2("Dataset Description")
    c.p("Four public benchmarks were used (DR-01). They were downloaded from their official distributions by "
        f"`scripts/fetch_data.py`, and no data was generated synthetically. {c.next_tab()} summarises them and {c.next_tab(2)} "
        "shows one real record of each. PopQA ships without documents, so a corpus of real Wikipedia summaries "
        "was fetched for the subject entity of each sampled question (design note A4). HotpotQA and "
        "2WikiMultiHopQA supply gold and distractor paragraphs, and those paragraphs, never the question–answer "
        "records, populate memory (DR-03).")
    c.table("Benchmarks used",
            ["Benchmark", "Source and licence", "Size of the file used", "Task type", "Metric"],
            [["PopQA", "Mallen et al. (2023); templates over Wikidata facts", "14,267 questions; corpus of 357 "
              "Wikipedia summaries (CC BY-SA)", "Single-hop, long-tail facts", "Answer contained (accuracy)"],
             ["HotpotQA (dev distractor)", "Yang et al. (2018); crowd-written over Wikipedia; CC BY-SA",
              "7,405 questions (5,918 bridge, 1,487 comparison), 10 paragraphs each", "Multi-hop", "Exact match, F1"],
             ["2WikiMultiHopQA (dev)", "Ho et al. (2020); Wikipedia and Wikidata", "12,576 questions",
              "Multi-hop (retrieval study only)", "Supporting-paragraph recall"],
             ["GSM8K (test; train for exemplars)", "Cobbe et al. (2021); human-written; MIT", "1,319 test; 7,473 "
              "train solutions", "Reasoning control", "Final-answer accuracy"]],
            [3.2, 4.2, 3.9, 2.6, 2.2])
    c.table("One record from each benchmark (verbatim)",
            ["Benchmark", "Question", "Reference answer", "Supporting evidence"],
            [["PopQA", "What is George Rankin's occupation?", "politician (also: political leader, political figure)",
              "Wikipedia summary of *George Rankin*"],
             ["HotpotQA", "Were Scott Derrickson and Ed Wood of the same nationality?", "yes",
              "Paragraphs *Scott Derrickson* and *Ed Wood* (gold) plus 8 distractors"],
             ["GSM8K", "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins "
              "for her friends every day with four. She sells the remainder … for $2 per fresh duck egg. How much in "
              "dollars does she make every day?", "18", "None (reasoning); solved train problems serve as exemplars"]],
            [2.3, 6.6, 3.2, 3.8])
    c.h3("Data Preparation and Partitioning")
    c.p("Each benchmark sample was drawn once from seed 13, sorted by question identifier before sampling so that "
        "the draw does not depend on file order, and persisted to `samples/<benchmark>.json` with the source file's "
        "hash (DR-02). Every condition and ablation reused the same questions, so all comparisons are paired. "
        "The pilot evaluation sample was 30 PopQA, 30 HotpotQA and 12 GSM8K questions (72 in total), limited by "
        "the time the 20B CPU ceiling needed (up to 150 s per GSM8K answer). For the learned policy, a "
        "**disjoint** training split of 144 questions (60 PopQA, 60 HotpotQA, 24 GSM8K) was drawn from the "
        "questions not in the evaluation sample. The code asserts that the two splits do not overlap.")
    c.p("Memory was built from documents only. The HotpotQA store also took the paragraphs of 100 further, "
        "unsampled questions as extra distractors (design note A5). Before ingestion a holdout guard scanned "
        "every document and refused any that contained an evaluation question verbatim (DR-04, TC-21). Text was "
        "normalised (Unicode NFKC, whitespace) and paragraphs were stored verbatim with their title prefixed, "
        "e.g. *The Loudwater Mystery (film): The Loudwater Mystery is a 1921 British silent…*. The structured "
        "(distilled) write policy is implemented and tested, but it was not used for the reported runs, because "
        "distilling every paragraph with the 0.5B model exceeded the pilot's time budget.")
    c.p(f"{c.next_tab()} follows one real record from the raw files to what the model finally reads.")
    c.table("One PopQA record before and after preparation",
            ["Stage", "Content"],
            [["Raw question (test.tsv)", "id 5939255 · subject *The Loudwater Mystery* · property *director* · "
              "question *Who was the director of The Loudwater Mystery?* · answers [\"Walter West\", \"Walter "
              "Alabaster West\"]"],
             ["Raw document (corpus)", "{\"title\": \"The Loudwater Mystery (film)\", \"text\": \"The Loudwater "
              "Mystery is a 1921 British silent crime film directed by Walter West and starring Gregory Scott, "
              "Pauline Peters and Clive Brook. It was based on the 1920 novel …\"}"],
             ["Stored note (#4863)", "*The Loudwater Mystery (film): The Loudwater Mystery is a 1921 British silent "
              "crime film directed by Walter West …* (47 tokens; 384-d BGE vector; provenance: dataset popqa, document "
              "id, ingestion time)"],
             ["Read at question time", "Similarity 0.77 → admitted; next candidate 0.62 → outside the 0.15 margin. "
              "The prompt's notes section contains this single note (47 tokens instead of a 512-token budget)."],
             ["Answer and score", "0.5B alone: *John Sturges* (wrong). 0.5B + CAMR: *Walter West*: contains = 1, "
              "EM = 1"]],
            [3.4, 12.5], size=9.5)

    # ---------------------------------------------------------------- implementation
    c.h2("System Implementation")
    c.p(f"{c.next_fig()} shows the implemented architecture. Everything inside the engine runs on the device. The "
        "cloud model is used only as a measurement ceiling and as the escalation target of the learned policy.")
    c.figure(DIAGRAMS / "architecture.png", "Implemented CAMR architecture: write path, single-file store, "
             "capability-adaptive read path (green), frozen local model and optional cloud escalation", 11.0)
    c.p("The implementation follows the package structure of Figure 4.6: `camr.memory` (the engine), "
        "`camr.models` (runners and prompt templates), `camr.harness` and `camr.eval` (experiments and "
        "analysis), `camr.learn` (the learned policy), `camr.cli` and `camr.inspect`. A test enforces the "
        "dependency rules of the package diagram (memory imports nothing from harness, eval, cli or inspect, and "
        "nothing imports inspect).")
    c.h3("Memory Engine: Write Path")
    c.p("Ingestion implements the sequence of Figure 4.4. A write policy turns a source document into candidate "
        "notes (FR-01). The screener rejects empty, degenerate, duplicate, over-length and injection-like candidates "
        "and logs the reason (FR-02). An importance score is assigned (FR-04). Then the note, its embedding and its "
        "provenance are committed in one SQLite transaction (FR-03, FR-05), so the store never holds a note without "
        "its vector or its source. Duplicate detection uses a checksum with a UNIQUE constraint, namespaced by note "
        "population, so ablations that change what is stored (write policy, screening) coexist in one file "
        "(design note A6). Ingesting 14,567 HotpotQA paragraphs into a 24,475-note store took 622 s on machine "
        "A, of which 569 s was embedding.")
    c.h3("Memory Engine: Read Path")
    c.p("Recall implements Figure 4.5 and Equations 4.1–4.5. The question is embedded and the k = 20 nearest "
        "notes are found by exact kNN in sqlite-vec (FR-06). The notes are ranked by the configured policy, "
        "similarity only or composite (FR-07), and packed greedily under the token budget (FR-08). Three "
        "capability-adaptive mechanisms were added during implementation, each switchable in configuration and "
        "each justified by measurement in section 5.8:")
    c.items(["**Gating.** The engine abstains when the best note's similarity is below 0.50, and admits only notes "
             "within 0.15 of the best. This keeps irrelevant text away from a small reader.",
             "**Entity-bridge expansion.** When an admitted note mentions the title of another stored entity, that "
             "entity's notes are pulled in. This is a one-step associative hop that needs no graph construction and "
             "no model call, and it replaces the optional graph layer of FR-18.",
             "**Procedural memory.** For reasoning questions, solved GSM8K *train* problems are retrieved as worked "
             "examples instead of factual notes."])
    c.p("Recency uses a logical clock, which advances one step per question instead of wall-clock time, and "
        "access state is reset before every run. This makes recall deterministic and independent of machine "
        "speed (NFR-05, design note A1).")
    c.h3("Model Runners")
    c.p("All runners expose a single `generate` operation, and none can modify model weights (FR-09). "
        "`OllamaRunner` calls the local runtime with greedy decoding (temperature 0, seed 13) and refuses any host "
        "but loopback, unless it is explicitly configured as a ceiling (IR-01, NFR-06). `OpenAICompatRunner` calls "
        "the Moonshot API with a pinned model identifier, a timeout and bounded exponential-backoff retries. When "
        "retries are exhausted the query is logged as failed rather than scored (IR-02, IR-07). The Kimi API "
        "accepts only temperature 1, so the cloud ceiling is a single stochastic sample per question; this "
        "limitation is reported in section 5.8.")
    c.h3("Evaluation Harness and Learned Policy")
    c.p("The harness runs four conditions over the fixed sample: **floor** (small model alone), **treatment** "
        "(small model + CAMR), **ceiling** (large model alone) and **ceiling_rag** (large model given the same "
        "notes). Each query writes a structured record (FR-13): condition, model and version, configuration hash, "
        "retrieved note identifiers and scores, prompt and generated tokens, retrieval, prefill and decode times, "
        "and the score. Analysis computes gap closed (Equation 3.1) with paired bootstrap confidence intervals over "
        "2,000 resamples (FR-15). Next to it, it reports the absolute gain, and the **residual gap** "
        "(ceiling_rag − treatment): what model size still buys when both models read the same evidence.")
    c.p("The learned policy (`camr learn`) chooses, per question, one of five actions: answer with the small model "
        "alone, with 128, 512 or 1,024 tokens of memory, or escalate to Kimi K3. Its training configuration is "
        f"given in {c.next_tab()}. No neural network was trained and no model weights changed. The learned "
        "parameters are a ridge-regression weight vector per action (5 × 11 numbers) and a grounding classifier.")
    c.table("Learned-policy training configuration (from `camr/learn/bandit.py` and `rl_report.json`)",
            ["Setting", "Value"],
            [["Language-model training", "None. All model weights frozen: 0 fine-tuning epochs, no learning rate, no gradient updates"],
             ["Training / evaluation questions", f"{rl['n_train']} / {rl['n_test']} (disjoint; 60/60/24 and 30/30/12 PopQA/HotpotQA/GSM8K)"],
             ["Actions (arms)", "local; mem128; mem512 (+ bridging); mem1024 (+ bridging); cloud (Kimi K3)"],
             ["Logged outcomes", f"Every action on every question: {rl['n_train'] * 5} training and {rl['n_test'] * 5} evaluation answers"],
             ["Context features (11)", "Bias; task type (3 one-hot); best-note similarity; margin to second note; "
              "number of near-best notes; question length; task type × best-note similarity (3)"],
             ["Reward", f"correct − {rl['costs']['cloud']} × [cloud call] − {rl['costs']['per_1k_tokens']} × prompt tokens / 1,000"],
             ["Offline learner", "Ridge regression per action, λ = 1.0, closed-form solution (one pass)"],
             ["Online learner (LinUCB)", "Bandit feedback only; exploration α = 0.5; **5 epochs** (passes) over the "
              "144 training questions = 720 episodes, shuffled with seed 13; held-out evaluation every 20 episodes "
              f"({len(rl['curve'])} checkpoints)"],
             ["Grounding cascade", "Ridge classifier on answer signals (answer words found in the notes, abstention-like "
              "text, length); escalation thresholds swept over 0–1.01"],
             ["Cloud-cost sweep", "0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2 (Pareto table)"]],
            [4.3, 11.6])
    c.p(f"{c.next_fig()} shows the learned decision for one question.")
    c.figure(DIAGRAMS / "policy.png", "Learned engine policy: a router chooses local memory budgets or the cloud from "
             "pre-answer features, and a grounding check escalates local answers that are not supported by the "
             "notes they read", 7.5)

    c.h3("Model Selection and the Validation–Test Protocol")
    c.p("Because no weights were trained, *selection* meant choosing which frozen model and which engine "
        "configuration to recommend, and that choice was made on evidence kept apart from the final test. The "
        "**baseline** was each small model answering alone (the floor condition). The **candidates** were 19 "
        "quantised models from 0.5B to 14.8B parameters across ten families (⟦sweep⟧), each run with the same "
        "store, questions and prompt templates (seed 13, greedy decoding, temperature 0). The pilot sample (30/30/12 "
        "questions) and the 500-question retrieval study served as the **validation** evidence: they fixed the "
        "read path (similarity ranking, gating at 0.50 with a 0.15 margin, entity bridging) and the budgets "
        "(128 tokens for single facts, 512 for multi-hop). The 200-question HotpotQA study (reported in section 5.8) then "
        "served as a **held-out test**: its configuration was written to `configs/hotpot200.yaml` before it ran "
        "and was not changed afterwards. Every run's configuration, hash, model digest and per-question records "
        "are saved in its results database and in `records/*.jsonl`, so each reported number can be regenerated.")

    c.h3("Inspection Interface and Integration Workflow")
    c.p("The inspector implements the four wireframes of Figures 4.10–4.13 and opens the results database "
        "read-only (`mode=ro`), so it cannot write (FR-17, IR-06). The screenshots below were captured "
        "automatically by Playwright from the real results database. "
        f"{c.next_fig()} is the Run Dashboard of the final pilot. {c.next_fig(2)} follows one question end to end: "
        "the 0.5B model alone answered \"John Sturges\" (wrong), and with CAMR it read one admitted note of "
        "47 tokens and answered \"Walter West\" (correct). Gating stopped the next candidate (similarity 0.62 vs "
        "0.77) at the budget cutoff.")
    c.figure(FIG / "setup" / "inspector_select_run.png", "Run Dashboard of the final pilot (markers: run selector, "
             "screen, gap closed per task type)")
    c.figure(FIG / "setup" / "inspector_query_trace.png", "Query Trace for one PopQA question at full memory, showing "
             "the admitted note and the budget cutoff")
    c.figure(FIG / "inspector" / "main_2_ablations.png", "Ablations and budget-sweep screen")
    c.figure(FIG / "inspector" / "grow-100_4_memory_store.png", "Memory Store browser: notes, provenance and "
             "retrieval counts")
    c.p("The deployment scenario of section 4.2.1 was exercised with the `camr ask` command on five personal-style "
        f"notes ({c.next_fig()}, {c.next_fig(2)}). With an empty store, the 0.5B model invented answers "
        "(\"next Monday\"). With the notes, it answered from them (\"Thursday 9 October at 14:30\"), showing the "
        "note used, 26 context tokens, 27 ms retrieval and 1.7 s generation. For an off-topic question the engine "
        "abstained (0 notes admitted) and the model answered wrongly from its weights. This failure mode motivates the "
        "escalation policy.")
    c.figure(FIG / "setup" / "terminal_ask_empty.png", "Assistant scenario with empty memory: the frozen model guesses", 15.0, key="askempty")
    c.figure(FIG / "setup" / "terminal_ask.png", "Assistant scenario with memory: answers grounded in the user's notes", 12.5, key="ask")
    c.h3("CAMR Personal: the Engine as an Application")
    c.p("To move from benchmarks to real use, the engine was packaged as **CAMR Personal**, a desktop application "
        "that gives any model the user already has in Ollama a long-term memory. The user teaches it notes and files "
        "(.txt, .md, .pdf), dropped anywhere on the window; states facts with *remember that …*; and approves good "
        "answers with a thumbs-up, which stores them as memory. What the user says in chat is also stored, so a fact "
        "mentioned weeks earlier is recalled even after it has left the model's context window. Each answer reads only "
        "the notes it needs, using the measured best read path (similarity, gating and bridging). A *Recalled N "
        "memories* card appears before the answer streams, and the answer shows how grounded it is in those notes. The "
        "model's weights never change: the application adapts to its user through storage, not through compute or a "
        "longer context window.")
    c.p("The interface was designed after studying the conventions of ChatGPT (a minimal composer and chat history), "
        "Ollama's desktop app (the model picker inside the composer, file drop) and Kimi (sources shown before the "
        "answer), with memory made the visible centre: a ring that fills as memory grows, and a panel showing what "
        "was read, everything stored, and how memory has grown. It is a standard-library Python server with a "
        "single-page front end, bound to 127.0.0.1, refusing foreign hosts and cross-site writes. Embeddings come from "
        "a small Ollama model (nomic-embed-text), so the download needs no PyTorch. Its abstain threshold (0.55) was "
        "calibrated on HotpotQA with the same rule that places BGE's benchmark threshold (0.50): the 90th percentile "
        "of off-topic similarity. Self-contained downloads are built by continuous integration for Windows (x64, "
        "ARM64), macOS (Apple Silicon, Intel) and Linux (x64, ARM64). "
        f"{c.next_fig()} and {c.next_fig(2)} show the application running with qwen2.5:1.5b on the demonstration notes.")
    c.p(f"{c.next_fig()} traces one message through the application. Numbered screenshots of the main steps follow: "
        "first-run setup, the empty chat, a conversation with a remembered fact, a recalled memory and an abstention, "
        "the memory panel, and the phone-width layout.")
    c.figure(DIAGRAMS / "query_flow.png", "One message through CAMR Personal (implemented flow)", 9.0)
    for name, cap, w in (("0_setup.png", "Step 1. First run: the app checks Ollama, finds the user's models and downloads the memory model", 14.5),
                         ("dark_1_home.png", "Step 2. Empty chat: the model picker sits inside the composer; suggestions start teaching", 14.5)):
        if (FIG / "app" / name).exists():
            c.figure(FIG / "app" / name, cap, w)
    if (FIG / "app" / "dark_3_panel_recall.png").exists():
        c.figure(FIG / "app" / "dark_3_panel_recall.png", "CAMR Personal: a remembered fact, an answer with its recalled "
                 "memory and grounding, and an abstention, with the memory panel open")
        c.figure(FIG / "app" / "dark_4_panel_growth.png", "CAMR Personal: the growth panel (memories, share of answers "
                 "drawn from memory, lookup time, sources of knowledge)")
    if (REPORT / "gating_calibration.png").exists():
        c.figure(REPORT / "gating_calibration.png", "Gating calibration: relevant and off-topic similarity on 200 HotpotQA "
                 "questions; the threshold is the 90th percentile of off-topic similarity for each embedder")
    for name, cap, w in (("dark_5_panel_memory.png", "All memory: search, provenance by kind, and Forget on every item", 14.5),
                         ("dark_6_mobile.png", "The same interface at phone width", 5.5)):
        if (FIG / "app" / name).exists():
            c.figure(FIG / "app" / name, cap, w)

    # ================================================================ 5.4 Testing
    c.h2("Testing and Evaluation")
    c.h3("Test Strategy and Acceptance Criteria")
    c.p("Testing combined three levels. **Unit and integration tests** (white-box, pytest, 102 tests, fully "
        "offline) verify each requirement with deterministic test doubles: dry-run models and a hashing embedder. "
        "**System tests** run the real pipeline end to end on real data with real models. **Measurements** "
        "(device profile, latency, memory) verify the non-functional requirements against their thresholds. Each "
        "test maps to a test case of Table 4.5. Acceptance criteria were fixed before the runs: a functional test "
        "passes when the observed behaviour equals the expected behaviour; NFR-02 passes when retrieval is ≤ 10% of "
        "median end-to-end latency; NFR-05 passes when two runs produce byte-identical prompts.")
    c.p(f"{c.next_fig()} shows a sample of requirement test cases running (captured output).")
    c.figure(FIG / "setup" / "terminal_tests_tc.png", "Example requirement test cases: failure handling (IR-07, D-07), "
             "holdout guard (DR-04), byte-identical prompts (NFR-05) and the bootstrap (FR-15)", 15.5)

    c.h3("Test Cases, Defects and Retesting")
    c.table("Test cases and results (unit tests: `pytest`, 102 passed; measurements: `camr profile`)",
            ["Test ID", "Traceability", "Scenario and data", "Expected result", "Actual result and verdict"],
            [["TC-01", "FR-01", "Verbatim and structured policies on fixture passages", "Notes produced; title kept", "As expected. Pass"],
             ["TC-02", "FR-02/03, DR-06", "Empty, duplicate, over-length, injection-like notes", "Rejected with logged reason; provenance on all notes", "As expected. Pass"],
             ["TC-03", "FR-04, IR-03", "Commit a note", "Timestamp, importance, 384-d embedding stored", "As expected. Pass"],
             ["TC-04", "FR-05, IR-04, NFR-03", "kNN via sqlite-vec vs NumPy fallback", "Identical scores; single file", "As expected. Pass"],
             ["TC-05", "FR-06/07", "Similarity-only and composite ranking; Eq. 4.3–4.4", "Order follows the equations", "As expected. Pass"],
             ["TC-06", "FR-08", "Budgets 0–1,024 over random note lengths", "Budget never exceeded", "As expected. Pass"],
             ["TC-07", "FR-09, IR-01", "Runner interface; non-loopback host", "Only `generate`; remote host refused", "As expected. Pass"],
             ["TC-08", "FR-10, IR-02, NFR-09", "Cloud runner with failing transport", "Bounded retries, then logged failure", "As expected. Pass"],
             ["TC-09", "FR-11, DR-02", "Shuffle the dataset file; redraw", "Same sample; persisted with seed and hash", "As expected. Pass"],
             ["TC-10", "FR-12", "EM, F1, contains, GSM8K final number", "Matches hand-computed values", "As expected. Pass"],
             ["TC-11, TC-19", "FR-13, NFR-05, NFR-08", "Run the same config twice", "Complete records; byte-identical prompts",
              "Unit: pass. System: 30/30 identical prompts. 0.5B answers identical on 20/30 only (D-02)"],
             ["TC-12", "FR-14, NFR-07", "Ablation plan from config", "All variants and budgets planned", "As expected. Pass"],
             ["TC-13", "FR-15", "Gap closed and bootstrap; near-zero denominator", "Correct CI; unstable flagged", "As expected. Pass"],
             ["TC-14", "FR-16, NFR-01", "Profile on machine A, 3 × 10 questions", "Peak memory recorded; fits 16 GB",
              f"Engine {profile['peak_rss_mb_engine_process']:.0f} MB + runtime {profile['peak_rss_mb_model_runtime']:.0f} MB. Pass"],
             ["TC-15", "FR-17, IR-06", "Write through the inspector connection", "Write fails at the driver", "As expected. Pass"],
             ["TC-17", "NFR-02", "Retrieval share of median latency, 0.5B", "≤ 10%",
              f"{100 * profile['retrieval_share_of_e2e']:.0f}% in the pilot profile. **Fail** (D-05; see 5.8)"],
             ["TC-18", "NFR-04, IR-05", "`camr reproduce` end to end (dry-run and real)", "All tables and figures regenerated", "As expected. Pass"],
             ["TC-20", "NFR-06", "Block sockets; run floor and treatment", "No external connection", "As expected. Pass"],
             ["TC-21", "DR-03/04", "Corpus containing an evaluation question", "Ingestion refused", "As expected. Pass"],
             ["TC-22", "IR-07", "Local runtime down mid-run", "Failures logged; run continues; store intact", "As expected. Pass"],
             ["TC-23", "Deployment (4.2.1)", "CAMR Personal: teach, ask, remember, 👍, forget, settings, export; server API, streaming, host/origin checks", "Answers cite notes; chat recalled beyond the window; export hides text; foreign hosts refused", "14 tests and a browser test with a real model. Pass"]],
            [1.6, 2.7, 4.0, 3.6, 4.0], size=9)
    c.p("The defects below were found during the real runs. Each was fixed and retested, or is reported as an "
        "open limitation. Failed results were kept in the record, not deleted.")
    c.table("Defects found and retests",
            ["ID", "Defect", "Found by", "Correction", "Retest"],
            [["D-01", "The screener rejected the real song title \"I Can't Get Next to You\" as a model refusal",
              "Retrieval run 1 rejection log", "Refusal check applied only to model-generated notes", "Regression test added. Pass"],
             ["D-02", "The 0.5B model's answers differed on 10/30 questions between identical runs (all wrong→wrong)",
              "Repeat runs", "Engine confirmed deterministic (prompts identical); floors reported as a range",
              "Open: runtime non-determinism"],
             ["D-03", "gpt-oss:20b was killed for running out of memory at 13.3 GB", "Pilot ceiling run",
              "Memory-mapped weights; one model loaded at a time", "Loaded. Pass"],
             ["D-04", "Changing a configuration field mid-study changed the hash, so resume re-ran finished runs",
              "Pilot resume", "Freeze the schema before final runs", "Pass"],
             ["D-05", "Retrieval took 56% of answer time (NFR-02)", "TC-17", "Diagnosed as CPU contention; "
              "thread partitioning settings added", "Engine alone 29 ms; p90 157→50 ms. Still above 10% for 0.5B"],
             ["D-06", "Composite score (Eq. 4.1) lowered full-support recall by 4.6 points", "Retrieval evaluation",
              "Similarity + gating + bridging as the best read path", "2Wiki recall 35.8%→78.4%; HotpotQA equal at 11% fewer tokens"],
             ["D-07", "When the model server stopped mid-sweep, failed queries were logged (IR-07) but the run was "
              "still marked completed, so resume skipped it", "Machine B sweep", "Resume re-runs any run with "
              "failed queries; the failed run is kept", "Regression test added. Pass; 19 runs re-run clean"],
             ["D-08", "gemma2:9b was killed for running out of memory three times at 13.4 GB (runtime prompt cache "
              "growing on top of the weights)", "Machine B sweep", "Runtime prompt cache capped at 1 GiB "
              "(affects prefill reuse only)", "No further kills. Pass"],
             ["D-09", "CAMR Personal: the shared store connection failed when the web UI called it from another "
              "thread, and the UI's file watcher crashed while crawling the PyTorch modules", "App browser test",
              "Store opened for cross-thread use behind a lock; file watcher disabled", "App tests and browser test. Pass"]],
            [1.2, 4.6, 2.6, 4.0, 3.5], size=9)

    c.h3("Application Testing (CAMR Personal)")
    c.p("The application was tested as a user would meet it, with valid, empty, out-of-scope and unsupported "
        "input and with the runtime missing. The live checks used qwen2.5:1.5b and nomic-embed-text through "
        "Ollama in a browser driven by Playwright. The automated checks are in `tests/test_app*.py` and in the "
        "continuous-integration smoke test.")
    c.table("Application test cases and results",
            ["Test ID", "Scenario", "Expected result", "Actual result and verdict"],
            [["TC-24", "Empty message (spaces only)", "Rejected; no model call; no chat created", "Error event, no chat (test). Pass"],
             ["TC-25", "Out-of-scope question (\"What's the capital of Kenya?\") with only personal notes stored",
              "Gating abstains; the answer is labelled as coming from the model alone", "0 memories admitted; labelled; answered \"Nairobi\". Pass"],
             ["TC-26", "\"remember that my bike lock code is 4471\"", "Stored without a model call; duplicate reported",
              "Stored; second time \"already in memory\" (test and browser). Pass"],
             ["TC-27", "Question answered by a note", "Recalled memory shown before the answer; grounded answer",
              "1 memory, 71 ms; correct answer, grounded 86%, 4.8 s (1.5B, CPU). Pass"],
             ["TC-28", "Fact said in chat, then asked after it left the context window", "Recalled from memory",
              "Recalled as \"something you said\" (test). Pass"],
             ["TC-29", "Teach a Markdown file and a PDF", "Chunked and stored as memory", "Stored (test; PDF via pypdf). Pass"],
             ["TC-30", "Ollama not running / memory model missing", "Setup screen with the missing step and a "
              "download button", "Setup screen; download with progress; then chat (browser; CI checks the not-running "
              "state). Pass"],
             ["TC-31", "Request with a foreign Host header, or a cross-site POST", "Refused (403)", "403 (test). Pass"],
             ["TC-32", "Path traversal (/../../etc/passwd)", "No file outside the app is served", "Index page served (test). Pass"],
             ["TC-33", "Downloadable build on six platforms", "Builds, launches, serves the UI and API",
              "All six green in CI (⟦ci⟧). Pass"]],
            [1.6, 5.0, 4.6, 4.7], size=9)
    c.figure(FIG / "setup" / "terminal_tests_app.png", "Application test run: 14 tests for the assistant core and the "
             "web server (captured output)", 15.5)
    if (FIG / "app" / "dark_0_setup_ollama_down.png").exists():
        c.figure(FIG / "app" / "dark_0_setup_ollama_down.png", "TC-30: with Ollama not running, the app shows what is "
                 "missing instead of failing", 14.5)
    c.p("These tests show that the application behaves correctly and fails safely. They do not show that people "
        "find it useful or easy to use. That requires a user study, which had not been run when this chapter "
        "was written (see Limitations, section 5.8).")

    # ---------------------------------------------------------------- evaluation design
    c.h3("Evaluation Design")
    c.p("The primary measure is the fraction of the capability gap closed (Equation 3.1) per task type, together "
        "with the absolute gain, the residual gap, tokens per question and latency. Two ceilings were used: the "
        "local gpt-oss:20b and the cloud Kimi K3. Against a closed-book ceiling that the small model plus memory "
        "*exceeds*, gap closed rises above 1 and stops being a fraction. Kimi K3, the frontier reference, is "
        "therefore the anchor for headline statements. With n = 30, one question is 3.3 percentage points, and "
        "confidence intervals are reported where they matter.")

    # ================================================================ 5.5 version control
    c.h2("Version Control and Implementation Evidence")
    c.p(f"Project repository: **{REPO_URL}** (development branch `claude/engine-build-docs-yfw9u0`, merged "
        "through a pull request into `main`). The repository contains the README, an illustrated setup "
        "walkthrough (`docs/SETUP.md`), the findings log with every measurement and its source file "
        "(`docs/FINDINGS.md`), the design critique (`docs/DESIGN_NOTES.md`), dependency files (`pyproject.toml`), "
        "every experiment configuration (`configs/`), the test suite, and the scripts that regenerate every figure "
        "and screenshot in this chapter. Raw results databases and downloaded datasets are excluded by "
        "`.gitignore`, because of their size and licence terms, and are regenerated by the scripts. The Kimi API "
        "key was supplied only through an environment variable and does not appear in any commit.")
    c.p(f"{c.next_tab()} lists the commit history as recorded by Git. Each commit corresponds to an implemented "
        "or measured increment, and the commit messages name the finding they add. The model-size sweep ran on "
        "separate machines on result branches, whose databases were merged with `camr merge`.")
    c.table("Commit history (`git log`)", ["Commit", "Date", "Author", "Change"],
            [[h, d, a, s] for h, d, a, s in hist], [1.6, 3.0, 2.0, 9.3], size=9)
    c.p("The work followed GitHub flow. Each round of work was developed on one branch and merged through a pull "
        "request whose description summarises the change and its test plan: Satasdin/CAMR#2 (engine, harness, "
        "findings) and Satasdin/CAMR#3 (CAMR Personal 0.2). Machines B–E pushed their results to their own branches, "
        "which were merged into the results database rather than into the code. Feedback from users is collected "
        "through a GitHub issue form (`.github/ISSUE_TEMPLATE/feedback.yml`). The code is released under the MIT "
        "licence. Continuous integration (`.github/workflows/release-app.yml`) runs the application tests and builds "
        "and launch-tests the downloadable application on six platforms for every change to the application. "
        f"{c.next_tab()} shows the run for the merged version. A published release (v0.2.0) attaches the six "
        "downloads.")
    repo_shots = [("1_repository.png", "Project repository on GitHub (README, licence, release)"),
                  ("2_pull_requests.png", "Pull requests used to merge each round of work"),
                  ("3_actions_run.png", "Continuous-integration run: tests, build and launch test on six platforms"),
                  ("4_release.png", "Release v0.2.0 with the six downloadable files"),
                  ("5_commits.png", "Commit history on the main branch")]
    for name, cap in repo_shots:
        if (FIG / "repo" / name).exists():
            c.figure(FIG / "repo" / name, cap + " (screenshot)", 14.5)
    c.table("Continuous-integration evidence: build and launch test per platform (GitHub Actions run 36870197366)",
            ["Target", "Runner", "Tests", "Build", "Launch test", "Result"],
            [["Windows x64", "windows-2025", "pass", "pass", "pass", "success"],
             ["Windows ARM64", "windows-11-arm", "pass", "pass", "pass", "success"],
             ["macOS Apple Silicon", "macos-15", "pass", "pass", "pass", "success"],
             ["macOS Intel", "macos-15-intel", "pass", "pass", "pass", "success"],
             ["Linux x64", "ubuntu-24.04", "pass", "pass", "pass", "success"],
             ["Linux ARM64", "ubuntu-24.04-arm", "pass", "pass", "pass", "success"]],
            [3.4, 3.2, 2.0, 2.0, 2.4, 2.9], size=9.5, key="ci")

    # ================================================================ 5.6 AI declaration
    c.h2("Author Oversight and Use of AI-Assisted Tools")
    c.p(declaration or (
        "Claude Code, an AI coding assistant provided by Anthropic, was used throughout the implementation and "
        "evaluation stages of this project. Under the student's direction it assisted with writing the engine "
        "and harness code and its tests, running the benchmark experiments on the cloud machines, producing the "
        "figures and screenshots, and drafting this chapter from the logged results. The student defined the "
        "research problem, objectives, requirements and design (Chapters 1–4), supplied the cloud model access, "
        "and decided which experiments were run, including the comparison with cloud models, the wider "
        "model-size sweep, the learned escalation policy and the use of real rather than synthetic benchmark data."))
    c.p("The student reviewed the intermediate results and screenshots as the work progressed and redirected it "
        "where it fell short; most importantly, the student required that this chapter report only experiments "
        "that had actually been run and benchmarked with real models, and an earlier draft written before the "
        "results existed was discarded for that reason. The AI-assisted output was checked through the automated "
        "test suite (102 tests), the per-query logs, the read-only inspector, and the findings log, which names "
        "the results file behind every reported number, so that each claim can be traced and re-run. The "
        "student made the final decisions and takes full responsibility for the submitted work.")

    # ================================================================ 5.7 results
    c.h2("Evaluation Results, Discussion and Limitations")
    c.p("The results are organised by research objective. Source files are in `results/` and every table is "
        "reproduced in `docs/FINDINGS.md`.")

    c.h3("Retrieval Quality (Objective ii)")
    rv = json.loads((ROOT / "results" / "retrieval_eval" / "tables" / "retrieval_eval.json").read_text())
    rr = {(r["benchmark"], r["label"]): r for r in rv["rows"]}

    def cell(bench: str, label: str, bold: bool = False) -> list[str]:
        r = rr[(bench, label)]
        v = [pct(r["support_all"]), f"{r['mean_context_tokens']:.0f}"]
        return [f"**{x}**" for x in v] if bold else v

    c.p("Before any language model was involved, the read path was evaluated on 500 HotpotQA and 500 "
        f"2WikiMultiHopQA questions against one store of {rv['store']['notes']:,} notes built from "
        f"{rv['store']['sources']:,} real paragraphs ({rv['store']['file_bytes'] / 1e6:.0f} MB). The measure was "
        "whether *both* gold supporting paragraphs reached the context, because a multi-hop question cannot be "
        "answered from one of them.")
    paths = [("Similarity only (baseline)", "control", False), ("+ recency and importance (Eq. 4.1)", "composite", False),
             ("+ gating", "gated", False), ("+ entity bridging, no gating", "bridged-ungated", False),
             ("**Similarity + gating + bridging**", "bridged-sim", True), ("Baseline @ 1,024 tokens", "control@1024", False),
             ("Similarity + gating + bridging @ 1,024", "bridged-sim@1024", True)]
    c.table("Full-support recall and tokens supplied, 500 questions each (`results/retrieval_eval/tables/retrieval_eval.json`)",
            ["Read path (512 tokens unless noted)", "2Wiki: both gold", "Tokens", "HotpotQA: both gold", "Tokens"],
            [[name, *cell("2wikimultihopqa", lab, b), *cell("hotpotqa", lab, b)] for name, lab, b in paths],
            [5.6, 2.6, 1.9, 3.0, 1.9])
    c.figure(FIG / "fig_retrieval_hotpotqa.png", "HotpotQA: change in full-support recall and tokens supplied relative to the baseline")
    w0, w1 = rr[("2wikimultihopqa", "control")], rr[("2wikimultihopqa", "bridged-sim")]
    c.p(f"Entity bridging was the decisive mechanism on 2WikiMultiHopQA: full-support recall rose from "
        f"{pct(w0['support_all'])} to {pct(w1['support_all'])} at the same budget, with "
        f"{100 * (1 - w1['mean_context_tokens'] / w0['mean_context_tokens']):.0f}% fewer tokens. Its questions are "
        "compositional (for example, *who is the father of the director of film X?*). The second paragraph shares "
        "almost no words with the question, so similarity search cannot find it, but the first paragraph names it, "
        "and that is the hop bridging follows. On HotpotQA the gain depended on the budget: none at 512 tokens, with "
        "11% fewer tokens, and +3.2 points at 1,024 tokens, with 26% fewer tokens. On both benchmarks the composite "
        "score of Equation 4.1 lowered recall. On independent questions, recency and importance carry no signal "
        "about the current question, which confirms the risk anticipated in section 4.4.7.")

    c.h3("Gap Closed and the Residual Gap (Objective iv)")
    c.table("Accuracy by condition, pilot sample (`results/pilot/tables/summary.json`, `gap_vs_kimi.md`)",
            ["Task (n)", "0.5B alone", "0.5B + CAMR", "gpt-oss-20b", "20B + same notes", "Kimi K3", "Kimi K3 + CAMR"],
            [["Single-hop, PopQA (30)", "10.0%", "**66.7%**", "23.3%", "76.7%", "66.7%", "83.3%"],
             ["Multi-hop, HotpotQA (30)", "6.7%", "**30.0%**", "30.0%", "53.3%", "53.3%", "63.3%"],
             ["Reasoning, GSM8K (12)", "33.3%", "16.7%", "100%", "100%", "100%", "100%"]],
            [3.6, 1.8, 2.0, 2.0, 2.4, 1.7, 2.4])
    c.p("Against Kimi K3, the engine closed the **entire** single-hop gap (gap closed 1.00) and **half** of the "
        "multi-hop gap (0.50, 95% CI 0.20–0.90). It closed none of the reasoning gap (−0.25). The 0.5B model with "
        "CAMR answered single-hop questions in 1.5 s against Kimi's 7.7 s. The residual gap (20B with the same "
        "notes minus 0.5B with them) was 10.0 points on single-hop, 23.3 on multi-hop and 83.3 on reasoning: "
        "the more a task needs reading and reasoning, the more model size still buys. This answers research "
        "question iii. Memory helps knowledge-bound tasks and does not help reasoning-bound ones. The same notes "
        "also lifted the frontier model (Kimi K3 rose from 66.7% to 83.3% on PopQA), so the engine helps beside any "
        "model.")
    c.figure(REPORT / "residual_gap.png", "Residual gap: accuracy of the 0.5B model and of gpt-oss-20b when both read the "
             "same notes (pilot)", 12.0)

    c.h3("Error Analysis: Where Answers Are Lost")
    c.p(f"{c.next_tab()} follows each question through the pipeline (from `tables/coverage.md`): is the gold "
        "answer in the store, among the retrieved candidates, in the context actually sent, and was the answer "
        "correct? The last column is accuracy *given* that the answer was in the context.")
    c.table("Failure decomposition for the 0.5B model with the full engine (pilot)",
            ["Benchmark (n)", "Answer in store", "In candidates", "In context", "Correct", "Correct when in context"],
            [["PopQA (30)", "93.3%", "93.3%", "90.0%", "66.7%", "74.1%"],
             ["PopQA, 128-token budget (30)", "93.3%", "93.3%", "86.7%", "76.7%", "84.6%"],
             ["HotpotQA (30)", "96.7%", "93.3%", "83.3%", "30.0%", "36.0%"]],
            [4.4, 2.3, 2.3, 2.1, 2.0, 2.8], size=9.5)
    c.p("Retrieval was rarely the problem. On HotpotQA the answer reached the context for 83% of questions, but "
        "the 0.5B model used it correctly only 36% of the time. Of its 21 misses, 16 (76%) had the gold answer in "
        "front of it. On PopQA a smaller budget raised correct-when-in-context from 74% to 85%: fewer notes, less "
        "distraction. Errors therefore fall into three groups, illustrated in "
        f"{c.next_tab(2)}: **correct** answers read from the note; **incomplete** answers that pick a related "
        "entity from the right evidence; and **unsupported** answers, where the model ignored or lacked the "
        "evidence and fell back on its own (wrong) knowledge.")
    c.figure(REPORT / "error_funnel.png", "Where answers are lost for the 0.5B model with CAMR: store, candidates, "
             "context and correct answer")
    c.table("Examples of correct, incomplete and unsupported answers (from the query logs)",
            ["Type", "Question (abridged)", "Gold", "Answer given"],
            [["Correct", "Who was the screenwriter for *The Graduate*?", "Calder Willingham, Buck Henry",
              "0.5B + CAMR: Buck Henry (alone: Linda Wachowski)"],
             ["Correct", "McLaren MP4/11 was driven by which Finnish driver?", "Mika Häkkinen",
              "0.5B + CAMR: Mika Häkkinen (gpt-oss-20b alone: Kimi Räikkönen)"],
             ["Incomplete", "City with the Nusretiye Clock Tower and …?", "Istanbul, Turkey",
              "Beyoğlu (a district of Istanbul; evidence was in context)"],
             ["Incomplete", "Event where Tyson Gay and Rodney Martin both represented the US?", "4 × 100 m relay",
              "100 m sprint (evidence in context)"],
             ["Unsupported", "Who was the director of *The Loudwater Mystery*? (no memory)", "Walter West",
              "0.5B alone: John Sturges (invented)"],
             ["Unsupported", "When is my dentist appointment? (empty memory)", "Thursday 9 October 14:30",
              "next Monday (invented); with the note: correct"]],
            [2.5, 5.3, 3.1, 5.0], size=9)

    c.h3("Knowledge Growth with Frozen Weights")
    c.p("The knowledge corpus was fed into one store in three stages, and the same frozen 0.5B model answered "
        f"the same questions after each stage ({c.next_fig()}). On long-tail facts, accuracy rose from 6.7% "
        "to 16.7%, 33.3% and 66.7% as memory grew to 25%, 50% and 100%. That matches Kimi K3 and is roughly three "
        "times the 20B model. Median decode speed stayed between 44 and 63 tokens/s at every stage "
        f"({c.next_fig(2)}). The cost of memory is in prefill (270–460 extra prompt tokens) and a bounded 3–17% "
        "per-token decode slowdown, measured across the model sweep, from attending over a longer prompt.")
    c.figure(FIG / "fig_growth_accuracy.png", "Accuracy of the frozen 0.5B model as the memory store grows")
    c.figure(FIG / "fig_decode_speed.png", "Decode speed of the frozen 0.5B model at each store size")

    c.h3("Ablation and Token Budget (Objective v)")
    c.table("Ablation and budget sweep, 0.5B model (`ablation.md`, `budget_sweep.md`)",
            ["Variant", "Single-hop acc. (tokens)", "Multi-hop acc. (tokens)", "Reasoning acc.", "Answer time (single / multi)"],
            [["Control: similarity only, fixed budget", "56.7% (464)", "26.7% (472)", "–", "2,343 / 2,469 ms"],
             ["Full engine: gating + bridging", "66.7% (267)", "30.0% (380)", "–", "688 / 1,480 ms"],
             ["Budget 0", "10.0% (0)", "3.3% (0)", "16.7%", "–"],
             ["**Budget 128**", "**76.7% (82)**", "30.0% (86)", "16.7%", "–"],
             ["Budget 512", "66.7% (267)", "**33.3% (380)**", "20.8%", "–"],
             ["Budget 1,024", "66.7% (434)", "26.7% (557)", "16.7%", "–"]],
            [4.6, 3.0, 3.0, 2.2, 3.1])
    c.figure(REPORT / "budget_curve.png", "Accuracy of the 0.5B model by memory budget (pilot)", 12.5)
    c.p("The full engine was more accurate than the control and 1.7–3.4 times faster per answer, because gating "
        "sent fewer tokens. For a 0.5B model, the budget that maximised gap closed per token was **128 tokens** "
        "for single-hop facts. Larger budgets *lowered* accuracy, because the small model was distracted by extra "
        "notes. Multi-hop questions peaked at 512 tokens, and reasoning never benefited. This answers research question "
        "iv: the best budget depends on the task type and the model, which motivated the learned policy.")

    c.h3("Small Models on Their Own: the Baseline Ranking")
    c.p(f"Before memory, the 19 candidate models were ranked by their own accuracy ({c.next_fig()}). The ranking "
        "follows size, but loosely: the rank correlation between parameter count and mean accuracy was ρ = 0.82. "
        "gemma3:12b led (51.7% mean), followed by qwen2.5:7b (47.8%) and gemma2:9b (47.2%); qwen2.5:0.5b was last "
        "(13.9%). The models' weakness was knowledge, not arithmetic. Alone, no model knew more than 33.3% of the "
        "long-tail facts (Kimi K3 knew 66.7%), and the mean across all 19 was 17.7%. Several, however, already "
        "scored 75–92% on GSM8K. Multi-hop questions were also out of reach: the best was qwen2.5:14b at 46.7%, "
        "below Kimi K3's 53.3%. Model families differed markedly at the same size. qwen2.5:3b was 16th of 19 on "
        "its own (6.7% on facts) while llama3.2:3b was 8th, and mistral:7b was 14th, below several 1–3B models.")
    c.figure(REPORT / "rank_alone.png", "Ranking of the 19 small models alone (no memory): mean accuracy and per-benchmark "
             "scores, with Kimi K3 for reference", 14.0)
    c.p(f"With CAMR the ranking changed ({c.next_fig()}). The size advantage on facts largely disappeared: the "
        "rank correlation between size and long-tail accuracy fell from 0.67 (p = 0.002) alone to 0.35 (p = 0.14, "
        "not significant) with memory, and mean fact accuracy rose from 17.7% to 74.2%. The models that gained "
        "most climbed the ranking: phi4-mini moved from 10th to 5th, falcon3:3b from 17th to 10th, and qwen2.5:14b "
        "from 5th to 2nd. Models with strong parametric knowledge but weaker reading of supplied evidence fell: "
        "gemma2:9b from 3rd to 8th, llama3.1:8b from 4th to 9th. Multi-hop accuracy with memory still tracked size "
        "(ρ = 0.78), because combining two pieces of evidence depends on the model as a reader. "
        f"{c.next_fig(2)} shows each model's gain and {c.next_fig(3)} its speed.")
    c.figure(REPORT / "rank_with_camr.png", "Ranking of the same 19 models with CAMR memory", 14.0)
    c.figure(REPORT / "gain_per_model.png", "What memory adds to each model, per benchmark (percentage points)")
    c.figure(REPORT / "speed_vs_accuracy.png", "Speed against accuracy with CAMR on long-tail facts; the shaded region is "
             "faster than the cloud model", 14.0)

    c.h3("Which Model Sizes Suit the Engine")
    c.p(f"The same store, questions and ceilings were used with {n_models} small models from 0.5B to "
        f"{sweep[-1]['params']} parameters ({c.next_tab()}, {c.next_fig()}). Accuracies are comparable across "
        "machines; decode speeds are comparable only within a machine.")
    lat = sweep_latency()
    rows = []
    for r in sweep:
        p, h, g = r.get("popqa", {}), r.get("hotpotqa", {}), r.get("gsm8k", {})
        rows.append([f"{r['model']} ({r['params']}, {r['quant']})",
                     f"{pct(p.get('floor'))[:-1]} → {pct(p.get('with_memory'))[:-1]}",
                     f"{pct(h.get('floor'))[:-1]} → {pct(h.get('with_memory'))[:-1]}",
                     f"{pct(g.get('floor'))[:-1]} → {pct(g.get('with_memory'))[:-1]}",
                     f"{p.get('decode_tok_s_floor', 0):.1f} → {p.get('decode_tok_s_memory', 0):.1f}",
                     f"{lat.get(r['model'], float('nan')):.1f}"])
    rows.append(["*Kimi K3 (cloud), no memory*", "*66.7*", "*53.3*", "*100*", "–", "*7.7*"])
    c.table("Model-size sweep: alone → with CAMR (`results/pilot/tables/model_sweep.json`)",
            ["Model (parameters, quantisation)", "PopQA (%)", "HotpotQA (%)", "GSM8K (%)", "Decode tok/s (PopQA)",
             "s / answer with CAMR (PopQA)"],
            rows, [4.5, 2.3, 2.3, 2.3, 2.3, 2.2], size=9, key="sweep")
    c.figure(FIG / "fig_model_sweep.png", "Accuracy without and with CAMR by model size, against the Kimi K3 ceiling")
    c.p(SWEEP_DISCUSSION)

    h200 = hotpot200()
    if h200:
        c.h3("Confirmation at Larger Scale: 200 HotpotQA Questions")
        c.p("To test whether the pilot's multi-hop results held beyond 30 questions, the study was repeated on 200 "
            "HotpotQA questions with the read path fixed in advance (similarity, gating and bridging, 512 tokens). "
            "Nothing was tuned on these questions. Three small models and Kimi K3 were run with and without the "
            "same notes. 95% confidence intervals come from 2,000 bootstrap resamples of the questions.")
        c.table("HotpotQA, n = 200: exact match, alone and with CAMR (`results/hotpot200`)",
                ["Model", "Alone", "With CAMR", "Gain (95% CI)", "s / answer with CAMR"], h200["rows"],
                [3.6, 2.4, 2.6, 4.4, 2.9])
        c.figure(REPORT / "hotpot200.png", "HotpotQA, 200 held-out questions: exact match alone and with the same notes, "
                 "95% bootstrap intervals", 13.5)
        c.p(h200["text"])

    c.h3("Learning When to Use Memory and When to Escalate")
    fixed = {k: v for k, v in rl["fixed"].items()}
    off = rl["learned_offline"]
    c.p("A single fixed configuration cannot be best for every question. The learned policy chose an action per "
        f"question from pre-answer features and was evaluated on the {rl['n_test']} held-out questions "
        f"({c.next_tab()}, {c.next_fig()}).")
    casc = [r for r in rl["cascade"] if abs(r["stage1_cloud_cost"] - 0.3) < 1e-9 and abs(r["threshold"] - 0.2) < 1e-9][0]
    c.table("Engine policies on the held-out split (`results/learn/tables/rl_policies.md`, `rl_cascade.md`)",
            ["Policy", "Accuracy", "Sent to cloud", "Mean s / answer"],
            [["Always 0.5B alone", pct(fixed["always local"]["accuracy"]), "0%", f"{fixed['always local']['mean_latency_s']:.1f}"],
             ["Always 0.5B + 128 tokens", pct(fixed["always mem128"]["accuracy"]), "0%", f"{fixed['always mem128']['mean_latency_s']:.1f}"],
             ["Always 0.5B + 512 tokens", pct(fixed["always mem512"]["accuracy"]), "0%", f"{fixed['always mem512']['mean_latency_s']:.1f}"],
             ["Always Kimi K3", pct(fixed["always cloud"]["accuracy"]), "100%", f"{fixed['always cloud']['mean_latency_s']:.1f}"],
             ["Learned router (ridge, cloud cost 0.3)", pct(off["accuracy"]), pct(off["cloud_share"]), f"{off['mean_latency_s']:.1f}"],
             ["Learned router (LinUCB, after 5 epochs)", pct(rl["curve"][-1]["accuracy"]), pct(rl["curve"][-1]["cloud_share"]), f"{rl['curve'][-1]['mean_latency_s']:.1f}"],
             ["**Router + grounding cascade**", f"**{pct(casc['accuracy'])}**", pct(casc["cloud_share"]), f"{casc['mean_latency_s']:.1f}"],
             ["Oracle (best action in hindsight)", pct(rl["oracle"]["accuracy"]), pct(rl["oracle"]["cloud_share"]), f"{rl['oracle']['mean_latency_s']:.1f}"]],
            [6.6, 2.8, 3.0, 3.4])
    c.figure(FIG / "fig_learned_policy.png", "Learned routing compared with fixed choices, and the LinUCB learning curve over 5 epochs")
    c.p("The policy learned without supervision to send every reasoning question to the cloud (12 of 12, all "
        "correct) and to answer factual questions locally with a small budget. With the grounding cascade, which "
        "answers locally first and escalates when the answer's words are not found in its notes, the hybrid "
        f"reached {pct(casc['accuracy'])} against always-Kimi's {pct(fixed['always cloud']['accuracy'])}. "
        f"{100 - 100 * casc['cloud_share']:.0f}% of questions never left the device, and mean latency was "
        f"{fixed['always cloud']['mean_latency_s'] / casc['mean_latency_s']:.1f} times lower. LinUCB, which sees "
        "only the outcome of the action it chose, rose from 13.9% to 54.2% held-out accuracy within the first 40 "
        "episodes and then fluctuated between 54% and 64% over the five epochs. The gap to the oracle (79.2%) is mostly on "
        "multi-hop questions, where pre-answer features cannot predict whether the small model will read the "
        "evidence correctly.")

    c.h3("Cost on the Device (Research Question v)")
    t = profile["treatment"]
    c.p(f"On machine A, median end-to-end latency was {profile['floor']['median_e2e_ms']:.0f} ms for the 0.5B "
        f"model alone and {t['median_e2e_ms']:.0f} ms with CAMR. The engine added a median of "
        f"{profile['added_latency_ms']:.0f} ms and about {t['median_prompt_tokens'] - profile['floor']['median_prompt_tokens']:.0f} "
        f"prompt tokens. Peak memory was {profile['peak_rss_mb_engine_process']:.0f} MB for the engine and "
        f"{profile['peak_rss_mb_model_runtime']:.0f} MB for the model runtime, and the store file was "
        f"{profile['store_file_mb']:.1f} MB. NFR-02 was **not met**: retrieval was "
        f"{100 * profile['retrieval_share_of_e2e']:.0f}% of answer time against a 10% target. In isolation the "
        "engine's retrieval took 29 ms (embedding 21.5 ms, search 6.2 ms, bridging 1.2 ms, packing 0.4 ms). The "
        "rest was contention between the embedder and the model runtime for the same four cores. Partitioning "
        "the threads cut the p90 from 157 ms to 50 ms. Because a 0.5B model generates in about 180 ms, the 10% "
        "target is reachable only for models whose generation takes 450 ms or more, roughly 1.5B parameters and "
        "above on this CPU.")
    c.p("The large local alternative behaved worse on the same device. gpt-oss:20b decoded at about 6.3 tokens/s "
        "and needed 19.5–38 s per answer. When a 0.7 GB process ran beside it, it collapsed to 0.4–0.9 tokens/s "
        "as its memory-mapped weights were evicted. On a 16 GB device, a small model with external memory is the "
        "practical design, not merely the cheaper one.")

    c.h3("From Desktop Assistant to Mobile: Progress")
    c.p("The deployment work progressed in three steps. (1) The engine was first exposed as a command (`camr ask`) "
        "over a user's own notes (⟦askempty⟧ and ⟦ask⟧). (2) It then became **CAMR Personal**, a desktop "
        "application released for six platforms (⟦ci⟧). (3) A **mobile prototype** for "
        "Android was then started, following the application case in `docs/ANDROID_ASSISTANT.md`: the same idea "
        "on the device people carry, a phone assistant that grows with its user.")
    c.table("Android prototype: what exists and what has been verified",
            ["Component", "Implementation", "Status"],
            [["Memory engine", "Kotlin port of the read and write paths: SQLite store with float32 vectors, exact "
              "cosine search, gating, entity bridging, greedy token budget, chat as memory, 👍 learning",
              "Compiles; 6 JVM unit tests pass, including token counting identical to the Python engine"],
             ["Embedder", "MediaPipe Text Embedder (Universal Sentence Encoder, 6 MB) bundled in the app", "Builds; gating "
              "threshold for this embedder not yet calibrated"],
             ["Language model", "On-device MediaPipe/LiteRT model file chosen by the user (e.g. Gemma 3 1B, Qwen2.5 "
              "1.5B), or Ollama on the user's computer over Wi-Fi", "Builds; not run"],
             ["Interface", "Jetpack Compose, same design language as the desktop app; chat, recall card, memory and "
              "settings screens; 'Share to CAMR' from any app", "Builds; not run"],
             ["Package", "Release APK, arm64-v8a, 57 MB (Android 8.0+)", "Built; not installed on a device"]],
            [2.8, 7.6, 5.5], size=9)
    c.p("The prototype has **not** been run on a phone or emulator: the build environment had no virtualisation "
        "support. Its accuracy, speed, memory use and battery cost on real handsets are therefore unmeasured, "
        "and development was paused to concentrate on the desktop application. Measuring them is set out as future "
        "work in Chapter 6.")

    c.h3("Limitations")
    c.items(["**Sample size.** Pilot samples were 30/30/12 questions per benchmark. One question is 3.3 points, "
             "so differences of one or two questions are within noise. Confidence intervals are reported for "
             "gap closed. The multi-hop results were confirmed on 200 questions, and the retrieval "
             "study used 500 questions per benchmark; the single-hop and reasoning results rest on the pilot sample.",
             "**Stochastic cloud ceiling.** Kimi accepts only temperature 1, so its scores are single samples. "
             "Small-model floors also varied between repeats (20/30 identical answers), so floors are best read as "
             "a range.",
             "**Oracle-like PopQA corpus.** PopQA documents are the subject's own Wikipedia summary, which favours "
             "retrieval. HotpotQA, with eight distractors per question and extra distractor paragraphs, is the "
             "more realistic test.",
             "**Benchmark questions are independent.** Recency could not show a benefit. A sessioned benchmark "
             "(e.g. LongMemEval) would be needed to evaluate it fairly.",
             "**Write policy.** Only verbatim notes were evaluated end to end. The structured policy is "
             "implemented and tested but was not run at scale.",
             "**Hardware.** All measurements are from CPU cloud containers of laptop class, not from a physical "
             "laptop or phone. Decode speeds differ between machines.",
             "**No user study yet.** The application was tested for correct and safe behaviour, not for usefulness or "
             "usability with real users, and the Android prototype has not run on a device.",
             "**Policy learning.** The learned policy was trained on 144 questions with costs set by the researcher. "
             "Its advantage over always-Kimi is 1.4 points, which is within sampling noise; the robust result is "
             "equal accuracy at 71% on-device use and lower latency."])
    c.p("Conclusions, recommendations and future work, including feedback from real users of CAMR Personal and a "
        "phone version of the assistant, are presented in Chapter 6.")

    return c.save(out)


# Interpretation of the 200-question study; written once its results are in (results/hotpot200).
def H200_TEXT(res: dict) -> str:  # noqa: N802 - kept as a named hook for the chapter text
    k = res.get("Kimi K3 (cloud)")
    l3, q15, q05 = res.get("llama3.2:3b"), res.get("qwen2.5:1.5b"), res.get("qwen2.5:0.5b")
    parts = ["The larger sample confirmed the pilot. Every small model gained substantially, and every 95% interval "
             "excludes zero."]
    if l3 and k:
        parts.append(f"With CAMR, llama3.2:3b reached {pct(l3[1])} exact match against Kimi K3's closed-book "
                     f"{pct(k[0])} (n = {k[3]}), and answered in {l3[2]:.1f} s against {k[4]:.1f} s. On multi-hop questions, a 3B "
                     "model on a laptop CPU with memory therefore matches a frontier cloud model at about a third of "
                     "the answer time.")
    if q15 and q05:
        parts.append(f"qwen2.5:1.5b reached {pct(q15[1])} and qwen2.5:0.5b {pct(q05[1])}. The ordering by size is the "
                     "pilot's finding that multi-hop gains depend on how well the model reads the evidence.")
    if k and k[1] is not None:
        parts.append(f"With the same notes, Kimi K3 rose from {pct(k[0])} to {pct(k[1])}. The residual gap between "
                     "the best small model and the frontier model reading the same evidence is the share of multi-hop "
                     "performance that memory cannot buy.")
    parts.append("Compared with the pilot (30 questions: 30.0%, 50.0% and 56.7% for the three models with memory), "
                 "the estimates moved by at most 9 points, within the pilot's uncertainty. Accuracy was identical "
                 "when the 0.5B run was repeated for clean timings (26.5% both times).")
    return " ".join(parts)

# Filled in after the B/D machines are merged; kept as data so the text matches the table.
SWEEP_DISCUSSION = (
    "All 19 models gained on knowledge tasks: +43 to +73 points on PopQA and +10 to +40 on HotpotQA. With CAMR, 18 "
    "of 19 reached or beat Kimi K3 on long-tail facts; only llama3.2:1b (63.3%) fell short. Parametric knowledge "
    "barely grew with size: even the 12–15B models alone knew 13–33% of the long-tail facts, while every model "
    "from 1.5B upward reached 70–80% with memory. Multi-hop questions depended on the model as a reader. Seven of 19 "
    "reached Kimi K3's 53.3%: llama3.2:3b, gemma3:4b and five of the eight 7–15B models, with the best at 63% "
    "(qwen2.5:14b, gemma3:12b). Family mattered as much as size, since mistral:7b reached only 43.3%. Speed set the "
    "upper bound. On the 4-core CPU, every model of 7B or more with memory answered more slowly than Kimi K3 "
    "(8–24 s against 7.7 s on PopQA), so **1.5–4B is the range that suits the engine on this class of device**: "
    "faster than the cloud model, at or above it on facts, and at it on multi-hop from about 3B. Worked-example "
    "memory for maths helped 8 models, was neutral for 4 and hurt 7, depending on family rather than size, so "
    "reasoning routing must be learned per model. A few runs on machine D had one to three queries fail with a "
    "runtime error; their accuracy is over the answered questions.")


def to_pdf(docx_path: Path) -> Path:
    profile = docx_path.parent / ".lo_profile"
    subprocess.run(["soffice", f"-env:UserInstallation=file://{profile.resolve()}", "--headless",
                    "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
                   check=True, capture_output=True, timeout=600)
    return docx_path.with_suffix(".pdf")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", required=True, help="the proposal .docx whose styles are reused")
    ap.add_argument("--out", default="build/Chapter5_CAMR")
    ap.add_argument("--declaration", help="text file with the student's own AI-use declaration")
    a = ap.parse_args()
    decl = Path(a.declaration).read_text().strip() if a.declaration else None
    path = build(Path(a.template), Path(a.out), decl)
    print("wrote", path)
    print("wrote", to_pdf(path))


if __name__ == "__main__":
    main()
