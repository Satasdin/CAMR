"""Claude as the agent's model reads the same words as the local one and goes through the metered client."""

from camr_engine.agentic.brain import Prompt
from camr_engine.agentic.claude_brain import ClaudeBrain, system_with_tools
from camr_engine.agentic.parse import calls


class Runner:
    def __init__(self):
        self.got = []

    def call(self, model, messages, *, max_tokens, purpose, system=None, cache=True):
        from camr_engine.bench.claude import Call
        from camr_engine.bench.cost import Tokens

        self.got.append((model, messages, max_tokens, purpose, system))
        text = '<tool_call>\n{"name": "write_file", "arguments": {"path": "index.html", "content": "<h1>x</h1>"}}\n</tool_call>'
        return Call(model, model, text, "end_turn", None, Tokens(input=900, output=40), 0.01, 0.02, 0.5, 0.4, 1.2)


SPEC = [{"type": "function", "function": {"name": "write_file", "parameters": {}}}]


def test_the_tools_are_offered_as_the_local_models_template_offers_them():
    s = system_with_tools("You build.", SPEC)
    assert s.startswith("You build.\n\n# Tools\n\nYou may call one or more functions")
    assert '<tools>\n{"type": "function"' in s and s.endswith("</tool_call>")


def test_a_step_goes_through_the_metered_client_and_parses_the_same_way():
    r = Runner()
    b = ClaudeBrain("claude-sonnet-5-5", runner=r)
    t = b.think(Prompt("You build.", "Task: make it", SPEC, ask="make it", max_tokens=3000))
    model, messages, max_tokens, purpose, system = r.got[0]
    assert (model, purpose, messages) == ("claude-sonnet-5-5", "t7-agent", [{"role": "user", "content": "Task: make it"}])
    assert max_tokens == 3000 + 8000 and "<tools>" in system
    assert [c.name for c in calls(t.text, known={"write_file"})] == ["write_file"]
    assert (t.prompt_tokens, t.gen_tokens) == (900, 40) and not b.memory_on


def test_an_ollama_model_gets_the_same_words_and_its_reasoning_is_kept_apart():
    from camr_engine.agentic.ollama_brain import OllamaBrain

    sent = []

    def post(body):
        sent.append(body)
        return {"message": {"content": '<tool_call>\n{"name": "write_file", "arguments": {"path": "a.html"}}\n</tool_call>'},
                "prompt_eval_count": 700, "eval_count": 30, "eval_duration": 1_000_000_000}

    b = OllamaBrain("qwen3:4b", post=post)
    t = b.think(Prompt("You build.", "Task: x", SPEC, ask="x", max_tokens=3000))
    body = sent[0]
    assert body["model"] == "qwen3:4b" and body["think"] is True and body["options"]["num_predict"] == 3000 + 4096
    assert body["messages"][0]["content"] == system_with_tools("You build.", SPEC)
    assert [c.name for c in calls(t.text, known={"write_file"})] == ["write_file"]
    assert (t.prompt_tokens, t.gen_tokens, t.decode_tps, b.label, b.memory_on) == (700, 30, 30.0, "ollama:qwen3:4b", False)


def test_the_agents_model_is_chosen_and_checked(tmp_path):
    from camr_engine.agentic.desk import Busy, Desk

    d = Desk(tmp_path / "code", brains=lambda spec: None)
    assert d.configure(agent_model="ollama:qwen3:4b")["agent_model"] == "ollama:qwen3:4b"
    assert d.configure(agent_model="claude-sonnet-5-5")["agent_model"] == "claude-sonnet-5-5"
    assert d.configure(agent_model="")["agent_model"] is None
    import pytest

    with pytest.raises(ValueError):
        d.configure(agent_model="rm -rf /")
    assert Desk(tmp_path / "code", brains=None).settings["agent_model"] is None


def test_the_app_picks_the_agents_model(monkeypatch):
    from camr_engine.agentic.claude_brain import ClaudeBrain
    from camr_engine.agentic.ollama_brain import OllamaBrain
    from camr_engine.app.routes.code import agent_brains

    chosen = {"m": None}
    make = agent_brains(lambda spec: "local", lambda: chosen["m"])
    monkeypatch.delenv("CAMR_AGENT_MODEL", raising=False)
    assert make({}) == "local"
    chosen["m"] = "ollama:qwen3:1.7b"
    assert isinstance(make({}), OllamaBrain)
    monkeypatch.setattr("camr_engine.bench.claude.Claude.__init__", lambda self, *a, **k: None)
    monkeypatch.setenv("CAMR_AGENT_MODEL", "claude-sonnet-5-5")
    assert isinstance(make({}), ClaudeBrain)
