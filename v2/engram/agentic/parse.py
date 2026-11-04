"""Every tool call in one reply, for a loop of several steps. ``engram.agent.parse`` reads one call (Qwen3's JSON
inside ``<tool_call>``, or the ``<function=name><parameter=key>`` form of Qwen 3.5 and later); here each block of a
reply goes through it in turn, so a reply may call several tools, and the words outside the calls are kept as the
model's answer.

A bare JSON object outside any block counts as a call only when it names a tool the agent has, so an answer that
shows JSON is not run by mistake.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from engram.agent import parse

MAX_CALLS = 4  # calls taken from one reply

_THINK = re.compile(r"<think>.*?(?:</think>|$)", re.S)
_BLOCK = re.compile(r"<tool_call>(.*?)(?:</tool_call>|$)", re.S)
_FUNCTION = re.compile(r"<function=[\w.-]+>.*?(?:</function>|(?=<function=)|$)", re.S)


@dataclass
class Call:
    name: str
    args: dict = field(default_factory=dict)
    start: int = 0  # where the call sits in the reply's text
    end: int = 0
    form: str = "json"  # "json" or "xml": how its arguments were written (the gutter reads them back)


def _blank(text: str, rx: re.Pattern) -> str:
    """The text with each match replaced by spaces, so positions stay where they were."""
    return rx.sub(lambda m: " " * len(m.group(0)), text)


def calls(text: str, known: set[str] | None = None, limit: int = MAX_CALLS) -> list[Call]:
    """The tool calls in a reply, in order. ``known`` is the tools the agent has: a bare JSON object is a call only
    when it names one of them, and with ``known`` given, calls of other tools are kept (the loop answers them with
    an error) but bare objects naming nothing known are not."""
    seen = _blank(text, _THINK)
    out: list[Call] = []
    blocks = list(_BLOCK.finditer(seen))
    if blocks:
        for b in blocks:
            inner = b.group(1)
            xml = "<function=" in inner
            name, args = parse(inner if xml else f"<tool_call>{inner}</tool_call>")
            if name is None and not xml and "{" in inner:
                name, args = parse(inner)
            if name:
                out.append(Call(str(name), args, b.start(), b.end(), "xml" if xml else "json"))
    else:
        for f in _FUNCTION.finditer(seen):
            name, args = parse(f.group(0))
            if name:
                out.append(Call(str(name), args, f.start(), f.end(), "xml"))
    if not out and known:
        out = _bare(seen, known)
    return out[:limit]


def _bare(text: str, known: set[str]) -> list[Call]:
    """JSON objects written without a block (sometimes in a code fence) that name a known tool."""
    out, dec, i = [], json.JSONDecoder(), 0
    while True:
        i = text.find("{", i)
        if i < 0:
            return out
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict) and obj.get("name") in known:
            args = obj.get("arguments", obj.get("parameters", {}))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            out.append(Call(obj["name"], args if isinstance(args, dict) else {}, i, end, "json"))
        i = end


def prose(text: str) -> str:
    """The reply's words without its thinking and its tool calls: what the model says to the person."""
    out = _THINK.sub("", text)
    out = _BLOCK.sub("", out)
    out = _FUNCTION.sub("", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()
