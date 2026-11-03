"""The Claude yardstick runner, against a fake client: no network, no key, no money."""

import json
from types import SimpleNamespace as NS

import anthropic
import httpx2
import pytest
from anthropic.types import Usage

from engram.bench import claude as cl
from engram.bench.claude import (OPENER, BudgetError, Checkpoint, Claude, ClaudeError, Ledger, parse_answers, read_key,
                                 smoke)
from engram.bench.cost import cost_usd, estimate_usd

URL = "https://api.anthropic.com/v1/messages"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Only the real transport is refused: the SDK can still run end to end over an httpx2.MockTransport."""
    def refuse(*a, **k):
        raise RuntimeError("a test tried to reach the network")

    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", refuse)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def ev(kind, **kw):
    return NS(type=kind, **kw)


def reply(text, *, model="claude-sonnet-5-5", answered_by=None, input=100, output=50, thinking=20, cache_read=0,
          cache_write=0, stop_reason="end_turn", category=None, t_first=1.0, t_text=2.0, t_end=4.0, break_after=None):
    """A scripted stream: times are seconds after the request was sent."""
    start_usage = NS(input_tokens=input, output_tokens=1, cache_read_input_tokens=cache_read,
                     cache_creation_input_tokens=cache_write, cache_creation=None, output_tokens_details=None)
    timeline = [(0.3, ev("message_start", message=NS(model=answered_by or model, usage=start_usage))),
                (t_first, ev("content_block_start", index=0, content_block=NS(type="thinking"))),
                (t_first + 0.1, ev("content_block_delta", index=0, delta=NS(type="signature_delta", signature="s"))),
                (t_text - 0.1, ev("content_block_start", index=1, content_block=NS(type="text"))),
                (t_text, ev("content_block_delta", index=1, delta=NS(type="text_delta", text=text[:1]))),
                (t_text + 0.1, ev("content_block_delta", index=1, delta=NS(type="text_delta", text=text[1:]))),
                (t_end - 0.1, ev("message_delta", usage=NS(output_tokens=output, input_tokens=None,
                                                           cache_read_input_tokens=None,
                                                           cache_creation_input_tokens=None),
                                 delta=NS(stop_reason=stop_reason)))]
    if not text:
        timeline = [x for x in timeline if x[1].type != "content_block_delta" or x[1].delta.type != "text_delta"]
    usage = Usage(input_tokens=input, output_tokens=output, cache_read_input_tokens=cache_read,
                  cache_creation_input_tokens=cache_write, output_tokens_details={"thinking_tokens": thinking})
    refusal = NS(type="refusal", category=category, explanation=None) if stop_reason == "refusal" else None
    final = NS(model=answered_by or model, id="msg_1", stop_reason=stop_reason, stop_details=refusal,
               content=[NS(type="thinking", thinking=""), NS(type="text", text=text)], usage=usage)
    if break_after is not None:
        return {"timeline": timeline[:1], "error": break_after, "end": t_end}
    return {"timeline": timeline, "final": final, "end": t_end}


class FakeStream:
    def __init__(self, clock, item):
        self.clock, self.item, self.request_id = clock, item, "req_test"

    def __enter__(self):
        if isinstance(self.item, BaseException):
            raise self.item
        self.base = self.clock.now
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        for at, e in self.item["timeline"]:
            self.clock.now = self.base + at
            yield e
        if self.item.get("error") is not None:
            raise self.item["error"]

    def get_final_message(self):
        self.clock.now = self.base + self.item["end"]
        return self.item["final"]


class FakeMessages:
    def __init__(self, clock, script, counter):
        self.clock, self.script, self.counter = clock, list(script), counter
        self.calls, self.counts = [], []

    def stream(self, **kw):
        self.calls.append(kw)
        return FakeStream(self.clock, self.script.pop(0))

    def count_tokens(self, **kw):
        self.counts.append(kw)
        return NS(input_tokens=self.counter(kw))


def chars_over_four(kw):
    text = kw.get("system") or ""
    for m in kw["messages"]:
        content = m["content"]
        text += content if isinstance(content, str) else "".join(b["text"] for b in content)
    return len(text) // 4


class FakeClient:
    def __init__(self, clock, script, counter=chars_over_four):
        self.messages = FakeMessages(clock, script, counter)


def make(tmp_path, script, *, counter=chars_over_four, **kw):
    clock, sleeps = Clock(), []
    fake = FakeClient(clock, script, counter)
    c = Claude(fake, ledger=tmp_path / "ledger.jsonl", records=tmp_path / "records", clock=clock,
               sleep=sleeps.append, **kw)
    return c, fake, sleeps


def lines(c):
    return c.ledger.lines()


def status_error(cls, status, kind, retry_after=None, message=None, headers=None):
    headers = {**({"retry-after": retry_after} if retry_after else {}), **(headers or {})}
    resp = httpx2.Response(status, headers=headers, request=httpx2.Request("POST", URL))
    return cls(kind, response=resp, body={"type": "error", "error": {"type": kind, "message": message or kind}})


ASK = [{"role": "user", "content": "hi"}]


# --- the real SDK over a mock transport -----------------------------------------------------------------------


def sse(kind, data):
    return f"event: {kind}\ndata: {json.dumps(data)}\n\n".encode()


def sse_reply(text, *, model="claude-sonnet-5-5", input=12, output=5, stop_reason="end_turn"):
    """The server-sent events of one streamed reply: a thinking block, then the text."""
    usage = {"input_tokens": input, "output_tokens": 1, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0}
    return [
        sse("message_start", {"type": "message_start", "message": {
            "id": "msg_mock", "type": "message", "role": "assistant", "model": model, "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": usage}}),
        sse("content_block_start", {"type": "content_block_start", "index": 0,
                                    "content_block": {"type": "thinking", "thinking": "", "signature": ""}}),
        sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                                    "delta": {"type": "signature_delta", "signature": "sig"}}),
        sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        sse("content_block_start", {"type": "content_block_start", "index": 1,
                                    "content_block": {"type": "text", "text": ""}}),
        sse("content_block_delta", {"type": "content_block_delta", "index": 1,
                                    "delta": {"type": "text_delta", "text": text}}),
        sse("content_block_stop", {"type": "content_block_stop", "index": 1}),
        sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                              "usage": {"output_tokens": output}}),
        sse("message_stop", {"type": "message_stop"}),
    ]


class Dropped(httpx2.SyncByteStream):
    """A body whose connection drops after its first events, as the peer closing mid-reply does."""

    def __init__(self, chunks):
        self.chunks = chunks

    def __iter__(self):
        yield from self.chunks
        raise httpx2.RemoteProtocolError("peer closed connection without sending complete message body")


SSE = {"content-type": "text/event-stream", "request-id": "req_mock"}


class Server:
    """A scripted API: count_tokens answers from the body's length; each stream request takes the next item."""

    def __init__(self, script):
        self.script, self.requests = list(script), []

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/count_tokens"):
            return httpx2.Response(200, json={"input_tokens": len(request.content) // 4})
        item = self.script.pop(0)
        if isinstance(item, httpx2.Response):
            return item
        if isinstance(item, Dropped):
            return httpx2.Response(200, headers=SSE, stream=item)
        return httpx2.Response(200, headers=SSE, content=b"".join(item))

    @property
    def streams(self):
        return [r for r in self.requests if not r.url.path.endswith("/count_tokens")]


def real(tmp_path, script, *, key="sk-test-not-a-key", **kw):
    """A runner whose client is made lazily from a key file, the real SDK talking to ``Server``."""
    p = tmp_path / "anthropic.env"
    p.write_text(f"ANTHROPIC_API_KEY={key}\n")
    server, sleeps = Server(script), []
    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(server))
    c = Claude(None, key_file=p, http_client=http, ledger=tmp_path / "ledger.jsonl", records=tmp_path / "records",
               sleep=sleeps.append, **kw)
    return c, server, sleeps


def api_error(status, kind, message, retry_after=None):
    headers = {"retry-after": retry_after} if retry_after else {}
    return httpx2.Response(status, headers=headers,
                           json={"type": "error", "error": {"type": kind, "message": message}})


# --- the key --------------------------------------------------------------------------------------------------


def test_read_key_formats(tmp_path):
    p = tmp_path / "anthropic.env"
    for text in ("ANTHROPIC_API_KEY=sk-test-1\n", 'export ANTHROPIC_API_KEY="sk-test-1"\n',
                 "# note\nOTHER=x\nANTHROPIC_API_KEY='sk-test-1'"):
        p.write_text(text)
        assert read_key(p) == "sk-test-1"
    p.write_text("OTHER=sk-not-this\n")
    with pytest.raises(ClaudeError) as e:
        read_key(p)
    assert "sk-not-this" not in str(e.value)


def test_client_is_made_from_the_key_file_and_the_key_is_never_written(tmp_path):
    key = "sk-sentinel-123"
    answers = json.dumps({"answers": [{"id": "a", "answer": "1003"}]})
    script = [sse_reply("ready"), sse_reply(answers),
              api_error(401, "authentication_error", "invalid x-api-key")]
    c, server, _ = real(tmp_path, script, key=key)
    assert c._client is None and key not in repr(c)  # the key file is read only when the first request is made
    call = c.call("claude-sonnet-5-5", ASK, max_tokens=100, purpose="unit")  # a count, then a stream
    assert call.text == "ready" and c.client.api_key == key
    rec = c.run("claude-sonnet-5-5", ["day 3: the oven code is 1003"] * 3,
                [Checkpoint("w1", 3, [{"qid": "a", "text": "Oven code?"}])], progress=lambda s: None)
    assert rec["checkpoints"][0]["answers"][0]["answer"] == "1003"
    with pytest.raises(ClaudeError) as e:
        c.call("claude-sonnet-5-5", ASK, max_tokens=100, purpose="unit", prompt_tokens=10)
    assert e.value.status == "http_401_authentication_error"
    assert key not in str(e.value) and key not in (e.value.detail or "") and key not in repr(c)
    assert key not in (tmp_path / "ledger.jsonl").read_text() and key not in open(rec["path"]).read()
    assert len(server.requests) >= 4
    for r in server.requests:  # the key goes out in the auth header and nowhere else
        auth = {k: v for k, v in r.headers.items() if k in ("authorization", "x-api-key")}
        assert any(key in v for v in auth.values())
        assert all(key not in v for k, v in r.headers.items() if k not in auth)
        assert key.encode() not in r.content


# --- one call -------------------------------------------------------------------------------------------------


def test_stream_measures_the_first_token_and_logs_the_call(tmp_path):
    c, fake, _ = make(tmp_path, [reply("ready", input=12, output=40, thinking=30)])
    call = c.call("claude-sonnet-5-5", ASK, max_tokens=100, purpose="unit", prompt_tokens=12)
    assert call.text == "ready" and call.answered_by == "claude-sonnet-5-5" and not call.refused
    assert call.first_token_s == pytest.approx(1.0)  # the thinking block started
    assert call.ttft_s == pytest.approx(2.0)  # the first word of the answer
    assert call.total_s == pytest.approx(4.0)
    assert call.output_tps == pytest.approx(round(40 / 3.0, 1))
    assert call.tokens.thinking == 30 and call.tokens.output == 40  # thinking is part of the output
    sent = fake.messages.calls[0]
    assert sent["model"] == "claude-sonnet-5-5"
    assert sent["output_config"] == {"effort": "medium"} and sent["thinking"] == {"type": "adaptive"}
    assert not {"fallbacks", "betas", "extra_body", "extra_headers", "temperature"} & set(sent)
    hold, line = lines(c)
    assert hold["kind"] == "hold" and line["kind"] == "call" and line["hold"] == hold["hold"]
    for key in ("model", "purpose", "input_tokens", "output_tokens", "thinking_tokens", "cache_read_input_tokens",
                "cache_creation_input_tokens", "cost_usd", "ttft_s", "total_s", "effort", "answered_by"):
        assert key in line
    assert line["purpose"] == "unit" and line["status"] == "ok" and line["effort"] == "medium"
    assert line["cost_usd"] == pytest.approx(cost_usd("claude-sonnet-5-5", {"input_tokens": 12, "output_tokens": 40}))
    assert c.spent() == pytest.approx(line["cost_usd"])  # the hold is closed by its call


def test_effort_stays_medium_and_models_are_exact(tmp_path):
    c, fake, _ = make(tmp_path, [reply("ok", model="claude-opus-5-5")])
    c.call("claude-opus-5-5", ASK, max_tokens=50, purpose="unit", output_config={"effort": "high"}, prompt_tokens=5)
    assert fake.messages.calls[0]["output_config"]["effort"] == "medium"
    for wrong in ("claude-opus-5", "claude-haiku-4-5", "opus"):
        with pytest.raises(ValueError):
            c.call(wrong, ASK, max_tokens=50, purpose="unit", prompt_tokens=5)
    assert len(fake.messages.calls) == 1


def test_prompt_is_counted_with_the_free_endpoint_when_not_given(tmp_path):
    c, fake, _ = make(tmp_path, [reply("ok")], counter=lambda kw: 321)
    c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit")
    assert len(fake.messages.counts) == 1 and fake.messages.counts[0]["model"] == "claude-sonnet-5-5"
    count = [x for x in lines(c) if x["kind"] == "count"][0]
    assert count["input_tokens"] == 321 and count["cost_usd"] == 0.0


def test_a_refusal_is_recorded_as_such(tmp_path):
    c, fake, _ = make(tmp_path, [reply("", stop_reason="refusal", category="cyber")])
    call = c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5)
    assert call.refused and call.refusal_category == "cyber" and call.ttft_s is None
    assert lines(c)[-1]["status"] == "refusal" and lines(c)[-1]["refusal_category"] == "cyber"


