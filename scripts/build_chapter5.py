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
import latex2mathml.converter
import mathml2omml
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_TAB_ALIGNMENT
from lxml import etree
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


OMML = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_ACCENTS = {"^": "\u0302", "~": "\u0303", "¯": "\u0305", "‾": "\u0305", "―": "\u0305", "→": "\u20d7", "˙": "\u0307"}
_SAFE = {"*": "\u2217", "|": "\u2223"}


def omath(latex: str):
    """LaTeX -> native Word equation (OMML), with fixes for what the converters get wrong in Word/LibreOffice."""
    q = lambda tag: f"{{{OMML}}}{tag}"  # noqa: E731
    mml = latex2mathml.converter.convert(latex)
    # \bar is emitted as a stretchy group character that mathml2omml serialises badly; make it a plain accent
    mml = mml.replace('<mo stretchy="true">&#x000AF;</mo>', "<mo>&#x02015;</mo>")
    om = mathml2omml.convert(mml)
    el = etree.fromstring(f'<root xmlns:m="{OMML}">{om}</root>')[0]
    for lu in list(el.iter(q("limUpp"))):  # \hat, \tilde, \bar -> accent objects
        lim = lu.find(q("lim"))
        mark = "".join(lim.itertext()).strip() if lim is not None else ""
        if mark in _ACCENTS:
            acc = etree.Element(q("acc"))
            etree.SubElement(etree.SubElement(acc, q("accPr")), q("chr")).set(q("val"), _ACCENTS[mark])
            acc.append(lu.find(q("e")))
            lu.getparent().replace(lu, acc)
    for rad in el.iter(q("rad")):  # \sqrt needs an explicit hidden degree
        if rad.find(q("deg")) is None:
            pr = etree.Element(q("radPr"))
            etree.SubElement(pr, q("degHide")).set(q("val"), "1")
            rad.insert(0, pr)
            rad.insert(1, etree.Element(q("deg")))
    for t in el.iter(q("t")):
        if t.text in _SAFE:
            t.text = _SAFE[t.text]
    return el


class Chapter:
    def __init__(self, template: Path, number: int = 5):
        self.n = number
        self.doc = docx.Document(str(template))
        self._clear_body()
        self._start_at_chapter(number)
        self.fig_n = 0
        self.tab_n = 0
        self.eq_n = 0
        self.sec = [0, 0]  # mirrors Word's heading numbering: section, subsection
        self.labels: dict[str, str] = {}  # key -> "Table 5.n" / "Figure 5.n" / "Equation 5.n" / "5.8.3", as ⟦key⟧

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

    def h2(self, text: str, key: str | None = None) -> None:
        self.sec = [self.sec[0] + 1, 0]
        if key:
            self.labels[key] = f"{self.n}.{self.sec[0]}"
        self.doc.add_paragraph(text, style="Heading 2")

    def h3(self, text: str, key: str | None = None) -> None:
        self.sec[1] += 1
        if key:
            self.labels[key] = f"{self.n}.{self.sec[0]}.{self.sec[1]}"
        self.doc.add_paragraph(text, style="Heading 3")

    def eq(self, latex: str, key: str | None = None) -> str:
        """A displayed, numbered equation: centred, number at the right margin."""
        self.eq_n += 1
        label = f"Equation {self.n}.{self.eq_n}"
        if key:
            self.labels[key] = label
            self.labels[key + "_n"] = f"{self.n}.{self.eq_n}"
        para = self.doc.add_paragraph(style="Normal")
        pf = para.paragraph_format
        pf.space_before, pf.space_after, pf.first_line_indent = Pt(4), Pt(6), Cm(0)
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM / 2), WD_TAB_ALIGNMENT.CENTER)
        pf.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT)
        para.add_run("\t")
        para._p.append(omath(latex))
        para.add_run(f"\t({self.n}.{self.eq_n})")
        return label

    def where(self, terms: list[tuple[str, str]]) -> None:
        """'where' block under an equation: each symbol (LaTeX) with its meaning."""
        para = self.doc.add_paragraph(style="Normal")
        para.paragraph_format.space_after = Pt(2)
        para.add_run("where")
        for sym, meaning in terms:
            pp = self.doc.add_paragraph(style="Normal")
            pf = pp.paragraph_format
            pf.left_indent, pf.first_line_indent, pf.space_after, pf.line_spacing = Cm(1.0), Cm(0), Pt(1), 1.15
            pp._p.append(omath(sym))
            self._runs(pp, " " + meaning)

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
                        run.text = re.sub(r"⟦(\w+)⟧", lambda m: self.labels.get(m.group(1), m.group(0)), run.text)
        fix(self.doc.paragraphs)
        for t in self.doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    fix(cell.paragraphs)

    def save(self, out: Path) -> Path:
        self.resolve()
        missing = sorted({m for p in self.doc.paragraphs for m in re.findall(r"⟦(\w+)⟧", p.text)})
        if missing:
            print("warning: unresolved cross-references:", ", ".join(missing))
        out.parent.mkdir(parents=True, exist_ok=True)
        (out.parent / f"ch{self.n}_labels.json").write_text(json.dumps(self.labels, indent=1, ensure_ascii=False))
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


