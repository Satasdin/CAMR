"""The Ollama contenders, against a stand-in Ollama and a stand-in embedder: no model is loaded and the real Ollama is
never reached. Bare keeps the most recent window and has it read before the first timed question, paired goes
through the pairing proxy and remembers only what was told, a model that would think is refused, and both report the
shared metrics with Ollama's own speeds."""

from __future__ import annotations

import http.client
import json
import os
import re
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import pytest

from camr_engine.bench import ollama_run as orun
from camr_engine.bench.contender import METRICS, Answer, Contender
from camr_engine.bench.ollama_run import (READ_QUESTION, Frame, Ollama, OllamaBare, OllamaError, OllamaPaired,
                                     ThinkingError, haul_meta, longhaul, longhaul_frame, make, speaker, speeds,
                                     think_off)
from camr_engine.pair.ollama import NOTES_END, NOTES_INTRO


@pytest.fixture(autouse=True)
def no_real_ollama(monkeypatch):
    """A test may reach only its own stand-in: the real Ollama's and the pairing's ports are refused."""
    real = http.client.HTTPConnection.__init__

    def guarded(self, host, port=None, *a, **k):
        if port in (11434, 11435):
            raise AssertionError("a test tried to reach the real Ollama")
        return real(self, host, port, *a, **k)

    monkeypatch.setattr(http.client.HTTPConnection, "__init__", guarded)


FINAL = {"done": True, "done_reason": "stop", "prompt_eval_count": 100, "prompt_eval_duration": 50_000_000,
         "eval_count": 10, "eval_duration": 100_000_000, "load_duration": 1_000_000, "total_duration": 200_000_000}
# The end of qwen3:1.7b's template (Ollama 0.13.5): think false gives an empty think block.
HYBRID = ('{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant\n{{ if and $.IsThinkSet (not $.Think) -}}\n'
          '<think>\n\n</think>\n\n{{ end -}}\n{{ end }}')
# The end of qwen3:4b's (Qwen3-4B-Thinking-2507): every prompt opens <think>.
THINKING = '{{- if and (ne .Role "assistant") $last }}<|im_start|>assistant\n<think>\n{{ end }}'


def prompt_text(req: dict) -> str:
    return "".join(f"\x00{m['role']}\x00{m['content']}" for m in req.get("messages", []))


