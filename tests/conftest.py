from __future__ import annotations

import time
from pathlib import Path

import pytest

from camr.config import Config
from camr.memory import HashingEmbedder, MemoryEngine, SQLiteVectorStore
from camr.models.runner import Generation, GenerationError, ModelRunner
from camr.models.tokenizer import RegexTokenizer

FIXTURES = Path(__file__).parent / "fixtures"


class ScriptedRunner(ModelRunner):
    """Test double: records prompts; answers via a function; can fail on demand."""

    def __init__(self, name="scripted", respond=None, fail_when=None, remote=False):
        self.model_name = name
        self.model_version = f"{name}-v1"
        self.is_remote = remote
        self.prompts: list[str] = []
        self._respond = respond or (lambda p: "unknown")
        self._fail_when = fail_when or (lambda p: False)

    def generate(self, prompt: str) -> Generation:
        self.prompts.append(prompt)
        if self._fail_when(prompt):
            raise GenerationError("scripted failure")
        t0 = time.perf_counter()
        text = self._respond(prompt)
        return Generation(text, len(prompt.split()), len(text.split()), (time.perf_counter() - t0) * 1000,
                          self.model_name, self.model_version)


def fixture_config(tmp_path: Path, **memory) -> Config:
    raw = {
        "seed": 7,
        "run_dir": str(tmp_path / "run"),
        "local_model": {"backend": "dry-run"},
        "ceiling_model": {"backend": "dry-run"},
        "embedder": {"backend": "hashing", "dim": 128},
        "memory": {"write_policy": "verbatim", **memory},
        "benchmarks": {
            "popqa": {"path": str(FIXTURES / "popqa.jsonl"), "corpus": str(FIXTURES / "popqa_corpus.jsonl"), "n": 4},
            "hotpotqa": {"path": str(FIXTURES / "hotpotqa.json"), "n": 4},
            "2wikimultihopqa": {"path": str(FIXTURES / "2wikimultihopqa.json"), "n": 2},
            "gsm8k": {"path": str(FIXTURES / "gsm8k.jsonl"), "n": 3},
        },
        "analysis": {"bootstrap": 200},
    }
    return Config.from_dict(raw)


@pytest.fixture
def cfg(tmp_path):
    return fixture_config(tmp_path)


@pytest.fixture
def tokenizer():
    return RegexTokenizer()


@pytest.fixture
def embedder():
    return HashingEmbedder(128)


@pytest.fixture(params=[True, False], ids=["sqlite-vec", "numpy"])
def store(request, tmp_path, embedder):
    if request.param:
        pytest.importorskip("sqlite_vec")
    s = SQLiteVectorStore(tmp_path / "m.sqlite", dim=embedder.dim, embedder_name=embedder.name, use_vec=request.param)
    yield s
    s.close()


@pytest.fixture
def engine(cfg, store, embedder, tokenizer):
    return MemoryEngine.from_config(cfg, store=store, embedder=embedder, tokenizer=tokenizer)
