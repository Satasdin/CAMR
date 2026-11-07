"""Claude as the agent's model, for the side-by-side (docs/real-use/TASKS.md, T7): the same lead, the same parts, the
same prompts, tools, page tests and told facts as the local model gets; only the model that writes is different.

The tools are offered the way the local model's chat template offers them (a <tools> block in the instructions, calls
written as <tool_call> JSON), so both read the very same words and both are parsed by the same parser. Claude has no
CAMR memory here (``memory_on`` is False): what the person told reaches it as the told notes in each prompt, as it
does for the local model. Every call goes through the yardstick's client (camr_engine.bench.claude), so it is
metered in the same ledger and refused past the same cap. The key is read there and never printed.
"""

from __future__ import annotations

import json
import time

from camr_engine.agentic.brain import Prompt, Thought

TOOLS_HEAD = ("# Tools\n\nYou may call one or more functions to assist with the user query.\n\nYou are provided with "
              "function signatures within <tools></tools> XML tags:\n<tools>\n")
TOOLS_TAIL = ("\n</tools>\n\nFor each function call, return a json object with function name and arguments within "
              "<tool_call></tool_call> XML tags:\n<tool_call>\n{\"name\": <function-name>, \"arguments\": "
              "<args-json-object>}\n</tool_call>")
THINKING_ROOM = 8000  # adaptive thinking is written inside max_tokens: room for it on top of the local model's limit


def system_with_tools(system: str, tools: list[dict]) -> str:
    if not tools:
        return system
    return f"{system}\n\n{TOOLS_HEAD}" + "\n".join(json.dumps(t, ensure_ascii=False) for t in tools) + TOOLS_TAIL


class ClaudeBrain:
    memory_on = False

    def __init__(self, model: str = "claude-sonnet-5-5", runner=None, purpose: str = "t7-agent"):
        from camr_engine.bench.claude import Claude, check_model

        check_model(model)
        self.model, self.label, self.purpose = model, model, purpose
        self.runner = runner or Claude()
        self.calls: list[dict] = []

    def think(self, p: Prompt) -> Thought:
        t = time.perf_counter()
        call = self.runner.call(self.model, [{"role": "user", "content": p.user}],
                                max_tokens=p.max_tokens + THINKING_ROOM, purpose=self.purpose,
                                system=system_with_tools(p.system, p.tools), cache=False)
        self.calls.append(call.as_dict())
        text = call.text or ""
        return Thought(text, [text], call.ttft_s or 0.0, time.perf_counter() - t, call.tokens.input,
                       call.tokens.output, call.output_tps)

    def keep(self, text: str, to: str | None = None, source: str = "model") -> dict | None:
        return None

    def moment(self, reach: str, mid: int) -> dict | None:
        return None

    def reaches(self) -> list[dict]:
        return []

    def close(self) -> None:
        pass