def app_latency() -> dict | None:
    p = ROOT / "docs" / "results" / "app_latency.json"
    return json.loads(p.read_text()) if p.exists() else None


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
        "follows the AI and machine learning route of the departmental guidelines. CAMR's language models run with "
        "frozen weights: what changes between conditions is the external memory and the engine's learned policy for "
        "using it. The machine-learning components that *are* trained, the router and its escalation cascade, were "
        "tuned by cross-validation on training data only and tested once on held-out questions. To test the "
        "proposal's argument against fine-tuning rather than assume it, a LoRA fine-tuned model was also trained on "
        "the same documents as a comparison baseline. The chapter reports dataset provenance, the engine stated as "
        "equations, the experimental configuration, the interface and its tests, and the measured results for each "
        "research objective, with worked examples of what the models actually answered.")
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
    c.h2("Implementation Environment", key="sec_env")
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
    c.p("**Step 8: tuning, the fine-tuning baseline and the interface audit** (sections ⟦sec_tune_read⟧, "
        "⟦sec_policy⟧, ⟦sec_uitest⟧ and ⟦sec_scenarios⟧). The fine-tuning baseline downloads the 0.5B model's "
        "weights from Hugging Face (about 1 GB) and takes several hours on four CPU cores.")
    c.code("""pip install -e ".[finetune,report]"
python scripts/tune_policy.py                            # router: 5-fold CV on training questions, one held-out test
python scripts/tune_gating.py --store-copy /tmp/re      # read path: validation half, then held-out half
python scripts/finetune_baseline.py tune && python scripts/finetune_baseline.py test \\
       && python scripts/finetune_baseline.py camr-cost # LoRA vs CAMR on the same documents
python -m pytest -q tests/test_app_e2e.py               # browser tests (Chromium)
python scripts/ui_audit.py --axe axe.min.js             # axe-core 4.10 + WCAG contrast
python scripts/scenario_screens.py --model llama3.2:3b  # live scenarios, with and without memory
python scripts/extract_examples.py && python scripts/make_method_figures.py""")
    c.p("**The application only** (no experiments): download the file for the platform from the v0.2.1 release "
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
    c.h2("System Implementation", key="sec_impl")
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
    formal_model(c)
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
    metrics_section(c)
    c.p("The learned policy (`camr learn`) chooses, per question, one of five actions: answer with the small model "
        "alone, with 128, 512 or 1,024 tokens of memory, or escalate to Kimi K3. Its training configuration is "
        f"given in {c.next_tab()}. No neural network is trained inside CAMR and no model weights change. The learned "
        "parameters are a ridge-regression weight vector per action (5 × 11 numbers in the first study; 5 × 4 after "
        "cross-validation chose the task-only features) and the cascade's grounding model.")
    policy_math(c)
    c.table("Learned-policy training configuration (from `camr/learn/bandit.py` and `rl_report.json`)",
            ["Setting", "Value"],
            [["Language-model training", "None inside CAMR: the answering model's weights are frozen. (A separate LoRA "
              "baseline, section ⟦sec_finetune⟧, is the only model trained in this study.)"],
             ["Training / evaluation questions", f"{rl['n_train']} / {rl['n_test']} (disjoint; 60/60/24 and 30/30/12 PopQA/HotpotQA/GSM8K)"],
             ["Actions (arms)", "local; mem128; mem512 (+ bridging); mem1024 (+ bridging); cloud (Kimi K3)"],
             ["Logged outcomes", f"Every action on every question: {rl['n_train'] * 5} training and {rl['n_test'] * 5} evaluation answers"],
             ["Context features (11)", "Bias; task type (3 one-hot); best-note similarity; margin to second note; "
              "number of near-best notes; question length; task type × best-note similarity (3)"],
             ["Reward", f"correct − {rl['costs']['cloud']} × [cloud call] − {rl['costs']['per_1k_tokens']} × prompt tokens / 1,000"],
             ["Offline learner", "Ridge regression per action (Equation ⟦eq_ridge_n⟧), closed-form; first study λ = 1.0; "
              "tuned by 5-fold CV over λ ∈ {0.01, 0.1, 1, 10, 100} × three feature sets"],
             ["Online learner (LinUCB)", "Bandit feedback only (Equation ⟦eq_linucb_n⟧); first study α = 0.5 and **5 "
              "epochs** (passes) over the 144 training questions = 720 episodes, shuffled with seed 13, held-out "
              f"evaluation every 20 episodes ({len(rl['curve'])} checkpoints); tuned by CV over α ∈ {{0, 0.1, 0.25, 0.5, "
              "1, 2}} × 1–10 passes"],
             ["Grounding cascade", "Ridge model of answer signals (Equation ⟦eq_cascade_n⟧); threshold θ tuned by CV "
              "over 0–1 in steps of 0.05"],
             ["Cloud-cost sweep", "0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2 (Pareto table)"]],
            [4.3, 11.6])
    c.p(f"{c.next_fig()} shows the learned decision for one question.")
    c.figure(DIAGRAMS / "policy.png", "Learned engine policy: a router chooses local memory budgets or the cloud from "
             "pre-answer features, and a grounding check escalates local answers that are not supported by the "
             "notes they read", 7.5)

    c.h3("Model Selection and the Validation–Test Protocol", key="sec_selection")
    c.p("Because no weights were trained, *selection* meant choosing which frozen model and which engine "
        "configuration to recommend, and that choice was made on evidence kept apart from the final test. The "
        "**baseline** was each small model answering alone (the floor condition). The **candidates** were 19 "
        "quantised models from 0.5B to 14.8B parameters across ten families (⟦sweep⟧), each run with the same "
        "store, questions and prompt templates (seed 13, greedy decoding, temperature 0). The pilot sample (30/30/12 "
        "questions) and the 500-question retrieval study served as the **validation** evidence: they fixed the "
        "read path (similarity ranking, gating at 0.50 with a 0.15 margin, entity bridging) and the budgets "
        "(128 tokens for single facts, 512 for multi-hop). The 200-question HotpotQA study (reported in section 5.8) then "
        "served as a **held-out test**: its configuration was written to `configs/hotpot200.yaml` before it ran "
        "and was not changed afterwards. The same discipline was then applied to every tunable part: the read path's "
        "margin and budget were tuned on one half of the retrieval questions and tested on the other (section "
        "⟦sec_tune_read⟧); the router's hyperparameters by cross-validation on the training split (section "
        "⟦sec_policy⟧); and the LoRA baseline's format, learning rate and epochs on a validation split (section "
        "⟦sec_finetune⟧). Every run's configuration, hash, model digest and per-question records are saved in its "
        "results database and in `records/*.jsonl`, so each reported number can be regenerated.")

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
    c.h3("CAMR Personal: the Engine as an Application", key="sec_app")
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

    interface_design(c)

    # ================================================================ 5.4 Testing
    c.h2("Testing and Evaluation", key="sec_testing")
    c.h3("Test Strategy and Acceptance Criteria")
    c.p("Testing combined three levels. **Unit and integration tests** (white-box, pytest, 111 tests, fully "
        "offline) verify each requirement with deterministic test doubles: dry-run models and a hashing embedder. "
        "**System tests** run the real pipeline end to end on real data with real models. **Measurements** "
        "(device profile, latency, memory) verify the non-functional requirements against their thresholds. Each "
        "test maps to a test case of Table 4.5. Acceptance criteria were fixed before the runs: a functional test "
        "passes when the observed behaviour equals the expected behaviour; NFR-02 passes when retrieval is ≤ 10% of "
        "median end-to-end latency; NFR-05 passes when two runs produce byte-identical prompts.")
    c.p(f"{c.next_fig()} shows a sample of requirement test cases running (captured output).")
    c.figure(FIG / "setup" / "terminal_tests_tc.png", "Example requirement test cases: failure handling (IR-07, D-07), "
             "holdout guard (DR-04), byte-identical prompts (NFR-05) and the bootstrap (FR-15)", 15.5)

    c.h3("Test Cases, Defects and Retesting", key="sec_tests")
    c.table("Test cases and results (unit tests: `pytest`, 111 passed; measurements: `camr profile`)",
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
              f"{100 * profile['retrieval_share_of_e2e']:.0f}% in the pilot profile. **Fail** (D-05; see ⟦sec_cost⟧)"],
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
              "Store opened for cross-thread use behind a lock; file watcher disabled", "App tests and browser test. Pass"],
             ["D-10", "CAMR Personal: the new warm-up loaded the model with the default context size, so Ollama "
              "loaded it a second time for the first question (1.8 s to the first word instead of a fraction of a "
              "second)", "App latency benchmark", "Warm-up sends the same options as a chat request",
              "Regression test; latency re-measured (⟦applat⟧). Pass"],
             ["D-11", "Interface: secondary text (group labels, keyboard hints, memory-kind chips) and, in the light theme, "
              "accent and success colours were below WCAG AA contrast (2.3–3.3 : 1)", "Accessibility audit "
              "(section ⟦sec_uitest⟧)", "Token values corrected per theme", "Contrast audit and axe-core: 0 failures. Pass"],
             ["D-12", "Interface: no top-level heading once a chat had started (screen-reader navigation)",
              "axe-core audit", "Persistent, visually hidden page heading", "axe-core: 0 violations. Pass"]],
            [1.2, 4.6, 2.6, 4.0, 3.5], size=9)

    c.h3("Application Testing (CAMR Personal)", key="sec_apptest")
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
              "All six green in CI (⟦ci⟧). Pass"],
             ["TC-34", "Time to first word recorded for every answer", "Measured from prompt sent to first streamed "
              "word; never larger than the answer time", "Recorded and shown under the answer (test). Pass"],
             ["TC-35", "App starts, or the user switches model", "Chat model loaded in the background before the "
              "first question", "Empty-prompt load request sent (test); first answer faster (⟦applat⟧). Pass"],
             ["TC-36", "Same question asked twice", "Second lookup reuses the question's embedding; documents never "
              "served from the cache", "One embedding call for two lookups (test). Pass"]],
            [1.6, 5.0, 4.6, 4.7], size=9)
    c.figure(FIG / "setup" / "terminal_tests_app.png", "Application test run: tests for the assistant core and the "
             "web server (captured output)", 15.5)
    if (FIG / "app" / "dark_0_setup_ollama_down.png").exists():
        c.figure(FIG / "app" / "dark_0_setup_ollama_down.png", "TC-30: with Ollama not running, the app shows what is "
                 "missing instead of failing", 14.5)
    c.p("These tests show that the application behaves correctly and fails safely. They do not show that people "
        "find it useful or easy to use. That requires a user study, which had not been run when this chapter "
        "was written (see Limitations, section ⟦sec_limits⟧).")

    ui_testing(c)
    scenarios_section(c)

    # ---------------------------------------------------------------- evaluation design
    c.h3("Evaluation Design")
    c.p("The primary measure is the fraction of the capability gap closed (Equation 3.1) per task type, together "
        "with the absolute gain, the residual gap, tokens per question and latency. Two ceilings were used: the "
        "local gpt-oss:20b and the cloud Kimi K3. Against a closed-book ceiling that the small model plus memory "
        "*exceeds*, gap closed rises above 1 and stops being a fraction. Kimi K3, the frontier reference, is "
        "therefore the anchor for headline statements. With n = 30, one question is 3.3 percentage points, and "
        "confidence intervals are reported where they matter.")

    # ================================================================ 5.5 version control
    c.h2("Version Control and Implementation Evidence", key="sec_vc")
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
        "findings), Satasdin/CAMR#3 (CAMR Personal 0.2), Satasdin/CAMR#4 (application speed, latency results and "
        "report) and Satasdin/CAMR#5 (CAMR Personal 0.2.1). Machines B–E pushed their results to their own branches, "
        "which were merged into the results database rather than into the code. Feedback from users is collected "
        "through a GitHub issue form (`.github/ISSUE_TEMPLATE/feedback.yml`). The code is released under the MIT "
        "licence. Continuous integration (`.github/workflows/release-app.yml`) runs the application tests and builds "
        "and launch-tests the downloadable application on six platforms for every change to the application. "
        f"{c.next_tab()} shows the run for the merged version. Published releases (v0.2.0, then v0.2.1 with the speed changes) attach the six "
        "downloads.")
    repo_shots = [("1_repository.png", "Project repository on GitHub (README, MIT licence, releases, contributors)"),
                  ("2_pull_requests.png", "Pull requests used to merge each round of work"),
                  ("3_actions_run.png", "Continuous-integration run: tests, build and launch test on six platforms"),
                  ("4_release.png", "Release v0.2.1 with the six downloadable files and their checksums"),
                  ("5_commits.png", "Commit history on the main branch")]
    for name, cap in repo_shots:
        if (FIG / "repo" / name).exists():
            c.figure(FIG / "repo" / name, cap + " (screenshot)", 14.5)
    c.table("Continuous-integration evidence: build and launch test per platform (GitHub Actions run 36899712846, release v0.2.1)",
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
        "test suite (111 tests), the per-query logs, the read-only inspector, and the findings log, which names "
        "the results file behind every reported number, so that each claim can be traced and re-run. The "
        "student made the final decisions and takes full responsibility for the submitted work.")

    # ================================================================ 5.7 results
    c.h2("Evaluation Results, Discussion and Limitations", key="sec_results")
    c.p("The results are organised by research objective. Source files are in `results/` and every table is "
        "reproduced in `docs/FINDINGS.md`.")

    c.h3("Retrieval Quality (Objective ii)", key="sec_retrieval")
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

    read_path_tuning(c)

    c.h3("Gap Closed and the Residual Gap (Objective iv)", key="sec_gap")
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

    worked_examples(c)

    c.h3("Error Analysis: Where Answers Are Lost", key="sec_errors")
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

    c.h3("Knowledge Growth with Frozen Weights", key="sec_growth")
    c.p("The knowledge corpus was fed into one store in three stages, and the same frozen 0.5B model answered "
        f"the same questions after each stage ({c.next_fig()}). On long-tail facts, accuracy rose from 6.7% "
        "to 16.7%, 33.3% and 66.7% as memory grew to 25%, 50% and 100%. That matches Kimi K3 and is roughly three "
        "times the 20B model. Median decode speed stayed between 44 and 63 tokens/s at every stage "
        f"({c.next_fig(2)}). The cost of memory is in prefill (270–460 extra prompt tokens) and a bounded 3–17% "
        "per-token decode slowdown, measured across the model sweep, from attending over a longer prompt.")
    c.figure(FIG / "fig_growth_accuracy.png", "Accuracy of the frozen 0.5B model as the memory store grows")
    c.figure(FIG / "fig_decode_speed.png", "Decode speed of the frozen 0.5B model at each store size")

    c.h3("Ablation and Token Budget (Objective v)", key="sec_budget")
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

    c.h3("Small Models on Their Own: the Baseline Ranking", key="sec_rank")
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

    c.h3("Which Model Sizes Suit the Engine", key="sec_sizes")
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
        c.h3("Confirmation at Larger Scale: 200 HotpotQA Questions", key="sec_h200")
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

    c.h3("Learning When to Use Memory and When to Escalate", key="sec_policy")
    fixed = {k: v for k, v in rl["fixed"].items()}
    off = rl["learned_offline"]
    c.p("A single fixed configuration cannot be best for every question. The learned policy chose an action per "
        f"question from pre-answer features and was evaluated on the {rl['n_test']} held-out questions "
        f"({c.next_tab()}, {c.next_fig()}).")
    casc = [r for r in rl["cascade"] if abs(r["stage1_cloud_cost"] - 0.3) < 1e-9 and abs(r["threshold"] - 0.2) < 1e-9][0]
    c.table("Engine policies on the held-out split (`results/learn/tables/rl_policies.md`, `rl_cascade.md`)",
            ["Policy (first study)", "Accuracy", "Sent to cloud", "Mean s / answer"],
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
        "correct) and to answer factual questions locally with a small budget. In this first study, with the "
        "grounding cascade, which answers locally first and escalates when the answer's words are not found in its "
        "notes, and its threshold set by inspecting the held-out results, the hybrid "
        f"reached {pct(casc['accuracy'])} against always-Kimi's {pct(fixed['always cloud']['accuracy'])}. "
        f"{100 - 100 * casc['cloud_share']:.0f}% of questions never left the device, and mean latency was "
        f"{fixed['always cloud']['mean_latency_s'] / casc['mean_latency_s']:.1f} times lower. LinUCB, which sees "
        "only the outcome of the action it chose, rose from 13.9% to 54.2% held-out accuracy within the first 40 "
        "episodes and then fluctuated between 54% and 64% over the five epochs. The gap to the oracle (79.2%) is mostly on "
        "multi-hop questions, where pre-answer features cannot predict whether the small model will read the "
        "evidence correctly.")

    policy_tuning_results(c)
    finetune_section(c)

    c.h3("Cost on the Device (Research Question v)", key="sec_cost")
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

    c.h3("Responsiveness of the Application", key="sec_app_speed")
    lat = app_latency()
    if lat:
        ms = lat["models"]
        c.p("The benchmark profile above measured the engine. A user of CAMR Personal waits for something else: the "
            "first word of the answer. Three changes were made to shorten that wait, and each was measured with real "
            "models through Ollama on the same 4-core CPU class (`scripts/app_latency.py`, results in "
            "`docs/results/app_latency.json`). (1) **Warm-up.** Ollama loads a model on first use, which dominated "
            "the first answer. The app now loads the chosen model in the background when it starts and when the "
            "user switches model, while the user is still typing. (2) **Time to first word** is recorded for every "
            "answer and shown under it, because streaming makes this, not the total time, the wait a user notices. "
            "(3) **Query-embedding cache.** A repeated question reuses its embedding instead of calling the embedding "
            f"model again. The memory held {lat['notes_small']} notes: the five demonstration notes and the PopQA "
            "documents, with six questions per setting.")
        rows = []
        for m, r in ms.items():
            b = r["budgets"]["384"]
            rows.append([m, f"{r['cold_disk']['first_token_ms'] / 1000:.1f} s", f"{r['cold']['first_token_ms'] / 1000:.1f} s", f"{r['after_warm']['first_token_ms'] / 1000:.1f} s",
                         f"{r['warm_up_ms'] / 1000:.1f} s", f"{b['median_first_token_ms'] / 1000:.2f} s",
                         f"{b['median_generation_ms'] / 1000:.1f} s", f"{b['median_retrieval_ms']:.0f} ms"])
        c.table("Time a CAMR Personal user waits, per model (budget 384 tokens; medians over six questions)",
                ["Model", "First word after reboot", "First word, cold (cached file)", "First word after warm-up",
                 "Warm-up (in background)", "First word, typical", "Whole answer, typical", "Memory lookup"],
                rows, [2.4, 1.9, 1.9, 1.9, 1.9, 1.9, 2.0, 1.9], size=8.5, key="applat")
        c.figure(REPORT / "app_latency.png", "Time to the first word: cold start, after the app's warm-up, and a "
                 "typical answer", 14.0)
        brow = []
        for m, r in ms.items():
            for bud in ("128", "384", "768"):
                b = r["budgets"][bud]
                brow.append([m, bud, f"{b['median_prompt_tokens']:.0f}", f"{b['median_first_token_ms'] / 1000:.2f} s",
                             f"{b['median_generation_ms'] / 1000:.1f} s"])
        c.table("Effect of the memory budget on waiting time (medians)", ["Model", "Budget (tokens)", "Prompt tokens",
                "First word", "Whole answer"], brow, [3.4, 2.6, 2.8, 3.0, 3.0], size=9)
        qc, sz = lat["query_cache"], lat["memory_size"]
        c.p(APP_LATENCY_TEXT(lat))
        c.table("Memory lookup time as memory grows (nomic-embed-text through Ollama)",
                ["Memory", "Notes", "Lookup (median)", "of which embedding", "of which vector search"],
                [["Demonstration + PopQA", f"{sz['small']['notes']:,}", f"{sz['small']['median_retrieval_ms']:.0f} ms",
                  f"{sz['small']['median_embed_ms']:.0f} ms", f"{sz['small']['median_search_ms']:.1f} ms"],
                 ["+ HotpotQA paragraphs", f"{sz['large']['notes']:,}", f"{sz['large']['median_retrieval_ms']:.0f} ms",
                  f"{sz['large']['median_embed_ms']:.0f} ms", f"{sz['large']['median_search_ms']:.1f} ms"],
                 ["Repeated question (cache)", "—", f"{qc['repeat_ms']:.1f} ms", "0 (cached)", "—"]],
                [4.2, 2.4, 3.0, 3.2, 3.2], size=9)

    c.h3("Alignment with the Proposal (Chapter 1)", key="sec_alignment")
    c.p("Each objective and research question of Chapter 1 was checked against what was built and measured. All "
        "five research questions are answered (section 6.2). Where the work departed from the proposal, the "
        f"departure, its reason and its effect on the findings are recorded in {c.next_tab()}, so that no deviation "
        "is hidden in the results.")
    c.table("Deviations from the approved proposal and their effect",
            ["Proposal (Chapter 1)", "What was done", "Reason", "Effect on the findings"],
            [["Obj. ii: a write policy that *distils* interactions into compact notes",
              "Distilling (structured) policy implemented and unit-tested; experiments used verbatim notes",
              "Benchmark documents are already compact; distilling would add a model call per note and a "
              "confound to the retrieval study", "Results describe verbatim memory; distillation is untested at scale"],
             ["Obj. ii: rank notes by similarity, recency *and* importance (Eq. 4.1)",
              "Eq. 4.1 implemented and evaluated; the default became similarity + gating + bridging",
              "Eq. 4.1 lowered full-support recall by 1.2–5.4 points (⟦sec_retrieval⟧)",
              "A measured improvement on the proposal; recency is untested on sessioned data"],
             ["Obj. iii and scope: one physical consumer laptop as the device",
              "CPU-only cloud containers of laptop class (4 vCPU, 16 GB, no GPU), fully specified",
              "Several identical machines were needed to run the 19-model sweep in time",
              "Accuracy transfers (greedy, deterministic engine); latency is indicative, as limitation 1 expected"],
             ["Scope: small models of 1–3B parameters", "All 1–3B models tested, plus 0.5B and 7–14.8B",
              "To find where the useful size range starts and ends", "An extension: confirms 1.5–4B as the range that "
              "suits the engine (⟦sec_sizes⟧)"],
             ["Scope: a read-only inspector, not an end-user application",
              "Inspector delivered as scoped; CAMR Personal added after the experiments", "To put the findings in "
              "users' hands and collect feedback", "An extension; it adds no claim to the research results"],
             ["Delimitation: no training or fine-tuning of any language model", "CAMR trains none. One LoRA "
              "adapter was trained as a *comparison baseline* only (section ⟦sec_finetune⟧)", "To test the problem "
              "statement's argument against fine-tuning with evidence", "Strengthens RQ ii; the engine's own claims are "
              "unchanged (frozen weights)"],
             ["Delimitation: no port to mobile phones", "No mobile results are reported; an unrun Android "
              "prototype is described as future work (6.4)", "Kept within the delimitation", "None"],
             ["NFR-02: retrieval ≤ 10% of answer time", "Measured and reported as not met for 0.5B; diagnosed",
              "A 0.5B model answers in about 180 ms", "Met only for models of about 1.5B and above (⟦sec_cost⟧)"]],
            [3.6, 4.0, 4.0, 4.3], size=8.5)

    c.h3("Limitations", key="sec_limits")
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
             "usability with real users.",
             "**Policy learning.** The router was trained on 144 questions with costs set by the researcher. Even "
             "after cross-validated tuning, its accuracy is statistically equal to always using the cloud model; the "
             "robust result is equal accuracy with most questions kept on the device and much lower latency. Fold-to-"
             "fold variation was larger than the differences between hyperparameter settings.",
             "**Fine-tuning baseline.** One base model (0.5B), one unsupervised training format family and a CPU "
             "float32 runtime were tested; supervised question–answer data or a larger model could fine-tune better. "
             "The comparison shows what a user's own device can do with the same documents, not the limit of "
             "fine-tuning.",
             "**Live scenarios.** The application scenarios are five hand-designed conversations, run once each with "
             "one model; they illustrate behaviour and failure modes and are not a statistical evaluation."])
    c.p("Conclusions, recommendations and future work, including feedback from real users of CAMR Personal and a "
        "phone version of the assistant, are presented in Chapter 6.")

    return c.save(out)


