"""Ollama as a contender, over its own HTTP API on this Mac, and the Long Haul through it.

- ``ollama:<model>`` is the model through the pairing proxy (engram.pair.ollama), started in this process on
  127.0.0.1:11435 (another free port if that one is taken). Its memory is the pairing's: words in a folder under
  work/memories/, found again by the engine's embedder. ``tell`` remembers into that memory; each question goes
  through the proxy, which puts the closest notes (512 tokens) in front of it.
- ``ollama-bare:<model>`` is plain Ollama with no memory: the most recent W = 32,768 tokens of the history are the
  context, as for the local bare contender. Before a checkpoint's first question the window is read by one untimed
  request (the same system message, a one-token reply), as local bare reads its window before its clock starts.
  Ollama keeps what it read, so each timed question reads only itself. The read counts as the checkpoint's ingest
  (``reading_s``), and every answer carries its size and time (``window_read_tokens``, ``window_read_s``). An answer
  that read the window again anyway, because Ollama let go of it, is marked ``paid_window_read``. Its first-word time
  and prefill speed then stay in ``extra`` and out of the summary.

    python -m engram.bench.ollama_run longhaul --contender ollama:qwen3-1.7b --dir work/haul/s1 [--cuts 64K] [--limit N]
    python -m engram.bench.ollama_run models   # what is pulled, each build, and whether it can answer with thinking off

The models are qwen3:1.7b, qwen3:4b-instruct-2507-q4_K_M and qwen3:8b (qwen3-1.7b, qwen3-4b and qwen3-8b name the
same). The 4B is the instruct build, as the local qwen3-4b (Qwen3-4B-Instruct-2507). Ollama's plain qwen3:4b is
Qwen3-4B-Thinking-2507: its template opens a <think> block after every prompt.

Thinking is off. Ollama's ``think: false`` becomes an empty think block and " /no_think" in qwen3's template. Each
model is checked once, with /api/show, which loads nothing. Three kinds are refused: a Thinking build, a template that
always opens <think>, and a thinking template with no way to turn it off. The build (general.finetune and
general.version) goes in the record. A reply that thought anyway is an error and is never graded. Decoding is greedy,
and num_ctx is set on every request: Ollama's default context would cut a long prompt silently. The speeds are
Ollama's own (prompt_eval_count over prompt_eval_duration, eval_count over eval_duration). The time to the first word,
the ms the proxy added and the recall time are measured here.

Tokens are counted with the Qwen3 tokenizer from the local cache, and a contender does not start without it. A guess
could size the bare window past num_ctx, and Ollama would then cut the prompt from the front without a word. A window
read that Ollama takes in far fewer tokens than planned means it cut the prompt, so it is an error.

The prompts are the local contenders' (engram.bench.local), so a model compares with itself across the two runtimes.
- Bare reads the yardstick's instructions and the history as its system message, the lines joined by a blank line.
  The family's one line on the form of the answer comes after the question.
- Paired reads the same instructions with notes in place of the history (local.LONGHAUL_INTRO), then
  "Today is <date>." and the family's line, all in the system message. The user message is the question alone, so the
  proxy looks the notes up by the question, as the engine does, and puts them in front of it.
- A paired note carries its day ("[day 50]") as an engine moment does, and day lines are not kept as notes of their
  own.

Only the told history goes into the pairing's memory. The proxy would also remember each question and its answer;
here that is off, so one answer never becomes the next question's notes, and every contender answers from the same
history.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import os
import re
import threading
import time
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from engram.bench.contender import RECORDS, THINKING, Answer, Contender, metrics, run, slug

WORK = Path(__file__).resolve().parents[3] / "work"
MEMORIES = WORK / "memories"
HAUL = WORK / "haul" / "s1"

OLLAMA = "127.0.0.1:11434"
PROXY_PORT = 11435
WINDOW = 32_768  # W: the most history the bare contender keeps, in tokens
NUM_CTX = WINDOW + 4_096  # the bare contender's context: W, plus the instructions, the question and the reply
PAIRED_CTX = 8_192  # the paired contender reads notes (512 tokens) and the question, never the whole history
KEEP_ALIVE = "30m"
TIMEOUT_S = 900.0  # an 8B model reading 32K tokens, or loading, can take minutes
TEMPLATE_TOKENS = 32  # about what qwen3's chat template adds around a system and a user message
NOTES_TOKENS = 48  # the proxy's words around the notes it adds
MODELS = {"qwen3-1.7b": "qwen3:1.7b", "qwen3-4b": "qwen3:4b-instruct-2507-q4_K_M", "qwen3-8b": "qwen3:8b"}
OPTIONS = {"temperature": 0.0, "seed": 0}
DAY_LINE = re.compile(r"^Day \d+ · [A-Z][a-z]+ \d{1,2} [A-Z][a-z]+ \d{4}$")
READ_QUESTION = "?"  # what the untimed window read asks, as local bare's template does
CUT_SHARE = 0.9  # a window read Ollama took in less than this share of the planned tokens was cut
CUT_SLACK = 64  # tokens of slack in that check, for a short prompt
FORCED_THINK = re.compile(r"<\|im_start\|>assistant\s*\n\s*<think>")  # a template that always opens <think>

PAIRED_SYSTEM = ("You answer questions about a project's history: one developer's log of chats, decisions, code, notes "
                 "and lessons. Notes from that history come before each question. Answer from them only. When they "
                 "never say, answer \"I don't know\". Keep each answer short unless the question asks for code or a "
                 "page.")


@dataclass(frozen=True)
class Frame:
    """How a task's prompt is worded: the instructions, the words around a history kept in the prompt and between
    its lines, whether the told day is given as today's date, and whether notes carry their day number."""

    system: str | None = None
    opener: str = "<context>\n"
    closer: str = "\n</context>"
    today: bool = False
    day_numbers: bool = False
    join: str = "\n"