def test_the_model_that_answered_is_recorded(tmp_path):
    c, _, _ = make(tmp_path, [reply("ok", answered_by="claude-opus-5")])
    call = c.call("claude-opus-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5)
    assert call.model_mismatch and call.answered_by == "claude-opus-5"
    assert lines(c)[-1]["model_mismatch"] is True


# --- the budget -----------------------------------------------------------------------------------------------


def test_budget_refuses_a_call_before_it_is_sent(tmp_path):
    c, fake, _ = make(tmp_path, [reply("ok", model="claude-haiku-5-5")])
    c.ledger.write({"kind": "call", "model": "claude-opus-5-5", "purpose": "earlier", "cost_usd": 57.95})
    # worst case: 1,000 prompt tokens as a cache write ($5/M) + 10,000 output tokens ($20/M) = $0.205 -> past $58
    with pytest.raises(BudgetError):
        c.call("claude-opus-5-5", ASK, max_tokens=10_000, purpose="too dear", prompt_tokens=1000)
    assert fake.messages.calls == []
    assert lines(c)[-1]["kind"] == "refused" and lines(c)[-1]["purpose"] == "too dear"
    c.call("claude-haiku-5-5", ASK, max_tokens=20, purpose="cheap", prompt_tokens=100)  # still fits under $58
    assert len(fake.messages.calls) == 1


def test_open_holds_count_until_their_call_closes_them(tmp_path):
    ledger = Ledger(tmp_path / "l.jsonl")
    hold = ledger.hold("claude-opus-5-5", "x", 1.5)
    assert ledger.spent() == pytest.approx(1.5)
    ledger.write({"kind": "call", "hold": hold, "cost_usd": 0.25})
    assert ledger.spent() == pytest.approx(0.25)
    other = Ledger(tmp_path / "l.jsonl", cap_usd=2.5, headroom_usd=2.0)  # $0.50 left under the cap
    with pytest.raises(BudgetError):
        other.hold("claude-opus-5-5", "y", 0.3)


def test_a_run_stops_at_the_budget(tmp_path):
    c, fake, _ = make(tmp_path, [], window=50_000, margin=100)
    c.ledger.write({"kind": "call", "cost_usd": 58.0})
    rec = c.run("claude-opus-5-5", ["a fact"] * 5, [Checkpoint("w1", 5, [{"qid": "q", "text": "?"}])],
                progress=lambda s: None)
    assert rec["stopped"].startswith("budget") and rec["checkpoints"] == [] and fake.messages.calls == []


# --- errors ---------------------------------------------------------------------------------------------------


def test_rate_limit_waits_for_retry_after_then_succeeds(tmp_path):
    c, _, sleeps = make(tmp_path, [status_error(anthropic.RateLimitError, 429, "rate_limit_error", "3"), reply("ok")])
    call = c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5)
    assert call.text == "ok" and call.attempts == 2 and sleeps == [3.0]
    calls = [x for x in lines(c) if x["kind"] == "call"]
    assert [x["status"] for x in calls] == ["rate_limited", "ok"] and [x["attempts"] for x in calls] == [1, 2]
    assert c.spent() == pytest.approx(call.cost_usd)  # a refused-at-the-door 429 costs nothing


