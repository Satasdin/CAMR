"""Claude as the yardstick: it answers the same tasks on its own, with no memory engine.

Each request streams, so the time to the first token is measured exactly. A stream is one HTTP try: the SDK's own
retries are off for it, so no retry wait is ever counted as time to the first word. Every try, and every free token
count, appends one line to the ledger (records/bench/claude-ledger.jsonl). The ledger also holds the night's hard
budget. Before a call is sent, its worst case is estimated and held in the ledger. The call is refused when that
estimate would push the total past the cap less the headroom.

The three models get the same settings: effort "medium" and adaptive thinking. Thinking cannot be turned off on
Opus 5.5; it is billed and recorded as output. No server-side fallback is ever asked for, so each record names the
model that answered. A refusal is recorded as a refusal.

A long history is cut from the front. Claude gets the most recent part that fits in its 1M-token window, with room
for the questions and the reply. A checkpoint's questions go in one request that asks for the answers as JSON. The
history goes as text blocks that end where earlier checkpoints ended. The block where the last request ended is
marked, so the cache is read there. The newest block is marked only when a later request can read it: not on the last
checkpoint, and not when this history or the next one is cut from the front.

A reply cut off by its own ``max_tokens`` is not graded as wrong. The questions it never reached are "truncated" and
are asked once more, alone, with twice the room.

The key is read from ~/.config/camr/anthropic.env when the client is made and handed straight to it. It is never
printed, logged or stored.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import platform
import re
import time
import uuid
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

import anthropic
import httpx2

from engram.bench.cost import Tokens, cost_usd, estimate_usd, tokens

MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5")
EFFORT = "medium"
THINKING = {"type": "adaptive"}
WINDOW = 1_000_000  # tokens; the same for all three models
MARGIN = 10_000  # tokens kept free in the window on top of the reply
MAX_REPLY = 64_000  # the most output tokens a checkpoint's first request asks for
MAX_OUTPUT = 128_000  # the most output tokens any of the three models can write: the re-ask's ceiling
CAP_USD = 60.0
HEADROOM_USD = 2.0
CHARS_PER_TOKEN = 3.0  # a first guess when cutting a history; the API's count decides
FIT_TRIES = 8
PATIENCE = 4  # tries after the first, for a stream and for a count: five in all, as many as the SDK's own default
RIGHT = {"right", "right_abstain"}  # grader verdicts that count as right
TOO_LONG = re.compile(r"too long|too many tokens|exceed", re.I)  # how the API says a prompt does not fit

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "records" / "bench"
LEDGER = RECORDS / "claude-ledger.jsonl"
KEY_FILE = Path.home() / ".config" / "camr" / "anthropic.env"

SYSTEM = ("You answer questions about a project's history: one developer's log of chats, decisions, code, notes and "
          "lessons, oldest first. Answer from the history only. When the history never says, answer \"I don't "
          "know\". Keep each answer short unless the question asks for code or a page.")
OPENER = "The project history, oldest first:\n<history>\n"
ANSWER_SCHEMA = {
    "type": "object",
    "properties": {"answers": {"type": "array", "items": {
        "type": "object", "properties": {"id": {"type": "string"}, "answer": {"type": "string"}},
        "required": ["id", "answer"], "additionalProperties": False}}},
    "required": ["answers"], "additionalProperties": False}


class BudgetError(RuntimeError):
    """A call would push the ledger past the night's cap, so it was not sent."""


class ClaudeError(RuntimeError):
    """A call failed after our retries. ``detail`` is the API's own message, when it sent one."""

    def __init__(self, message: str, status: str, retryable: bool = False, wait_s: float = 0.0,
                 detail: str | None = None):
        super().__init__(message)
        self.status, self.retryable, self.wait_s, self.detail = status, retryable, wait_s, detail


def read_key(path: Path = KEY_FILE) -> str:
    """The API key from an env file (``ANTHROPIC_API_KEY=...``, optionally with ``export`` and quotes)."""
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        if sep and name.strip() == "ANTHROPIC_API_KEY":
            value = value.strip().strip("'\"")
            if value:
                return value
    raise ClaudeError(f"no ANTHROPIC_API_KEY in {path}", "no_key")


def make_client(key_file: Path = KEY_FILE, *, max_retries: int = 4, timeout: float = 600.0,
                http_client: Any = None) -> anthropic.Anthropic:
    """The official client with the key from ``key_file``. The SDK itself retries 408, 409, 429 and 5xx on the free
    token counts; the runner turns that off for its paid streams. ``http_client`` is an ``anthropic.DefaultHttpxClient``
    (a proxy, or a mock transport in tests)."""
    kw: dict[str, Any] = {"http_client": http_client} if http_client is not None else {}
    return anthropic.Anthropic(api_key=read_key(key_file), max_retries=max_retries, timeout=timeout, **kw)


def check_model(model: str) -> None:
    if model not in MODELS:
        raise ValueError(f"the yardstick models are exactly {', '.join(MODELS)}; not {model!r}")


# --- the ledger -------------------------------------------------------------------------------------------------