SUITE = Frame()


def longhaul_frame(paired: bool = False) -> Frame:
    """The Long Haul's wording. Bare reads the yardstick's instructions and opener (engram.bench.claude), its lines
    joined by a blank line and the history closed after one more, as engram.bench.local's bare reads them. Paired is
    told its notes come from that history, and today's date."""
    from engram.bench.claude import OPENER, SYSTEM

    if paired:
        return Frame(PAIRED_SYSTEM, today=True, day_numbers=True)
    return Frame(SYSTEM, OPENER, "\n\n</history>", join="\n\n")


def hint(family: str | None) -> str:
    """The family's one line on the form of its answer, the same as the local contenders get."""
    from engram.bench.local import HINTS

    return HINTS.get(family or "", "")


def counter(strict: bool = True) -> tuple[Callable[[str], int], str]:
    """A token counter and its name: Qwen3's tokenizer from the local cache. Without it, ``strict`` raises (a
    benchmark run never guesses); otherwise it counts about four characters a token."""
    try:
        from engram.bench.haul import tokens

        return tokens.counter(), tokens.TOKENIZER
    except Exception as e:  # no tokenizer in the cache
        if strict:
            raise RuntimeError(f"no Qwen3 tokenizer in the local Hugging Face cache ({type(e).__name__}: {e}); "
                               "without it a prompt cannot be sized against num_ctx") from e
        return (lambda text: len(text) // 4 + 1), "chars/4"


def memory_folder(task: str, name: str, memories: Path = MEMORIES) -> Path:
    """A new memory folder, named as engram.bench.local names its own (``.nosync``, so iCloud leaves it alone)."""
    return Path(memories) / f"{task}-{slug(name)}-{dt.datetime.now():%Y%m%d-%H%M%S}.nosync"


def think_off(show: dict) -> tuple[str | None, str | None]:
    """Whether a model answers with its thinking off when a request says ``think: false``, read from /api/show:
    (why it would think anyway, or None; how its thinking stays off). A Thinking build, a template that always opens
    <think>, and a thinking template with no think-off branch ("not $.Think", " /no_think") think whatever the
    request says. An instruct build, or a template with no thinking in it, does not think."""
    info = show.get("model_info") or {}
    finetune = str(info.get("general.finetune") or "")
    template = str(show.get("template") or "")
    if "think" in finetune.lower():
        return f"it is a {finetune} build (general.finetune), which always thinks", None
    if FORCED_THINK.search(template):
        return "its template opens a <think> block after every prompt", None
    if "not $.Think" in template or "/no_think" in template:
        return None, "its template's think-off branch (think: false)"
    thinks = "thinking" in (show.get("capabilities") or []) or "$.Think" in template
    if "instruct" in finetune.lower() or not thinks:
        return None, "it does not think (an instruct build, or no thinking in its template)"
    return "its template thinks and has no way to turn that off", None


def build_of(show: dict) -> dict:
    """The build a model is, from /api/show: its name, finetune (Instruct, Thinking or none) and version."""
    info = show.get("model_info") or {}
    return {k: info.get(f"general.{k}") for k in ("basename", "finetune", "version", "size_label", "parameter_count")}


# --- Ollama over HTTP --------------------------------------------------------------------------------------------


class OllamaError(RuntimeError):
    pass


class ThinkingError(OllamaError):
    """A reply thought before it answered, though thinking was off: it is never graded as a think-off answer."""


@dataclass
class Reply:
    """One streamed chat answer and what it took, timed from the moment the request was sent."""

    text: str
    thinking: str
    ttft_s: float | None  # to the first piece with a word in it
    total_s: float
    final: dict  # Ollama's last line: its counts and durations
    headers: dict


def _why(body: bytes) -> str:
    try:
        return str(json.loads(body).get("error") or body[:300])
    except (ValueError, AttributeError):
        return body[:300].decode(errors="replace")


class Ollama:
    """Ollama's HTTP API at ``address``, on this Mac only."""

    def __init__(self, address: str = OLLAMA, timeout_s: float = TIMEOUT_S):
        host, _, port = address.rpartition(":")
        if host not in ("127.0.0.1", "localhost"):
            raise ValueError("Ollama must be on this Mac")
        self.address, self.host, self.port, self.timeout_s = address, host, int(port), timeout_s

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout_s)
        try:
            data = json.dumps(body).encode() if body is not None else None
            conn.request(method, path, data, {"Content-Type": "application/json"} if data else {})
            resp = conn.getresponse()
            raw = resp.read()
        except (OSError, http.client.HTTPException) as e:
            raise OllamaError(f"Ollama is not answering at {self.address} ({type(e).__name__})") from e
        finally:
            conn.close()
        if resp.status != 200:
            raise OllamaError(f"{path}: Ollama answered {resp.status}: {_why(raw)}")
        return json.loads(raw) if raw.strip() else {}

    def get(self, path: str) -> dict:
        return self._request("GET", path)

    def post(self, path: str, body: dict) -> dict:
        return self._request("POST", path, body)

    def chat(self, body: dict) -> Reply:
        """One /api/chat request, streamed, so the first word is timed exactly."""
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout_s)
        texts, thoughts, first, final = [], [], None, None
        try:
            t0 = time.perf_counter()
            conn.request("POST", "/api/chat", json.dumps({**body, "stream": True}, ensure_ascii=False).encode(),
                         {"Content-Type": "application/json"})
            resp = conn.getresponse()
            if resp.status != 200:
                raise OllamaError(f"/api/chat: Ollama answered {resp.status}: {_why(resp.read())}")
            headers = {k.lower(): v for k, v in resp.getheaders()}
            for raw in resp:
                raw = raw.strip()
                if not raw:
                    continue
                obj = json.loads(raw)
                if obj.get("error"):
                    raise OllamaError(f"/api/chat: {obj['error']}")
                msg = obj.get("message") or {}
                piece = msg.get("content") or ""
                if piece:
                    texts.append(piece)
                    if first is None and piece.strip():
                        first = time.perf_counter() - t0
                if msg.get("thinking"):
                    thoughts.append(msg["thinking"])
                if obj.get("done"):
                    final = obj
                    break
            total = time.perf_counter() - t0
        except (OSError, http.client.HTTPException, ValueError) as e:
            raise OllamaError(f"/api/chat at {self.address} failed ({type(e).__name__})") from e
        finally:
            conn.close()
        if final is None:
            raise OllamaError("the answer ended before Ollama said it was done")
        return Reply("".join(texts).strip(), "".join(thoughts), first, total, final, headers)