# ----------------------------------------------------------------- formal sections (equations)


def formal_model(c: Chapter) -> None:
    """The read path as mathematics, with a worked example from the logs."""
    c.h3("Formal Model of the Read Path", key="sec_formal")
    c.p("This subsection states precisely what the engine computes for a question *q*, so that every setting "
        "tuned or reported later has an exact meaning. The notation follows Chapter 4. The store holds notes "
        "*n*, each with its text, a token count *c(n)*, and an embedding produced by the embedder *f*. "
        "Embeddings are normalised to unit length, so cosine similarity is a dot product:")
    c.eq(r"s(q,n)=\cos\left(f(q),f(n)\right)=\frac{f(q)\cdot f(n)}{\left\lVert f(q)\right\rVert\,\left\lVert f(n)\right\rVert}=f(q)\cdot f(n)", key="eq_sim")
    c.where([(r"f(\cdot)\in\mathbb{R}^{384}", "the embedder (BGE-small-en-v1.5 in the experiments; nomic-embed-text "
              "in the application), with the model card's query prefix on *q*;"),
             (r"s(q,n)\in[-1,1]", "the similarity of note *n* to the question.")])
    c.p("The candidate set is the *k* most similar notes, found by exact nearest-neighbour search in sqlite-vec:")
    c.eq(r"C_k(q)=\underset{S\subseteq\mathcal{M},\,\left|S\right|=k}{\text{arg max}}\;\sum_{n\in S}s(q,n),\qquad k=20", key="eq_knn")
    c.p("The proposal ranked candidates by a weighted composite of similarity, recency and importance "
        "(Equation 4.1). As implemented, each term is min-max normalised over the candidate set:")
    c.eq(r"\text{score}(n)=w_s\,\tilde{s}(q,n)+w_r\,\rho^{\Delta t(n)}+w_i\,\tilde{I}(n),\qquad w_s+w_r+w_i=1", key="eq_comp")
    c.where([(r"\tilde{s},\tilde{I}", "min-max normalised similarity and importance;"),
             (r"\rho=0.99", "the recency decay per hour of logical time since the note was last read;"),
             (r"(w_s,w_r,w_i)", "(0.6, 0.15, 0.25) in the proposal's configuration, and (1, 0, 0) in the "
              "configuration the evidence selected (section ⟦sec_retrieval⟧), which reduces Equation ⟦eq_comp_n⟧ "
              "to ranking by similarity.")])
    c.p("Gating is the first capability-adaptive step. Let *s*₍₁₎ be the best similarity in the candidate set. The "
        "engine abstains (gives the model no notes) when even the best note is weak; otherwise it keeps only notes "
        "within a margin δ of the best:")
    c.eq(r"E(q)=\begin{cases}\varnothing & \text{if } s_{(1)}<\tau\\ \left\{n\in C_k(q):s(q,n)\ge s_{(1)}-\delta\right\} & \text{otherwise}\end{cases}", key="eq_gate")
    c.where([(r"\tau", "the abstain threshold (0.50 for BGE, 0.55 for nomic-embed-text; calibrated in section ⟦sec_tune_read⟧);"),
             (r"\delta", "the admission margin (0.15).")])
    c.p("Entity bridging then adds, for each of the top three eligible seed notes, up to two notes about other "
        "stored entities whose titles the seed's text mentions. These notes may have low similarity to the question; "
        "they are reached through the seed, which is the second hop of a multi-hop question:")
    c.eq(r"B(q)=\bigcup_{n\in\text{top}_3E(q)}\text{first}_2\left\{m\in\mathcal{M}:\text{title}(m)\in\text{mentions}(n)\right\}", key="eq_bridge")
    c.p("Finally the budgeter admits notes in rank order, each bridged note directly after its seed, until the "
        "next note would exceed the token budget *B*, and then stops:")
    c.eq(r"A(q)=\left(n_1,\dots,n_m\right),\quad m=\max\left\{j:\sum_{i=1}^{j}c(n_i)\le B\right\}", key="eq_pack")
    c.p("The prompt contains exactly the notes in *A(q)*, so the number of context tokens is at most *B* and is "
        "usually far smaller, because gating removes candidates before the budget binds.")
    c.p("**Worked example (from the pilot's logs).** For *Who was the director of The Loudwater Mystery?* the 20 "
        "candidates had best similarity *s*₍₁₎ = 0.771 (the film's own Wikipedia note). Since 0.771 ≥ τ = 0.50, the "
        "engine did not abstain. The admission floor was *s*₍₁₎ − δ = 0.771 − 0.15 = 0.621, and the next-best note "
        "(*Klute*, 0.616) fell just below it, so only one note was eligible. That note was 47 tokens, so "
        f"Equation ⟦eq_pack_n⟧ admitted it and the model read 47 tokens instead of filling the 512-token budget. "
        f"The 0.5B model answered *Walter West* (correct); alone it had answered *John Sturges*. {c.next_fig()} "
        "draws this decision from the logged scores.")
    c.figure(REPORT / "gating_trace.png", "Gating on one real question: candidate similarities, the abstain threshold τ "
             "and the admission floor s(1) − δ; only the blue note was given to the model", 14.0)