def test_rate_limit_gives_up_after_patience(tmp_path):
    rl = status_error(anthropic.RateLimitError, 429, "rate_limit_error", "3")
    c, _, sleeps = make(tmp_path, [rl, rl], patience=1)
    with pytest.raises(ClaudeError) as e:
        c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5)
    assert e.value.status == "rate_limited" and sleeps == [3.0]


def test_a_bad_request_is_not_retried(tmp_path):
    c, _, sleeps = make(tmp_path, [status_error(anthropic.BadRequestError, 400, "invalid_request_error")])
    with pytest.raises(ClaudeError) as e:
        c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5)
    assert e.value.status == "http_400_invalid_request_error" and not e.value.retryable and sleeps == []
    assert [x["status"] for x in lines(c) if x["kind"] == "call"] == ["http_400_invalid_request_error"]


def test_a_broken_stream_is_logged_with_what_it_used_and_retried(tmp_path):
    overload = status_error(anthropic.APIStatusError, 200, "overloaded_error")  # sent inside a 200 stream
    c, _, sleeps = make(tmp_path, [reply("", input=5000, break_after=overload), reply("ok")])
    call = c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5000)
    broken, ok = [x for x in lines(c) if x["kind"] == "call"]
    assert broken["status"] == "http_200_overloaded_error" and broken["input_tokens"] == 5000
    assert broken["cost_usd"] > 0 and ok["status"] == "ok" and call.attempts == 2 and len(sleeps) == 1
    assert c.spent() == pytest.approx(broken["cost_usd"] + ok["cost_usd"])