def speeds(final: dict) -> dict:
    """Ollama's own numbers from its last line: reading and writing speeds, counts, and its load time."""
    def tps(n: str, d: str) -> float | None:
        return round(final[n] / (final[d] / 1e9), 1) if final.get(d) and final.get(n) is not None else None

    return {"prefill_tps": tps("prompt_eval_count", "prompt_eval_duration"),
            "decode_tps": tps("eval_count", "eval_duration"), "prompt_eval_count": final.get("prompt_eval_count"),
            "eval_count": final.get("eval_count"), "done_reason": final.get("done_reason"),
            "load_ms": round(final["load_duration"] / 1e6, 2) if final.get("load_duration") else None,
            "ollama_total_s": round(final["total_duration"] / 1e9, 4) if final.get("total_duration") else None}


# --- the two contenders ------------------------------------------------------------------------------------------


class _OllamaContender(Contender):
    """What both share: the model, the request, the one check and warm-up, and what Ollama holds for the model."""

    kind = "ollama"

    def __init__(self, model: str, *, frame: Frame = SUITE, ollama: str = OLLAMA, num_ctx: int = NUM_CTX,
                 count: Callable[[str], int] | None = None, timeout_s: float = TIMEOUT_S, warm: bool = True):
        self.model = MODELS.get(model, model)
        self.name = f"{self.kind}:{self.model}"
        self.frame, self.num_ctx, self.warm_up = frame, num_ctx, warm
        self.client = Ollama(ollama, timeout_s)
        self._count, self._counter_name = count, "given" if count else None
        self.history_tokens = 0
        self.thinking = THINKING
        self._info: dict | None = None
        self._show: dict | None = None
        self._checked = False

    def count(self, text: str | None) -> int:
        if not text:
            return 0
        if self._count is None:
            self._count, self._counter_name = counter()
        return self._count(text)

    def body(self, messages: list[dict], max_tokens: int, num_ctx: int) -> dict:
        return {"model": self.model, "messages": messages, "think": THINKING, "keep_alive": KEEP_ALIVE,
                "options": {**OPTIONS, "num_ctx": num_ctx, "num_predict": max_tokens}}

    @staticmethod
    def question(question: str, family: str | None) -> str:
        then = hint(family)
        return question + (f"\n\n{then}" if then else "")

    def show(self) -> dict:
        """What /api/show says of the model (its build, template and capabilities). Asked once; it loads nothing."""
        if self._show is None:
            self._show = self.client.post("/api/show", {"model": self.model})
        return self._show

    def check(self) -> None:
        """Once per contender, before its first question. The model must be pulled and able to answer with its
        thinking off, and the tokenizer must be there. Then the model is loaded with this contender's context, so no
        answer waits for that."""
        if self._checked:
            return
        names = {m.get("name") for m in self.client.get("/api/tags").get("models", [])}
        if self.model not in names and f"{self.model}:latest" not in names:
            raise OllamaError(f"{self.model} is not pulled (ollama pull {self.model})")
        self.count("x")  # the real tokenizer, or no run
        why, _ = think_off(self.show())
        if why:
            raise OllamaError(f"{self.model} cannot answer with thinking off: {why}"
                              + (f" (qwen3-4b is {MODELS['qwen3-4b']}, the instruct build)"
                                 if self.model.startswith("qwen3:4b") else ""))
        if self.warm_up:
            self.client.post("/api/generate", {"model": self.model, "keep_alive": KEEP_ALIVE,
                                               "options": {"num_ctx": self.num_ctx}})
        self._checked = True

    def answered(self, reply: Reply) -> Reply:
        """The reply, when it did not think. One that did (Ollama's thinking field, or a <think> block in its words)
        is an error, so it is never graded as an answer given with thinking off."""
        if reply.thinking.strip() or "</think>" in reply.text or reply.text.lstrip().startswith("<think>"):
            raise ThinkingError(f"{self.model} thought before answering ({len(reply.thinking)} characters of "
                                "thinking) though thinking was off")
        return reply

    def resident(self) -> tuple[float | None, int | None]:
        """What Ollama holds for this model now: its size in GB (weights and keys and values), and its context."""
        try:
            for m in self.client.get("/api/ps").get("models", []):
                if m.get("name") in (self.model, f"{self.model}:latest") or m.get("model") == self.model:
                    return round(m.get("size", 0) / 1e9, 3), m.get("context_length")
        except (OllamaError, ValueError):
            pass
        return None, None

    def describe(self) -> dict:
        if self._info is None:
            info: dict[str, Any] = {"name": self.name, "kind": self.kind, "model": self.model, "runtime": "ollama",
                                    "enable_thinking": THINKING, "think": THINKING, "options": OPTIONS,
                                    "num_ctx": self.num_ctx, "keep_alive": KEEP_ALIVE, "system": self.frame.system,
                                    "frame": {"opener": self.frame.opener, "closer": self.frame.closer,
                                              "lines_joined_by": self.frame.join, "today_line": self.frame.today,
                                              "day_numbers": self.frame.day_numbers},
                                    "hints": True}
            try:
                info["ollama_version"] = self.client.get("/api/version").get("version")
                show = self.show()
                info["details"], info["capabilities"] = show.get("details"), show.get("capabilities")
                info["build"] = build_of(show)
                info["finetune"], info["version"] = info["build"]["finetune"], info["build"]["version"]
                why, how = think_off(show)
                info["think_off"] = how or f"no: {why}"
                for m in self.client.get("/api/tags").get("models", []):
                    if m.get("name") in (self.model, f"{self.model}:latest"):
                        info["digest"] = m.get("digest")
            except (OllamaError, ValueError) as e:
                info["describe_error"] = str(e)
                self._info = None
                return {**info, "token_counter": self._counter_name}
            self._info = info
        return {**self._info, "token_counter": self._counter_name}

    def _answer(self, reply: Reply, num_ctx: int, *, retrieval_ms: float | None, context_tokens: int,
                disk_gb: float | None, tier: str | None, bytes_read: int | None, extra: dict) -> Answer:
        size, loaded = self.resident()
        s = speeds(reply.final)
        m = metrics(ttft_s=None if reply.ttft_s is None else round(reply.ttft_s, 4), total_s=round(reply.total_s, 4),
                    prefill_tps=s.pop("prefill_tps"), decode_tps=s.pop("decode_tps"), retrieval_ms=retrieval_ms,
                    bytes_read=bytes_read, gbps=None, read_share=None, context_tokens=context_tokens,
                    history_tokens=self.history_tokens, peak_ram_gb=size, disk_gb=disk_gb, tier=tier)
        return Answer(reply.text, m, {**s, "answer_tokens": s.get("eval_count"), "num_ctx": num_ctx,
                                      "loaded_ctx": loaded, "ollama_gb": size, "thinking_chars": len(reply.thinking),
                                      **extra})


