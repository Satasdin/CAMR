"""Harness and evaluation tests: TC-07 to TC-22."""

from __future__ import annotations

import json
import socket
import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest

from camr.cli.commands import cmd_analyse
from camr.cli.main import main as cli_main
from camr.config import CeilingModelConfig, ConfigError, LocalModelConfig
from camr.eval import GapAnalyzer, RunLogger, contains, exact_match, extract_answer, f1, math_accuracy, score
from camr.harness import (
    AblationRunner,
    ExperimentRunner,
    LeakageError,
    Workspace,
    build_corpus,
    check_holdout,
    ingest,
    load_questions,
    load_sample,
)
from camr.memory import Document, HashingEmbedder
from camr.models.runner import CloudRunner, GenerationError, OllamaRunner

from conftest import FIXTURES, ScriptedRunner, fixture_config


POPQA_FACTS = {"Kithuku": "botanist", "Ondiri": "Kenya", "Zeta": "jazz", "Loolmalasin": "Tanzania"}


def question_of(prompt: str) -> str:
    return prompt.rsplit("Question:", 1)[-1]


def oracle_reader(prompt: str) -> str:
    """Toy reader: answers only if a note about the question's subject states the answer."""
    notes = prompt.split("Notes:", 1)[1].split("Question:", 1)[0].splitlines() if "Notes:" in prompt else []
    for subject, answer in POPQA_FACTS.items():
        if subject in question_of(prompt):
            if any(subject in line and answer in line for line in notes):
                return answer
    return "unknown"


def oracle_ceiling(prompt: str) -> str:
    """Toy ceiling: 'knows' every PopQA fact parametrically."""
    return next((a for s, a in POPQA_FACTS.items() if s in question_of(prompt)), "unknown")


def workspace(cfg, local=None, ceiling=None):
    return Workspace(cfg, local_runner=local or ScriptedRunner("local"),
                     ceiling_runner=ceiling or ScriptedRunner("cloud", remote=True),
                     embedder=HashingEmbedder(cfg.embedder.dim))


# ------------------------------------------------------------------ TC-07
def test_ollama_runner_is_greedy_and_loopback_only():
    r = OllamaRunner(LocalModelConfig(host="http://127.0.0.1:11434"), seed=5)
    opts = r.payload("hi")["options"]
    assert opts["temperature"] == 0 and opts["top_k"] == 1 and opts["seed"] == 5
    OllamaRunner(LocalModelConfig(host="http://localhost:11434"))
    with pytest.raises(ConfigError):
        OllamaRunner(LocalModelConfig(host="http://10.0.0.5:11434"))


def test_ollama_runner_parses_response():
    class Sess:
        def post(self, url, json, timeout):
            assert url.endswith("/api/generate") and json["stream"] is False
            return SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: {"response": "Paris", "prompt_eval_count": 12, "eval_count": 2})
    g = OllamaRunner(LocalModelConfig(), session=Sess()).generate("q")
    assert (g.text, g.prompt_tokens, g.generated_tokens) == ("Paris", 12, 2)


# ------------------------------------------------------------------ TC-08
class _Err(Exception):
    def __init__(self, retryable):
        super().__init__("boom")
        self.retryable = retryable


def _cloud(responses):
    calls = []

    class Messages:
        def create(self, **kw):
            calls.append(kw)
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

    return SimpleNamespace(messages=Messages()), calls


def _resp(text="Paris", stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
                           stop_reason=stop, model="claude-opus-5-5",
                           usage=SimpleNamespace(input_tokens=20, output_tokens=3))


def test_cloud_runner_retries_with_exponential_backoff(monkeypatch):
    client, calls = _cloud([_Err(True), _Err(True), _resp()])
    sleeps = []
    r = CloudRunner(CeilingModelConfig(max_retries=4, backoff_base_s=2.0), client=client, sleep=sleeps.append)
    monkeypatch.setattr(r, "_retryable", lambda e: getattr(e, "retryable", False))
    g = r.generate("q")
    assert g.text == "Paris" and g.prompt_tokens == 20 and g.model_version == "claude-opus-5-5"
    assert sleeps == [2.0, 4.0]
    assert calls[0]["model"] == "claude-opus-5-5" and "temperature" not in calls[0]