class Ledger:
    """One JSON line per call. What has been spent is the sum of ``cost_usd``, plus every hold not yet closed.

    A hold is written before a call is sent and closed by the call's own line. A process that dies mid-call leaves
    its hold open, so its worst case stays counted. The file is locked while it is read and written, so several
    runners can share it.
    """

    def __init__(self, path: Path = LEDGER, cap_usd: float = CAP_USD, headroom_usd: float = HEADROOM_USD):
        self.path, self.cap_usd, self.headroom_usd = Path(path), cap_usd, headroom_usd

    @contextmanager
    def _locked(self) -> Iterator[Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield f
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    @staticmethod
    def _lines(f) -> list[dict]:
        f.seek(0)
        out = []
        for line in f.read().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    @staticmethod
    def _spent(lines: list[dict]) -> float:
        closed = {x.get("hold") for x in lines if x.get("kind") != "hold"}
        return (sum(float(x.get("cost_usd") or 0.0) for x in lines)
                + sum(float(x.get("hold_usd") or 0.0) for x in lines if x.get("kind") == "hold" and x.get("hold")
                      not in closed))

    def lines(self) -> list[dict]:
        with self._locked() as f:
            return self._lines(f)

    def spent(self) -> float:
        """Dollars spent so far, counting open holds."""
        with self._locked() as f:
            return self._spent(self._lines(f))

    def hold(self, model: str, purpose: str, estimate: float) -> str:
        """Hold ``estimate`` dollars for a call, or raise BudgetError if it would pass the cap less the headroom."""
        with self._locked() as f:
            spent = self._spent(self._lines(f))
            limit = self.cap_usd - self.headroom_usd
            if spent + estimate > limit:
                f.write(json.dumps({"at": _now(), "kind": "refused", "model": model, "purpose": purpose,
                                    "estimate_usd": round(estimate, 6), "spent_usd": round(spent, 6),
                                    "cap_usd": self.cap_usd, "headroom_usd": self.headroom_usd}) + "\n")
                f.flush()
                raise BudgetError(f"{purpose}: ${spent:.2f} spent + ${estimate:.2f} worst case would pass "
                                  f"${limit:.2f} (the ${self.cap_usd:.0f} cap less ${self.headroom_usd:.0f} headroom)")
            hold = uuid.uuid4().hex[:12]
            f.write(json.dumps({"at": _now(), "kind": "hold", "hold": hold, "model": model, "purpose": purpose,
                                "hold_usd": round(estimate, 6)}) + "\n")
            f.flush()
            return hold

    def write(self, line: dict) -> None:
        with self._locked() as f:
            f.write(json.dumps({"at": _now(), **line}, default=str) + "\n")
            f.flush()


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


# --- one call ---------------------------------------------------------------------------------------------------


@dataclass
class Call:
    """One streamed reply and what it took."""

    model: str  # the model asked
    answered_by: str | None  # the model the API says answered
    text: str
    stop_reason: str | None
    refusal_category: str | None
    tokens: Tokens
    cost_usd: float
    estimate_usd: float
    ttft_s: float | None  # request sent -> first word of the answer (the first text token)
    first_token_s: float | None  # request sent -> first token of any kind, thinking included
    total_s: float
    request_id: str | None = None
    message_id: str | None = None
    attempts: int = 1

    @property
    def refused(self) -> bool:
        return self.stop_reason == "refusal"

    @property
    def model_mismatch(self) -> bool:
        return self.answered_by is not None and self.answered_by != self.model

    @property
    def output_tps(self) -> float | None:
        """Output tokens (thinking included) per second, from the first token to the end."""
        start = self.first_token_s if self.first_token_s is not None else self.ttft_s
        span = self.total_s - (start or 0.0)
        return round(self.tokens.output / span, 1) if span > 0 and self.tokens.output else None

    def as_dict(self) -> dict:
        return {"model": self.model, "answered_by": self.answered_by, "model_mismatch": self.model_mismatch,
                "stop_reason": self.stop_reason, "refused": self.refused, "refusal_category": self.refusal_category,
                **self.tokens.as_dict(), "cost_usd": round(self.cost_usd, 6),
                "estimate_usd": round(self.estimate_usd, 6),
                "ttft_s": _r(self.ttft_s), "first_token_s": _r(self.first_token_s), "total_s": _r(self.total_s),
                "output_tps": self.output_tps, "request_id": self.request_id, "message_id": self.message_id,
                "attempts": self.attempts}


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None else round(x, nd)


def _merge_usage(into: dict, usage: Any) -> None:
    """Keep the latest non-empty usage numbers from a stream event."""
    if usage is None:
        return
    for name in ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                 "cache_creation", "output_tokens_details"):
        value = usage.get(name) if isinstance(usage, dict) else getattr(usage, name, None)
        if value is not None:
            into[name] = value


def _retry_after(e: anthropic.APIStatusError, default: float = 30.0) -> float:
    try:
        return min(max(float(e.response.headers.get("retry-after", default)), 1.0), 120.0)
    except (TypeError, ValueError, AttributeError):
        return default