class OllamaBare(_OllamaContender):
    """ollama-bare:<model>: no memory. The most recent ``window`` tokens of the history, whole lines only, are the
    system message, after the instructions; the question is the user message. Before the first question on a window,
    one untimed request has Ollama read it (``read_window``); Ollama keeps what it read, so each timed question reads
    only itself. A question too long for the room left takes its room from the front of the history, so the prompt
    always fits ``num_ctx``; that window is read first in the same way."""

    kind = "ollama-bare"

    def __init__(self, model: str, *, window: int = WINDOW, num_ctx: int = NUM_CTX, **kw: Any):
        super().__init__(model, num_ctx=num_ctx, **kw)
        self.window = window
        self.lines: list[str] = []
        self.cum = [0]  # tokens of lines[:i], each line with the words that join it to the next
        self._sep: int | None = None
        self.read: dict = {}  # the last window read
        self.reads, self.read_s = 0, 0.0
        self._held: tuple[int, int] | None = None  # (first line, lines told) of the window Ollama has read
        self._held_text = ""

    def sep(self) -> int:
        """The tokens joining one line to the next (one in Qwen3's vocabulary, for a newline or a blank line)."""
        if self._sep is None:
            self._sep = max(1, self.count(self.frame.join))
        return self._sep

    def open(self, folder: Path) -> None:
        """A new, empty history. What Ollama last read (``_held_text``) is kept: its cache outlives this call, so a
        new window that starts the same way is read only from where it differs."""
        self.lines, self.cum, self.history_tokens = [], [0], 0
        self._held, self.read = None, {}
        self.check()

    def tell(self, text: str, day: int) -> None:
        n = self.count(text)
        self.lines.append(text)
        self.cum.append(self.cum[-1] + n + self.sep())
        self.history_tokens += n

    def system(self, start: int) -> str:
        f = self.frame
        parts = [f.system] if f.system else []
        if start < len(self.lines):
            parts.append(f.opener + f.join.join(self.lines[start:]) + f.closer)
        return "\n\n".join(parts)

    def fit(self, user: str, max_tokens: int) -> tuple[int, int]:
        """(first line, tokens) of the most recent history that fits ``num_ctx`` with the instructions, the question
        and the reply."""
        f = self.frame
        fixed = (self.count(f.system) + self.count(f.opener + f.closer) + self.count(user) + max_tokens
                 + TEMPLATE_TOKENS)
        budget = max(0, min(self.window, self.num_ctx - fixed))
        start = bisect_left(self.cum, self.cum[-1] - budget)
        return start, self.cum[-1] - self.cum[start]

    def read_window(self, start: int, system: str) -> None:
        """Have Ollama read ``system`` (the window from line ``start``), untimed: one request with a one-token reply.
        Ollama reuses what it holds of an earlier prompt, so only what changed is read. A read that took in far
        fewer tokens than that means Ollama cut the prompt, which is an error."""
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": READ_QUESTION}]
        t = time.perf_counter()
        reply = self.client.chat(self.body(msgs, 1, self.num_ctx))
        seconds = time.perf_counter() - t
        self.read_s += seconds
        fin = reply.final
        n, d = fin.get("prompt_eval_count"), fin.get("prompt_eval_duration")
        planned = self.count(system) + self.count(READ_QUESTION) + TEMPLATE_TOKENS
        cached = self.count(os.path.commonprefix([self._held_text, system])) if self._held_text else 0
        if n is not None and (n > self.num_ctx or n < CUT_SHARE * (planned - cached) - CUT_SLACK):
            self._held, self._held_text = None, ""
            raise OllamaError(f"Ollama read {n} tokens of the window's {planned - cached} (num_ctx {self.num_ctx}): "
                              "the prompt was cut")
        self.reads += 1
        self.read = {"tokens": n, "planned_tokens": planned, "cached_tokens": cached, "seconds": round(seconds, 3),
                     "ollama_s": round(d / 1e9, 3) if d else None,
                     "tps": round(n / (d / 1e9), 1) if n and d else None, "lines": len(self.lines) - start,
                     "first_line": start,
                     "load_ms": round(fin["load_duration"] / 1e6, 2) if fin.get("load_duration") else None}
        self._held, self._held_text = (start, len(self.lines)), system

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        f = self.frame
        user = self.question(question, family)
        start, used = self.fit(user, max_tokens)
        system = self.system(start)
        if system and self._held != (start, len(self.lines)):
            self.read_window(start, system)
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        reply = self.answered(self.client.chat(self.body(msgs, max_tokens, self.num_ctx)))
        asked = self.count(user)
        read = reply.final.get("prompt_eval_count")
        paid = used > 0 and read is not None and read > asked + TEMPLATE_TOKENS + used // 2
        frame = self.count(f.opener + f.closer)
        out = self._answer(reply, self.num_ctx, retrieval_ms=None, bytes_read=0, disk_gb=0.0, tier=None,
                           context_tokens=self.count(f.system) + (frame + used if used else 0) + asked,
                           extra={"window_tokens": used, "window_lines": len(self.lines) - start,
                                  "cut_from_front": start > 0, "question_tokens": asked,
                                  "window_read_tokens": self.read.get("tokens") if system else None,
                                  "window_read_s": self.read.get("seconds") if system else None,
                                  "paid_window_read": paid})
        if paid:  # Ollama let go of the window and read it again inside this answer's time: kept out of the summary
            out.extra.update(ttft_with_window_s=out.metrics["ttft_s"],
                             prefill_tps_with_window=out.metrics["prefill_tps"])
            out.metrics["ttft_s"] = out.metrics["prefill_tps"] = None
        return out

    def reading_s(self) -> float:
        return self.read_s

    def status(self) -> dict:
        return {"window": self.window, "num_ctx": self.num_ctx, "lines_told": len(self.lines),
                "history_tokens": self.history_tokens, "prefill": dict(self.read), "prefills": self.reads}

    def describe(self) -> dict:
        return {**super().describe(), "window": self.window,
                "prompt": "system: the instructions, then the window's lines joined by lines_joined_by inside the "
                          "opener and closer; user: the question, then the family's line",
                "hint_in": "user, after the question", "read_question": READ_QUESTION,
                "cost": "each window is read once by an untimed request with a one-token reply, counted as the "
                        "checkpoint's ingest; each question then reads only itself"}

    def close(self) -> None:
        self.lines, self.cum = [], [0]
        self._held, self._held_text = None, ""