def test_cloud_runner_fails_after_exhausting_retries_or_on_refusal(monkeypatch):
    client, _ = _cloud([_Err(True)] * 3)
    r = CloudRunner(CeilingModelConfig(max_retries=2), client=client, sleep=lambda s: None)
    monkeypatch.setattr(r, "_retryable", lambda e: getattr(e, "retryable", False))
    with pytest.raises(GenerationError):
        r.generate("q")
    client, calls = _cloud([_Err(False)])
    r = CloudRunner(CeilingModelConfig(max_retries=5), client=client, sleep=lambda s: None)
    monkeypatch.setattr(r, "_retryable", lambda e: getattr(e, "retryable", False))
    with pytest.raises(GenerationError):
        r.generate("q")
    assert len(calls) == 1  # non-retryable errors are not retried
    client, _ = _cloud([_resp(stop="refusal")])
    with pytest.raises(GenerationError):
        CloudRunner(CeilingModelConfig(), client=client).generate("q")


# ------------------------------------------------------------------ TC-09
def test_sample_is_fixed_persisted_and_order_invariant(tmp_path, cfg):
    b = cfg.benchmarks["hotpotqa"]
    s1 = load_sample("hotpotqa", b, 7, tmp_path / "s")
    s2 = load_sample("hotpotqa", b, 7, tmp_path / "s")
    assert [q.qid for q in s1] == [q.qid for q in s2]
    meta = json.loads((tmp_path / "s" / "hotpotqa.json").read_text())
    assert meta["seed"] == 7 and meta["question_ids"] == [q.qid for q in s1]
    reordered = tmp_path / "rev.json"
    reordered.write_text(json.dumps(list(reversed(json.loads((FIXTURES / "hotpotqa.json").read_text())))))
    b2 = b.__class__(path=str(reordered), n=b.n)
    s3 = load_sample("hotpotqa", b2, 7, tmp_path / "s2")
    assert [q.qid for q in s3] == [q.qid for q in s1]
    assert [q.qid for q in load_sample("hotpotqa", b, 7, tmp_path / "s", n=2)] == [q.qid for q in s1[:2]]
    with pytest.raises(ValueError):
        load_sample("hotpotqa", b, 7, tmp_path / "s", n=99)
    with pytest.raises(ValueError):
        load_sample("hotpotqa", b, 8, tmp_path / "s")


def test_loaders_read_official_layouts():
    wiki = load_questions("2wikimultihopqa", FIXTURES / "2wikimultihopqa.json")
    assert wiki[1].context == [("Alpha Road", "Alpha Road is a 1954 drama film."),
                               ("Beta Street", "Beta Street is a 1971 comedy film.")]
    pop = load_questions("popqa", FIXTURES / "popqa.jsonl")
    assert pop[0].answers == ["botanist", "plant scientist"] and pop[0].task_type == "single_hop"
    assert load_questions("gsm8k", FIXTURES / "gsm8k.jsonl")[0].task_type == "reasoning"


# ------------------------------------------------------------------ TC-10
def test_scoring_metrics():
    assert extract_answer("Answer: The Eiffel Tower.\nBecause...") == "The Eiffel Tower."
    assert exact_match("the Eiffel Tower!", ["Eiffel Tower"]) == 1.0
    assert f1("Eiffel Tower in Paris", ["Eiffel Tower"]) == pytest.approx(2 * 0.5 * 1 / 1.5)
    assert contains("He worked as a botanist in Kenya.", ["botanist"]) == 1.0
    assert contains("He was a botanistic writer.", ["botanist"]) == 0.0
    assert math_accuracy("so 4 x 1250 = 5000\n#### 5000", "4*1250=5000\n#### 5,000") == 1.0
    assert math_accuracy("The answer is 26.", "#### 26") == 1.0
    assert math_accuracy("#### 25", "#### 26") == 0.0
    assert set(score("multi_hop", "x", ["x"])) == {"em", "f1", "contains"}
    assert score("reasoning", "#### 3", ["#### 3"]) == {"accuracy": 1.0}


