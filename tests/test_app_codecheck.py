"""Code answers in CAMR Personal: syntax checked on this computer (never run), one retry on an error, and the user's
fix kept as a correction that the next similar request reads."""

from __future__ import annotations

import shutil

import pytest

from camr.app import codecheck
from camr.app.assistant import Assistant
from camr.memory.embedder import HashingEmbedder
from test_app_code import FakeOllama, _Resp

BROKEN = "```python\ndef total(xs)\n    return sum(xs)\n```"
FIXED = "```python\ndef total(xs):\n    return sum(xs)\n```"


class SloppyCoder(FakeOllama):
    """Writes code with a missing colon, and fixes it when told the error."""

    def post(self, url, json=None, stream=False, timeout=None):
        prompt = json.get("prompt", "")
        if "coding assistant" not in prompt:
            return super().post(url, json, stream, timeout)
        self.bodies.append(json)
        text = FIXED if "Your code has a syntax error" in prompt else BROKEN
        lines = [__import__("json").dumps({"response": text, "done": False}).encode(),
                 __import__("json").dumps({"response": "", "done": True, "prompt_eval_count": 10}).encode()]
        return _Resp(lines=lines)


@pytest.fixture
def assistant(tmp_path):
    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=SloppyCoder(),
                  min_similarity=0.3)
    a.save_settings(check_model="", trust_learning=False)
    yield a
    a.close()


def test_python_is_parsed_not_run():
    assert codecheck.check("python", "import os\nos.remove('x')\n")["ok"]  # parsed only: nothing is removed
    bad = codecheck.check("python", "def f(:\n    pass\n")
    assert not bad["ok"] and bad["line"] == 1
    assert codecheck.check("", "ls -la\n") is None  # an unlabelled shell command is not checked
    assert codecheck.check("rust", "fn main() {}") is None


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_javascript_is_checked_with_node_without_running_it(tmp_path):
    assert codecheck.check("js", "require('fs').writeFileSync('x', '1')\n")["ok"]
    bad = codecheck.check("javascript", "function f( {\n  return 1\n}\n")
    assert not bad["ok"] and bad["language"] == "JavaScript"


def test_a_syntax_error_gets_one_retry_with_the_error(assistant):
    events = list(assistant.events("write a python function total(xs) that sums a list"))
    assert any(e["type"] == "fixing" for e in events)
    t = events[-1]["turn"]
    assert t["answer"] == FIXED and t["check"]["ok"] and t["check"]["retried"]
    assert "Your code has a syntax error: expected ':'" in assistant._http.bodies[-1]["prompt"]


def test_a_fix_is_kept_and_read_by_the_next_similar_request(assistant):
    t = assistant.ask("write a python function total(xs) that sums a list")
    fixed = "def total(xs):\n    return sum(x for x in xs if x is not None)"
    out = assistant.save_fix(t.turn_id, fixed)
    assert out["expert"] == "code" and out["check"]["ok"] and out["notes"] == 1
    again = assistant.save_fix(t.turn_id, fixed + "  # v2")  # a second fix replaces the first
    rows = assistant.store.conn.execute("SELECT s.title, s.dataset, s.expert FROM source s WHERE s.doc_id=?",
                                        (f"fix-{t.turn_id}",)).fetchall()
    assert again["notes"] == 1 and [tuple(r) for r in rows] == [("Correction: code", "fix", "code")]
    assistant.ask("write a python function total(xs) that sums a list, skipping missing values")
    assert "x is not None" in assistant._http.bodies[-1]["prompt"]  # the fix is in front of the model
    with pytest.raises(KeyError):
        assistant.save_fix(999, "x = 1")