def _error_type(e: anthropic.APIStatusError) -> str | None:
    kind = getattr(e, "type", None)
    if kind is None and isinstance(e.body, dict) and isinstance(e.body.get("error"), dict):
        kind = e.body["error"].get("type")
    return kind


def _error_message(e: anthropic.APIStatusError) -> str:
    """The API's own words for an error (at most 300 characters)."""
    body = e.body if isinstance(e.body, dict) else {}
    inner = body.get("error") if isinstance(body.get("error"), dict) else {}
    return str(inner.get("message") or getattr(e, "message", "") or "")[:300]


def _status(e: anthropic.APIStatusError) -> str:
    etype = _error_type(e)
    return f"http_{e.status_code}" + (f"_{etype}" if etype else "")


def _retryable(e: anthropic.APIStatusError) -> bool:
    """The SDK's own rule: the server's ``x-should-retry`` first, then 408, 409, 429 and 5xx. An overload or a server
    error sent inside a 200 stream is retried too."""
    flag = getattr(getattr(e, "response", None), "headers", {}).get("x-should-retry")
    if flag in ("true", "false"):
        return flag == "true"
    return (e.status_code in (408, 409, 429) or e.status_code >= 500
            or _error_type(e) in ("overloaded_error", "api_error", "rate_limit_error"))


def _too_long(e: ClaudeError) -> bool:
    """A count refused because the prompt does not fit: a 413, or a 400 that says so. Any other 400 is a real error."""
    if e.status.startswith("http_413"):
        return True
    return e.status.startswith("http_400") and bool(TOO_LONG.search(e.detail or ""))


@dataclass
class Segments:
    """Where earlier requests of one run cut the history, so the next request repeats their blocks byte for byte."""

    start: int = -1
    cuts: list[int] = field(default_factory=list)

    def plan(self, start: int, end: int) -> list[int]:
        cuts = [c for c in self.cuts if start < c < end] if start == self.start else []
        return cuts + [end] if end > start else []

    def keep(self, start: int, cuts: list[int]) -> None:
        self.start, self.cuts = start, list(cuts)