class FakeOllama:
    """Speaks enough of Ollama's API for the contenders, and keeps every request it was sent.

    Like Ollama, it keeps the last prompt it read: a request that starts the same way reads only what follows the
    shared start, and ``prompt_eval_count`` counts those words (at 2,000 a second). ``limit`` cuts a longer prompt to
    that many words, as Ollama cuts one past num_ctx; ``forget()`` drops what it holds."""

    def __init__(self, models=("qwen3:1.7b",), reply=None, *, template=HYBRID, info=None, thinking=""):
        self.seen: list[tuple[str, str, dict]] = []
        self.models = list(models)
        self.reply = reply or (lambda req: "I don't know.")
        self.error: str | None = None
        self.loaded_ctx: int | None = None
        self.template, self.thinking = template, thinking
        self.info = {"general.architecture": "qwen3", "general.basename": "Qwen3", "general.size_label": "1.7B",
                     **(info or {})}
        self.held = ""
        self.limit: int | None = None
        self.done_reason = "stop"
        fake = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _json(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _chat(self, req):
                if fake.loaded_ctx != req["options"]["num_ctx"]:
                    fake.held = ""  # a new context is a reload: nothing is kept
                fake.loaded_ctx = req["options"]["num_ctx"]
                text = prompt_text(req)
                read = len(text[len(os.path.commonprefix([fake.held, text])):].split()) or 1
                if fake.limit is not None:
                    read = min(read, fake.limit)
                fake.held = text
                reply = fake.reply(req)
                lines = []
                if fake.thinking:
                    lines.append({"model": req["model"], "message": {"role": "assistant", "content": "",
                                                                     "thinking": fake.thinking}, "done": False})
                lines += [{"model": req["model"], "message": {"role": "assistant", "content": p}, "done": False}
                          for p in (reply[:3], reply[3:]) if p]
                final = {**FINAL, "done_reason": fake.done_reason, "prompt_eval_count": read,
                         "prompt_eval_duration": read * 500_000}
                lines.append({"error": fake.error} if fake.error else
                             {"model": req["model"], "message": {"role": "assistant", "content": ""}, **final})
                body = b"".join(json.dumps(x).encode() + b"\n" for x in lines)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for piece in (body[:40], body[40:]):
                    if piece:
                        self.wfile.write(b"%x\r\n%s\r\n" % (len(piece), piece))
                self.wfile.write(b"0\r\n\r\n")

            def _any(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if n else b""
                req = json.loads(raw) if raw else {}
                fake.seen.append((self.command, self.path, req))
                details = {"family": "qwen3", "parameter_size": "2.0B", "quantization_level": "Q4_K_M"}
                if self.path == "/api/tags":
                    return self._json({"models": [{"name": m, "model": m, "digest": "d" * 64, "details": details}
                                                  for m in fake.models]})
                if self.path == "/api/version":
                    return self._json({"version": "0.13.5"})
                if self.path == "/api/ps":
                    return self._json({"models": [{"name": fake.models[0], "model": fake.models[0],
                                                   "size": 2_000_000_000, "context_length": fake.loaded_ctx}]
                                       if fake.loaded_ctx else []})
                if self.path == "/api/show":
                    return self._json({"details": details, "capabilities": ["completion", "thinking"],
                                       "model_info": fake.info, "template": fake.template})
                if self.path == "/api/generate":
                    fake.loaded_ctx = req["options"]["num_ctx"]
                    return self._json({"model": req["model"], "done": True, "done_reason": "load"})
                if self.path == "/api/chat":
                    return self._chat(req)
                return self._json({"error": "not found"}, 404)

            do_GET = do_POST = _any

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.address = f"127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def chats(self) -> list[dict]:
        return [req for _, path, req in self.seen if path == "/api/chat"]

    def asked(self) -> list[dict]:
        """The chats that were questions, not window reads."""
        return [r for r in self.chats() if r["options"]["num_predict"] != 1]

    def forget(self) -> None:
        self.held = ""


class Words:
    """A stand-in embedder: hashed words, unit length."""

    name = "fake-words"

    def encode(self, texts, is_query=False):
        out = np.zeros((len(texts), 64), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                out[i, zlib.crc32(w.encode()) % 64] += 1
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


def words(text: str) -> int:
    return len(text.split())


def bare(fake: FakeOllama, **kw) -> OllamaBare:
    return OllamaBare("qwen3-1.7b", ollama=fake.address, count=words, **kw)


def paired(fake: FakeOllama, **kw) -> OllamaPaired:
    return OllamaPaired("qwen3:1.7b", ollama=fake.address, port=0, embedder=Words, count=words, **kw)


# --- names and Ollama's own numbers


def test_names_take_either_spelling_of_the_model():
    assert make("ollama:qwen3-1.7b").model == "qwen3:1.7b"
    assert make("ollama-bare:qwen3:8b").name == "ollama-bare:qwen3:8b"
    assert isinstance(make("ollama:qwen3-4b"), OllamaPaired) and isinstance(make("ollama-bare:qwen3-4b"), OllamaBare)
    for bad in ("ollama", "lmstudio:qwen3-1.7b"):
        with pytest.raises(ValueError):
            make(bad)
    with pytest.raises(ValueError):
        Ollama("10.0.0.2:11434")  # this Mac only


def test_the_4b_is_the_instruct_build_as_the_local_4b():
    from camr_engine.bench.local import MODELS as LOCAL

    assert make("ollama:qwen3-4b").model == "qwen3:4b-instruct-2507-q4_K_M"
    assert "Instruct-2507" in LOCAL["qwen3-4b"]


def test_speeds_are_ollamas_own_counts_over_its_own_durations():
    s = speeds(FINAL)
    assert s["prefill_tps"] == 2000.0 and s["decode_tps"] == 100.0
    assert s["load_ms"] == 1.0 and s["ollama_total_s"] == 0.2 and s["eval_count"] == 10
    assert speeds({"done": True})["decode_tps"] is None


def test_a_told_line_keeps_its_speaker():
    assert speaker("User: hello") == ("user", "hello")
    assert speaker("Assistant: done") == ("assistant", "done")
    assert speaker("Tool: a log") == ("user", "Tool: a log")


# --- thinking stays off


def test_which_builds_can_answer_with_thinking_off():
    hybrid = {"capabilities": ["completion", "thinking"], "template": HYBRID, "model_info": {}}
    assert think_off(hybrid) == (None, "its template's think-off branch (think: false)")
    for show in ({"capabilities": ["thinking"], "template": THINKING, "model_info": {"general.finetune": "Thinking"}},
                 {"capabilities": ["thinking"], "template": THINKING, "model_info": {}},  # always opens <think>
                 {"capabilities": ["thinking"], "template": "{{ if .Thinking }}<think>{{ .Thinking }}</think>{{ end }}",
                  "model_info": {}}):  # a thinking template with no way to turn it off
        why, how = think_off(show)
        assert why and how is None
    instruct = {"capabilities": ["completion", "thinking"], "template": "<think>{{ .Thinking }}</think>",
                "model_info": {"general.finetune": "Instruct", "general.version": "2507"}}
    assert think_off(instruct)[0] is None
    assert think_off({"capabilities": ["completion"], "template": "{{ .Prompt }}", "model_info": {}})[0] is None


def test_a_thinking_build_is_refused_before_anything_is_asked(tmp_path):
    fake = FakeOllama(models=("qwen3:4b",), template=THINKING,
                      info={"general.finetune": "Thinking", "general.version": "2507"})
    c = OllamaBare("qwen3:4b", ollama=fake.address, count=words)
    with pytest.raises(OllamaError, match="Thinking build.*instruct build"):
        c.open(tmp_path)
    assert fake.chats() == [] and not any(path == "/api/generate" for _, path, _ in fake.seen)  # nothing loaded


def test_the_record_names_the_build_and_how_its_thinking_is_off(tmp_path):
    fake = FakeOllama(models=("qwen3:4b-instruct-2507-q4_K_M",), template="{{ .Prompt }}",
                      info={"general.finetune": "Instruct", "general.version": "2507"})
    c = OllamaBare("qwen3-4b", ollama=fake.address, count=words)
    c.open(tmp_path)
    d = c.describe()
    assert d["model"] == "qwen3:4b-instruct-2507-q4_K_M" and d["finetune"] == "Instruct" and d["version"] == "2507"
    assert d["think_off"].startswith("it does not think") and d["enable_thinking"] is False


def test_a_reply_that_thought_is_an_error_never_an_answer(tmp_path):
    fake = FakeOllama(thinking="Let me work this out first.")
    c = bare(fake)
    c.open(tmp_path)
    with pytest.raises(ThinkingError, match="thought before answering"):
        c.ask("Where?", max_tokens=10)
    fake.thinking = ""
    fake.reply = lambda req: "<think>hmm</think> Nairobi"
    with pytest.raises(ThinkingError):
        c.ask("Where?", max_tokens=10)
    fake.reply = lambda req: "<think>still thinking"
    with pytest.raises(ThinkingError):
        c.ask("Where?", max_tokens=10)


def test_an_empty_think_block_is_no_thinking_and_is_cut_off_the_answer(tmp_path):
    fake = FakeOllama()
    c = bare(fake)
    c.open(tmp_path)
    fake.reply = lambda req: "</think>The most recent location of Sandra is the kitchen."
    assert c.ask("Where is Sandra?", max_tokens=20).text == "The most recent location of Sandra is the kitchen."
    fake.reply = lambda req: "<think>\n\n</think>\n\nNairobi"
    assert c.ask("Where?", max_tokens=10).text == "Nairobi"
    fake.reply = lambda req: "</think>Nairobi</think>"
    with pytest.raises(ThinkingError):
        c.ask("Where?", max_tokens=10)


def test_the_model_is_checked_and_loaded_once_per_run(tmp_path):
    fake = FakeOllama()
    c = bare(fake)
    for k in range(3):
        c.open(tmp_path / str(k))
    assert sum(path == "/api/tags" for _, path, _ in fake.seen) == 1
    assert sum(path == "/api/generate" for _, path, _ in fake.seen) == 1


def test_no_tokenizer_means_no_run(tmp_path, monkeypatch):
    from camr_engine.bench.haul import tokens

    def missing():
        raise FileNotFoundError("no tokenizer.json")

    monkeypatch.setattr(tokens, "counter", missing)
    with pytest.raises(RuntimeError, match="tokenizer"):
        orun.counter()
    assert orun.counter(strict=False)[1] == "chars/4"
    fake = FakeOllama()
    with pytest.raises(RuntimeError, match="num_ctx"):
        OllamaBare("qwen3-1.7b", ollama=fake.address).open(tmp_path)
    assert fake.chats() == []


# --- bare


def test_bare_keeps_the_most_recent_window_and_sets_the_context_and_thinking_off(tmp_path):
    fake = FakeOllama()
    c = bare(fake, window=20, num_ctx=200, frame=Frame("SYS", "<h>\n", "\n</h>"))
    c.open(tmp_path)
    assert fake.seen[-1][1] == "/api/generate" and fake.seen[-1][2]["options"]["num_ctx"] == 200  # loaded at once
    for i in range(10):
        c.tell(f"line {i} has five words", 1)  # 5 tokens, and one for its newline
    a = c.ask("Where?", max_tokens=50, family="fact")
    req = fake.chats()[-1]
    assert req["think"] is False and req["stream"] is True
    assert req["options"] == {"temperature": 0.0, "seed": 0, "num_ctx": 200, "num_predict": 50}
    system, user = req["messages"]
    assert system == {"role": "system", "content": "SYS\n\n<h>\nline 7 has five words\nline 8 has five words\n"
                                                    "line 9 has five words\n</h>"}
    assert user == {"role": "user", "content": "Where?"}
    assert isinstance(a, Answer) and a.text == "I don't know."
    assert set(a.metrics) == set(METRICS)
    m = a.metrics
    assert m["prefill_tps"] == 2000.0 and m["decode_tps"] == 100.0 and m["ttft_s"] is not None
    assert m["history_tokens"] == 50 and m["tier"] is None and m["disk_gb"] == 0.0 and m["retrieval_ms"] is None
    assert m["peak_ram_gb"] == 2.0 and a.extra["loaded_ctx"] == 200
    assert a.extra["window_tokens"] == 18 and a.extra["window_lines"] == 3 and a.extra["cut_from_front"]
    assert m["context_tokens"] == 1 + 2 + 18 + 1  # instructions, opener and closer, window, question
    assert a.extra["answer_tokens"] == 10 and a.extra["done_reason"] == "stop"


def test_the_window_is_read_untimed_before_the_first_question_and_each_question_reads_only_itself(tmp_path):
    fake = FakeOllama()
    c = bare(fake, window=400, frame=Frame("SYS", "<h>\n", "\n</h>"))
    c.open(tmp_path)
    for i in range(50):
        c.tell(f"line {i} has five words", 1)
    first = c.ask("Where was line seven?", max_tokens=50, family="fact")
    read, asked = fake.chats()[-2:]
    assert read["options"]["num_predict"] == 1 and read["messages"][-1] == {"role": "user", "content": READ_QUESTION}
    assert read["messages"][0] == asked["messages"][0] and read["options"]["num_ctx"] == asked["options"]["num_ctx"]
    assert asked["options"]["num_predict"] == 50
    assert first.extra["prompt_eval_count"] == 4  # the question alone: the window was read before the clock
    assert first.extra["window_read_tokens"] > 250 and first.extra["window_read_s"] is not None
    assert first.extra["paid_window_read"] is False and first.metrics["ttft_s"] is not None
    second = c.ask("And line eight?", max_tokens=50, family="fact")
    assert len(fake.chats()) == 3 and second.extra["prompt_eval_count"] == 3  # no second read
    assert c.reading_s() > 0 and c.status()["prefills"] == 1
    c.tell("line 50 has five words", 2)  # the window moved: read again before the next question
    c.ask("And line fifty?", max_tokens=50, family="fact")
    assert len(fake.chats()) == 5 and c.status()["prefills"] == 2
    assert c.status()["prefill"]["cached_tokens"] > 0  # Ollama kept the start the two windows share


def test_an_answer_that_read_the_window_again_is_kept_out_of_the_speeds(tmp_path):
    fake = FakeOllama()
    c = bare(fake, window=400)
    c.open(tmp_path)
    for i in range(50):
        c.tell(f"line {i} has five words", 1)
    c.ask("Where?", max_tokens=50)
    fake.forget()  # Ollama let go of the window (another prompt, or the model was unloaded)
    a = c.ask("Where now?", max_tokens=50)
    assert a.extra["paid_window_read"] is True and a.metrics["ttft_s"] is None and a.metrics["prefill_tps"] is None
    assert a.extra["ttft_with_window_s"] is not None and a.extra["prompt_eval_count"] > 250


def test_a_window_ollama_cut_is_an_error(tmp_path):
    fake = FakeOllama()
    c = bare(fake, window=2_000, num_ctx=3_000)
    c.open(tmp_path)
    for i in range(300):
        c.tell(f"line {i} has five words", 1)
    fake.limit = 500  # Ollama took in only the end of a 1,800-word prompt
    with pytest.raises(OllamaError, match="the prompt was cut"):
        c.ask("Where?", max_tokens=10)
    fake.limit, fake.held = None, ""
    assert c.ask("Where?", max_tokens=10).text == "I don't know."  # read again, whole


def test_a_new_context_that_starts_as_the_last_one_did_is_not_taken_for_a_cut_prompt(tmp_path):
    fake = FakeOllama()
    c = bare(fake, window=2_000, num_ctx=3_000)
    for k in (1, 2):  # the same story twice: Ollama still holds the first, so it reads almost nothing the second time
        c.open(tmp_path / str(k))
        for i in range(300):
            c.tell(f"line {i} has five words", 1)
        assert c.ask("Where?", max_tokens=10).text == "I don't know."
    assert c.status()["prefill"]["tokens"] <= 2 and c.status()["prefill"]["cached_tokens"] > 1_000


def test_the_long_haul_wording_is_local_bares(tmp_path):
    from camr_engine.bench.claude import OPENER, SYSTEM

    fake = FakeOllama()
    c = bare(fake, frame=longhaul_frame())
    c.open(tmp_path)
    c.tell("Day 1 · Monday 22 September 2025", 1)
    c.tell("User: hello", 1)
    c.ask("What did the user say?", max_tokens=120, family="maths")
    system, user = fake.chats()[-1]["messages"]
    # local bare: f"{BARE_SYSTEM}\n\n{OPENER}" + "".join(line + "\n\n") + "</history>"
    assert system["content"] == f"{SYSTEM}\n\n{OPENER}Day 1 · Monday 22 September 2025\n\nUser: hello\n\n</history>"
    from camr_engine.bench.local import HINTS

    assert user["content"] == f"What did the user say?\n\n{HINTS['maths']}"


def test_a_long_question_takes_its_room_from_the_front_of_the_history(tmp_path):
    fake = FakeOllama()
    c = bare(fake, window=60, num_ctx=120, frame=Frame())
    c.open(tmp_path)
    for i in range(10):
        c.tell(f"line {i} has five words", 1)
    c.ask("short", max_tokens=10, family="fact")
    whole = fake.chats()[-1]["messages"][0]["content"]
    c.ask(" ".join(["long"] * 40), max_tokens=10, family="fact")
    cut = fake.chats()[-1]["messages"][0]["content"]
    assert whole.count("line") == 10 and 0 < cut.count("line") < 10 and cut.rstrip().endswith("</context>")
    assert "line 9" in cut
    assert fake.chats()[-2]["options"]["num_predict"] == 1  # the shorter window was read before that question


def test_each_family_gets_the_local_contenders_line_on_the_form_of_its_answer(tmp_path):
    from camr_engine.bench.local import HINTS

    fake = FakeOllama()
    c = bare(fake)
    c.open(tmp_path)
    c.ask("Write the helper.", max_tokens=600, family="code")
    assert fake.chats()[-1]["messages"][-1]["content"] == f"Write the helper.\n\n{HINTS['code']}"
    c.ask("Which day?", max_tokens=120, family="babilong")
    assert fake.chats()[-1]["messages"] == [{"role": "user", "content": "Which day?"}]  # nothing told, no system
    assert len(fake.chats()) == 2  # nothing to read first


def test_a_model_that_is_not_pulled_is_a_clear_error(tmp_path):
    fake = FakeOllama(models=("qwen3:1.7b",))
    with pytest.raises(OllamaError, match="not pulled"):
        OllamaBare("qwen3-8b", ollama=fake.address, count=words).open(tmp_path)


def test_an_error_inside_the_stream_is_raised(tmp_path):
    fake = FakeOllama()
    c = bare(fake)
    c.open(tmp_path)
    fake.error = "the runner stopped"
    with pytest.raises(OllamaError, match="the runner stopped"):
        c.ask("Where?", max_tokens=10)


# --- paired


def test_paired_remembers_what_was_told_and_the_proxy_puts_it_before_the_question(tmp_path):
    fake = FakeOllama()
    c = paired(fake, frame=longhaul_frame(paired=True))
    c.open(tmp_path / "mem")
    try:
        c.tell("Day 3 · Wednesday 24 September 2025", 3)  # every note carries its day: no note of its own
        c.tell("User: Staging now listens on port 8443.", 3)
        c.tell("Assistant: Noted, staging is on 8443.", 3)
        assert len(c.vault.notes) == 2
        a = c.ask("What port does staging use?", max_tokens=120, family="changed")
        req = fake.chats()[-1]
        system, user = req["messages"]
        assert system["content"].endswith("Today is Wednesday 24 September 2025.")
        assert user["content"].startswith(NOTES_INTRO) and NOTES_END in user["content"]
        assert "[2025-09-24 09:00] The user said: [day 3] Staging now listens on port 8443." in user["content"]
        assert user["content"].endswith("What port does staging use?")
        assert req["think"] is False and req["options"]["num_ctx"] == orun.PAIRED_CTX
        assert set(a.metrics) == set(METRICS)
        m = a.metrics
        assert m["tier"] == "vault" and m["retrieval_ms"] is not None and m["disk_gb"] > 0
        assert m["history_tokens"] == sum(words(t) for t in ("Day 3 · Wednesday 24 September 2025",
                                                             "User: Staging now listens on port 8443.",
                                                             "Assistant: Noted, staging is on 8443."))
        assert m["context_tokens"] > words(user["content"].split(NOTES_END)[-1])
        assert a.extra["proxy_ms"] is not None and a.extra["notes_chars"] > 0 and a.extra["notes"] == 2
        c.pairing.settled(5)
        assert len(c.vault.notes) == 2  # the question and its answer were not remembered
        assert len(list((tmp_path / "mem" / "ollama" / "vault").glob("*.md"))) == 2
    finally:
        c.close()


def test_paired_looks_notes_up_by_the_question_alone_and_reads_the_familys_line_last_in_its_system(tmp_path):
    from camr_engine.bench.local import HINTS
    from camr_engine.memory import today_text

    fake = FakeOllama()
    c = paired(fake, frame=longhaul_frame(paired=True))
    c.open(tmp_path)
    try:
        c.tell("User: The fee is 1% rounded up to the next 5 shillings.", 4)
        a = c.ask("What is the fee on 7,321 shillings?", max_tokens=400, family="maths")
        system, user = fake.chats()[-1]["messages"]
        assert system["content"] == (f"{orun.PAIRED_SYSTEM}\n\nToday is {today_text(c.date())}.\n\n"
                                     f"{HINTS['maths']}")
        assert HINTS["maths"] not in user["content"] and user["content"].endswith("What is the fee on 7,321 shillings?")
        assert c.gate.query == "What is the fee on 7,321 shillings?" and a.extra["recall_query_is_question"] is True
        assert c.describe()["hint_in"] == "system, at the end"
    finally:
        c.close()


def test_a_long_told_text_is_kept_whole(tmp_path):
    from camr_engine.pair.provider import PIECE_CHARS, TURN_PIECES

    fake = FakeOllama()
    c = paired(fake)
    c.open(tmp_path)
    try:
        paras = [f"paragraph {i} " + "word " * (PIECE_CHARS // 6) for i in range(TURN_PIECES * 2 + 3)]
        c.tell("\n\n".join(paras), 0)
        assert c.left_out == 0
        kept = " ".join(n["text"] for n in c.vault.notes)
        assert all(f"paragraph {i} " in kept for i in range(len(paras)))
    finally:
        c.close()


def test_opening_a_new_folder_starts_an_empty_memory_on_the_same_proxy(tmp_path):
    fake = FakeOllama()
    c = paired(fake)
    c.open(tmp_path / "a")
    try:
        port = c.port
        c.tell("User: The fridge code is 4417.", 0)
        c.ask("What is the fridge code?", max_tokens=120)
        assert NOTES_INTRO in fake.chats()[-1]["messages"][-1]["content"]
        c.open(tmp_path / "b")
        c.ask("What is the fridge code?", max_tokens=120)
        assert fake.chats()[-1]["messages"] == [{"role": "user", "content": "What is the fridge code?"}]
        assert c.port == port and c.status()["notes"] == 0
    finally:
        c.close()
    assert c.httpd is None


def test_an_exchange_still_being_remembered_never_reaches_the_next_memory(tmp_path):
    fake = FakeOllama(reply=lambda req: "The fridge code is 4417.")
    c = paired(fake, remember_questions=True)
    c.open(tmp_path / "g1")
    try:
        slow = c.pairing.remember

        def held(*a, **k):  # the worker is slow to write the exchange down
            time.sleep(0.3)
            return slow(*a, **k)

        c.pairing.remember = held
        c.tell("User: The fridge code is 4417.", 0)
        c.ask("What is the fridge code?", max_tokens=120)
        c.open(tmp_path / "g2")
        assert c.vault.notes == []
        assert not (tmp_path / "g2" / "ollama" / "metrics.jsonl").exists()
        assert len(list((tmp_path / "g1" / "ollama" / "vault").glob("*.md"))) == 3  # told, asked, answered
    finally:
        c.close()


# --- the Long Haul through the shared runner


class Recorder(Contender):
    name = "recorder:none"

    def __init__(self):
        self.told, self.asked, self.opened, self.closed = [], [], [], False

    def open(self, folder):
        self.opened.append(folder)

    def tell(self, text, day):
        self.told.append((day, text))

    def ask(self, question, *, max_tokens, family=None):
        from camr_engine.bench.contender import metrics

        self.asked.append((family, max_tokens))
        return Answer("I don't know.", metrics(ttft_s=0.1, history_tokens=len(self.told)))

    def close(self):
        self.closed = True


def test_the_long_haul_runs_through_the_shared_runner_with_each_familys_room(tmp_path):
    from haul_shared import built

    from camr_engine.bench.haul import write

    write(built(), tmp_path / "haul")
    c = Recorder()
    rec = longhaul(c, tmp_path / "haul", cuts=["64K"], limit=8, memories=tmp_path / "mem",
                   records=tmp_path / "records", progress=lambda s: None)
    cp = rec["checkpoints"][0]
    assert len(c.told) == cp["events"] and c.told[0][1].startswith("Day 1 ·") and c.closed
    assert c.opened[0].parent == tmp_path / "mem" and c.opened[0].name.endswith(".nosync")
    assert len(cp["answers"]) == 8 and {f for f, _ in c.asked} >= {"fact", "maths", "page", "code", "never"}
    rooms = {"page": 1200, "code": 600, "maths": 400}
    assert all(room == rooms.get(f, 120) for f, room in c.asked)
    assert all(a["right"] for a in cp["answers"] if a["family"] == "never")  # a decline is right
    saved = json.loads(open(rec["path"]).read())
    assert saved["thinking"] is False and saved["environment"] and saved["haul"]["seed"] == 1
    assert saved["haul"]["script_sha"] and saved["haul"] == haul_meta(tmp_path / "haul")
    assert "never" in saved["checkpoints"][0]["summary"] and "all" in saved["checkpoints"][0]["summary"]
    assert "/records/" in rec["path"] and rec["path"].endswith("-longhaul-recorder-none.json")


def test_bare_ollama_end_to_end_on_the_long_haul(tmp_path):
    from haul_shared import built

    from camr_engine.bench.haul import write

    write(built(), tmp_path / "haul")
    fake = FakeOllama()
    c = OllamaBare("qwen3:1.7b", ollama=fake.address, count=words, frame=longhaul_frame())
    rec = longhaul(c, tmp_path / "haul", cuts=["64K"], limit=3, memories=tmp_path / "mem",
                   records=tmp_path / "records", progress=lambda s: None)
    cp = rec["checkpoints"][0]
    answers = cp["answers"]
    assert len(answers) == 3 and all(a["verdict"] != "error" for a in answers)
    assert all(a["metrics"]["decode_tps"] == 100.0 for a in answers)
    assert all(a["extra"]["paid_window_read"] is False and a["metrics"]["ttft_s"] is not None for a in answers)
    assert len(fake.chats()) == 4 and cp["ingest"]["read_s"] > 0  # one window read, counted as ingest
    system = fake.chats()[-1]["messages"][0]["content"]
    assert system.startswith("You answer questions about a project's history") and "\n<history>\n" in system
    assert system.endswith("\n\n</history>")
    assert rec["contender"]["name"] == "ollama-bare:qwen3:1.7b" and rec["contender"]["ollama_version"] == "0.13.5"
    assert rec["contender"]["think_off"].startswith("its template's think-off branch")


def test_the_command_line_runs_against_the_ollama_it_is_given(tmp_path, capsys):
    from haul_shared import built

    from camr_engine.bench.haul import write

    write(built(), tmp_path / "haul")
    fake = FakeOllama()
    rc = orun.main(["longhaul", "--contender", "ollama-bare:qwen3-1.7b", "--dir", str(tmp_path / "haul"),
                    "--cuts", "64K", "--limit", "2", "--ollama", fake.address, "--records", str(tmp_path / "r"),
                    "--memories", str(tmp_path / "m")])
    assert rc == 0
    path = capsys.readouterr().out.strip().splitlines()[-1]
    assert path.endswith("-longhaul-ollama-bare-qwen3-1.7b.json")
    saved = json.loads(open(path).read())
    assert saved["contender"]["token_counter"] == "mlx-community/Qwen3-1.7B-4bit"  # the real tokenizer
    with pytest.raises(SystemExit):
        orun.main(["longhaul", "--contender", "ollama:qwen3-1.7b", "--cuts", "5M"])


def test_the_models_command_reads_each_build_and_loads_nothing(capsys):
    fake = FakeOllama(models=("qwen3:1.7b", "qwen3:4b"))
    assert orun.main(["models", "--ollama", fake.address]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [m["name"] for m in out["pulled"]] == ["qwen3:1.7b", "qwen3:4b"] and out["version"] == "0.13.5"
    assert out["benchmark_models"]["qwen3-4b"] == "qwen3:4b-instruct-2507-q4_K_M"
    assert not any(path in ("/api/generate", "/api/chat") for _, path, _ in fake.seen)