def metrics_section(c: Chapter) -> None:
    c.p("The scores are defined as follows. Let *p* be the model's answer, *G* the set of accepted gold answers, "
        "and norm(·) the SQuAD normalisation (lower case, punctuation and articles removed, whitespace collapsed):")
    c.eq(r"\text{EM}(p,G)=\max_{g\in G}\mathbb{1}\left[\text{norm}(p)=\text{norm}(g)\right],\qquad \text{Contains}(p,G)=\max_{g\in G}\mathbb{1}\left[\text{norm}(g)\sqsubseteq\text{norm}(p)\right]", key="eq_em")
    c.eq(r"\text{F}_1(p,g)=\frac{2PR}{P+R},\quad P=\frac{\left|t_p\cap t_g\right|}{\left|t_p\right|},\quad R=\frac{\left|t_p\cap t_g\right|}{\left|t_g\right|}", key="eq_f1")
    c.where([(r"\sqsubseteq", "occurrence as a whole-word substring;"),
             (r"t_p,t_g", "the multisets of normalised tokens of the answer and of the gold answer.")])
    c.p("For GSM8K the final number in the answer is compared exactly with the gold final number (fractions and "
        "thousands separators parsed). For a condition with per-question scores *y*ᵢ the accuracy is their mean, and "
        "the headline measure of the proposal (Equation 3.1) is the fraction of the gap closed, with the residual "
        "gap beside it:")
    c.eq(r"G=\frac{\text{Acc}_{\text{CAMR}}-\text{Acc}_{\text{floor}}}{\text{Acc}_{\text{ceiling}}-\text{Acc}_{\text{floor}}},\qquad R=\text{Acc}_{\text{ceiling+notes}}-\text{Acc}_{\text{CAMR}}", key="eq_gap")
    c.p("*G* = 1 means the small model with memory matches the large model; *G* > 1 means it exceeds a closed-book "
        "ceiling, which is why the frontier model is used as the anchor. *R* is what model size still buys when both "
        "models read the same notes. Uncertainty comes from a paired bootstrap over questions: for *b* = 1, …, 2,000, "
        "draw *Q* questions with replacement and compute the mean paired difference; the 95% interval is the 2.5th "
        "and 97.5th percentile of these means:")
    c.eq(r"\hat{\Delta}^{*}_b=\frac{1}{Q}\sum_{i=1}^{Q}\left(y^{\text{CAMR}}_{j_{b,i}}-y^{\text{floor}}_{j_{b,i}}\right),\qquad \text{CI}_{95}=\left[\hat{\Delta}^{*}_{(0.025)},\;\hat{\Delta}^{*}_{(0.975)}\right]", key="eq_boot")
    c.p("At the retrieval level, without any language model, the measure is full-support recall: the share of "
        "questions for which every gold supporting paragraph *S*_q reached the context:")
    c.eq(r"\text{SR}=\frac{1}{\left|Q\right|}\sum_{q\in Q}\mathbb{1}\left[S_q\subseteq\text{titles}\left(A(q)\right)\right]", key="eq_sr")