class Claude:
    """The yardstick runner. ``client`` is an ``anthropic.Anthropic`` (made from the key file when not given)."""

    def __init__(self, client: Any = None, *, ledger: Path = LEDGER, records: Path = RECORDS, cap_usd: float = CAP_USD,
                 headroom_usd: float = HEADROOM_USD, key_file: Path = KEY_FILE, window: int = WINDOW,
                 margin: int = MARGIN, cache_ttl: str = "5m", structured: bool = True, patience: int = PATIENCE,
                 max_retries: int = 4, timeout: float = 600.0, system: str = SYSTEM, http_client: Any = None,
                 clock: Callable[[], float] = time.perf_counter, sleep: Callable[[float], None] = time.sleep):
        if cache_ttl not in ("5m", "1h"):
            raise ValueError("cache_ttl is '5m' or '1h'")
        self._client, self.key_file, self.max_retries, self.timeout = client, Path(key_file), max_retries, timeout
        self._http_client, self._streamer = http_client, None
        self.ledger, self.records = Ledger(ledger, cap_usd, headroom_usd), Path(records)
        self.window, self.margin, self.cache_ttl = window, margin, cache_ttl
        self.structured, self.patience = structured, patience
        self.system, self.clock, self.sleep = system, clock, sleep

    def __repr__(self) -> str:
        return f"Claude(ledger={str(self.ledger.path)!r}, cap_usd={self.ledger.cap_usd})"

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = make_client(self.key_file, max_retries=self.max_retries, timeout=self.timeout,
                                       http_client=self._http_client)
        return self._client

    @property
    def streamer(self) -> Any:
        """The client for paid streams, with the SDK's retries off: the clock then starts at the one HTTP try that
        answers, and every try is a ledger line of its own."""
        if self._streamer is None:
            c = self.client
            self._streamer = c.with_options(max_retries=0) if callable(getattr(c, "with_options", None)) else c
        return self._streamer

    def spent(self) -> float:
        return self.ledger.spent()

    # counting ------------------------------------------------------------------------------------------------

    def count(self, model: str, messages: list, purpose: str, *, system: str | None = None,
              output_config: dict | None = None) -> int:
        """The exact prompt tokens of a request, from the free count_tokens endpoint (logged at $0)."""
        check_model(model)
        kw: dict[str, Any] = {"model": model, "messages": messages, "thinking": THINKING}
        if system:
            kw["system"] = system
        if output_config:
            kw["output_config"] = output_config
        for attempt in range(1, self.patience + 2):
            t0 = self.clock()
            detail = None
            try:
                n = int(self.client.messages.count_tokens(**kw).input_tokens)
            except anthropic.RateLimitError as e:
                status, retryable, wait, detail = "rate_limited", True, _retry_after(e), _error_message(e)
            except anthropic.APIStatusError as e:
                status, retryable, wait, detail = _status(e), _retryable(e), 10.0 * attempt, _error_message(e)
            except anthropic.APIConnectionError:
                status, retryable, wait = "connection", True, 10.0 * attempt
            else:
                self.ledger.write({"kind": "count", "model": model, "purpose": purpose, "status": "ok",
                                   "input_tokens": n, "cost_usd": 0.0, "total_s": _r(self.clock() - t0)})
                return n
            self.ledger.write({"kind": "count", "model": model, "purpose": purpose, "status": status,
                               "detail": detail, "cost_usd": 0.0, "total_s": _r(self.clock() - t0)})
            if not retryable or attempt > self.patience:
                raise ClaudeError(f"{purpose}: token count failed ({status})" + (f": {detail}" if detail else ""),
                                  status, retryable, wait, detail)
            self.sleep(wait)
        raise AssertionError("unreachable")

    # calling -------------------------------------------------------------------------------------------------

    def call(self, model: str, messages: list, *, max_tokens: int, purpose: str, system: str | None = None,
             output_config: dict | None = None, prompt_tokens: int | None = None, cache: bool = True) -> Call:
        """One streamed request. ``prompt_tokens`` (counted when not given) sizes the worst-case estimate. ``cache``
        says whether the messages carry a cache marker, which can write the cache at 1.25x the input price.

        Each try is one HTTP request; the SDK does not retry it, so the time to the first word never holds a wait. A
        rate limit waits for ``retry-after``. An overload, a 408, 409 or 5xx, a lost connection and a stream that
        breaks mid-way (a server error event, or the connection dropping while the reply is read) wait a little
        longer each time. Each is tried again up to ``patience`` times, and each try is its own ledger line, with
        what a broken try had used. Other errors raise ClaudeError at once.
        """
        check_model(model)
        config = {**(output_config or {}), "effort": EFFORT}
        params: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "messages": messages,
                                  "thinking": THINKING, "output_config": config}
        if system:
            params["system"] = system
        if prompt_tokens is None:
            prompt_tokens = self.count(model, messages, purpose, system=system, output_config=config)
        estimate = estimate_usd(model, prompt_tokens, max_tokens, self.cache_ttl if cache else None)
        attempt = 1
        while True:
            try:
                return self._stream(params, purpose, estimate, attempt)
            except ClaudeError as e:
                if not e.retryable or attempt > self.patience:
                    raise
                self.sleep(e.wait_s)
                attempt += 1

    def _stream(self, params: dict, purpose: str, estimate: float, attempt: int = 1) -> Call:
        model = params["model"]
        hold = self.ledger.hold(model, purpose, estimate)
        usage: dict = {}
        answered_by = request_id = None
        first = first_text = None
        failure: tuple[str, bool, float] | None = None
        err: BaseException | None = None
        line = {"kind": "call", "hold": hold, "model": model, "purpose": purpose, "effort": EFFORT,
                "thinking": THINKING["type"], "max_tokens": params["max_tokens"], "cache_ttl": self.cache_ttl,
                "attempts": attempt}
        detail: str | None = None
        t0 = self.clock()  # the SDK makes one HTTP try only, so this is when the answering request was sent
        try:
            with self.streamer.messages.stream(**params) as stream:
                request_id = getattr(stream, "request_id", None)
                for event in stream:
                    kind = event.type
                    if kind == "message_start":
                        answered_by = event.message.model
                        _merge_usage(usage, event.message.usage)
                    elif kind == "message_delta":
                        _merge_usage(usage, event.usage)
                    elif kind in ("content_block_start", "content_block_delta"):
                        now = self.clock() - t0
                        first = now if first is None else first
                        if (first_text is None and kind == "content_block_delta"
                                and event.delta.type == "text_delta" and event.delta.text):
                            first_text = now
                message = stream.get_final_message()
        except anthropic.RateLimitError as e:  # 429
            failure, err, detail = ("rate_limited", True, _retry_after(e)), e, _error_message(e)
        except anthropic.APIStatusError as e:  # other 4xx and 5xx, and errors sent inside the stream
            failure, err, detail = (_status(e), _retryable(e), 15.0 * attempt), e, _error_message(e)
        except anthropic.APIConnectionError as e:  # no reply at all (the SDK wraps it, timeouts included)
            failure, err = ("connection", True, 15.0 * attempt), e
        except httpx2.TransportError as e:  # the connection dropped while the reply was read: the SDK passes it on raw
            failure, err = (f"connection_{type(e).__name__}", True, 15.0 * attempt), e
        except BaseException as e:
            t = tokens(usage, self.cache_ttl)
            self.ledger.write({**line, "status": f"error_{type(e).__name__}", **t.as_dict(),
                               "cost_usd": round(cost_usd(model, t), 6), "estimate_usd": round(estimate, 6),
                               "total_s": _r(self.clock() - t0), "request_id": request_id})
            raise
        total = self.clock() - t0
        if failure is not None:
            status, retryable, wait = failure
            t = tokens(usage, self.cache_ttl)  # what a broken stream had used, from its events
            self.ledger.write({**line, "status": status, "detail": detail, **t.as_dict(),
                               "cost_usd": round(cost_usd(model, t), 6), "estimate_usd": round(estimate, 6),
                               "ttft_s": _r(first_text), "first_token_s": _r(first), "total_s": _r(total),
                               "request_id": request_id or getattr(err, "request_id", None)})
            raise ClaudeError(f"{purpose}: {model} failed ({status})" + (f": {detail}" if detail else ""),
                              status, retryable, wait, detail) from err
        t = tokens(message.usage, self.cache_ttl)
        details = getattr(message, "stop_details", None)
        result = Call(model=model, answered_by=getattr(message, "model", None) or answered_by,
                      text="".join(b.text for b in message.content if getattr(b, "type", None) == "text"),
                      stop_reason=message.stop_reason,
                      refusal_category=getattr(details, "category", None) if details is not None else None,
                      tokens=t, cost_usd=cost_usd(model, t), estimate_usd=estimate, ttft_s=first_text,
                      first_token_s=first, total_s=total, request_id=request_id,
                      message_id=getattr(message, "id", None), attempts=attempt)
        self.ledger.write({**line, "status": "refusal" if result.refused else "ok", **result.as_dict()})
        return result

    # a checkpoint --------------------------------------------------------------------------------------------

    def _messages(self, history: Sequence[str], start: int, end: int, segments: Segments, block: str,
                  cache: bool = True) -> tuple[list, list[int]]:
        """The request: the opener, the history as blocks ending where earlier requests ended, then ``block``.

        The block where the last request ended is marked, so its cache is read. The newest block is marked only when
        ``cache`` is true, as that marker writes the cache at 1.25x the input price.
        """
        cuts = segments.plan(start, end)
        marker: dict[str, Any] = {"type": "ephemeral", **({"ttl": "1h"} if self.cache_ttl == "1h" else {})}
        content: list[dict] = [{"type": "text", "text": OPENER}]
        a = start
        for c in cuts:
            content.append({"type": "text", "text": "\n\n".join(history[a:c]) + "\n\n"})
            a = c
        if len(cuts) > 1:  # the previous checkpoint's end: an exact read point for its cache
            content[-2]["cache_control"] = dict(marker)
        if cuts and cache:  # the newest block, written for a later request to read
            content[-1]["cache_control"] = dict(marker)
        content.append({"type": "text", "text": block})
        return [{"role": "user", "content": content}], cuts

    def fit(self, model: str, history: Sequence[str], cut: int, block: str, max_tokens: int,
            output_config: dict, segments: Segments, purpose: str) -> dict:
        """The most recent part of ``history[:cut]`` that fits the window with ``block`` and the reply.

        A first guess from characters is checked with the free token count, then moved by the measured characters
        per token until it fits snugly. Returns the start, the exact prompt tokens, the messages and the cuts. A
        count refused as too long counts as twice the window; any other refusal is raised at once.
        """
        target = self.window - max_tokens - self.margin
        tail = [0] * (cut + 1)  # tail[s]: characters of history[s:cut]
        for i in range(cut - 1, -1, -1):
            tail[i] = tail[i + 1] + len(history[i]) + 2
        fixed = len(self.system or "") + len(OPENER) + len(block)

        def start_for(chars_per_token: float) -> int:
            room, lo, hi = target * chars_per_token - fixed, 0, cut
            while lo < hi:
                mid = (lo + hi) // 2
                lo, hi = (lo, mid) if tail[mid] <= room else (mid + 1, hi)
            return lo

        start, best, worst = start_for(CHARS_PER_TOKEN), None, -1
        for _ in range(FIT_TRIES):
            messages, cuts = self._messages(history, start, cut, segments, block)
            try:
                n = self.count(model, messages, purpose + " (fit)", system=self.system, output_config=output_config)
            except ClaudeError as e:  # the count may refuse a prompt far past the window: take it as twice too big
                if start >= cut or not _too_long(e):
                    raise
                n = 2 * self.window
            chars_per_token = (tail[start] + fixed) / max(n, 1)
            if n <= target:
                best = {"start": start, "prompt_tokens": n, "messages": messages, "cuts": cuts,
                        "chars_per_token": chars_per_token}
                if start == 0 or n >= 0.98 * target:
                    break
            else:
                worst = start
                if start >= cut:
                    break
            nxt = max(start_for(chars_per_token * 0.995), worst + 1)
            if best is not None and nxt >= best["start"]:
                break
            start = min(nxt, cut)
        if best is None:
            raise ClaudeError(f"{purpose}: the questions and a {max_tokens}-token reply leave no room for any history "
                              f"in {self.window} tokens", "no_room")
        best.update(tail=tail, target=target, fixed=fixed)
        return best

    def _worth_caching(self, fit: dict, history: Sequence[str], cut: int, next_cut: int | None) -> bool:
        """Whether a later request can read this one's newest block: not when this history is cut from the front, nor
        when the next one is expected to be (a history cut from the front starts further on, so its prefix differs)."""
        if fit["start"] > 0:
            return False
        if next_cut is None or next_cut <= cut:
            return True
        more = sum(len(history[i]) + 2 for i in range(cut, min(next_cut, len(history))))
        return (fit["tail"][0] + more + fit["fixed"]) / fit["chars_per_token"] <= fit["target"]

    def _prepare(self, model: str, history: Sequence[str], cut: int, qs: list[dict], max_tokens: int,
                 segments: Segments, purpose: str, *, cache: bool, next_cut: int | None) -> dict:
        """Fit the history around ``qs`` and build the request. The fit also says whether the newest block is
        written to the cache (``cache``) and whether any marker is set (``marked``: a read point may write, too)."""
        block = question_block(qs)
        output_config = {"format": {"type": "json_schema", "schema": ANSWER_SCHEMA}} if self.structured else {}
        fit = self.fit(model, history, cut, block, max_tokens, {"effort": EFFORT, **output_config}, segments, purpose)
        fit["cache"] = cache and self._worth_caching(fit, history, cut, next_cut)
        fit["messages"], fit["cuts"] = self._messages(history, fit["start"], cut, segments, block, fit["cache"])
        fit["marked"] = any("cache_control" in b for b in fit["messages"][0]["content"])
        fit["output_config"] = output_config
        return fit

    def _send(self, model: str, fit: dict, max_tokens: int, purpose: str) -> Call:
        return self.call(model, fit["messages"], max_tokens=max_tokens, purpose=purpose, system=self.system,
                         output_config=fit["output_config"], prompt_tokens=fit["prompt_tokens"], cache=fit["marked"])

    def ask(self, model: str, history: Sequence[str], cut: int, questions: Sequence[Any], *,
            grader: Callable[[Any, str], Any] | None = None, name: str = "", segments: Segments | None = None,
            max_tokens: int | None = None, cache: bool = True, next_cut: int | None = None,
            reask: bool = True) -> dict:
        """Ask every question in one request, Claude having been told ``history[:cut]``; returns the checkpoint record.

        ``questions`` are objects or dicts with an id (``qid`` or ``id``) and a text (``text`` or ``question``), and
        optionally ``expected``. ``grader(question, answer)`` returns a bool or a verdict such as "right".

        ``cache`` false leaves the newest history block unmarked (nothing later will read it). ``next_cut`` is where
        the next checkpoint will ask; when that history will not fit whole, this one is not cached either. When the
        reply stops at ``max_tokens``, the questions it never reached are asked again once (``reask``), alone, with
        twice the room (at most MAX_OUTPUT); any still missing stay "truncated", which is never graded.
        """
        check_model(model)
        segments = segments if segments is not None else Segments()
        qs = [_question(q) for q in questions]
        if len({q["qid"] for q in qs}) != len(qs):
            raise ValueError(f"{name}: question ids must be unique")
        max_tokens = max_tokens or min(MAX_REPLY, 8192 + 256 * len(qs))
        purpose = f"{name or 'checkpoint'} [{model}]"
        record: dict[str, Any] = {"checkpoint": name, "model": model, "effort": EFFORT, "thinking": THINKING["type"],
                                  "questions": len(qs), "history_pieces_told": cut, "max_tokens": max_tokens}
        try:
            fit = self._prepare(model, history, cut, qs, max_tokens, segments, purpose, cache=cache,
                                next_cut=next_cut)
            tail, start = fit["tail"], fit["start"]
            record.update({"history_start": start, "history_pieces_used": cut - start, "cut_from_front": start > 0,
                           "history_chars_told": tail[0], "history_chars_used": tail[start],
                           "history_tokens_told_est": round(tail[0] / fit["chars_per_token"]),
                           "context_tokens": fit["prompt_tokens"], "cached": fit["cache"]})
            call = self._send(model, fit, max_tokens, purpose)
        except ClaudeError as e:
            record.update({"error": e.status, "error_detail": e.detail,
                           "answers": [_answer(q, None, "error", None, None, len(qs)) for q in qs]})
            record["summary"] = summarize(record["answers"])
            return record
        segments.keep(start, fit["cuts"])
        record["request"] = call.as_dict()
        answers = _answers(qs, call, grader)
        missing = [q for q, a in zip(qs, answers) if a["verdict"] == "truncated"]
        bigger = min(MAX_OUTPUT, 2 * max_tokens)
        if missing and reask and bigger > max_tokens:
            record["reask"] = {"questions": len(missing), "max_tokens": bigger}
            try:
                fit2 = self._prepare(model, history, cut, missing, bigger, segments, purpose + " (re-ask)",
                                     cache=fit["cache"], next_cut=None)
                record["reask"].update({"history_start": fit2["start"], "context_tokens": fit2["prompt_tokens"]})
                call2 = self._send(model, fit2, bigger, purpose + " (re-ask)")
            except (ClaudeError, BudgetError) as e:  # the first reply is paid for: keep it, marked as truncated
                record["reask"]["error"] = e.status if isinstance(e, ClaudeError) else f"budget: {e}"
            else:
                record["reask"]["request"] = call2.as_dict()
                again = {a["qid"]: a for a in _answers(missing, call2, grader)}
                answers = [_with_share(again[a["qid"]], a) if a["qid"] in again else a for a in answers]
        record["answers"] = answers
        record["summary"] = summarize(answers)
        return record

    def run(self, model: str, history: Sequence[str], checkpoints: Sequence["Checkpoint"], *,
            grader: Callable[[Any, str], Any] | None = None, task: str = "longhaul", save: bool = True,
            progress: Callable[[str], None] = print) -> dict:
        """Put ``model`` through every checkpoint in order and return the run record (saved after each one).

        A checkpoint writes the cache only when the next one can read it, so the last one never does. A budget
        refusal stops the run: the record then says so in ``stopped``.
        """
        check_model(model)
        started = dt.datetime.now()
        path = self.records / started.strftime("%Y-%m-%d") / f"{started.strftime('%H%M%S')}-claude-{model}-{task}.json"
        record: dict[str, Any] = {"kind": "claude-yardstick", "task": task, "model": model, "effort": EFFORT,
                                  "thinking": THINKING["type"], "structured": self.structured, "window": self.window,
                                  "cache_ttl": self.cache_ttl, "fallbacks": None,
                                  "started": started.isoformat(timespec="seconds"), "environment": _environment(),
                                  "checkpoints": [], "cost_usd": 0.0}
        segments = Segments()
        for i, cp in enumerate(checkpoints):
            nxt = checkpoints[i + 1] if i + 1 < len(checkpoints) else None
            try:
                r = self.ask(model, history, cp.cut, cp.questions, grader=grader, name=cp.name, segments=segments,
                             cache=nxt is not None, next_cut=nxt.cut if nxt is not None else None)
            except BudgetError as e:
                record["stopped"] = f"budget: {e}"
                progress(f"claude {model} stopped at {cp.name}: {e}")
                break
            record["checkpoints"].append(r)
            record["cost_usd"] = round(sum(_checkpoint_cost(c) for c in record["checkpoints"]), 6)
            record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
            if save:
                write_record(record, path)
            s, q = r["summary"], r.get("request") or {}
            progress(f"claude {model} {cp.name}: right {s['right']}/{s['questions']}, refused {s['refused']}, "
                     f"truncated {s['truncated']}, errors {s['errors']}, context {r.get('context_tokens')} tokens, "
                     f"ttft {q.get('ttft_s')} s, ${_checkpoint_cost(r):.4f} (spent ${self.spent():.2f})")
        record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
        if save:
            record["path"] = str(write_record(record, path))
        return record


