"""Workspace and ExperimentRunner (FR-10, FR-11, FR-13).

A workspace is one results directory:

    results/YYYY-MM-DD/
        camr.sqlite      memory + harness tables, one file (NFR-03)
        records/*.jsonl  one structured record per query (NFR-04)
        samples/*.json   the fixed paired samples (DR-02)
        figures/  tables/
        config.yaml      the configuration that produced it
"""

from __future__ import annotations

import logging
import sqlite3
import time
from functools import cached_property
from pathlib import Path

from camr.config import Config
from camr.eval.analysis import TASK_TYPES
from camr.eval.logger import RunLogger
from camr.eval.scoring import score
from camr.harness.benchmarks import Question, build_corpus, check_holdout, load_sample
from camr.memory.clock import LogicalClock
from camr.memory.embedder import Embedder, build_embedder
from camr.memory.engine import IngestSummary, MemoryEngine
from camr.memory.store import SQLiteVectorStore
from camr.models.prompt import answer_template
from camr.models.runner import GenerationError, ModelRunner, build_ceiling_runner, build_local_runner
from camr.models.tokenizer import Tokenizer, build_tokenizer

log = logging.getLogger(__name__)

CONDITIONS = ("floor", "ceiling", "treatment")


class Workspace:
    def __init__(self, cfg: Config, run_dir: str | Path | None = None, *, local_runner: ModelRunner | None = None,
                 ceiling_runner: ModelRunner | None = None, embedder: Embedder | None = None):
        self.cfg = cfg
        self.run_dir = Path(run_dir) if run_dir else cfg.resolve_run_dir()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("records", "samples", "figures", "tables"):
            (self.run_dir / sub).mkdir(exist_ok=True)
        cfg_path = self.run_dir / "config.yaml"
        if not cfg_path.exists():
            cfg.dump(cfg_path)
        self._local_runner = local_runner
        self._ceiling_runner = ceiling_runner
        self._embedder = embedder
        self._samples: dict[str, list[Question]] = {}

    @property
    def db_path(self) -> Path:
        return self.run_dir / "camr.sqlite"

    # Components are built lazily: a floor run never loads the embedder, and
    # nothing but a ceiling run ever constructs the network-facing runner (NFR-06).
    @cached_property
    def tokenizer(self) -> Tokenizer:
        return build_tokenizer(self.cfg.tokenizer.backend, self.cfg.tokenizer.name)

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = build_embedder(self.cfg.embedder)
        return self._embedder

    @cached_property
    def store(self) -> SQLiteVectorStore:
        return SQLiteVectorStore(self.db_path, dim=self.embedder.dim, embedder_name=self.embedder.name)

    @cached_property
    def conn(self) -> sqlite3.Connection:
        # Harness tables share the store's connection when it exists, so both
        # live in one file under one transaction boundary.
        if "store" in self.__dict__:
            return self.store.conn
        return sqlite3.connect(self.db_path)

    @cached_property
    def logger(self) -> RunLogger:
        return RunLogger(self.conn, self.run_dir / "records")

    @property
    def local_runner(self) -> ModelRunner:
        if self._local_runner is None:
            runner = build_local_runner(self.cfg.local_model, self.cfg.seed)
            describe = getattr(runner, "describe", None)
            if describe:
                describe()
            self._local_runner = runner
        return self._local_runner

    @property
    def ceiling_runner(self) -> ModelRunner:
        if self._ceiling_runner is None:
            self._ceiling_runner = build_ceiling_runner(self.cfg.ceiling_model)
        return self._ceiling_runner

    def sample(self, benchmark: str, n: int | None = None) -> list[Question]:
        if benchmark not in self.cfg.benchmarks:
            raise KeyError(f"benchmark {benchmark!r} is not configured")
        if benchmark not in self._samples:  # parse the dataset file once per workspace
            self._samples[benchmark] = load_sample(
                benchmark, self.cfg.benchmarks[benchmark], self.cfg.seed, self.run_dir / "samples")
        sample = self._samples[benchmark]
        if n is None:
            return sample
        if n > len(sample):
            raise ValueError(f"{benchmark}: requested n={n} but the persisted sample has {len(sample)} questions")
        return sample[:n]

    def engine(self, cfg: Config, clock=None) -> MemoryEngine:
        needs_model = cfg.memory.write_policy == "structured" or cfg.memory.importance == "model"
        return MemoryEngine.from_config(
            cfg,
            store=self.store,
            embedder=self.embedder,
            tokenizer=self.tokenizer,
            local_runner=self.local_runner if needs_model else None,
            clock=clock,
        )

    def close(self) -> None:
        if "store" in self.__dict__:
            self.store.close()
        elif "conn" in self.__dict__:
            self.conn.close()


# ------------------------------------------------------------------ ingest