def test_a_connection_dropped_mid_stream_is_logged_with_what_it_used_and_retried(tmp_path):
    dropped = httpx2.RemoteProtocolError("peer closed connection")  # the SDK passes this on raw, unwrapped
    c, _, sleeps = make(tmp_path, [reply("", input=5000, break_after=dropped), reply("ok")])
    call = c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5000)
    broken, ok = [x for x in lines(c) if x["kind"] == "call"]
    assert broken["status"] == "connection_RemoteProtocolError" and broken["input_tokens"] == 5000
    assert broken["cost_usd"] > 0 and broken["hold"] != ok["hold"] and ok["status"] == "ok"
    assert call.text == "ok" and call.attempts == 2 and len(sleeps) == 1
    assert c.spent() == pytest.approx(broken["cost_usd"] + ok["cost_usd"])  # both holds are closed


def test_a_run_goes_on_after_a_dropped_connection(tmp_path):
    dropped = httpx2.ReadTimeout("read timed out")
    script = [reply("", break_after=dropped), reply(answers_json(q="1")), reply(answers_json(q="2"))]
    c, fake, _ = make(tmp_path, script, window=50_000, margin=100)
    cps = [Checkpoint("w1", 2, [{"qid": "q", "text": "?"}]), Checkpoint("w2", 4, [{"qid": "q", "text": "?"}])]
    rec = c.run("claude-haiku-5-5", ["a note"] * 4, cps, grader=lambda q, a: True, progress=lambda s: None)
    assert [r["summary"]["right"] for r in rec["checkpoints"]] == [1, 1] and "stopped" not in rec
    assert rec["checkpoints"][0]["request"]["attempts"] == 2 and len(fake.messages.calls) == 3
    assert [x["status"] for x in lines(c) if x["kind"] == "call"] == ["connection_ReadTimeout", "ok", "ok"]