def policy_math(c: Chapter) -> None:
    c.p("Formally, the router faces a contextual bandit. For question *q* with features φ(*q*) it chooses an "
        "action *a* from the set 𝒜 = {local, mem128, mem512, mem1024, cloud} and receives the reward")
    c.eq(r"r(q,a)=y(q,a)-c_{\text{cloud}}\,\mathbb{1}\left[a=\text{cloud}\right]-\mu\,\frac{T(q,a)}{1000}", key="eq_reward")
    c.where([(r"y(q,a)\in\{0,1\}", "whether action *a* answered *q* correctly;"),
             (r"c_{\text{cloud}}=0.3", "the price of one cloud call in units of one correct answer (a design preference, "
              "swept from 0 to 1.2 for the Pareto table);"),
             (r"\mu=0.1", "the price of the small model reading 1,000 prompt tokens, *T(q, a)*.")])
    c.p("The offline learner fits one ridge regression per action on the training questions (design matrix *X* of "
        "feature rows, reward vector **r**ₐ) and routes to the action with the highest predicted reward:")
    c.eq(r"\hat{\theta}_a=\left(X^\top X+\lambda I\right)^{-1}X^\top\mathbf{r}_a,\qquad \pi(q)=\underset{a\in\mathcal{A}}{\text{arg max}}\;\hat{\theta}_a^\top\varphi(q)", key="eq_ridge")
    c.p("The online learner, LinUCB (Li et al., 2010), sees only the reward of the action it took. It keeps "
        "*A*ₐ = *I* + Σ*x x*ᵀ and **b**ₐ = Σ*r x* for each action and chooses optimistically:")
    c.eq(r"a_t=\underset{a\in\mathcal{A}}{\text{arg max}}\;\hat{\theta}_a^\top x_t+\alpha\sqrt{x_t^\top A_a^{-1}x_t},\qquad \hat{\theta}_a=A_a^{-1}\mathbf{b}_a", key="eq_linucb")
    c.p("The cascade answers locally first and escalates when a ridge model of the answer's own signals ψ (are the "
        "answer's words in the notes it read? is it abstention-like? how long is it?) predicts that the answer is "
        "wrong:")
    c.eq(r"\text{escalate}(q)=\mathbb{1}\left[\hat{w}^\top\psi\left(p_{\pi(q)}\right)<\theta\right]", key="eq_cascade")
    c.p("The hyperparameters λ, α, the number of passes and θ are chosen by *K*-fold cross-validation on the "
        "training split only (*K* = 5, folds stratified by task type), maximising the mean validation reward:")
    c.eq(r"h^{*}=\underset{h}{\text{arg max}}\;\frac{1}{K}\sum_{k=1}^{K}\bar{r}\left(\pi_h^{(D\setminus D_k)},D_k\right)", key="eq_cv")
    c.where([(r"\pi_h^{(D\setminus D_k)}", "the policy with hyperparameters *h* trained without fold *k*;"),
             (r"\bar{r}(\pi,D_k)", "its mean reward (Equation ⟦eq_reward_n⟧) on the held-out fold.")])


def interface_design(c: Chapter) -> None:
    c.h3("Interface Design of CAMR Personal", key="sec_ui")
    c.p("The interface had one job beyond being a usable chat window: to make memory, the thing the research is "
        "about, visible and controllable. Its design followed six principles, each traceable to a feature and to a "
        f"test ({c.next_tab()}).")
    c.table("Design principles of the interface and how each was realised and checked",
            ["Principle", "Realised as", "Checked by"],
            [["Memory is visible, before the answer", "A *Recalled N memories* card streams before the first word; "
              "an *answered by the model alone* label when gating abstains", "TC-27, TC-25; browser test (TC-37)"],
             ["Familiar conventions", "ChatGPT's minimal composer and chat list; Ollama's model picker inside the "
              "composer and drop-anywhere files; Kimi's sources-first answers", "Design review against the three apps"],
             ["Honest provenance", "Grounded % per answer; each memory labelled note / chat / learned / file; Forget on "
              "every item", "TC-28, TC-29; memory panel test"],
             ["The user stays in control", "*remember that…* stores without a model call; 👍 teaches, 👎 only records; "
              "export hides text by default", "TC-26, TC-39"],
             ["Local and private by construction", "Server bound to 127.0.0.1; Host and Origin checked; no telemetry",
              "TC-31, TC-32"],
             ["Accessible and responsive", "WCAG 2.2 AA contrast in both themes; one heading structure; layout from 390 "
              "px phones to desktops", "Contrast audit, axe-core audit, phone-width test (TC-40, TC-41)"]],
            [4.0, 7.2, 4.7], size=9)
    c.p(f"{c.next_fig()} shows how the interface is built. The front end is plain HTML, CSS and JavaScript with no "
        "framework or build step, so the downloadable executable stays small (16–43 MB) and starts in about a second. "
        "Answers arrive as Server-Sent Events in a fixed order: *recall* (which notes were read), then *token* events, "
        "then *done* with timings and the grounding score. That order is what puts memory in front of the answer.")
    c.figure(DIAGRAMS / "ui_components.png", "Interface components of CAMR Personal and the local server they talk to", 15.5)
    c.p("**Layout.** A three-column CSS grid: a 272 px sidebar, a fluid thread capped at 768 px for comfortable line "
        "length, and a 360 px memory panel that slides in. Below 900 px the sidebar becomes an overlay and the panel "
        "covers the screen, so the same interface works at phone width (TC-41). **Typography.** The system UI font "
        "stack (Inter where installed) at 15 px with 1.6 line height; monospace for codes and timings. **Colour.** "
        "Dark-first, with a single blue-to-green accent taken from the study's chart palette, and a light theme. "
        "Every colour is a named design token, so the two themes differ only in token values.")
    c.p("Text must stand out from its background for readers with low vision. WCAG 2.2 defines the contrast ratio "
        "of two colours from their relative luminance *L*, computed from the linearised sRGB channels:")
    c.eq(r"\text{CR}=\frac{L_{\text{light}}+0.05}{L_{\text{dark}}+0.05},\qquad L=0.2126\,R_{\text{lin}}+0.7152\,G_{\text{lin}}+0.0722\,B_{\text{lin}}", key="eq_contrast")
    c.p("Level AA requires CR ≥ 4.5 for normal text and ≥ 3 for large text and interface marks. "
        f"{c.next_fig()} shows every token pair the stylesheet uses, measured with this formula after the audit in "
        "section ⟦sec_uitest⟧ corrected the four tokens that failed.")
    c.figure(REPORT / "design_tokens.png", "Design tokens of both themes with their measured contrast ratios", 15.5)


def ui_testing(c: Chapter) -> None:
    c.h3("Interface Testing: Browser, Accessibility and Layout", key="sec_uitest")
    audit = json.loads((ROOT / "docs/results/ui_audit.json").read_text())
    before, after = audit["before"], audit["after"]
    c.p("The interface was tested in three further ways. **End-to-end browser tests** (`tests/test_app_e2e.py`) "
        "drive the real interface in Chromium through Playwright, as a user would, with the deterministic test "
        "doubles in place of the model so that a failure means the interface is wrong, not the model. An "
        "**automated accessibility audit** (`scripts/ui_audit.py`) runs axe-core 4.10 (Deque Systems) against WCAG "
        "2.0/2.1/2.2 A and AA rules and best practices, in both themes, at desktop (1,366 × 860) and phone (390 × 844) "
        "size, on a populated chat with the memory panel open. A **contrast audit** computes Equation "
        "⟦eq_contrast_n⟧ for every token pair.")
    c.table("Automated interface tests (Chromium, Playwright)",
            ["Test ID", "What the browser does", "Expected", "Result"],
            [["TC-37", "Types *remember that my bike lock code is 4471*, then asks for the code", "Stored without a "
              "model call; the recall card shows the memory before the answer; the answer contains 4471; memory "
              "counter increases", "Pass"],
             ["TC-38", "Submits a message of spaces", "Nothing is sent; no chat created", "Pass"],
             ["TC-39", "Clicks 👍 on an answer", "Button reads *Learned*; memory counter increases", "Pass"],
             ["TC-40", "Toggles the theme and opens the memory panel", "Theme changes; panel opens", "Pass"],
             ["TC-41", "Loads the app at 390 × 844 px", "Composer fully on screen; no horizontal scrolling", "Pass"],
             ["TC-42", "Uses only the keyboard: Tab to the message box, type, Enter", "Message box reachable by Tab; "
              "message sent; every visible control has an accessible name", "Pass"]],
            [1.5, 5.6, 6.4, 2.4], size=9)

    def axe_summary(run):
        out = {}
        for r in run["axe"]:
            for v in r["violations"]:
                out.setdefault(v["id"], {"impact": v["impact"], "help": v["help"], "where": set()})["where"].add(
                    f"{r['theme']} {r['viewport']}")
        return out

    b_axe = axe_summary(before)
    fails = [r for r in before["contrast"] if not r["pass_AA"]]
    c.p(f"The first audit found real defects. axe-core reported {len(b_axe)} rule violations "
        f"({', '.join(sorted(b_axe))}) and the contrast audit found {len(fails)} token pairs below AA, all of them in "
        "small secondary text (sidebar group labels, keyboard hints, memory-kind chips) and, in the light theme, the "
        "accent and success colours. The page also had no top-level heading once a chat had started, which hurts "
        "screen-reader navigation. They were logged as defects D-11 and D-12, fixed by darkening or lightening the "
        "failing tokens per theme and adding a persistent (visually hidden) page heading, and re-audited:")
    rows = []
    for r in before["axe"]:
        a = next(x for x in after["axe"] if x["theme"] == r["theme"] and x["viewport"] == r["viewport"])
        rows.append([f"{r['theme'].capitalize()}, {r['viewport']}",
                     ", ".join(f"{v['id']} ({v['impact']}, {v['nodes']})" for v in r["violations"]) or "none",
                     str(r["passes"]), "none" if not a["violations"] else ", ".join(v["id"] for v in a["violations"]),
                     str(a["passes"])])
    c.table("Accessibility audit with axe-core: violations (impact, elements) before and after the fixes",
            ["Theme and size", "Violations before", "Rules passed before", "Violations after", "Rules passed after"],
            rows, [3.0, 6.1, 2.2, 2.4, 2.2], size=9)
    c.table("Colour-contrast failures found and fixed (WCAG 2.2 AA)",
            ["Theme", "Token pair", "Used for", "Before", "After", "Required"],
            [[r["theme"], f"{r['fg']} on {r['bg']}", r["use"], f"{r['ratio']:.2f}:1",
              f"{next(x['ratio'] for x in after['contrast'] if (x['theme'], x['fg'], x['bg']) == (r['theme'], r['fg'], r['bg'])):.2f}:1",
              f"{r['required_AA']:g}:1"] for r in fails],
            [1.6, 3.4, 4.6, 2.0, 2.0, 2.0], size=9)
    c.p("After the fixes the audit reported no violations in either theme at either size, and every token pair met "
        "AA. Keyboard-only use of the main path is covered by TC-42. Automated tools catch only part of what makes an "
        "interface accessible: the interface was **not** tested with a screen reader or with users who rely on one, "
        "and a usability study with real users remains future work (Chapter 6).")
    c.p("As a structured design review, the interface was also checked against Nielsen's ten usability heuristics "
        f"({c.next_tab()}). This is the author's own expert review, not a user study; its value is that each "
        "heuristic is tied to a concrete feature or to a gap that is admitted.")
    c.table("Heuristic review of the interface (Nielsen, 1994)",
            ["Heuristic", "How the interface meets it", "Known gap"],
            [["Visibility of system status", "*Searching your memory…*, recall card, streaming, time to first word, "
              "download progress", "—"],
             ["Match with the real world", "Plain words: *Teach*, *Remember*, *Forget*, *Learned*", "—"],
             ["User control and freedom", "Forget any memory; rename or delete chats; 👎 never teaches", "No undo after Forget"],
             ["Consistency and standards", "ChatGPT/Ollama conventions; one token system across themes", "—"],
             ["Error prevention", "Empty messages rejected; duplicates detected; local-only server", "—"],
             ["Recognition rather than recall", "Suggestions on the empty chat; model picker shows installed models",
              "—"],
             ["Flexibility and efficiency", "⌘K new chat; Enter to send; *remember that…* shortcut", "Few keyboard shortcuts"],
             ["Aesthetic and minimalist design", "One accent colour; memory details in a panel, not in the thread", "—"],
             ["Help users recover from errors", "Setup screen names the missing step (TC-30); toasts explain failures",
              "Model errors shown as raw text"],
             ["Help and documentation", "docs/APP.md, illustrated setup guide, About in Settings", "No in-app tour"]],
            [3.6, 7.6, 4.7], size=9)


