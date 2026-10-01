"""Model runners.  ``ModelRunner`` exposes only ``generate``: there is no code path
through which a runner can modify model weights (FR-09, TC-07).
"""

from __future__ import annotations

import ipaddress
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from camr.config import CeilingModelConfig, ConfigError, LocalModelConfig

log = logging.getLogger(__name__)


class GenerationError(RuntimeError):
    """A query could not be answered.  The harness logs it as failed, never scores it."""


@dataclass
class Generation:
    text: str
    prompt_tokens: int | None
    generated_tokens: int | None
    latency_ms: float
    model: str
    model_version: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class ModelRunner(ABC):
    """Frozen-model interface.  Deliberately the only public operation is ``generate``."""

    model_name: str
    model_version: str | None = None
    is_remote: bool = False

    @abstractmethod
    def generate(self, prompt: str) -> Generation: ...


# ---------------------------------------------------------------------- local

_LOOPBACK_NAMES = {"localhost"}


def _is_loopback(host: str) -> bool:
    if host in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class OllamaRunner(ModelRunner):
    """Local runtime reached over its HTTP interface on the loopback address (IR-01).

    Decoding is greedy (temperature 0, top_k 1, fixed seed) so that identical
    prompts produce identical answers (NFR-05).
    """

    def __init__(self, cfg: LocalModelConfig, seed: int = 0, session: requests.Session | None = None,
                 *, allow_remote: bool = False, api_key: str | None = None):
        host = urlparse(cfg.host).hostname or ""
        self.is_remote = not _is_loopback(host)
        if self.is_remote and not allow_remote:
            # NFR-06: nothing but the ceiling condition may open a non-local connection.
            raise ConfigError(f"local_model.host must be a loopback address, got {cfg.host!r}")
        self.cfg = cfg
        self.seed = seed
        self.model_name = cfg.name
        self._http = session or requests.Session()
        if api_key:
            self._http.headers["Authorization"] = f"Bearer {api_key}"
        self.model_version = None

    def describe(self) -> str | None:
        """Best-effort model digest so the exact quantised weights are recorded."""
        try:
            resp = self._http.get(f"{self.cfg.host}/api/tags", timeout=5)
            resp.raise_for_status()
            for m in resp.json().get("models", []):
                if m.get("name") == self.cfg.name or m.get("model") == self.cfg.name:
                    self.model_version = (m.get("digest") or "")[:12] or None
        except (requests.RequestException, ValueError):
            pass
        return self.model_version

    def payload(self, prompt: str) -> dict[str, Any]:
        body = {
            "model": self.cfg.name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.cfg.keep_alive,
            "options": {
                "temperature": 0,
                "top_k": 1,
                "top_p": 1.0,
                "seed": self.seed,
                "num_predict": self.cfg.max_tokens,
                "num_ctx": self.cfg.num_ctx,
                # Memory-map weights so they are reclaimable page cache rather than
                # anonymous RAM: lets a 20B model fit a 16 GB device (measured).
                "use_mmap": True,
            },
        }
        if self.cfg.think:
            body["think"] = self.cfg.think
        return body

    def generate(self, prompt: str) -> Generation:
        t0 = time.perf_counter()
        try:
            resp = self._http.post(
                f"{self.cfg.host}/api/generate", json=self.payload(prompt), timeout=self.cfg.timeout_s
            )
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException as exc:  # IR-07: runtime unavailable
            raise GenerationError(f"local runtime error: {exc}") from exc
        except ValueError as exc:
            raise GenerationError(f"local runtime returned invalid JSON: {exc}") from exc
        latency_ms = (time.perf_counter() - t0) * 1000
        return Generation(
            text=body.get("response", ""),
            prompt_tokens=body.get("prompt_eval_count"),
            generated_tokens=body.get("eval_count"),
            latency_ms=latency_ms,
            model=self.cfg.name,
            model_version=self.model_version,
            meta={
                "thinking_chars": len(body.get("thinking") or ""),
                "load_ms": (body.get("load_duration") or 0) / 1e6,
                "prompt_eval_ms": (body.get("prompt_eval_duration") or 0) / 1e6,
                "eval_ms": (body.get("eval_duration") or 0) / 1e6,
            },
        )


# ---------------------------------------------------------------------- cloud