def test_the_real_sdk_retries_a_stream_whose_connection_drops_mid_reply(tmp_path):
    c, server, sleeps = real(tmp_path, [Dropped(sse_reply("", input=5000)[:1]), sse_reply("ok")])
    call = c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5000)
    assert call.text == "ok" and call.attempts == 2 and len(sleeps) == 1 and len(server.streams) == 2
    broken, ok = [x for x in lines(c) if x["kind"] == "call"]
    assert broken["status"] == "connection_RemoteProtocolError" and broken["input_tokens"] == 5000
    assert ok["status"] == "ok" and broken["request_id"] == "req_mock"


def test_a_rate_limit_wait_is_never_counted_as_time_to_the_first_word(tmp_path):
    limited = api_error(429, "rate_limit_error", "input tokens per minute exceeded", retry_after="2")
    c, server, sleeps = real(tmp_path, [limited, sse_reply("ok")])
    call = c.call("claude-sonnet-5-5", ASK, max_tokens=50, purpose="unit", prompt_tokens=5)
    assert sleeps == [2.0]  # our wait, logged, and outside the timed try
    assert call.ttft_s is not None and call.ttft_s < 1.0 and call.total_s < 1.0 and call.attempts == 2
    assert [x["status"] for x in lines(c) if x["kind"] == "call"] == ["rate_limited", "ok"]
    assert len(server.streams) == 2  # one HTTP try per attempt: the SDK did not retry on its own
    assert [r.headers["x-stainless-retry-count"] for r in server.streams] == ["0", "0"]
    assert "input tokens per minute" in lines(c)[1]["detail"]


@pytest.mark.parametrize("err,retry", [
    (status_error(anthropic.InternalServerError, 529, "overloaded_error"), True),
    (status_error(anthropic.APIStatusError, 408, "timeout_error"), True),
    (status_error(anthropic.ConflictError, 409, "conflict_error"), True),
    (status_error(anthropic.InternalServerError, 500, "api_error", headers={"x-should-retry": "false"}), False),
    (status_error(anthropic.BadRequestError, 400, "invalid_request_error", headers={"x-should-retry": "true"}), True),
    (status_error(anthropic.BadRequestError, 400, "invalid_request_error"), False),
    (status_error(anthropic.NotFoundError, 404, "not_found_error"), False),
])
def test_the_retry_rule_is_the_sdks(err, retry):
    assert cl._retryable(err) is retry


# --- a checkpoint ---------------------------------------------------------------------------------------------


def answers_json(**answers):
    return json.dumps({"answers": [{"id": k, "answer": v} for k, v in answers.items()]})


def grade_exact(q, answer):
    expected = q["expected"] if isinstance(q, dict) else q.expected
    return "right" if answer == expected else "wrong"


def test_a_checkpoint_is_one_json_request_graded_per_answer(tmp_path):
    history = [f"day {i}: the oven code is {1000 + i}" for i in range(30)]
    qs = [{"qid": "a", "text": "Oven code on day 3?", "expected": "1003"},
          NS(qid="b", text="Oven code on day 4?", expected="1004"),
          {"id": "c", "question": "Who is Wanjiru?"}]
    c, fake, _ = make(tmp_path, [reply(answers_json(a="1003", b="1009"), input=900, output=60)], window=50_000,
                      margin=100)
    graded = []
    rec = c.ask("claude-sonnet-5-5", history, 30, qs, grader=lambda q, a: graded.append(a) or grade_exact(q, a),
                name="week 1")
    assert len(fake.messages.calls) == 1 and graded == ["1003", "1009"]
    sent = fake.messages.calls[0]
    assert sent["output_config"]["effort"] == "medium" and sent["output_config"]["format"]["type"] == "json_schema"
    last = sent["messages"][0]["content"][-1]["text"]
    assert "Oven code on day 3?" in last and '"id": "c"' in last
    a, b, cc = rec["answers"]
    assert (a["right"], a["verdict"]) == (True, "right") and (b["right"], b["verdict"]) == (False, "wrong")
    assert (cc["right"], cc["verdict"], cc["answer"]) == (False, "no_answer", None)
    for x in rec["answers"]:
        assert x["ttft_s"] == pytest.approx(2.0) and x["total_s"] == pytest.approx(4.0) and x["batch"] == 3
        assert x["cost_usd"] == pytest.approx(rec["request"]["cost_usd"] / 3, abs=1e-6)
        assert x["output_tps"] is not None and x["input_tokens"] == pytest.approx(300)
    assert rec["summary"]["right"] == 1 and rec["summary"]["no_answer"] == 1
    assert rec["context_tokens"] > 0 and not rec["cut_from_front"] and rec["history_pieces_used"] == 30