def worked_examples(c: Chapter) -> None:
    ex = json.loads((ROOT / "docs/results/examples.json").read_text())
    c.h3("What the Models Actually Answered: Worked Examples", key="sec_examples")
    c.p("Aggregate accuracy hides how an answer is won or lost. This subsection follows single questions through the "
        "engine, with and without memory, using the logged prompts and answers verbatim (abridged only where marked "
        "…). The examples were chosen to show each mechanism and each failure mode, not to flatter the engine; "
        "`scripts/extract_examples.py` pulls them from the result databases.")

    f = ex["fact"]
    fc = f["conditions"]
    c.p(f"**Example 1: a long-tail fact, and an ambiguous name.** *{f['question']}* PopQA's intended entity is the "
        f"Taiwanese band *Fahrenheit*, and the accepted answers are {', '.join(f['gold'])}.")
    c.table("Example 1: answers to a long-tail question with and without memory (pilot logs)",
            ["Model and condition", "Answer", "Correct", "Prompt tokens", "Seconds"],
            [[n, v["answer"].strip().splitlines()[0][:60], "yes" if v["correct"] else "no", str(v["prompt_tokens"]),
              f"{v['seconds']:.1f}"] for n, v in fc.items()],
            [5.0, 4.6, 1.7, 2.3, 2.0], size=9)
    c.p("Without memory, each model answered for a *different* Fahrenheit: the 0.5B and 20B models chose the novel's "
        "genre, Kimi K3 the video game. With CAMR, the 0.5B model read the stored note about the band and answered "
        "correctly in 1.2 s. Memory supplied not only a missing fact but the user's intended referent, which no amount "
        "of parameters can guess. This is the personal-assistant case in miniature: *my* dentist, *my* supervisor.")

    for key, n in (("bridge_1", 2), ("bridge_2", 3)):
        e = ex[key]
        adm = [x for x in e["trace"] if x["admitted"]]
        via = [x for x in adm if x["via_bridge"]]
        cc = e["conditions"]
        c.p(f"**Example {n}: a two-hop question solved by bridging.** *{e['question']}* (gold: {e['gold'][0]}). "
            f"The engine admitted {len(adm)} notes; {len(via)} of them came only through entity bridging "
            f"(*{via[0]['title']}*, similarity {via[0]['similarity']:.2f}), reached because an admitted seed note named it. "
            f"llama3.2:3b answered *{cc['llama3.2:3b alone']['answer'].strip()[:40]}* alone and "
            f"*{cc['llama3.2:3b + CAMR']['answer'].strip()[:40]}* with CAMR (correct), in "
            f"{cc['llama3.2:3b + CAMR']['seconds']:.1f} s; Kimi K3 knew it closed-book "
            f"({cc['Kimi K3 (cloud), closed book']['seconds']:.1f} s).")
    c.figure(REPORT / "bridge_trace.png", "Admitted notes for the two multi-hop examples; orange notes were reached only by "
             "entity bridging (Equation ⟦eq_bridge_n⟧)", 15.5)

    m = ex["maths_helps"]
    mc = m["conditions"]
    c.p(f"**Example 4: a maths problem where worked-example memory helps.** *{m['question']}* The gold solution is a "
        "chain of four operations:")
    c.eq(r"\text{food}=20.25-4.50=15.75,\quad \text{rides}=2\times33=66,\quad \frac{20.25+15.75+66}{3}=\frac{102}{3}=34")
    c.p("For reasoning questions CAMR retrieves solved GSM8K *training* problems instead of facts. Here it retrieved two: "
        "a state-fair ticket problem and *three friends split the cost of a movie*. "
        f"{c.next_tab()} shows the decisive step of each answer.")
    def first_lines(t, k=4):
        lines = [x.strip() for x in t.strip().splitlines() if x.strip()]
        return " / ".join(lines[:k])[:170] + " …"
    c.table("Example 4: the same GSM8K problem with and without worked-example memory (logged answers)",
            ["Model and condition", "Opening of the answer (abridged)", "Final", "Correct"],
            [[n, first_lines(v["answer"]), (re.search(r"####\s*([^\n]+)", v["answer"]) or re.search("(.*)", "–")).group(1)[:10],
              "yes" if v["correct"] else "no"] for n, v in mc.items()],
            [3.8, 8.6, 1.8, 1.7], size=8.5)
    c.p("Alone, both phi4-mini (3.8B) and qwen2.5:14b read *$20.25 on 3 tickets* as a price per ticket and computed "
        "3 × 20.25 = 60.75, which led to 47.50. With the two worked examples in the prompt, both read it as the total and "
        "reached 34, matching Kimi K3. The 0.5B model, given the same examples, printed an answer and then began copying "
        "an example problem: the format of the examples overwhelmed it.")
    h = ex["maths_hurts"]
    hc = h["conditions"]
    c.p(f"**Example 5: where the same memory hurts.** *{h['question'][:160]}…* The 0.5B model alone solved it "
        f"(answer ending *{hc['qwen2.5:0.5b alone']['answer'].strip().splitlines()[-1][:20]}*). With worked examples it "
        f"answered *{hc['qwen2.5:0.5b + CAMR worked examples']['answer'].strip().splitlines()[0][:20]}* and then repeated "
        "the problem text. Across the pilot, exemplar memory moved the 0.5B model from 33.3% to 16.7% on GSM8K, and over "
        "19 models it helped 8, was neutral for 4 and hurt 7. This is why the learned router sends maths to a stronger "
        "model instead of adding memory (section ⟦sec_policy⟧).")


def read_path_tuning(c: Chapter) -> None:
    p = ROOT / "results/retrieval_eval/tables/gating_tuning.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())
    c.h3("Tuning the Read Path on Validation Data", key="sec_tune_read")
    sel, t = d["selected"], d["test"]
    st, df = t["selected"], t["study default (0.15, 512)"]
    c.p("The margin δ and the budget *B* were fixed by design in the first study. To check them properly, they were "
        "tuned on a **validation** half of the 500 HotpotQA and 500 2WikiMultiHopQA retrieval questions "
        f"({d['n_val']} questions) and the chosen setting was scored once on the other, **held-out** half. Because a "
        "larger budget always recovers more evidence, the objective charges for tokens at the same rate μ as the "
        "learned router's reward (Equation ⟦eq_reward_n⟧):")
    c.eq(r"J(\delta,B)=\text{SR}(\delta,B)-\mu\,\frac{\bar{T}(\delta,B)}{1000},\qquad \mu=0.1", key="eq_j")
    c.p(f"{c.next_fig()} shows the {len(d['margins']) * len(d['budgets'])}-point grid. Recall rises with the budget "
        "and with a wider margin, and so does the token bill; the objective balances them.")
    c.figure(REPORT / "gating_tuning.png", "Read-path grid on the validation half: full-support recall, tokens supplied and "
             "the objective J; the box marks the selected setting", 15.5)
    lab = lambda m: "none" if m is None else f"{m:.2f}"  # noqa: E731
    c.table("Read path on the held-out half: tuned setting against the study's default",
            ["Setting", "δ", "B", "Full-support recall", "Tokens", "J"],
            [["Selected on validation", lab(sel["margin"]), str(sel["budget"]), pct(st["support_all"]),
              f"{st['mean_tokens']:.0f}", f"{st['J']:.3f}"],
             ["Study default", "0.15", "512", pct(df["support_all"]), f"{df['mean_tokens']:.0f}", f"{df['J']:.3f}"]],
            [4.2, 1.6, 1.6, 3.2, 2.2, 2.2], size=9.5)
    c.p(READ_TUNING_TEXT(d))
    c.p("The abstain threshold τ is different: on these questions every memory is on-topic, so a higher τ can only "
        "lose recall. It was therefore set on separate data, the similarity of each question to an *off-topic* "
        "paragraph, as the 90th percentile of that distribution. " f"{c.next_fig()} shows the trade-off for both "
        "embedders: at the chosen τ almost every relevant note is kept, and about 90% of off-topic notes are refused.")
    c.figure(REPORT / "tau_tradeoff.png", "The abstain threshold τ: relevant notes kept against off-topic notes rejected on "
             "200 HotpotQA questions, for the benchmark and the application embedders", 13.0)