# ------------------------------------------------------ TC-11, TC-19, TC-20
def test_records_are_complete_and_prompts_byte_identical(cfg):
    ws = workspace(cfg)
    ingest(ws)
    runner = ExperimentRunner(ws)
    r1 = runner.run("treatment", "hotpotqa", label="a", resume=False)
    r2 = runner.run("treatment", "hotpotqa", label="b", resume=False)
    p1 = [r[0] for r in ws.conn.execute("SELECT prompt FROM query_log WHERE run_id=? ORDER BY query_id", (r1,))]
    p2 = [r[0] for r in ws.conn.execute("SELECT prompt FROM query_log WHERE run_id=? ORDER BY query_id", (r2,))]
    assert p1 == p2 and len(p1) == 4  # NFR-05

    row = ws.conn.execute("SELECT * FROM query_log WHERE run_id=? LIMIT 1", (r1,)).fetchone()
    cols = [d[0] for d in ws.conn.execute("SELECT * FROM query_log LIMIT 0").description]
    rec = dict(zip(cols, row))
    for field in ("question_id", "dataset", "task_type", "context_tokens", "prompt_tokens", "generated_tokens",
                  "retrieval_latency_ms", "generation_latency_ms", "e2e_latency_ms", "budget", "answer_text"):
        assert rec[field] is not None, field
    run = ws.conn.execute("SELECT model_name, config_json, template_id FROM run WHERE run_id=?", (r1,)).fetchone()
    assert run[0] == "local" and json.loads(run[1])["memory"]["token_budget"] == 512
    assert ws.conn.execute("SELECT COUNT(*) FROM retrieved_note rn JOIN query_log q USING(query_id)"
                           " WHERE q.run_id=?", (r1,)).fetchone()[0] > 0
    jsonl = list((ws.run_dir / "records").glob(f"run_{r1:04d}_*.jsonl"))[0].read_text().splitlines()
    assert json.loads(jsonl[0])["type"] == "run" and json.loads(jsonl[-1])["type"] == "end"
    assert len(jsonl) == 1 + 4 + 1


def test_only_ceiling_touches_the_cloud_runner(cfg, monkeypatch):
    local = ScriptedRunner("local")
    cloud = ScriptedRunner("cloud", remote=True)
    ws = Workspace(cfg, local_runner=local, ceiling_runner=cloud, embedder=HashingEmbedder(cfg.embedder.dim))
    ingest(ws)

    real_connect = socket.socket.connect

    def guarded(self, addr):  # NFR-06: no non-loopback connection outside the ceiling
        host = addr[0] if isinstance(addr, tuple) else addr
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"network connection to {host}")
        return real_connect(self, addr)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    runner = ExperimentRunner(ws)
    for cond in ("floor", "treatment"):
        runner.run(cond, "popqa")
    assert cloud.prompts == []
    runner.run("ceiling", "popqa")
    assert len(cloud.prompts) == 4
    assert all("Notes:" not in p for p in cloud.prompts)  # ceiling sends the bare question only


# ------------------------------------------------------------------ TC-21
def test_holdout_guard(cfg):
    sample = load_questions("hotpotqa", FIXTURES / "hotpotqa.json")
    docs = build_corpus("hotpotqa", cfg.benchmarks["hotpotqa"], sample, 7)
    assert {d.dataset for d in docs} == {"hotpotqa"}
    check_holdout(docs, sample)  # supporting paragraphs are fine
    leaked = docs + [Document("hotpotqa", "qa", f"Q: {sample[0].question} A: {sample[0].answers[0]}")]
    with pytest.raises(LeakageError):
        check_holdout(leaked, sample)