class _Gate:
    """The pairing's memory as the benchmark uses it: each recall is timed and its notes kept for the record, and
    what the proxy would remember of a question and its answer is dropped (``keep`` turns that back on)."""

    def __init__(self, inner: Any, keep: bool = False):
        self.inner, self.keep = inner, keep
        self.last: tuple[str, float] | None = None
        self.query: str | None = None  # what the proxy looked the notes up by

    def recall_text(self, query: str, budget_tokens: int) -> str:
        t = time.perf_counter()
        notes = self.inner.recall_text(query, budget_tokens)
        self.last, self.query = (notes, round((time.perf_counter() - t) * 1000, 3)), query
        return notes

    def remember(self, text: str, role: str) -> int:
        return self.inner.remember(text, role) if self.keep else 0


_SPEAKER = re.compile(r"^(User|Assistant): ")


def speaker(text: str) -> tuple[str, str]:
    """(role, words) of a told line: "User: ..." and "Assistant: ..." keep their role; anything else (a pasted log,
    a day line) is kept as the user's."""
    m = _SPEAKER.match(text)
    return (m.group(1).lower(), text[m.end():]) if m else ("user", text)


def folder_gb(folder: Path) -> float:
    total = 0
    for p in Path(folder).rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return round(total / 1e9, 6)


