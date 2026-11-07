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