@dataclass
class Checkpoint:
    """A point in the history where questions are asked: ``history[:cut]`` has been told by then."""

    name: str
    cut: int
    questions: list = field(default_factory=list)


# --- questions, answers and records -------------------------------------------------------------------------------


def _field(obj: Any, *names: str) -> Any:
    for n in names:
        value = obj.get(n) if isinstance(obj, dict) else getattr(obj, n, None)
        if value is not None and not callable(value):
            return value
    return None


def _question(q: Any) -> dict:
    qid, text = _field(q, "qid", "id"), _field(q, "text", "question")
    if qid is None or text is None:
        raise ValueError(f"a question needs an id and a text: {q!r}")
    return {"qid": str(qid), "text": str(text), "expected": _field(q, "expected"), "obj": q}


def question_block(qs: Sequence[dict]) -> str:
    """The text after the history: how to answer, then the questions as JSON lines."""
    lines = "\n".join(json.dumps({"id": q["qid"], "question": q["text"]}, ensure_ascii=False) for q in qs)
    return ("</history>\n\nAnswer each question below from the history above. Each question is a JSON object "
            "with an id.\n\n" + lines + "\n\nReply with JSON only, in this shape: "
            '{"answers": [{"id": "<id>", "answer": "<your answer>"}]}, with one entry for every question, in the '
            "same order.")