def test_a_refused_checkpoint_is_not_graded(tmp_path):
    c, _, _ = make(tmp_path, [reply("", stop_reason="refusal", category="general_harms")], window=50_000, margin=100)
    rec = c.ask("claude-haiku-5-5", ["x"] * 3, 3, [{"qid": "a", "text": "?"}, {"qid": "b", "text": "?"}],
                grader=lambda q, a: pytest.fail("a refusal must not be graded"))
    assert [x["verdict"] for x in rec["answers"]] == ["refused", "refused"]
    assert all(x["right"] is False and x["refused"] for x in rec["answers"])
    assert rec["summary"]["refused"] == 2 and rec["request"]["refusal_category"] == "general_harms"


def test_a_long_history_keeps_its_most_recent_part(tmp_path):
    history = [f"{i:04d} " + "x" * 95 for i in range(400)]  # ~25 tokens each, ~10,000 in all
    c, fake, _ = make(tmp_path, [reply(answers_json(q="0399"))], window=3000, margin=100)
    rec = c.ask("claude-sonnet-5-5", history, 400, [{"qid": "q", "text": "The last number?"}], max_tokens=500)
    target = 3000 - 500 - 100
    assert rec["cut_from_front"] and rec["history_start"] > 0
    assert 0.9 * target <= rec["context_tokens"] <= target
    body = "".join(b["text"] for b in fake.messages.calls[0]["messages"][0]["content"])
    assert history[-1] in body and history[0] not in body and history[rec["history_start"] - 1] not in body
    assert history[rec["history_start"]] in body
    assert len(fake.messages.counts) <= cl.FIT_TRIES


def test_later_checkpoints_repeat_earlier_history_blocks_for_the_cache(tmp_path):
    history = [f"note {i}: " + "y" * 40 for i in range(30)]
    cps = [Checkpoint(f"w{k}", 10 * k, [{"qid": "q", "text": "?"}]) for k in (1, 2, 3)]
    script = [reply(answers_json(q="1")), reply(answers_json(q="2"), cache_read=200),
              reply(answers_json(q="3"), cache_read=400)]
    c, fake, _ = make(tmp_path, script, window=50_000, margin=100)
    said = []
    rec = c.run("claude-haiku-5-5", history, cps, grader=lambda q, a: True, progress=said.append)
    blocks = [call["messages"][0]["content"] for call in fake.messages.calls]
    assert [len(b) for b in blocks] == [3, 4, 5]  # opener, one block per checkpoint so far, the questions
    assert all(b[0]["text"] == OPENER for b in blocks)
    assert blocks[1][1]["text"] == blocks[0][1]["text"] and blocks[2][2]["text"] == blocks[1][2]["text"]
    marked = [[i for i, x in enumerate(b) if "cache_control" in x] for b in blocks]
    # the newest history block, and the one the last request ended on; the last checkpoint only reads
    assert marked == [[1], [1, 2], [2]]
    assert all("cache_control" not in b[-1] for b in blocks)  # the questions are never cached
    assert [x["cached"] for x in rec["checkpoints"]] == [True, True, False]
    assert len(rec["checkpoints"]) == 3 and len(said) == 3 and "stopped" not in rec
    assert rec["cost_usd"] == pytest.approx(sum(x["request"]["cost_usd"] for x in rec["checkpoints"]))
    saved = json.loads(open(rec["path"]).read())
    assert saved["model"] == "claude-haiku-5-5" and saved["effort"] == "medium" and saved["fallbacks"] is None


def test_parse_answers_survives_fences_and_truncation():
    assert parse_answers('```json\n{"answers": [{"id": "a", "answer": "x"}]}\n```') == {"a": "x"}
    cut = '{"answers": [{"id": "a", "answer": "x"}, {"id": "b", "answer": "say \\"hi\\""}, {"id": "c", "ans'
    assert parse_answers(cut) == {"a": "x", "b": 'say "hi"'}
    assert parse_answers("no json here") == {}


def test_smoke_is_one_small_haiku_call(tmp_path):
    c, fake, _ = make(tmp_path, [reply("ready", model="claude-haiku-5-5", output=3)])
    call = smoke(c)
    assert call.text == "ready" and fake.messages.counts == [] and len(fake.messages.calls) == 1
    sent = fake.messages.calls[0]
    assert sent["model"] == "claude-haiku-5-5" and sent["max_tokens"] == 20
    assert lines(c)[-1]["purpose"] == "smoke" and lines(c)[-1]["kind"] == "call"