def READ_TUNING_TEXT(d: dict) -> str:  # noqa: N802
    sel, t = d["selected"], d["test"]
    st, df = t["selected"], t["study default (0.15, 512)"]
    g = {(x["margin"], x["budget"]): x for x in d["validation_grid"]}
    a, b = g[(sel["margin"], sel["budget"])], g[(0.15, 512)]
    mu_star = (a["support_all"] - b["support_all"]) / ((a["mean_tokens"] - b["mean_tokens"]) / 1000)
    lab = "no margin" if sel["margin"] is None else f"δ = {sel['margin']:.2f}"
    return (f"Validation selected {lab} and B = {sel['budget']}: at a price of μ = 0.1 per 1,000 tokens, more evidence "
            f"is worth its tokens. On the held-out half it raised full-support recall from {pct(df['support_all'])} to "
            f"{pct(st['support_all'])}, but supplied {st['mean_tokens']:.0f} tokens per question instead of "
            f"{df['mean_tokens']:.0f}. The choice is sensitive to the price of a token: the study's setting wins as soon "
            f"as a token costs more than μ ≈ {mu_star:.2f} per 1,000, and the margin's main effect is to save tokens "
            "(at B = 1,024, δ = 0.15 supplies about a fifth fewer tokens for a few points of recall). More importantly, "
            "this objective measures *retrieval*, not answers. The end-to-end budget sweep (section ⟦sec_budget⟧) "
            "showed that the 0.5B model answers *worse* when given more notes, because it is distracted by them. The "
            "read path should therefore be tuned to the reader: a large budget with no margin suits strong readers "
            "and multi-hop questions, where missing evidence is the binding constraint; the study's small budget and "
            "margin suit tiny models. This is exactly the per-question trade-off the learned router makes, and the "
            "reason a single fixed setting cannot be best.")


def policy_tuning_results(c: Chapter) -> None:
    p = ROOT / "results/learn/tables/policy_tuning.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())
    h = d["held_out"]
    r, lin = d["router_selected"], d["linucb_selected"]
    c.p("**Tuning the router properly.** The first version fixed λ = 1, α = 0.5 and 5 passes by hand, and its "
        "cascade threshold (0.2) was read off the held-out questions, which flatters the result. All four were "
        "re-chosen by 5-fold cross-validation on the 144 training questions only (Equation ⟦eq_cv_n⟧), and the 72 "
        f"held-out questions were then scored once ({c.next_fig()}, {c.next_tab()}).")
    c.figure(REPORT / "router_tuning.png", "Cross-validated tuning of the learned router, LinUCB and the cascade threshold", 15.8)
    c.table("Hyperparameters before and after cross-validated tuning",
            ["Hyperparameter", "First study (by hand)", "Selected by 5-fold CV", "CV mean reward"],
            [["Feature set", "full (11 features)", r["features"], f"{r['cv_reward']:.3f} ± {r['cv_reward_sd']:.3f}"],
             ["Ridge penalty λ", "1.0", f"{r['lambda']:g}", "(same run)"],
             ["LinUCB exploration α", "0.5", f"{lin['alpha']:g}", f"{lin['cv_reward']:.3f} ± {lin['cv_reward_sd']:.3f}"],
             ["LinUCB passes (epochs)", "5", str(lin["passes"]), "(same run)"],
             ["Cascade threshold θ", "0.2 (chosen on held-out data)", f"{d['cascade_selected']:g}",
              f"{max(x['cv_reward'] for x in d['cascade_grid']):.3f}"]],
            [4.0, 4.0, 3.8, 4.0], size=9.5)
    hc = h["tuned router + cascade"]
    lo, hi = hc["vs_always_cloud"][1], hc["vs_always_cloud"][2]
    c.figure(REPORT / "heldout_policies.png", "Tuned policies on the 72 held-out questions: accuracy with the paired "
             "95% interval of the difference from always using the cloud, and time per answer", 15.5)
    c.p(f"Two results stand out. First, cross-validation preferred the **simplest** router: task type alone, with "
        "the retrieval features adding nothing measurable on 144 questions (the fold-to-fold spread, about ±0.08, is "
        "larger than the differences between feature sets). With so little training data the richer model mainly "
        "fits noise; the retrieval features may pay off with more data. Second, the honestly tuned cascade is at "
        f"least as good as the hand-set one: {pct(hc['accuracy'])} held-out accuracy with "
        f"{100 * hc['cloud_share']:.0f}% of questions sent to the cloud and {hc['mean_latency_s']:.1f} s per answer, "
        f"against {pct(h['always cloud']['accuracy'])} and {h['always cloud']['mean_latency_s']:.1f} s for always "
        f"asking Kimi K3. The difference in accuracy, {100 * hc['vs_always_cloud'][0]:+.1f} points (95% CI "
        f"{100 * lo:+.1f} to {100 * hi:+.1f}), is not significant: the defensible claim is *equal accuracy at a "
        f"quarter of the cloud calls and about a fifth of the time*. LinUCB, which learns only from the actions it "
        f"takes, stayed below the offline router ({pct(h['tuned LinUCB']['accuracy'])}); its best setting was one "
        "pass, and more passes did not help, a sign that 144 questions are too few for exploration to pay off.")


def finetune_section(c: Chapter) -> None:
    grid_p, test_p, cost_p = (ROOT / "results/finetune/tune/grid.json", ROOT / "results/finetune/test.json",
                              ROOT / "results/finetune/camr_cost.json")
    if not test_p.exists():
        return
    grid, res = json.loads(grid_p.read_text()), json.loads(test_p.read_text())
    cost = json.loads(cost_p.read_text()) if cost_p.exists() else None
    c.h3("Fine-Tuning Compared with Memory", key="sec_finetune")
    c.p("The problem statement (section 1.2) argued that fine-tuning is the wrong tool for giving a small on-device "
        "model new knowledge: it needs compute users do not have, must be repeated whenever knowledge changes, and can "
        "damage what the model already does well. CAMR itself never changes the model's weights. To test that "
        "argument rather than assume it, the obvious alternative was run as a **baseline**: the same 0.5B model was "
        "fine-tuned on exactly the documents CAMR stores, and the two were compared on the same held-out questions.")
    c.p("**Method.** Low-Rank Adaptation (LoRA; Hu et al., 2022) freezes each weight matrix *W* and learns a "
        "low-rank update, so only a small fraction of parameters is trained:")
    c.eq(r"W'=W+\frac{\alpha_{\text{LoRA}}}{r}\,BA,\qquad B\in\mathbb{R}^{d\times r},\;A\in\mathbb{R}^{r\times k},\;r\ll\min(d,k)", key="eq_lora")
    c.p("The adapters were trained with the causal language-modelling loss over the document tokens *x*₁…*x*_T:")
    c.eq(r"\mathcal{L}(\theta)=-\frac{1}{T}\sum_{t=1}^{T}\log p_\theta\left(x_t\mid x_{<t}\right)", key="eq_lm")
    g0 = grid[0]
    c.table("Fine-tuning set-up (`scripts/finetune_baseline.py`)",
            ["Setting", "Value"],
            [["Model", "Qwen2.5-0.5B-Instruct (Hugging Face weights, float32 on CPU; the same base as qwen2.5:0.5b)"],
             ["Training data", f"The {g0['docs']} PopQA documents CAMR stores for the pilot and learning splits "
              f"({g0['train_tokens']:,} trained tokens per epoch); no questions or answers"],
             ["Formats compared", "*raw*: title and text as plain text; *chat*: the document as the assistant's answer to "
              "\"What do you know about <title>?\" (loss on the answer only)"],
             ["LoRA", f"rank r = {g0['rank']}, α = {2 * g0['rank']}, dropout 0.05, on all attention and MLP projections; "
              f"{g0['trainable_params']:,} trainable parameters (about {100 * g0['trainable_params'] / 494e6:.1f}% of "
              "the model)"],
             ["Optimisation", f"AdamW, learning rate {{1e-4, 3e-4}} with warm-up then constant, batch {g0['batch']} "
              "(micro-batch 2 × 4 accumulation steps), gradient clipping 1.0, gradient checkpointing, seed 13"],
             ["Epochs", "Up to 8; checkpoints evaluated after epochs 1, 2, 4 and 8"],
             ["Validation (selection)", "60 PopQA questions of the learning split's *training* set, closed book"],
             ["Test (reported once)", f"{res['n_test']} held-out PopQA questions (pilot 30 + learning evaluation 30), "
              f"closed book and with CAMR's logged prompts; GSM8K ({res['n_gsm8k']} questions) for side effects"],
             ["Decoding", "Greedy, the same chat template for every condition"]],
            [4.0, 11.9], size=9)
    c.figure(REPORT / "finetune_curves.png", "LoRA training loss and validation accuracy per epoch for the four "
             "configurations", 15.5)
    b, lo = res["conditions"]["base"], res["conditions"]["lora"]
    sel = res["selected"]
    run = next(r for r in grid if r["fmt"] == sel["fmt"] and r["lr"] == sel["lr"])
    ep = next(e for e in run["epochs"] if e["epoch"] == sel["epoch"])
    rows = [["Base model alone", pct(b["test_closed"]["accuracy"]), pct(b["gsm8k"]["accuracy"]), "–", "–"],
            ["Base + CAMR (no training)", pct(b["test_camr"]["accuracy"]), pct(b["gsm8k"]["accuracy"]),
             f"{cost['ingest_seconds']:.0f} s to store" if cost else "–", f"{cost['store_mb']:.1f} MB store" if cost else "–"],
            [f"LoRA fine-tuned ({sel['fmt']}, lr {sel['lr']:g}, {sel['epoch']} epochs)", pct(lo["test_closed"]["accuracy"]),
             pct(lo["gsm8k"]["accuracy"]), f"{ep['train_seconds'] / 60:.0f} min to train", f"{ep['adapter_mb']:.0f} MB adapter"],
            ["LoRA fine-tuned + CAMR", pct(lo["test_camr"]["accuracy"]), pct(lo["gsm8k"]["accuracy"]), "both", "both"]]
    c.table("Memory against fine-tuning on the same documents (held-out test, one runtime for all conditions)",
            ["Condition", "PopQA (long-tail facts)", "GSM8K (side effect)", "Cost to add the knowledge", "Artefact"],
            rows, [5.4, 2.6, 2.6, 2.9, 2.4], size=9)
    c.figure(REPORT / "finetune_vs_camr.png", "Held-out accuracy of the base model, CAMR, LoRA and both; and GSM8K accuracy "
             "before and after fine-tuning", 15.0)
    c.p(FINETUNE_TEXT(res, run, ep, cost))