_PAIR = re.compile(r'"id"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', re.S)


def parse_answers(text: str) -> dict[str, str]:
    """Answers by id from Claude's JSON. A truncated or fenced reply still gives every complete answer."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t)
    obj = None
    for candidate in (t, t[t.find("{"):t.rfind("}") + 1] if "{" in t else ""):
        try:
            obj = json.loads(candidate)
            break
        except (json.JSONDecodeError, ValueError):
            continue
    out: dict[str, str] = {}
    if isinstance(obj, dict) and isinstance(obj.get("answers"), list):
        for a in obj["answers"]:
            if isinstance(a, dict) and a.get("id") is not None and a.get("answer") is not None:
                ans = a["answer"]
                out[str(a["id"])] = ans if isinstance(ans, str) else json.dumps(ans)
        return out
    if isinstance(obj, dict):
        return {str(k): v if isinstance(v, str) else json.dumps(v) for k, v in obj.items()}
    for qid, ans in _PAIR.findall(t):
        try:
            out[json.loads(f'"{qid}"')] = json.loads(f'"{ans}"')
        except json.JSONDecodeError:
            continue
    return out


def _grade(grader: Callable[[Any, str], Any] | None, q: Any, answer: str) -> tuple[bool | None, str | None]:
    """(right, verdict) from the grader's bool, verdict or dict. A grader that fails leaves the answer ungraded,
    so a paid reply is never lost."""
    if grader is None:
        return None, None
    try:
        out = grader(q, answer)
    except Exception:
        return None, "grader_error"
    if isinstance(out, bool):
        return out, "right" if out else "wrong"
    if isinstance(out, str):
        return out in RIGHT, out
    if isinstance(out, dict):
        verdict = out.get("verdict")
        return bool(out.get("right", verdict in RIGHT)), verdict
    return bool(out), "right" if out else "wrong"


def _answer(q: dict, text: str | None, verdict: str | None, right: bool | None, call: Call | None, batch: int) -> dict:
    """One answer's record. A batched request's tokens and dollars are shared equally by its answers."""
    a: dict[str, Any] = {"qid": q["qid"], "question": q["text"], "expected": q["expected"], "answer": text,
                         "right": right, "verdict": verdict, "refused": verdict == "refused", "batch": batch}
    if call is not None:
        t = call.tokens
        a.update({"answered_by": call.answered_by, "ttft_s": _r(call.ttft_s), "first_token_s": _r(call.first_token_s),
                  "total_s": _r(call.total_s), "output_tps": call.output_tps,
                  "input_tokens": round(t.input / batch, 1), "cache_write_tokens": round(t.cache_write / batch, 1),
                  "cache_read_tokens": round(t.cache_read / batch, 1), "output_tokens": round(t.output / batch, 1),
                  "thinking_tokens": round(t.thinking / batch, 1), "cost_usd": round(call.cost_usd / batch, 6)})
    return a


def _answers(qs: list[dict], call: Call, grader: Callable[[Any, str], Any] | None) -> list[dict]:
    """Every question's record from one reply. A question the reply never reached because it hit its own
    ``max_tokens`` is "truncated" and left ungraded; one a finished reply skipped is "no_answer" and wrong."""
    replies = {} if call.refused else parse_answers(call.text)
    cut_off = call.stop_reason == "max_tokens"
    out = []
    for q in qs:
        if call.refused:
            out.append(_answer(q, None, "refused", False, call, len(qs)))
            continue
        text = replies.get(q["qid"])
        if text is None:
            out.append(_answer(q, None, "truncated", None, call, len(qs)) if cut_off
                       else _answer(q, None, "no_answer", False, call, len(qs)))
            continue
        right, verdict = _grade(grader, q["obj"], text)
        out.append(_answer(q, text, verdict, right, call, len(qs)))
    return out


_SHARED = {"input_tokens": 1, "cache_write_tokens": 1, "cache_read_tokens": 1, "output_tokens": 1,
           "thinking_tokens": 1, "cost_usd": 6}  # per-answer fields, with their rounding


def _with_share(again: dict, first: dict) -> dict:
    """A re-asked answer, also carrying its share of the first, cut-off request, so no dollar is lost."""
    for name, nd in _SHARED.items():
        again[name] = round((again.get(name) or 0.0) + (first.get(name) or 0.0), nd)
    again["reasked"] = True
    return again


def _checkpoint_cost(r: dict) -> float:
    """What a checkpoint's requests cost: the first one and the re-ask, if there was one."""
    return sum(float(((x or {}).get("request") or {}).get("cost_usd") or 0.0) for x in (r, r.get("reask")))