@pytest.mark.parametrize("cls,code,kind,message", [
    (anthropic.BadRequestError, 400, "invalid_request_error", "prompt is too long: 7000 tokens > 6000 maximum"),
    (anthropic.RequestTooLargeError, 413, "request_too_large", "Request exceeds the maximum allowed size"),
])
def test_a_count_refused_as_too_long_moves_the_cut_later(tmp_path, monkeypatch, cls, code, kind, message):
    history = [f"{i:04d} " + "x" * 95 for i in range(400)]

    def counter(kw):
        n = chars_over_four(kw)
        if n > 6000:
            raise status_error(cls, code, kind, message=message)
        return n

    monkeypatch.setattr(cl, "CHARS_PER_TOKEN", 40.0)  # a first guess far too long
    c, fake, _ = make(tmp_path, [reply(answers_json(q="0399"))], counter=counter, window=3000, margin=100)
    rec = c.ask("claude-sonnet-5-5", history, 400, [{"qid": "q", "text": "?"}], max_tokens=500)
    assert rec["cut_from_front"] and rec["context_tokens"] <= 2400 and "error" not in rec
    first = [x for x in lines(c) if x["kind"] == "count"][0]
    assert first["status"] == f"http_{code}_{kind}" and first["detail"] == message


def test_any_other_refused_count_is_an_error_record_at_once(tmp_path):
    def counter(kw):
        raise status_error(anthropic.BadRequestError, 400, "invalid_request_error",
                           message="output_config.format.schema: unsupported keyword 'patternProperties'")

    c, fake, _ = make(tmp_path, [], counter=counter, window=50_000, margin=100)
    rec = c.run("claude-sonnet-5-5", ["x"] * 3, [Checkpoint("w1", 3, [{"qid": "q", "text": "?"}])],
                progress=lambda s: None)  # the run is not crashed by it
    r = rec["checkpoints"][0]
    assert r["error"] == "http_400_invalid_request_error" and "patternProperties" in r["error_detail"]
    assert len(fake.messages.counts) == 1 and fake.messages.calls == []  # not retried, not taken as too long
    assert r["answers"][0]["verdict"] == "error" and r["summary"]["errors"] == 1


def test_a_failed_call_keeps_what_the_fit_measured(tmp_path):
    bad = status_error(anthropic.BadRequestError, 400, "invalid_request_error", message="max_tokens: too large")
    c, fake, _ = make(tmp_path, [bad], window=50_000, margin=100)
    rec = c.ask("claude-sonnet-5-5", ["x"] * 3, 3, [{"qid": "q", "text": "?"}])
    assert rec["error"] == "http_400_invalid_request_error" and rec["error_detail"] == "max_tokens: too large"
    assert rec["context_tokens"] > 0 and rec["history_pieces_used"] == 3 and len(fake.messages.calls) == 1


def test_no_room_for_any_history_is_an_error_record(tmp_path):
    c, fake, _ = make(tmp_path, [], window=600, margin=100)
    rec = c.ask("claude-sonnet-5-5", ["x" * 400] * 3, 3, [{"qid": "q", "text": "?"}], max_tokens=500)
    assert rec["error"] == "no_room" and fake.messages.calls == []


def test_a_reply_cut_off_at_max_tokens_is_not_wrong_and_the_rest_is_asked_again(tmp_path):
    history = [f"day {i}: the oven code is {1000 + i}" for i in range(10)]
    qs = [{"qid": "a", "text": "Day 1?", "expected": "1001"}, {"qid": "b", "text": "Day 2?", "expected": "1002"},
          {"qid": "c", "text": "Day 3?", "expected": "1003"}]
    cut_off = '{"answers": [{"id": "a", "answer": "1001"}, {"id": "b", "ans'
    script = [reply(cut_off, stop_reason="max_tokens", output=500), reply(answers_json(b="1002", c="1009"))]
    c, fake, _ = make(tmp_path, script, window=50_000, margin=100)
    rec = c.run("claude-opus-5-5", history, [Checkpoint("w1", 10, qs)], grader=grade_exact,
                progress=lambda s: None)
    r = rec["checkpoints"][0]
    first, again = fake.messages.calls
    assert again["max_tokens"] == 2 * first["max_tokens"]
    asked = again["messages"][0]["content"][-1]["text"]
    assert '"id": "b"' in asked and '"id": "c"' in asked and '"id": "a"' not in asked
    a, b, cc = r["answers"]
    assert (a["right"], a.get("reasked")) == (True, None)
    assert (b["right"], b["reasked"]) == (True, True) and (cc["right"], cc["verdict"]) == (False, "wrong")
    s = r["summary"]
    assert (s["graded"], s["right"], s["truncated"], s["reasked"]) == (3, 2, 0, 2)
    paid = r["request"]["cost_usd"] + r["reask"]["request"]["cost_usd"]
    assert rec["cost_usd"] == pytest.approx(paid) and s["cost_usd"] == pytest.approx(paid, abs=1e-5)
    assert b["cost_usd"] == pytest.approx(r["request"]["cost_usd"] / 3 + r["reask"]["request"]["cost_usd"] / 2,
                                          abs=1e-5)