class OllamaPaired(_OllamaContender):
    """ollama:<model>: Ollama through the pairing proxy, run in this process. What was told is kept as notes in the
    memory folder, and the proxy puts the closest ones (``budget`` tokens) in front of each question.

    A long told text is remembered as several turns of at most TURN_PIECES pieces, since the pairing keeps only the
    ends of a longer turn. Notes are dated by the history's own days (the Long Haul's working calendar), not by the
    clock. ``embedder`` makes the embedder (engram.models.Embedder by default, loaded once and shared by every folder
    this contender opens); tests pass a fake."""

    kind = "ollama"

    def __init__(self, model: str, *, port: int = PROXY_PORT, budget: int | None = None, num_ctx: int = PAIRED_CTX,
                 embedder: Callable[[], Any] | None = None, remember_questions: bool = False, **kw: Any):
        from engram.bench.haul.script import LONGEST, calendar
        from engram.pair.ollama import BUDGET

        super().__init__(model, num_ctx=num_ctx, **kw)
        self.want_port, self.budget = port, BUDGET if budget is None else budget
        self.make_embedder, self.remember_questions = embedder, remember_questions
        self._emb: Any = None
        self._mlx = False
        self.pairing: Any = None
        self.httpd: Any = None
        self._thread: threading.Thread | None = None
        self.proxy: Ollama | None = None
        self.port: int | None = None
        self.folder: Path | None = None
        self.vault: Any = None
        self.gate: _Gate | None = None
        self.day, self._seq, self.left_out, self.notes_told = 0, 0, 0, 0
        self._disk: float | None = None
        self._dates = calendar(LONGEST)  # the 110 days, and the days a longer script adds after them

    def _embedder(self) -> Any:
        if self._emb is None:
            if self.make_embedder is not None:
                self._emb = self.make_embedder()
            else:
                from engram.bench.local import EMBEDDER
                from engram.models import Embedder

                self._emb, self._mlx = Embedder(EMBEDDER), True
        return self._emb

    def date(self) -> dt.date:
        """The told day as a date: day 1 is the Long Haul's first working day."""
        d = self._dates
        return d[self.day - 1] if 1 <= self.day <= len(d) else d[0] + dt.timedelta(days=self.day - 1)

    def _now(self) -> dt.datetime:
        """When a note is dated: the told day at 09:00, a second later for each note told that day."""
        return dt.datetime.combine(self.date(), dt.time(9)) + dt.timedelta(seconds=min(self._seq, 53_999))

    def _serve(self) -> None:
        from engram.pair.ollama import make_server

        try:
            self.httpd = make_server(self.pairing, self.want_port)
        except OSError:  # the port is taken (a pairing someone else runs): any free port will do
            self.httpd = make_server(self.pairing, 0)
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="engram-pairing", daemon=True)
        self._thread.start()
        self.proxy = Ollama(f"127.0.0.1:{self.port}", self.client.timeout_s)

    def open(self, folder: Path) -> None:
        """A new, empty memory in ``folder``, on the same proxy. Whatever the proxy's worker still has to remember of
        the last memory's exchanges is written there first, so none of it reaches the new one."""
        from engram.pair.ollama import WAIT_S, Pairing
        from engram.pair.provider import VaultWords

        self.check()
        if self.pairing is not None and not self.pairing.settled(WAIT_S):
            raise OllamaError("the last memory's exchanges are still being remembered: a new memory would get them")
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.vault = VaultWords(self.folder, embedder=self._embedder(), clock=self._now)
        self.gate = _Gate(self.vault, keep=self.remember_questions)
        log = self.folder / "ollama" / "metrics.jsonl"
        if self.pairing is None:
            self.pairing = Pairing(self.gate, self.client.address, budget_tokens=self.budget, metrics_path=log)
            self._serve()
        else:
            with self.pairing.lock:
                self.pairing.provider, self.pairing.metrics_path = self.gate, log
        self.history_tokens, self.day, self._seq, self.left_out, self.notes_told, self._disk = 0, 0, 0, 0, 0, None

    def tell(self, text: str, day: int) -> None:
        from engram.pair.provider import TURN_PIECES, pieces

        assert self.vault is not None and self.pairing is not None, "open() first"
        if day != self.day:
            self.day, self._seq = day, 0
        self.history_tokens += self.count(text)
        if self.frame.day_numbers and DAY_LINE.match(text):
            return  # every note carries its day
        role, words = speaker(text)
        if self.frame.day_numbers and day >= 1:
            words = f"[day {day}] {words}"
        cut = pieces(words)
        with self.pairing.lock:
            for k in range(0, len(cut), TURN_PIECES):
                self.left_out += self.vault.remember("\n\n".join(cut[k:k + TURN_PIECES]), role) or 0
                self._seq += 1
        self.notes_told += 1
        self._disk = None

    def disk_gb(self) -> float | None:
        if self._disk is None and self.folder is not None:
            self._disk = folder_gb(self.folder)
        return self._disk

    def system(self, family: str | None = None) -> str | None:
        """The system message: the instructions, today's date and the family's line, in that order, as the engine's
        and words' system prompts end. The notes come in the user message, from the proxy."""
        from engram.memory import today_text

        f = self.frame
        parts = [f.system] if f.system else []
        if f.today and self.day >= 1:
            parts.append(f"Today is {today_text(self.date())}.")
        then = hint(family)
        if then:
            parts.append(then)
        return "\n\n".join(parts) or None

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        from engram.pair.ollama import NOTES_END, NOTES_INTRO

        assert self.gate is not None and self.proxy is not None, "open() first"
        system, user = self.system(family), question  # the proxy looks notes up by the question alone
        words = self.count(system) + self.count(user)
        need = words + self.budget + NOTES_TOKENS + max_tokens + TEMPLATE_TOKENS
        num_ctx = self.num_ctx if need <= self.num_ctx else -(-need // 4096) * 4096
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        self.gate.last = self.gate.query = None
        reply = self.answered(self.proxy.chat(self.body(msgs, max_tokens, num_ctx)))
        notes, recall_ms = self.gate.last or ("", None)
        notes_tokens = self.count(f"{NOTES_INTRO}\n\n{notes}\n\n{NOTES_END}\n\n") if notes else 0
        extra = {"proxy_ms": _float(reply.headers.get("x-engram-added-ms")), "notes_tokens": notes_tokens,
                 "notes_chars": len(notes), "notes": len(self.vault.notes), "left_out_chars": self.left_out,
                 "recall_query_is_question": self.gate.query == question if self.gate.query is not None else None}
        out = self._answer(reply, num_ctx, retrieval_ms=recall_ms, bytes_read=None, disk_gb=self.disk_gb(),
                           tier="vault", context_tokens=words + notes_tokens, extra=extra)
        if self._mlx and out.metrics["peak_ram_gb"] is not None:  # the embedder runs in this process, with MLX
            from engram.models import peak_gb

            out.extra["embedder_peak_gb"] = round(peak_gb() or 0.0, 3)
            out.metrics["peak_ram_gb"] = round(out.metrics["peak_ram_gb"] + out.extra["embedder_peak_gb"], 3)
        return out

    def status(self) -> dict:
        return {"notes": len(self.vault.notes) if self.vault is not None else 0, "told": self.notes_told,
                "history_tokens": self.history_tokens, "disk_gb": self.disk_gb(), "left_out_chars": self.left_out,
                "proxy_port": self.port}

    def describe(self) -> dict:
        from engram.pair.ollama import NOTES_END, NOTES_INTRO

        emb = self._emb
        return {**super().describe(), "proxy_port": self.port, "notes_budget_tokens": self.budget,
                "remember_questions": self.remember_questions, "day_numbers": self.frame.day_numbers,
                "prompt": "system: the instructions, \"Today is <date>.\" (when the task gives a day), then the "
                          "family's line; user: the proxy's notes between notes_intro and notes_end, then the question",
                "hint_in": "system, at the end", "notes_intro": NOTES_INTRO, "notes_end": NOTES_END,
                "recall_query": "the question alone",
                "embedder": getattr(emb, "name", None) or (type(emb).__name__ if emb is not None else None)}

    def close(self) -> None:
        from engram.pair.ollama import WAIT_S

        if self.pairing is not None:
            self.pairing.settled(WAIT_S)  # the last exchanges are written before the proxy goes
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            if self._thread is not None:
                self._thread.join(5)
        self.httpd = self.pairing = self._thread = self.proxy = None


def _float(x: str | None) -> float | None:
    try:
        return float(x) if x is not None else None
    except ValueError:
        return None


def make(name: str, **kw: Any) -> OllamaBare | OllamaPaired:
    """A contender by name: ollama:<model> or ollama-bare:<model>, the model as Ollama names it (qwen3:1.7b) or as
    the benchmarks do (qwen3-1.7b)."""
    kind, _, model = name.partition(":")
    if not model:
        raise ValueError(f"name a model, as in {kind}:qwen3-1.7b")
    if kind == "ollama":
        return OllamaPaired(model, **kw)
    if kind == "ollama-bare":
        return OllamaBare(model, **kw)
    raise ValueError(f"no Ollama contender {kind!r}: use ollama:<model> or ollama-bare:<model>")


# --- the Long Haul ------------------------------------------------------------------------------------------------


def haul_meta(folder: Path) -> dict:
    """The built Long Haul a record answered, as engram.bench.local records it: the script's hash pins it."""
    m = json.loads((Path(folder) / "manifest.json").read_text())
    return {"dir": str(folder), "seed": m.get("seed"), "version": m.get("version"), "tokens": m.get("tokens"),
            "events": m.get("events"), "script_sha": m.get("script_sha")}


def longhaul(contender: Contender, folder: Path = HAUL, *, cuts: Sequence[str] | None = None, limit: int | None = None,
             memories: Path = MEMORIES, records: Path = RECORDS, progress: Callable[[str], None] = print) -> dict:
    """``contender`` through the Long Haul's checkpoints (the same as every contender's), with the shared runner."""
    from engram.bench.longhaul import CUTS, checkpoints, grader

    names = list(cuts or CUTS)
    unknown = set(names) - set(CUTS)
    if unknown:
        raise ValueError(f"no cut {', '.join(sorted(unknown))}; there are {', '.join(CUTS)}")
    events, cps = checkpoints(Path(folder), {n: CUTS[n] for n in names})
    return run(contender, events, cps, task="longhaul", grader=grader,
               folder=memory_folder("longhaul", contender.name, memories), limit=limit, records=records,
               progress=progress, meta={"haul": haul_meta(folder), "cuts": names})


def models(client: Ollama) -> dict:
    """What Ollama has pulled and holds now, and for each pulled model its build and whether it can answer with its
    thinking off. Reads metadata only: nothing is loaded."""
    pulled = []
    for m in client.get("/api/tags").get("models", []):
        try:
            show = client.post("/api/show", {"model": m["name"]})
            why, how = think_off(show)
            pulled.append({"name": m["name"], **build_of(show), "think_off": how or f"no: {why}"})
        except OllamaError as e:
            pulled.append({"name": m["name"], "error": str(e)})
    return {"version": client.get("/api/version").get("version"), "pulled": pulled,
            "loaded": [m["name"] for m in client.get("/api/ps").get("models", [])],
            "benchmark_models": MODELS}


def main(argv: Sequence[str] | None = None) -> int:
    from engram.bench.longhaul import CUTS

    ap = argparse.ArgumentParser(prog="python -m engram.bench.ollama_run",
                                 description="Ollama contenders: paired (memory as words) and bare (a 32K window).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("longhaul", help="the Long Haul, checkpoint by checkpoint")
    h.add_argument("--contender", required=True, help="ollama:<model> or ollama-bare:<model>, e.g. ollama:qwen3-1.7b")
    h.add_argument("--dir", type=Path, default=HAUL, help="a built Long Haul")
    h.add_argument("--cuts", nargs="+", choices=list(CUTS), help="some of the cuts (default: all)")
    h.add_argument("--limit", type=int, help="at most N questions per checkpoint, every family in turn")
    h.add_argument("--memories", type=Path, default=MEMORIES)
    h.add_argument("--records", type=Path, default=RECORDS)
    h.add_argument("--port", type=int, default=PROXY_PORT, help="the pairing proxy's port (ollama: only)")
    h.add_argument("--ollama", default=OLLAMA, help="where Ollama listens (this Mac only)")
    m = sub.add_parser("models", help="what Ollama has pulled and holds, each build and its thinking (loads nothing)")
    m.add_argument("--ollama", default=OLLAMA)
    a = ap.parse_args(argv)
    if a.cmd == "models":
        print(json.dumps(models(Ollama(a.ollama)), indent=1))
        return 0
    paired = a.contender.startswith("ollama:")
    contender = make(a.contender, frame=longhaul_frame(paired), ollama=a.ollama,
                     **({"port": a.port} if paired else {}))
    record = longhaul(contender, a.dir, cuts=a.cuts, limit=a.limit, memories=a.memories, records=a.records)
    print(record.get("path"))
    return 0


__all__ = ["MODELS", "NUM_CTX", "PAIRED_CTX", "READ_QUESTION", "SUITE", "WINDOW", "Frame", "Ollama", "OllamaBare",
           "OllamaError", "OllamaPaired", "ThinkingError", "build_of", "counter", "haul_meta", "hint", "longhaul",
           "longhaul_frame", "make", "memory_folder", "models", "speeds", "think_off"]


if __name__ == "__main__":
    from engram.app.measuring import measuring

    with measuring("ollama_run"):  # the app pauses its views and loads nothing while this measures
        raise SystemExit(main())