def ingest(ws: Workspace, cfg: Config | None = None, benchmarks: list[str] | None = None) -> list[IngestSummary]:
    """Populate the store for ``cfg``'s note population from every factual benchmark."""
    cfg = cfg or ws.cfg
    names = benchmarks or list(cfg.benchmarks)
    engine = ws.engine(cfg)
    summaries = []
    all_questions: list[Question] = []
    corpora = []
    for name in names:
        sample = ws.sample(name)
        all_questions.extend(sample)
        docs = build_corpus(name, cfg.benchmarks[name], sample, cfg.seed)
        corpora.append((name, docs))
    # The guard runs against *every* sampled question, not just the benchmark's own.
    for name, docs in corpora:
        check_holdout(docs, all_questions)
    for name, docs in corpora:
        if not docs:
            continue
        log.info("ingesting %d %s documents as %s notes", len(docs), name, engine.note_type)
        summaries.append(engine.ingest(docs, progress=True))
    return summaries


# -------------------------------------------------------------------- runs


class ExperimentRunner:
    def __init__(self, ws: Workspace):
        self.ws = ws

    def existing_run(self, label: str, condition: str, benchmark: str, config_hash: str) -> int | None:
        self.ws.logger  # ensure the harness schema exists
        row = self.ws.conn.execute(
            "SELECT MAX(run_id) FROM run WHERE label=? AND condition=? AND benchmark=? AND config_hash=?"
            " AND status='completed'",
            (label, condition, benchmark, config_hash),
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def run(self, condition: str, benchmark: str, *, cfg: Config | None = None, n: int | None = None,
            label: str = "main", resume: bool = True) -> int:
        if condition not in CONDITIONS:
            raise ValueError(f"condition must be one of {CONDITIONS}")
        cfg = cfg or self.ws.cfg
        self.ws.logger  # create harness tables before the resume lookup
        if resume:
            prior = self.existing_run(label, condition, benchmark, cfg.fingerprint())
            if prior is not None:
                log.info("skipping %s/%s/%s: completed as run %d", label, condition, benchmark, prior)
                return prior
        questions = self.ws.sample(benchmark, n)
        task_type = TASK_TYPES[benchmark]
        with_memory = condition == "treatment"
        template = answer_template(task_type, with_memory)
        runner = self.ws.ceiling_runner if condition == "ceiling" else self.ws.local_runner

        engine = clock = None
        if with_memory:
            note_type = cfg.memory.note_type
            if self.ws.store.count(note_type) == 0:
                raise RuntimeError(f"memory population {note_type!r} is empty; run `camr ingest` first")
            self.ws.store.reset_access_state(note_type)
            start = self.ws.store.latest_created_at(note_type)
            clock = LogicalClock(start, cfg.memory.clock_step_hours)
            engine = self.ws.engine(cfg, clock)

        logger = self.ws.logger
        run_id = logger.start_run(
            label=label, condition=condition, benchmark=benchmark, task_type=task_type,
            model_name=runner.model_name, model_version=runner.model_version,
            config_json=cfg.to_json(), config_hash=cfg.fingerprint(), template_id=template.template_id,
            seed=cfg.seed,
        )
        log.info("run %d: %s %s %s (%d questions)", run_id, label, condition, benchmark, len(questions))
        served_versions: set[str] = set()
        status = "completed"
        try:
            for q in questions:
                self._one(run_id, q, template, runner, engine, cfg, served_versions)
                if clock:
                    clock.tick()
        except KeyboardInterrupt:
            status = "interrupted"
            raise
        finally:
            version = ",".join(sorted(served_versions)) or None
            logger.finish_run(run_id, status, model_version=version)
        return run_id

    def _one(self, run_id, q: Question, template, runner: ModelRunner, engine: MemoryEngine | None,
             cfg: Config, served: set[str]) -> None:
        t0 = time.perf_counter()
        recall = None
        if engine is not None:
            recall = engine.recall(q.question)
            prompt = template.render(q.question, recall.context)
        else:
            prompt = template.render(q.question)
        common = dict(
            question_id=q.qid, dataset=q.dataset, task_type=q.task_type, question=q.question, prompt=prompt,
            context_tokens=recall.context_tokens if recall else 0,
            retrieval_ms=recall.retrieval_ms if recall else None,
            budget=cfg.memory.token_budget if recall else None,
            retrieved=[{
                "note_id": c.note.note_id, "rank": c.rank, "similarity": c.similarity, "recency": c.recency,
                "importance": c.importance, "composite": c.composite, "tokens": c.tokens, "admitted": c.admitted,
            } for c in recall.candidates] if recall else None,
        )
        try:
            gen = runner.generate(prompt)
        except GenerationError as exc:
            # IR-02 / IR-07: logged as failed, never scored; the run continues.
            self.ws.logger.log_query(run_id, status="failed", error=str(exc),
                                     e2e_ms=(time.perf_counter() - t0) * 1000, **common)
            return
        e2e_ms = (time.perf_counter() - t0) * 1000
        if gen.model_version:
            served.add(gen.model_version)
        self.ws.logger.log_query(
            run_id, status="ok", prompt_tokens=gen.prompt_tokens, generated_tokens=gen.generated_tokens,
            generation_ms=gen.latency_ms, e2e_ms=e2e_ms, answer=gen.text,
            served_model=gen.meta.get("served_model", gen.model_version),
            scores=score(q.task_type, gen.text, q.answers), **common,
        )