def test_popqa_requires_a_corpus(cfg):
    b = cfg.benchmarks["popqa"].__class__(path=cfg.benchmarks["popqa"].path, corpus=None, n=4)
    with pytest.raises(ValueError, match="corpus"):
        build_corpus("popqa", b, [], 7)


# ------------------------------------------------------------------ TC-22
def test_runtime_down_logs_failures_and_continues(cfg):
    down = ScriptedRunner("local", fail_when=lambda p: any(w in question_of(p) for w in ("Rusalka", "Acme")))
    ws = workspace(cfg, local=down)
    ingest(ws)
    n_notes = ws.store.count("verbatim")
    run_id = ExperimentRunner(ws).run("treatment", "hotpotqa")
    rows = ws.conn.execute("SELECT status, error FROM query_log WHERE run_id=?", (run_id,)).fetchall()
    assert sorted(r[0] for r in rows) == ["failed", "failed", "ok", "ok"]
    assert ws.conn.execute("SELECT COUNT(*) FROM score s JOIN query_log q USING(query_id)"
                           " WHERE q.status='failed'").fetchone()[0] == 0
    assert ws.store.count("verbatim") == n_notes
    assert ws.conn.execute("SELECT status FROM run WHERE run_id=?", (run_id,)).fetchone()[0] == "completed"


def test_real_ollama_unreachable_raises_generation_error():
    r = OllamaRunner(LocalModelConfig(host="http://127.0.0.1:9", timeout_s=1))
    with pytest.raises(GenerationError):
        r.generate("hello")


# ------------------------------------------------------------------ TC-13
def _fake_runs(conn, floor, ceil, treat, task="single_hop", bench="popqa"):
    lg = RunLogger(conn)
    for cond, vals in (("floor", floor), ("ceiling", ceil), ("treatment", treat)):
        rid = lg.start_run(label="main", condition=cond, benchmark=bench, task_type=task, model_name="m",
                           model_version=None, config_json="{}", config_hash="h", template_id="t", seed=1)
        for i, v in enumerate(vals):
            lg.log_query(rid, question_id=str(i), dataset=bench, task_type=task, question="q", status="ok",
                         context_tokens=100 if cond == "treatment" else 0, e2e_ms=10.0, retrieval_ms=1.0,
                         scores={"contains": v})
        lg.finish_run(rid)


def test_gap_closed_and_bootstrap():
    conn = sqlite3.connect(":memory:")
    rng = np.random.default_rng(0)
    n = 300
    floor = (rng.random(n) < 0.2).astype(float)
    ceil = np.maximum(floor, (rng.random(n) < 0.8)).astype(float)
    treat = np.where(rng.random(n) < 0.5, ceil, floor)
    _fake_runs(conn, floor, ceil, treat)
    [r] = GapAnalyzer(conn, {"popqa": "contains"}, bootstrap=500).compute("main")
    expected = (treat.mean() - floor.mean()) / (ceil.mean() - floor.mean())
    assert r.gap_closed == pytest.approx(expected)
    assert r.ci_low < r.gap_closed < r.ci_high
    assert r.n == n and not r.unstable
    assert r.gap_per_1k_tokens == pytest.approx(expected * 10)


def test_gap_flags_unstable_denominator():
    conn = sqlite3.connect(":memory:")
    _fake_runs(conn, [1, 0, 1, 0], [1, 0, 1, 0], [1, 1, 1, 0], task="reasoning", bench="gsm8k")
    [r] = GapAnalyzer(conn, {"gsm8k": "contains"}, bootstrap=100).compute("main")
    assert r.unstable and r.gap_closed is None and r.absolute_gain == pytest.approx(0.25)


