"""Coding in CAMR Personal: a coding request gets a coding prompt over the user's own code and conventions, a long
answer, no lookup and no trust link, and is not kept as chat memory; a code file is learned a function per note."""

from __future__ import annotations

import json

import pytest

from camr.app.assistant import CODE_ANSWER_TOKENS, Assistant, is_code_request
from camr.memory.embedder import HashingEmbedder


class _Resp:
    def __init__(self, lines=None, body=None):
        self.lines, self.body, self.status_code = lines or [], body, 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield from self.lines

    def json(self):
        return self.body


class FakeOllama:
    """Answers a coding prompt with a code block, any other prompt with the first note it was given."""

    def __init__(self):
        self.bodies: list[dict] = []

    def get(self, url, timeout=None):
        return _Resp(body={"models": [{"name": "tiny:1b", "size": 1e9, "details": {"parameter_size": "1B"}}]})

    def post(self, url, json=None, stream=False, timeout=None):
        self.bodies.append(json)
        prompt = json.get("prompt", "")
        if not prompt:
            return _Resp(body={"done": True})
        if "coding assistant" in prompt:
            text = "```python\ndef weekday(s):\n    return s\n```\nReturns the weekday."
        elif not json.get("stream"):
            text = "Summary: A Python module.\nQuestion: Which project is this from?"
        else:
            notes = prompt.split("### Notes from memory\n", 1)[-1].split("\n\n###", 1)[0]
            text = notes.splitlines()[0] if notes else "ok"
        if not json.get("stream"):
            return _Resp(body={"response": text, "done": True})
        lines = [__import__("json").dumps({"response": w + " ", "done": False}).encode() for w in text.split(" ")]
        lines.append(__import__("json").dumps({"response": "", "done": True, "prompt_eval_count": 42}).encode())
        return _Resp(lines=lines)


@pytest.fixture
def assistant(tmp_path):
    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.3)
    a.save_settings(check_model="")
    yield a
    a.close()


def test_a_coding_request_is_answered_as_code_and_not_kept_as_memory(assistant):
    assistant.teach("To list users from our internal API, call GET https://api.acme.test/v2/users with the X-Acme-Key "
                    "header.")
    before = assistant.store.count()
    t = assistant.ask("write a python requests call that lists users from our internal API")
    body = assistant._http.bodies[-1]
    assert "coding assistant" in body["prompt"] and "api.acme.test" in body["prompt"]  # memory as code context
    assert body["options"]["num_predict"] == CODE_ANSWER_TOKENS and body["options"]["num_ctx"] >= 8192
    assert t.link is None and not t.saved_to_memory and t.learned is None and assistant.store.count() == before
    assert "```python" in t.answer


def test_a_follow_up_in_a_coding_chat_stays_code_but_a_personal_question_does_not(assistant):
    conv = assistant.new_conversation()
    assistant.ask("write a python function that returns the weekday of an ISO date", conv)
    assistant.ask("now make it handle invalid dates by returning None", conv)
    assert "coding assistant" in assistant._http.bodies[-1]["prompt"]
    assistant.ask("What did my brother study?", conv)
    assert "private personal assistant" in assistant._http.bodies[-1]["prompt"]


def test_a_code_file_is_learned_a_whole_function_per_note(assistant):
    long_body = "\n".join(f"    total = total + item.price * {k}  # step {k}" for k in range(40))
    src = (f"import math\nRATE = 0.16\n\n\ndef invoice_total(items):\n    total = 0\n{long_body}\n    return total\n\n\n"
           "def slugify(text):\n    return '-'.join(text.lower().split())\n")
    out = assistant.learn_upload("billing.py", src.encode())
    assert out["kind"] == "code" and out["notes"] == 4 and out["chips"] == []  # contents, module, two functions
    notes = [r[0] for r in assistant.store.conn.execute(
        "SELECT n.text FROM note n JOIN source s USING(source_id) WHERE s.doc_id LIKE 'file-billing.py%'")]
    whole = next(n for n in notes if "def invoice_total(items)" in n)
    assert "step 39" in whole and "return total" in whole  # one note, though far longer than 120 tokens
    assert any("defines def invoice_total, def slugify" in n for n in notes)
    main = assistant.store.conn.execute("SELECT source_id FROM source WHERE doc_id='file-billing.py'").fetchone()[0]
    assistant.forget(main)
    assert assistant.store.conn.execute("SELECT COUNT(*) FROM source WHERE doc_id LIKE 'file-billing.py%'"
                                        ).fetchone()[0] == 0


@pytest.mark.parametrize("text,code", [
    ("write a python function that returns the weekday name of an ISO date string", True),
    ("fix this code:\n```python\ndef add(a, b)\n    return a + b\n```", True),
    ("How do I reverse a list in Python?", True),
    ("Traceback (most recent call last):\n  File \"x.py\", line 1", True),
    ("can you write a SQL query for the top customers", True),
    ("Using our acme_pay library, write a Python function price_with_vat(cents)", True),
    ("I need to implement a retry loop around our http client", True),
    ("What is my API key?", False),
    ("write a birthday message for my mum", False),
    ("Where did I put my Java coffee mug?", False),
    ("hi", False),
])
def test_what_counts_as_a_coding_request(text, code):
    assert is_code_request(text) is code


def test_the_engine_still_chunks_documents_not_marked_whole():
    from camr.memory.note import Document
    from camr.memory.write_policy import VerbatimWritePolicy
    from camr.models.tokenizer import RegexTokenizer

    wp = VerbatimWritePolicy(RegexTokenizer(), chunk_tokens=20, overlap=4)
    text = " ".join(f"word{k}" for k in range(60))
    assert len(wp.distil(Document("d", "x", text))) > 1 and len(wp.distil(Document("d", "x", text, whole=True))) == 1
    assert json.dumps(Document("d", "x", "t").whole) == "false"
