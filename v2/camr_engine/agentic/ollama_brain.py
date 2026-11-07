"""A model in Ollama as the agent's model: the lead, its parts, the skills, the page tests and the fact check work with
any model that writes text. What does not: CAMR's memory itself, which lays the model's own saved notes (its KV cache)
into it, and Ollama does not let anything in at that level. So with an Ollama model what the person told reaches it
as the told notes in each prompt, as text, and nothing it does is kept as notes (``memory_on`` is False).

The tools are offered in the instructions in the same words the local model's template uses (as for Claude,
camr_engine.agentic.claude_brain), and the reply is parsed by the same parser. Thinking is off, as for the local
model's agent steps. Only the Ollama server on this Mac is spoken to.
"""

from __future__ import annotations

import json
import time
import urllib.request

from camr_engine.agentic.brain import Prompt, Thought
from camr_engine.agentic.claude_brain import system_with_tools

HOST = "http://127.0.0.1:11434"
TIMEOUT_S = 900


def models(host: str = HOST) -> list[dict]:
    """The models Ollama has here: {name, size}. Empty when Ollama is not running."""
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as r:
            got = json.loads(r.read())
    except (OSError, ValueError):
        return []
    return [{"name": m.get("name", ""), "size": int(m.get("size") or 0)} for m in got.get("models") or []]


class OllamaBrain:
    memory_on = False

    def __init__(self, model: str, host: str = HOST, post=None):
        self.model, self.host = model, host
        self.label = f"ollama:{model}"
        self.post = post or self._post

    def _post(self, body: dict) -> dict:
        req = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            return json.loads(r.read())

    def think(self, p: Prompt) -> Thought:
        t = time.perf_counter()
        got = self.post({"model": self.model, "stream": False, "think": False,
                         "options": {"num_predict": p.max_tokens, "num_ctx": 32768},
                         "messages": [{"role": "system", "content": system_with_tools(p.system, p.tools)},
                                      {"role": "user", "content": p.user}]})
        text = (got.get("message") or {}).get("content") or ""
        total = time.perf_counter() - t
        n_out = int(got.get("eval_count") or 0)
        decode_s = (got.get("eval_duration") or 0) / 1e9
        first = (got.get("load_duration", 0) + got.get("prompt_eval_duration", 0)) / 1e9
        return Thought(text, [text], first, total, int(got.get("prompt_eval_count") or 0), n_out,
                       round(n_out / decode_s, 1) if decode_s else None)

    def keep(self, text: str, to: str | None = None, source: str = "model") -> dict | None:
        return None

    def moment(self, reach: str, mid: int) -> dict | None:
        return None

    def reaches(self) -> list[dict]:
        return []

    def close(self) -> None:
        pass