# ------------------------------------------------------------ TC-12, TC-18
def test_ablation_plan_covers_variants_and_sweep(tmp_path):
    cfg = fixture_config(tmp_path).with_overrides({"ablation": {
        "variants": [{"label": "control", "overrides": {"memory": {"retrieval_policy": "similarity_only",
                                                                    "weights": {"similarity": 1, "recency": 0, "importance": 0}}}},
                     {"label": "full", "overrides": {}}],
        "budget_sweep": [0, 64], "sweep_base": "full"}})
    ws = workspace(cfg)
    steps = AblationRunner(ws).plan(cfg.ablation)
    assert [s[0] for s in steps] == ["control", "full", "budget-0000", "budget-0064"]
    assert steps[0][1].memory.retrieval_policy == "similarity_only"
    assert steps[3][1].memory.token_budget == 64


def test_reproduce_end_to_end_and_memory_closes_the_gap(tmp_path):
    cfg = fixture_config(tmp_path).with_overrides({"ablation": {
        "variants": [{"label": "control", "overrides": {"memory": {"retrieval_policy": "similarity_only",
                                                                    "weights": {"similarity": 1, "recency": 0, "importance": 0}}}},
                     {"label": "full", "overrides": {}}],
        "budget_sweep": [0, 256], "sweep_base": "full"}})
    local = ScriptedRunner("local", respond=oracle_reader)
    ceiling = ScriptedRunner("cloud", respond=oracle_ceiling, remote=True)
    ws = workspace(cfg, local=local, ceiling=ceiling)
    ingest(ws)
    runner = ExperimentRunner(ws)
    for cond in ("floor", "ceiling", "treatment"):
        runner.run(cond, "popqa")
    AblationRunner(ws).run(cfg.ablation, benchmarks=["popqa"])
    ws.close()
    summary = cmd_analyse(ws.run_dir, cfg=cfg)
    [main] = summary["main"]
    assert main["floor"] == 0.0 and main["ceiling"] == 1.0
    assert main["gap_closed"] == pytest.approx(1.0)  # every PopQA fact is in memory
    sweep = {r["budget"]: r["gap_closed"] for r in summary["budget_sweep"]}
    assert sweep[0] == 0.0 and sweep[256] == pytest.approx(1.0)
    cov = {(r["label"], r["benchmark"]): r for r in summary["coverage"]}
    assert cov[("main", "popqa")]["answer_in_store"] == 1.0
    assert cov[("budget-0000", "popqa")]["answer_in_context"] == 0.0
    assert cov[("main", "popqa")]["correct_when_in_context"] == 1.0
    for f in ("gap_main.md", "ablation.md", "budget_sweep.md", "templates.md", "summary.json", "coverage.md"):
        assert (ws.run_dir / "tables" / f).exists()


def test_cli_reproduce_with_dry_run_models(tmp_path):
    cfg = fixture_config(tmp_path)
    cfg_path = tmp_path / "c.yaml"
    raw = cfg.to_dict()
    raw["ablation"] = {"variants": [{"label": "control", "overrides": {}}], "budget_sweep": [0, 128],
                       "sweep_base": "control"}
    raw["profile"] = {"repeats": 1, "n": 1, "benchmark": "hotpotqa", "warmup": 0}
    import yaml
    cfg_path.write_text(yaml.safe_dump(raw))
    assert cli_main(["reproduce", "--config", str(cfg_path)]) == 0
    run_dir = tmp_path / "run"
    assert (run_dir / "camr.sqlite").exists() and (run_dir / "tables" / "profile.json").exists()
    prof = json.loads((run_dir / "tables" / "profile.json").read_text())
    assert prof["treatment"]["queries"] == 1 and "hardware" in prof
    assert cli_main(["analyse", "--run-dir", str(run_dir)]) == 0


def test_cli_reports_config_errors(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("memory: {wieghts: {}}\n")
    assert cli_main(["run", "--config", str(p), "--condition", "floor", "--benchmark", "popqa"]) == 2