def summarize(answers: list[dict]) -> dict:
    v = Counter(a["verdict"] for a in answers)
    return {"questions": len(answers), "right": sum(a["right"] is True for a in answers),
            "graded": sum(a["right"] is not None for a in answers), "refused": v["refused"],
            "no_answer": v["no_answer"], "truncated": v["truncated"], "errors": v["error"],
            "reasked": sum(bool(a.get("reasked")) for a in answers), "verdicts": dict(v),
            "cost_usd": round(sum(a.get("cost_usd") or 0.0 for a in answers), 6)}


def _environment() -> dict:
    env = {"anthropic": anthropic.__version__, "python": platform.python_version()}
    try:
        from engram.ruler.harness import source_sha

        env["engram_source_sha"] = source_sha()
    except Exception:
        env["engram_source_sha"] = None
    return env


def write_record(record: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, default=str))
    return path


# --- the live smoke call ----------------------------------------------------------------------------------------


def smoke(claude: Claude | None = None) -> Call:
    """One tiny live call to Haiku (at most 20 output tokens), logged in the ledger like any other."""
    claude = claude or Claude()
    return claude.call("claude-haiku-5-5", [{"role": "user", "content": "Reply with one word: ready"}],
                       max_tokens=20, purpose="smoke", prompt_tokens=64, cache=False)


def main(argv: Sequence[str] | None = None) -> int:
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["smoke"]:
        c = smoke()
        d = c.as_dict()
        print(json.dumps({k: d[k] for k in ("model", "answered_by", "stop_reason", "input_tokens", "output_tokens",
                                             "thinking_tokens", "cost_usd", "ttft_s", "first_token_s", "total_s")}))
        print(f"reply: {c.text!r}")
        return 0
    if args[:1] == ["spent"]:
        ledger = Ledger()
        spent = ledger.spent()
        limit = ledger.cap_usd - ledger.headroom_usd
        print(f"spent ${spent:.4f} of ${ledger.cap_usd:.0f} (calls are refused past ${limit:.0f})")
        return 0
    print("usage: python -m engram.bench.claude smoke|spent")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