class CloudRunner(ModelRunner):
    """Pinned hosted reference model for the ceiling condition (FR-10, IR-02, NFR-09).

    Uses the official Anthropic SDK.  SDK-level retries are disabled so the retry
    policy (bounded, exponential backoff) is the one the study specifies and logs.
    Server-side model fallbacks are intentionally *not* enabled: a fallback would
    silently answer with a different model and break the pinned ceiling.  A refusal
    is therefore recorded as a failed query instead.
    """

    is_remote = True

    def __init__(
        self,
        cfg: CeilingModelConfig,
        client: Any | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.cfg = cfg
        self.model_name = cfg.name
        self.model_version = cfg.name
        self._sleep = sleep
        if client is None:
            try:
                import anthropic  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError("the ceiling condition requires `pip install camr[cloud]`") from exc
            client = anthropic.Anthropic(timeout=cfg.timeout_s, max_retries=0)
        self._client = client

    def _request(self, prompt: str) -> dict[str, Any]:
        req: dict[str, Any] = {
            "model": self.cfg.name,
            "max_tokens": self.cfg.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.cfg.effort:
            req["output_config"] = {"effort": self.cfg.effort}
        return req

    def _retryable(self, exc: Exception) -> bool:
        try:
            import anthropic  # type: ignore
        except ImportError:  # test doubles
            return bool(getattr(exc, "retryable", False))
        if isinstance(exc, (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError)):
            return True
        if isinstance(exc, anthropic.APIStatusError):
            return exc.status_code in (408, 409, 429) or exc.status_code >= 500
        return bool(getattr(exc, "retryable", False))

    def generate(self, prompt: str) -> Generation:
        attempts = self.cfg.max_retries + 1
        last: Exception | None = None
        t0 = time.perf_counter()
        for attempt in range(attempts):
            try:
                resp = self._client.messages.create(**self._request(prompt))
                break
            except Exception as exc:  # noqa: BLE001 - classified below
                last = exc
                if not self._retryable(exc) or attempt == attempts - 1:
                    raise GenerationError(f"cloud error after {attempt + 1} attempt(s): {exc}") from exc
                delay = self.cfg.backoff_base_s * (2**attempt)
                log.warning("cloud call failed (%s); retrying in %.1fs", exc, delay)
                self._sleep(delay)
        else:  # pragma: no cover - loop always breaks or raises
            raise GenerationError(str(last))
        latency_ms = (time.perf_counter() - t0) * 1000

        if getattr(resp, "stop_reason", None) == "refusal":
            raise GenerationError("cloud model refused the request")
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        served = getattr(resp, "model", self.cfg.name)
        usage = getattr(resp, "usage", None)
        return Generation(
            text=text,
            prompt_tokens=getattr(usage, "input_tokens", None),
            generated_tokens=getattr(usage, "output_tokens", None),
            latency_ms=latency_ms,
            model=self.cfg.name,
            model_version=served,
            meta={"stop_reason": getattr(resp, "stop_reason", None), "served_model": served},
        )


# ---------------------------------------------------------- openai-compatible


class OpenAICompatRunner(ModelRunner):
    """Hosted model behind an OpenAI-style ``/chat/completions`` API (e.g. Kimi on
    Moonshot).  Same contract as the other runners: bounded retries with
    exponential backoff (IR-02), the served model id logged per query (NFR-09),
    reasoning text excluded from the scored answer.  The API key is read from the
    environment only and never logged.
    """

    is_remote = True

    def __init__(self, cfg: CeilingModelConfig, session: requests.Session | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        import os

        key = os.environ.get(cfg.api_key_env)
        if not key:
            raise ConfigError(f"ceiling_model.backend=openai_compat needs {cfg.api_key_env} in the environment")
        self.cfg = cfg
        self.model_name = cfg.name
        self.model_version = cfg.name
        self._http = session or requests.Session()
        self._http.headers.update({"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        self._sleep = sleep

    def payload(self, prompt: str) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.cfg.name, "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": self.cfg.max_tokens}
        if self.cfg.temperature is not None:
            body["temperature"] = self.cfg.temperature
        return body

    def generate(self, prompt: str) -> Generation:
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        t0 = time.perf_counter()
        for attempt in range(self.cfg.max_retries + 1):
            try:
                r = self._http.post(url, json=self.payload(prompt), timeout=self.cfg.timeout_s)
            except requests.RequestException as exc:
                err, retry = f"connection error: {exc}", True
            else:
                if r.status_code == 200:
                    break
                err = f"HTTP {r.status_code}: {r.text[:200]}"
                retry = r.status_code in (408, 409, 429) or r.status_code >= 500
            if not retry or attempt == self.cfg.max_retries:
                raise GenerationError(f"cloud error after {attempt + 1} attempt(s): {err}")
            self._sleep(self.cfg.backoff_base_s * (2 ** attempt))
        d = r.json()
        choice = (d.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        if choice.get("finish_reason") == "content_filter":
            raise GenerationError("cloud model refused the request")
        usage = d.get("usage") or {}
        return Generation(
            text=msg.get("content") or "",
            prompt_tokens=usage.get("prompt_tokens"),
            generated_tokens=usage.get("completion_tokens"),
            latency_ms=(time.perf_counter() - t0) * 1000,
            model=self.cfg.name,
            model_version=d.get("model", self.cfg.name),
            meta={"served_model": d.get("model"), "finish_reason": choice.get("finish_reason"),
                  "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")},
        )


# -------------------------------------------------------------------- dry run


class DryRunRunner(ModelRunner):
    """Deterministic, offline stand-in used to smoke-test the pipeline end to end.

    It is not a language model and its scores mean nothing; runs made with it are
    labelled ``dry-run`` in every record so they cannot be mistaken for results.
    """

    def __init__(self, name: str = "dry-run"):
        self.model_name = name
        self.model_version = "dry-run"

    def generate(self, prompt: str) -> Generation:
        t0 = time.perf_counter()
        text = self._respond(prompt)
        return Generation(
            text=text,
            prompt_tokens=len(prompt.split()),
            generated_tokens=len(text.split()),
            latency_ms=(time.perf_counter() - t0) * 1000,
            model=self.model_name,
            model_version="dry-run",
        )

    @staticmethod
    def _respond(prompt: str) -> str:
        if prompt.startswith("Rewrite the passage"):
            passage = prompt.split("Passage:", 1)[1].rsplit("Note:", 1)[0].strip()
            title = prompt.split("Title:", 1)[1].split("\n", 1)[0].strip()
            first = re.split(r"(?<=[.!?])\s", passage, maxsplit=1)[0]
            return f"{title}: {first}"
        if prompt.startswith("On a scale of 1 to 10"):
            return "5"
        if "'#### <number>'" in prompt:
            return "#### 0"
        m = re.search(r"Notes:\n- (.+)", prompt)
        if m:
            note = m.group(1)
            return note.split(": ", 1)[-1].split(".")[0]
        return "unknown"


def build_local_runner(cfg: LocalModelConfig, seed: int) -> ModelRunner:
    if cfg.backend == "ollama":
        return OllamaRunner(cfg, seed=seed)
    return DryRunRunner(f"dry-run:{cfg.name}")


def build_ceiling_runner(cfg: CeilingModelConfig, seed: int = 0) -> ModelRunner:
    if cfg.backend == "anthropic":
        return CloudRunner(cfg)
    if cfg.backend == "openai_compat":
        return OpenAICompatRunner(cfg)
    if cfg.backend == "ollama":
        # A larger model through the Ollama API: local (loopback), or an Ollama Cloud
        # model such as gpt-oss:120b-cloud when host is https://ollama.com.  Same
        # greedy decoding as the small model; reasoning models get a `think` level.
        import os

        local = LocalModelConfig(backend="ollama", name=cfg.name, host=cfg.host, timeout_s=max(cfg.timeout_s, 900.0),
                                 max_tokens=cfg.max_tokens, think=cfg.think)
        remote = not _is_loopback(urlparse(cfg.host).hostname or "")
        key = os.environ.get(cfg.api_key_env) if remote else None
        if remote and not key:
            raise ConfigError(f"ceiling_model.host is remote; set {cfg.api_key_env}")
        runner = OllamaRunner(local, seed=seed, allow_remote=remote, api_key=key)
        runner.describe()
        return runner
    return DryRunRunner(f"dry-run:{cfg.name}")