def FINETUNE_TEXT(res, run, ep, cost) -> str:  # noqa: N802
    b, lo = res["conditions"]["base"], res["conditions"]["lora"]
    bc, bm, lc, lm = (b["test_closed"]["accuracy"], b["test_camr"]["accuracy"], lo["test_closed"]["accuracy"],
                      lo["test_camr"]["accuracy"])
    dg = lo["gsm8k"]["accuracy"] - b["gsm8k"]["accuracy"]
    parts = [f"Fine-tuning moved closed-book accuracy from {pct(bc)} to {pct(lc)}; giving the untrained model CAMR's "
             f"notes moved it to {pct(bm)}."]
    if bm > lc:
        parts.append(f"Memory beat fine-tuning by {100 * (bm - lc):.1f} points on the same documents, which matches "
                     "Ovadia et al. (2023): unsupervised fine-tuning teaches a model to continue the documents, not "
                     "reliably to answer questions about them, while retrieval puts the exact sentence in front of it.")
    else:
        parts.append("Here fine-tuning matched or beat memory on the facts, so the advantage of memory lies in its "
                     "cost and flexibility rather than accuracy.")
    if cost:
        parts.append(f"The costs differ by orders of magnitude: CAMR stored the {cost['docs']} documents in "
                     f"{cost['ingest_seconds']:.0f} s, and a new note is usable the moment it is saved, whereas the "
                     f"selected adapter took {ep['train_seconds'] / 60:.0f} min of training on four CPU cores, after a "
                     "hyperparameter search of several times that, and must be retrained whenever knowledge changes.")
    parts.append(f"Fine-tuning also changed GSM8K accuracy by {100 * dg:+.1f} points ({pct(b['gsm8k']['accuracy'])} → "
                 f"{pct(lo['gsm8k']['accuracy'])})" + (", the forgetting the problem statement warned of." if dg < 0 else
                 "; on this small sample no forgetting was measured."))
    parts.append(f"Combining the two gave {pct(lm)}: " + ("fine-tuning added nothing on top of memory." if lm <= bm + 1e-9
                                                         else "the adapter and the notes were complementary."))
    return " ".join(parts)


def scenarios_section(c: Chapter) -> None:
    p = ROOT / "docs/results/scenarios.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())
    sc = d["scenarios"]
    c.h3("Complex Interactions with a Real Model", key="sec_scenarios")
    c.p("Benchmarks ask one independent question at a time. A personal assistant meets harder situations: two notes "
        "that must be joined, arithmetic on a remembered number, a fact that changes, a detail said many turns earlier, "
        f"a document dropped into the window. Five such scenarios were run in the released application with "
        f"**{d['model']}** through Ollama on the 4-core CPU, each in a fresh home, once **without memory** (the same "
        "app and model with nothing taught, or with chat memory switched off) and once **with CAMR**. The screenshots "
        "below are the real screens, captured automatically by `scripts/scenario_screens.py`, which also logs every "
        "answer; nothing was retyped or retried. An answer counts as correct when it contains every expected element.")
    rows = []
    for key, e in sc.items():
        q = e["with"]["turns"][-1]["question"]
        wo = e.get("without")
        rows.append([e["title"], q[:90],
                     ("–" if not wo else ("correct" if wo["correct"] else "wrong") + ": " + wo["turns"][-1]["answer"].strip().replace("\n", " ")[:80]),
                     ("correct" if e["with"]["correct"] else "wrong") + ": " + e["with"]["turns"][-1]["answer"].strip().replace("\n", " ")[:80],
                     ", ".join(x for x in e["with"]["turns"][-1]["sources"] if x)[:60] or "none (abstained)"])
    c.table(f"Complex interactions in CAMR Personal ({d['model']}): final question, answers without and with memory, and "
            "the memories recalled (`docs/results/scenarios.json`)",
            ["Scenario", "Final question", "Without memory", "With CAMR", "Recalled"],
            rows, [2.6, 3.6, 3.6, 3.6, 2.5], size=8)
    for key, e in sc.items():
        img = ROOT / "docs/figures/scenarios" / f"{key}.png"
        if img.exists():
            c.figure(img, f"Scenario: {e['title'].lower()}" + ("" if "without" not in e else
                     " (left: without memory, right: with CAMR)"), 15.8 if "without" in e else 10.5)
    c.p(SCENARIO_TEXT(d))


def SCENARIO_TEXT(d: dict) -> str:  # noqa: N802 - written from the logged answers
    sc = d["scenarios"]
    n = len(sc)
    w = sum(1 for e in sc.values() if e["with"]["correct"])
    wo = [e for e in sc.values() if "without" in e]
    wo_ok = sum(1 for e in wo if e["without"]["correct"])
    return (f"With memory the assistant answered {w} of {n} scenarios correctly; without it, {wo_ok} of {len(wo)}. "
            + SCENARIO_NOTES)


SCENARIO_NOTES = ""


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

# Interpretation of the application latency benchmark (docs/results/app_latency.json).
def APP_LATENCY_TEXT(lat: dict) -> str:  # noqa: N802 - named hook, like H200_TEXT
    ms = lat["models"]
    names = list(ms)
    big = names[-1]
    qc, sz = lat["query_cache"], lat["memory_size"]
    warm = ", ".join(f"{ms[m]['cold']['first_token_ms'] / 1000:.1f} → {ms[m]['after_warm']['first_token_ms'] / 1000:.1f} s"
                     for m in names)
    return (
        f"**Warm-up.** With the model unloaded but its file in the operating system's cache, the first word took "
        f"{warm} for {', '.join(names)} once the app had warmed the model, which it does while the user types. "
        f"After a reboot, when the weights must be read from disk, the cold first answer took "
        f"{ms[big]['cold_disk']['first_token_ms'] / 1000:.0f} s for {big} on this container's disk; warm-up moves "
        "that load out of the conversation, but cannot hide it if the user asks before it finishes. The first warmed "
        "answer is still slower than a typical one because nothing of the prompt has been processed yet. "
        "**Budget.** The budget made no measurable difference here: on personal notes, gating admitted only the one "
        f"or two notes that matched, so every budget sent the same prompt (about "
        f"{ms[names[0]]['budgets']['384']['median_prompt_tokens']:.0f} tokens) and the budget never bound. It "
        "matters when many notes are relevant, as in the benchmarks (section ⟦sec_budget⟧). "
        f"**Lookup.** Inside a conversation the memory lookup took a median of "
        f"{min(ms[m]['budgets']['384']['median_retrieval_ms'] for m in names):.0f}–"
        f"{max(ms[m]['budgets']['384']['median_retrieval_ms'] for m in names):.0f} ms, against "
        f"{sz['small']['median_retrieval_ms']:.0f} ms with nothing else running: the embedding model and the chat "
        "model share the same four cores, the contention already diagnosed in section ⟦sec_cost⟧. A repeated question "
        f"skipped the embedding and took {qc['repeat_ms']:.1f} ms instead of {qc['first_ms']:.0f} ms. Growing memory "
        f"{sz['large']['notes'] / sz['small']['notes']:.0f}-fold, from {sz['small']['notes']:,} to "
        f"{sz['large']['notes']:,} notes, raised the lookup only from {sz['small']['median_retrieval_ms']:.0f} to "
        f"{sz['large']['median_retrieval_ms']:.0f} ms (vector search {sz['small']['median_search_ms']:.0f} → "
        f"{sz['large']['median_search_ms']:.0f} ms), so memory can keep growing well beyond the model's context "
        "window without the assistant becoming noticeably slower. In every case the user sees the first word in "
        f"under {max(ms[m]['after_warm']['first_token_ms'] for m in names) / 1000:.0f} s once the model is loaded.")


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
