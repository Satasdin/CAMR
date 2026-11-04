"""An OpenAI-compatible endpoint with memory: what OpenCode, LM Studio's clients, curl and any OpenAI SDK point at.

    python -m camr_engine.pair.openai --backend ollama          # or: camr serve --backend ollama
    curl http://127.0.0.1:11436/v1/chat/completions -H 'Content-Type: application/json' \\
      -d '{"model": "qwen3:1.7b", "messages": [{"role": "user", "content": "What did we pick for the logo?"}]}'

It sits in front of a local runtime that already speaks the OpenAI API, and gives it memory the way the Ollama
pairing does, with the same code (camr_engine.pair.ollama): before ``/v1/chat/completions`` is forwarded, notes on the
last user message are put at the front of that message, and once the answer has streamed back the exchange is
remembered. Streaming and whole answers both work; ``/v1/models`` and the other ``/v1/`` paths pass through as they
are, and nothing outside ``/v1/`` is served (``/camr_engine/metrics`` aside).

The backends (``--backend``), all on this Mac:

| backend | runtime | where it listens |
|---|---|---|
| ``ollama`` | Ollama's own OpenAI-style API | 127.0.0.1:11434 |
| ``lmstudio`` | LM Studio's server (``lms server start``) | 127.0.0.1:1234 |
| ``mlx`` | mlx_lm.server, MLX models on this Mac | 127.0.0.1:8080 |

Through each of them memory goes in as words, since none lets outside code put tensors into its model. The engine's
own reader, which reads rooms as saved keys and values, is meant to be the next backend behind the same routes.

The memory folder is the Ollama pairing's (``~/.camr/default`` by default): the same notes, whichever door they came
in by. The security rules are the pairing's too: 127.0.0.1 only, this host named, nothing a web page sends, and the
runtime on this Mac.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from camr_engine.pair.ollama import BUDGET, MAX_BODY, METRICS, WAIT_S, Pairing, make_server
from camr_engine.pair.provider import NoMemory, Provider, VaultWords

PORT = 11436  # next to the Ollama pairing's 11435
BACKENDS = {  # name: (what the runtime is called, where it listens)
    "ollama": ("Ollama", "127.0.0.1:11434"),
    "lmstudio": ("LM Studio", "127.0.0.1:1234"),
    "mlx": ("mlx_lm.server", "127.0.0.1:8080"),
}
CHAT = "/v1/chat/completions"


class Endpoint(Pairing):
    """The pairing narrowed to the OpenAI API: one path gets notes, and only ``/v1/`` is forwarded."""

    memory = {CHAT: "openai"}

    def __init__(self, provider: Provider, backend: str = "ollama", upstream: str | None = None, **kw):
        if backend not in BACKENDS:
            raise ValueError(f"no backend {backend!r}: pick one of {', '.join(BACKENDS)}")
        self.backend = backend
        self.name = BACKENDS[backend][0]
        super().__init__(provider, upstream or BACKENDS[backend][1], **kw)

    def serves(self, path: str) -> bool:
        return path.startswith("/v1/")


def build(argv: list[str] | None = None, prog: str = "python -m camr_engine.pair.openai") -> tuple[Endpoint, int]:
    """The endpoint and port the command line asks for. Nothing is loaded yet."""
    ap = argparse.ArgumentParser(prog=prog, description="An OpenAI-compatible endpoint with CAMR memory, in front of "
                                                        "a local runtime.")
    ap.add_argument("--backend", choices=list(BACKENDS), default="ollama", help="the runtime that runs the model")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--memory", type=Path, default=Path.home() / ".camr" / "default",
                    help="the memory folder (an engine memory, or a new folder)")
    ap.add_argument("--upstream", help="where the backend listens, if not its usual place (this Mac only)")
    ap.add_argument("--budget", type=int, default=BUDGET, help="tokens of notes added to each chat")
    ap.add_argument("--no-memory", action="store_true", help="a plain passthrough, to measure the endpoint alone")
    ap.add_argument("--allow-origin", action="append", default=[],
                    help="an origin allowed in on paths that never touch memory, port may be * (repeatable)")
    ap.add_argument("--max-body-mb", type=float, default=MAX_BODY / 2**20)
    ap.add_argument("--metrics", type=Path, help="where measurements go (default <memory>/openai/metrics.jsonl)")
    a = ap.parse_args(argv)
    memory = a.memory.expanduser()
    provider = NoMemory() if a.no_memory else VaultWords(memory)
    metrics = a.metrics or (None if a.no_memory else memory / "openai" / "metrics.jsonl")
    endpoint = Endpoint(provider, a.backend, a.upstream, budget_tokens=a.budget,
                        max_body=int(a.max_body_mb * 2**20), allow_origins=tuple(a.allow_origin),
                        metrics_path=metrics)
    return endpoint, a.port


def main(argv: list[str] | None = None, prog: str = "python -m camr_engine.pair.openai") -> None:
    endpoint, port = build(argv, prog)
    if isinstance(endpoint.provider, VaultWords):  # load the embedder now, and refuse notes another one wrote
        print("Loading the embedder...", flush=True)
        try:
            endpoint.provider.warm()
        except ValueError as e:
            raise SystemExit(f"camr serve: {e}")
    httpd = make_server(endpoint, port)
    port = httpd.server_address[1]
    where = "no memory" if isinstance(endpoint.provider, NoMemory) else f"memory: {endpoint.provider.folder}"
    print(f"CAMR on http://127.0.0.1:{port}/v1 -> {endpoint.name} at http://{endpoint.upstream}  ({where})\n"
          f"Routes: POST {CHAT} (with memory), GET /v1/models, GET {METRICS}\n"
          f"Point any OpenAI client at base URL http://127.0.0.1:{port}/v1 (any API key).", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        endpoint.settled(WAIT_S)  # the last exchanges are kept before the process ends


if __name__ == "__main__":
    main()