def test_without_a_reask_cut_off_answers_stay_truncated_and_ungraded(tmp_path):
    cut_off = '{"answers": [{"id": "a", "answer": "x"}, {"id": "b"'
    c, fake, _ = make(tmp_path, [reply(cut_off, stop_reason="max_tokens")], window=50_000, margin=100)
    rec = c.ask("claude-sonnet-5-5", ["x"], 1, [{"qid": "a", "text": "?"}, {"qid": "b", "text": "?"}],
                grader=lambda q, a: True, reask=False)
    assert [(x["verdict"], x["right"]) for x in rec["answers"]] == [("right", True), ("truncated", None)]
    s = rec["summary"]
    assert (s["graded"], s["truncated"], s["no_answer"]) == (1, 1, 0) and len(fake.messages.calls) == 1


def test_a_reask_past_the_budget_keeps_the_paid_reply(tmp_path):
    cut_off = '{"answers": [{"id": "a", "answer": "x"}, {"id": "b"'
    c, fake, _ = make(tmp_path, [reply(cut_off, model="claude-opus-5-5", stop_reason="max_tokens", output=500)],
                      window=50_000, margin=100)
    c.ledger.write({"kind": "call", "cost_usd": 57.975})  # room for a 500-token reply, not for a 1,000-token one
    rec = c.ask("claude-opus-5-5", ["x"], 1, [{"qid": "a", "text": "?"}, {"qid": "b", "text": "?"}],
                grader=lambda q, a: True, max_tokens=500)
    assert rec["reask"]["error"].startswith("budget") and len(fake.messages.calls) == 1
    assert [x["verdict"] for x in rec["answers"]] == ["right", "truncated"] and rec["request"]["cost_usd"] > 0


def test_no_cache_is_written_when_no_later_request_can_read_it(tmp_path):
    history = [f"{i:04d} " + "x" * 395 for i in range(400)]  # ~100 tokens each, ~40,000 in all
    cps = [Checkpoint("w1", 10, [{"qid": "q", "text": "?"}]), Checkpoint("w2", 200, [{"qid": "q", "text": "?"}]),
           Checkpoint("w3", 400, [{"qid": "q", "text": "?"}])]
    script = [reply(answers_json(q="1")), reply(answers_json(q="2")), reply(answers_json(q="3"))]
    c, fake, _ = make(tmp_path, script, window=20_000, margin=100)  # ~11,450 tokens left for history
    rec = c.run("claude-sonnet-5-5", history, cps, progress=lambda s: None)
    # w1 fits whole but w2 will not; w2 is cut from the front; w3 is the last
    assert [r["cut_from_front"] for r in rec["checkpoints"]] == [False, True, True]
    assert [r["cached"] for r in rec["checkpoints"]] == [False, False, False]
    for call in fake.messages.calls:
        assert all("cache_control" not in b for b in call["messages"][0]["content"])
    for r in rec["checkpoints"]:  # held at the plain input price, not a cache write
        assert r["request"]["estimate_usd"] == pytest.approx(
            estimate_usd("claude-sonnet-5-5", r["context_tokens"], r["max_tokens"], None), abs=1e-6)


def test_a_read_point_is_held_at_the_cache_write_price(tmp_path):
    cps = [Checkpoint("w1", 2, [{"qid": "q", "text": "?"}]), Checkpoint("w2", 4, [{"qid": "q", "text": "?"}])]
    c, fake, _ = make(tmp_path, [reply(answers_json(q="1")), reply(answers_json(q="2"))], window=50_000, margin=100)
    rec = c.run("claude-sonnet-5-5", ["a note"] * 4, cps, progress=lambda s: None)
    last = fake.messages.calls[1]["messages"][0]["content"]
    assert [i for i, b in enumerate(last) if "cache_control" in b] == [1]  # reads w1's block, writes nothing new
    r = rec["checkpoints"][1]  # an expired read point is written again, so the hold allows for it
    assert r["request"]["estimate_usd"] == pytest.approx(
        estimate_usd("claude-sonnet-5-5", r["context_tokens"], r["max_tokens"], "5m"), abs=1e-6)


def test_a_failing_grader_does_not_lose_the_paid_reply(tmp_path):
    c, _, _ = make(tmp_path, [reply(answers_json(a="x", b="y"))], window=50_000, margin=100)

    def grader(q, a):
        if q["qid"] == "b":
            raise KeyError("no rule")
        return True

    rec = c.ask("claude-sonnet-5-5", ["x"], 1, [{"qid": "a", "text": "?"}, {"qid": "b", "text": "?"}], grader=grader)
    assert [(x["right"], x["verdict"], x["answer"]) for x in rec["answers"]] == [(True, "right", "x"),
                                                                                  (None, "grader_error", "y")]
