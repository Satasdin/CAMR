"""Single configuration object through which every switchable component is bound (NFR-07).

The proposal places configuration inside ``camr.cli``; it lives here instead, as a
leaf module, because ``camr.memory`` must read it and the package diagram forbids
``camr.memory`` from depending on ``camr.cli``.  Unknown keys are rejected so a
typo in an ablation file fails loudly instead of silently running the default.
"""

from __future__ import annotations

import copy
import dataclasses
import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised for invalid or inconsistent configuration."""


@dataclass
class LocalModelConfig:
    backend: str = "ollama"  # ollama | dry-run
    name: str = "qwen2.5:3b"
    host: str = "http://127.0.0.1:11434"
    max_tokens: int = 256
    timeout_s: float = 300.0
    keep_alive: str = "30m"
    num_ctx: int = 4096
    think: str | None = None  # reasoning models (e.g. gpt-oss): low | medium | high
    num_thread: int | None = None  # CPU threads for the model; leave one core for the embedder (measured: removes retrieval tail)


@dataclass
class CeilingModelConfig:
    backend: str = "anthropic"  # anthropic | ollama (local larger-model proxy, pilots only) | dry-run
    name: str = "claude-opus-5-5"  # pinned for the whole study (NFR-09)
    host: str = "http://127.0.0.1:11434"  # ollama backend: local, or https://ollama.com for cloud models
    api_key_env: str = "OLLAMA_API_KEY"  # read only when host is not loopback (Ollama Cloud)
    think: str | None = None  # reasoning effort for reasoning models (gpt-oss: low | medium | high)
    base_url: str = "https://api.moonshot.ai/v1"  # openai_compat backend (e.g. Kimi on Moonshot)
    temperature: float | None = None  # openai_compat: None = provider default (Kimi accepts only 1)
    max_tokens: int = 16000
    effort: str | None = "medium"
    timeout_s: float = 120.0
    max_retries: int = 4
    backoff_base_s: float = 2.0


@dataclass
class EmbedderConfig:
    backend: str = "bge"  # bge | hashing
    name: str = "BAAI/bge-small-en-v1.5"
    dim: int = 384
    query_instruction: str = "Represent this sentence for searching relevant passages: "
    device: str = "cpu"
    batch_size: int = 32
    torch_threads: int | None = None  # pin the embedder's CPU threads (e.g. 1 beside a model on 3 cores)


@dataclass
class TokenizerConfig:
    backend: str = "regex"  # regex | hf
    name: str | None = None


@dataclass
class Weights:
    similarity: float = 0.60
    recency: float = 0.15
    importance: float = 0.25


@dataclass
class MemoryConfig:
    write_policy: str = "structured"  # verbatim | structured
    screening: bool = True
    chunk_tokens: int = 96
    chunk_overlap: int = 16
    min_note_tokens: int = 3
    max_note_tokens: int = 160
    importance: str = "heuristic"  # heuristic | model
    retrieval_policy: str = "composite"  # similarity_only | composite
    weights: Weights = field(default_factory=Weights)
    recency_decay: float = 0.99  # per hour
    normalise_similarity: bool = True
    k: int = 20
    token_budget: int = 512
    packing: str = "greedy_stop"  # greedy_stop | greedy_skip
    write_back: bool = False
    graph_layer: bool = False
    clock_step_hours: float = 1.0
    # Capability-adaptive gating (docs/BRIDGING_THE_GAP.md section 3.1).
    min_similarity: float = 0.0  # abstain when the best note is weaker than this (raw cosine)
    similarity_margin: float | None = None  # admit only notes within this of the best one
    # Entity-bridge expansion (section 3.2).
    expansion: str = "none"  # none | entity
    expansion_seeds: int = 3
    expansion_per_seed: int = 2
    # Memory used for reasoning tasks (section 3.3).
    reasoning_memory: str = "facts"  # facts | exemplars | none
    exemplar_max_tokens: int = 400

    @property
    def note_type(self) -> str:
        """Key of the note population this configuration reads and writes.

        Write policy and screening change what is *stored*, so each combination
        is kept as its own population inside the single store file.  This lets
        the ablation compare write policies without a second database.
        """
        return self.write_policy + ("" if self.screening else "-unscreened")


@dataclass
class BenchmarkConfig:
    path: str = ""
    corpus: str | None = None  # required for PopQA, which ships no documents
    n: int = 100
    extra_corpus_questions: int = 0  # grow the store with paragraphs of unsampled questions
    exemplars: str | None = None  # gsm8k only: train split used as procedural memory


@dataclass
class AnalysisConfig:
    bootstrap: int = 1000
    ci: float = 0.95
    min_denominator: float = 0.05


@dataclass
class ProfileConfig:
    repeats: int = 5
    n: int = 20
    benchmark: str = "hotpotqa"
    warmup: int = 2


@dataclass
class AblationVariant:
    label: str
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass
class AblationConfig:
    benchmarks: list[str] = field(default_factory=list)
    variants: list[AblationVariant] = field(default_factory=list)
    budget_sweep: list[int] = field(default_factory=lambda: [0, 128, 256, 512, 1024, 2048])
    sweep_base: str = "full"  # label of the variant the budget sweep is run on


DEFAULT_PRIMARY_METRIC = {
    "popqa": "contains",
    "hotpotqa": "em",
    "2wikimultihopqa": "em",
    "gsm8k": "accuracy",
}


@dataclass
class Config:
    seed: int = 13
    run_dir: str | None = None
    # Opt-in: ceiling_rag gives the cloud model the same notes (sends public benchmark text).
    extra_conditions: list[str] = field(default_factory=list)
    local_model: LocalModelConfig = field(default_factory=LocalModelConfig)
    ceiling_model: CeilingModelConfig = field(default_factory=CeilingModelConfig)
    embedder: EmbedderConfig = field(default_factory=EmbedderConfig)
    tokenizer: TokenizerConfig = field(default_factory=TokenizerConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    benchmarks: dict[str, BenchmarkConfig] = field(default_factory=dict)
    primary_metric: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_PRIMARY_METRIC))
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)
    ablation: AblationConfig = field(default_factory=AblationConfig)

    # ------------------------------------------------------------------ io
    @classmethod
    def load(cls, path: str | Path) -> "Config":
        path = Path(path)
        with path.open() as fh:
            raw = yaml.safe_load(fh) or {}
        cfg = cls.from_dict(raw)
        # Relative data paths are resolved against the config file's directory.
        base = path.resolve().parent
        for b in cfg.benchmarks.values():
            if b.path and not Path(b.path).is_absolute():
                b.path = str((base / b.path).resolve())
            if b.corpus and not Path(b.corpus).is_absolute():
                b.corpus = str((base / b.corpus).resolve())
            if b.exemplars and not Path(b.exemplars).is_absolute():
                b.exemplars = str((base / b.exemplars).resolve())
        if cfg.run_dir and not Path(cfg.run_dir).is_absolute():
            cfg.run_dir = str((base / cfg.run_dir).resolve())
        return cfg

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Config":
        cfg = _build(cls, raw, "config")
        cfg.validate()
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        """Canonical serialisation stored in every Run row (self-describing records)."""
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()[:12]

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.to_dict(), sort_keys=False))

    def with_overrides(self, overrides: dict[str, Any]) -> "Config":
        merged = _deep_merge(self.to_dict(), overrides)
        return Config.from_dict(merged)

    def resolve_run_dir(self) -> Path:
        if self.run_dir:
            return Path(self.run_dir)
        return Path("results") / _dt.date.today().isoformat()

    # ---------------------------------------------------------- validation
    def validate(self) -> None:
        m = self.memory
        w = m.weights
        for name, value in (("similarity", w.similarity), ("recency", w.recency), ("importance", w.importance)):
            if value < 0:
                raise ConfigError(f"memory.weights.{name} must be non-negative")
        if abs(w.similarity + w.recency + w.importance - 1.0) > 1e-6:
            raise ConfigError("memory.weights must sum to one (Equation 4.1)")
        if not 0.0 < m.recency_decay < 1.0:
            raise ConfigError("memory.recency_decay must lie in the open unit interval (Equation 4.3)")
        if m.token_budget < 0:
            raise ConfigError("memory.token_budget must be >= 0")
        if m.k < 1:
            raise ConfigError("memory.k must be >= 1")
        _choice("memory.write_policy", m.write_policy, {"verbatim", "structured"})
        _choice("memory.retrieval_policy", m.retrieval_policy, {"similarity_only", "composite"})
        _choice("memory.packing", m.packing, {"greedy_stop", "greedy_skip"})
        _choice("memory.importance", m.importance, {"heuristic", "model"})
        _choice("memory.expansion", m.expansion, {"none", "entity"})
        _choice("memory.reasoning_memory", m.reasoning_memory, {"facts", "exemplars", "none"})
        if m.similarity_margin is not None and m.similarity_margin < 0:
            raise ConfigError("memory.similarity_margin must be >= 0")
        for c in self.extra_conditions:
            _choice("extra_conditions[]", c, {"ceiling_rag"})
        _choice("local_model.backend", self.local_model.backend, {"ollama", "dry-run"})
        _choice("ceiling_model.backend", self.ceiling_model.backend, {"anthropic", "ollama", "openai_compat", "dry-run"})
        _choice("embedder.backend", self.embedder.backend, {"bge", "hashing"})
        _choice("tokenizer.backend", self.tokenizer.backend, {"regex", "hf"})
        if m.chunk_overlap >= m.chunk_tokens:
            raise ConfigError("memory.chunk_overlap must be smaller than memory.chunk_tokens")
        if m.graph_layer:
            raise ConfigError(
                "memory.graph_layer is the optional fifth increment (FR-18) and is not implemented; "
                "register a RetrievalPolicy under a new name instead"
            )
        labels = [v.label for v in self.ablation.variants]
        if len(labels) != len(set(labels)):
            raise ConfigError("ablation variant labels must be unique")


def _choice(name: str, value: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise ConfigError(f"{name}={value!r}; expected one of {sorted(allowed)}")


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (over or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _build(tp: Any, raw: Any, where: str) -> Any:
    """Recursively build dataclass ``tp`` from ``raw``, rejecting unknown keys."""
    if raw is None:
        return tp()
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: expected a mapping")
    hints = {f.name: f for f in dataclasses.fields(tp)}
    unknown = set(raw) - set(hints)
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {sorted(unknown)}")
    kwargs: dict[str, Any] = {}
    for name, value in raw.items():
        sub = f"{where}.{name}"
        if tp is Config and name == "benchmarks":
            kwargs[name] = {k: _build(BenchmarkConfig, v, f"{sub}.{k}") for k, v in (value or {}).items()}
        elif tp is AblationConfig and name == "variants":
            kwargs[name] = [_build(AblationVariant, v, f"{sub}[{i}]") for i, v in enumerate(value or [])]
        elif name in _NESTED.get(tp, {}):
            kwargs[name] = _build(_NESTED[tp][name], value, sub)
        else:
            kwargs[name] = value
    try:
        return tp(**kwargs)
    except TypeError as exc:  # missing required field
        raise ConfigError(f"{where}: {exc}") from exc


_NESTED: dict[Any, dict[str, Any]] = {
    Config: {
        "local_model": LocalModelConfig,
        "ceiling_model": CeilingModelConfig,
        "embedder": EmbedderConfig,
        "tokenizer": TokenizerConfig,
        "memory": MemoryConfig,
        "analysis": AnalysisConfig,
        "profile": ProfileConfig,
        "ablation": AblationConfig,
    },
    MemoryConfig: {"weights": Weights},
}
