"""The answering systems an automation can call, behind one interface: ask, teach, forget.

  llm:<model>     the model alone (no company knowledge; teaching does nothing)
  stuff:<model>   the whole knowledge base pasted into every prompt ("context stuffing"; taught documents appended)
  rag:<model>     modern RAG over the same documents: hybrid search (dense + BM25, reciprocal-rank fusion), a
                  cross-encoder reranker, top 5 into LangChain's standard RAG prompt
  camr:<model>    CAMR: the documents in memory, the verified answerer (an answer is stated only if a stored
                  sentence supports it; otherwise the question is handed to a person)

Every answer records what it cost: model calls, prompt and generated tokens, seconds, and US dollars for the cloud
model at Moonshot's list price (input $3, output $15 per million tokens).
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AG = ROOT / "results/agentic"
PRICE = {"kimi-k3": (3.0, 15.0)}  # USD per million input / output tokens (Moonshot list price)
SYSTEM = ("You are the customer support assistant of Helio Solar. Answer the customer's question in one or two "
          "sentences. If you do not know the answer, say that you don't know.")
# per scenario: the instruction, what the documents are called, and the turn labels
PERSONAS = {"helio": (SYSTEM, "company documents", "Customer", "Assistant"),
            "fresh": ("You are a news assistant. Answer the question in one or two sentences. If you do not know the "
                      "answer, say that you don't know.", "news items", "Question", "Answer")}
DECLINE = re.compile(r"\b(?:don'?t|do not|cannot|can'?t|unable to) (?:know|find|determine|answer|confirm|provide|identify|tell|say|give|specify|share)|"
                     r"\bI (?:don'?t|do not) have\b|\bI'?m sorry\b|\bI am sorry\b|"
                     r"\bnot (?:mentioned|provided|specified|stated|available|in the)|\bno (?:specific )?"
                     r"(?:information|details|data)\b|\bI'?m not sure\b|\bI am not sure\b|\bnot sure\b", re.I)


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def runner(model: str):
    from camr.models.runner import CachedRunner

    el = _load("eager_learning", ROOT / "scripts/eager_learning.py")
    r = el.runner_for(model)
    if hasattr(r, "cfg") and hasattr(r.cfg, "max_tokens") and not model.startswith("kimi"):
        r.cfg.max_tokens = 96
    return CachedRunner(r, AG / "answers.sqlite", offline=False)


def cost_usd(model: str, prompt_tokens: int, gen_tokens: int) -> float:
    pin, pout = PRICE.get(model, (0.0, 0.0))
    return (prompt_tokens * pin + gen_tokens * pout) / 1e6


def declined(text: str) -> bool:
    from camr.memory.verify import abstention_like

    text = (text or "").replace("\u2019", "'").replace("\u2018", "'")  # "I don’t know" is a decline too (D-38)
    return abstention_like(text) or bool(DECLINE.search(text))


class Meter:
    def __init__(self, r, model: str):
        self.r, self.model, self.model_name = r, model, r.model_name
        self.reset()

    def reset(self):
        self.calls, self.pt, self.gt, self.ms = 0, 0, 0, 0.0

    def generate(self, prompt: str):
        g = self.r.generate(prompt)
        self.calls += 1
        self.pt += g.prompt_tokens or 0
        self.gt += g.generated_tokens or 0
        self.ms += g.latency_ms or 0.0
        return g

    def __getattr__(self, name):
        return getattr(self.r, name)

    def usage(self) -> dict:
        return {"calls": self.calls, "prompt_tokens": self.pt, "gen_tokens": self.gt, "model_ms": round(self.ms, 1),
                "cost_usd": round(cost_usd(self.model, self.pt, self.gt), 6)}


class System:
    """Documents by id; subclasses answer from them."""

    def __init__(self, model: str, scenario: str = "helio"):
        self.model = model
        self.persona = PERSONAS[scenario]
        self.docs: dict[str, tuple[str, str]] = {}
        self.reader = Meter(runner(model), model)

    def teach(self, doc_id: str, title: str, text: str) -> None:
        self.docs[doc_id] = (title, text)

    def forget(self, doc_id: str) -> None:
        self.docs.pop(doc_id, None)

    def answer(self, question: str) -> dict:
        raise NotImplementedError

    def ask(self, question: str) -> dict:
        self.reader.reset()
        t0 = time.perf_counter()
        out = self.answer(question)
        out.setdefault("stated", not declined(out["answer"]))
        return {**out, "wall_ms": round((time.perf_counter() - t0) * 1000, 1), **self.reader.usage()}


class LLMOnly(System):
    kind = "llm"

    def teach(self, doc_id, title, text):  # a model alone keeps nothing
        pass

    def answer(self, question):
        system, _, asker, answerer = self.persona
        return {"answer": self.reader.generate(f"{system}\n\n{asker}: {question}\n{answerer}:").text.strip()}


class Stuffing(System):
    kind = "stuff"

    def answer(self, question):
        kb = "\n".join(f"- {t}: {x}" for t, x in self.docs.values())
        system, docs, asker, answerer = self.persona
        p = f"{system} Use the {docs} below.\n\nDocuments:\n{kb}\n\n{asker}: {question}\n{answerer}:"
        return {"answer": self.reader.generate(p).text.strip(), "context_words": len(kb.split())}


class RAG(System):
    kind = "rag"
    _ce = None

    def __init__(self, model: str, scenario: str = "helio"):
        super().__init__(model, scenario)
        self.dir = Path(tempfile.mkdtemp(prefix="agentic-rag-"))
        self.engine, self.store = build_store(self.dir / "rag.sqlite")
        if RAG._ce is None:
            from sentence_transformers import CrossEncoder

            RAG._ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
        rb = _load("rag_bench", ROOT / "scripts/rag_bench.py")
        self.rt, self.prompt = rb.Retriever(self.engine, self.store, RAG._ce), rb.RAG_PROMPT

    def teach(self, doc_id, title, text):
        from camr.memory.note import Document

        super().teach(doc_id, title, text)
        self.engine.ingest([Document("agentic", doc_id, text, title)])

    def forget(self, doc_id):
        super().forget(doc_id)
        forget_doc(self.store, doc_id)

    def answer(self, question):
        notes, _ = self.rt.rerank(question, 5)
        ctx = "\n".join(f"- {n.text}" for n in notes)
        return {"answer": self.reader.generate(self.prompt.format(question=question, context=ctx)).text.strip(),
                "context_words": len(ctx.split())}


class CAMR(System):
    kind = "camr"

    def __init__(self, model: str, scenario: str = "helio"):
        super().__init__(model, scenario)
        from camr.memory.answer import READ, VerifiedAnswerer

        self.dir = Path(tempfile.mkdtemp(prefix="agentic-camr-"))
        self.engine, self.store = build_store(self.dir / "camr.sqlite")
        self.va = VerifiedAnswerer(self.engine, [self.reader], lookup=None, budget=128, fact_reader=True,
                                   compressed=True, typed=True, relation_cue=True, closed_book=True, template=READ)

    def teach(self, doc_id, title, text):
        from camr.memory.note import Document

        super().teach(doc_id, title, text)
        self.engine.ingest([Document("agentic", doc_id, text, title)])

    def forget(self, doc_id):
        super().forget(doc_id)
        forget_doc(self.store, doc_id)

    def answer(self, question):
        r = self.va.answer(question, allow_web=False)
        verified = r.status == "verified"
        lead = r.attempts[0].answer if r.attempts else ""
        return {"answer": r.claim if verified else lead, "stated": verified, "evidence": r.evidence,
                "source": r.source, "by": r.by}


def build_store(path: Path):
    from camr.memory.embedder import CachedEmbedder

    el = _load("eager_learning", ROOT / "scripts/eager_learning.py")
    el.CAMR["token_budget"] = 128
    engine, store = el.build_engine(path)
    engine.embedder = CachedEmbedder(engine.embedder, AG / "vectors.sqlite")
    return engine, store


def forget_doc(store, doc_id: str) -> int:
    ids = [r[0] for r in store.conn.execute("SELECT source_id FROM source WHERE doc_id=?", (doc_id,))]
    return sum(store.delete_source(i) for i in ids)


KINDS = {"llm": LLMOnly, "stuff": Stuffing, "rag": RAG, "camr": CAMR}


def make(spec: str, scenario: str = "helio") -> System:
    kind, model = spec.split(":", 1)
    return KINDS[kind](model, scenario)
