"""Agentic work execution: an operations agent that uses tools, with and without a memory, on Helio Solar's tasks.

The agent plans in a loop (one action per turn, then the tool's result), with these tools:

  search_memory {"query"}                    the company's knowledge (absent when the agent has no memory)
  calculate     {"expression"}                arithmetic, evaluated exactly
  create_invoice {"customer", "lines", "total"}
  reply         {"message"}                   to the customer
  escalate      {"reason"}                    hand the task to a person

Memory configurations: none (the model's own knowledge), rag (modern RAG: the top five reranked passages, always),
camr (CAMR's recall: the gate returns nothing when nothing stored is relevant, and only the sentences that matter
otherwise). The knowledge is the support desk's: the knowledge base plus the resolutions agents taught.

A task succeeds when every check on the tool calls holds (an invoice total within 50 cents, a reply that contains
the fact, an escalation where nothing can be known). A tool call with a number or a fact that is not the company's
counts as a hallucinated action.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import systems  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "data/agentic/helio.json").read_text())
MAX_STEPS = 8

TASKS = [
    {"id": "A01", "task": "Customer Amina Odhiambo orders 12 HS-400 panels with installation. Create her invoice "
     "(panels and the installation fee).", "checks": [("invoice_total", 5640)]},
    {"id": "A02", "task": "Customer Brian Kipchoge orders 8 HS-520 panels with installation. Create his invoice "
     "(panels and the installation fee).", "checks": [("invoice_total", 5340)]},
    {"id": "A03", "task": "Customer Wanjiru Mwangi orders 2 Lumen LB-13 batteries with rush shipping. Create the "
     "invoice including the rush shipping surcharge.", "checks": [("invoice_total", 19046)]},
    {"id": "A04", "task": "Customer Otieno Ouma orders 1 Lumen LB-13 battery with rush shipping. Create the invoice "
     "including the rush shipping surcharge.", "checks": [("invoice_total", 9523)]},
    {"id": "A05", "task": "A customer writes: 'My Volta-2 shows error E34.' Reply with the fix.",
     "checks": [("reply_contains", ["CAN cable"])]},
    {"id": "A06", "task": "A customer writes: 'My Volta-X shows error E57.' Reply with the fix.",
     "checks": [("reply_contains", ["intake grille", "fan"])]},
    {"id": "A07", "task": "A customer asks how many panels one Volta-2 inverter can take. Reply.",
     "checks": [("reply_contains", ["18"])]},
    {"id": "A08", "task": "A customer wants HS-400 panels to fill two Volta-2 inverters to their maximum. Reply with "
     "the number of panels and the total panel cost (no installation).", "checks": [("reply_contains", ["36"]),
                                                                                  ("reply_contains",
                                                                                   ["15,120", "15120"])]},
    {"id": "A09", "task": "A customer asks for the warranty on the HS-520 panel. Reply.",
     "checks": [("reply_contains", ["30"])]},
    {"id": "A10", "task": "A customer bought unused equipment 50 days ago and wants to return it. Reply saying "
     "whether that is possible under the returns policy.", "checks": [("reply_contains", ["45"])]},
    {"id": "A11", "task": "Customer Grace Achieng orders 3 bird mesh kits. Create her invoice.",
     "checks": [("invoice_total", 285)]},
    {"id": "A12", "task": "Customer Daniel Mutua orders 10 HS-400 panels with installation and rush shipping on the "
     "panels (the surcharge applies to the panel cost only). Create the invoice.", "checks": [("invoice_total", 5024)]},
    {"id": "A13", "task": "A customer asks which app shows their system's production. Reply.",
     "checks": [("reply_contains", ["Helio Pulse", "Pulse"])]},
    {"id": "A14", "task": "A customer asks when the support desk opens. Reply.",
     "checks": [("reply_contains", ["07:00", "7:00", "7 am", "7am"])]},
    {"id": "A15", "task": "A customer asks which firmware version to install on the Volta-2. Reply.",
     "checks": [("reply_contains", ["4.2.1"])]},
    {"id": "A16", "task": "A customer asks which cable connects the Lumen LB-13 battery. Reply.",
     "checks": [("reply_contains", ["CB-3"])]},
    {"id": "A17", "task": "A customer asks for the warranty on the HS-700 panel. Handle the request.",
     "checks": [("escalated", True)]},
    {"id": "A18", "task": "A customer asks whether Helio offers financing plans. Handle the request.",
     "checks": [("escalated", True)]},
    {"id": "A19", "task": "Customer Peter Njoroge orders one Volta-X inverter. Create his invoice.",
     "checks": [("escalated", True)]},
    {"id": "A20", "task": "A customer wants 20 HS-400 panels on a single Volta-2 inverter. Reply with whether that "
     "works.", "checks": [("reply_contains", ["18"])]},
]

PROMPT = """You are the operations agent of Helio Solar (a solar installer). Complete the task with the tools.

Tools (one call per turn):
{tools}- calculate {{"expression": "..."}}: evaluate arithmetic exactly, e.g. {{"expression": "12*420 + 180 + 35*12"}}
- create_invoice {{"customer": "...", "lines": [{{"item": "...", "qty": 1, "unit_price": 0}}], "total": 0}}
- reply {{"message": "..."}}: send a message to the customer
- escalate {{"reason": "..."}}: hand the task to a person

Answer each turn with exactly one line:  ACTION <tool> <json arguments>   or, when the task is complete:  DONE
Never invent a price, fee, rule or fact: {never}

Task: {task}
{history}
Your next line (ACTION <tool> <json> or DONE):"""
MEMORY_TOOL = "- search_memory {\"query\": \"...\"}: look up Helio's prices, policies and known fixes\n"


class Agent:
    def __init__(self, model: str, memory: str):
        self.model, self.memory = model, memory
        self.reader = systems.Meter(systems.runner(model), model)
        self.engine = self.store = self.rt = None
        if memory in ("rag", "camr"):
            import tempfile

            d = Path(tempfile.mkdtemp(prefix=f"agent-{memory}-"))
            self.engine, self.store = systems.build_store(d / "mem.sqlite")
            from camr.memory.note import Document

            docs = [Document("agentic", "kb:" + x["title"], x["text"], x["title"]) for x in DATA["kb"]]
            docs += [Document("agentic", "res:" + k, v["text"], v["title"]) for k, v in DATA["resolutions"].items()]
            self.engine.ingest(docs)
            if memory == "rag":
                rb = systems._load("rag_bench", ROOT / "scripts/rag_bench.py")
                if systems.RAG._ce is None:
                    from sentence_transformers import CrossEncoder

                    systems.RAG._ce = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
                self.rt = rb.Retriever(self.engine, self.store, systems.RAG._ce)

    def search(self, query: str) -> str:
        if self.memory == "rag":
            notes, _ = self.rt.rerank(query, 5)
            return "\n".join(f"- {n.text}" for n in notes) or "(no results)"
        r = self.engine.recall(query, touch=False)
        if r.abstained:
            return "Nothing relevant is stored in memory."
        return r.context.strip() or "Nothing relevant is stored in memory."

    def run(self, task: dict) -> dict:
        from importlib import import_module

        calc = import_module("math_learning").calculate if "math_learning" in sys.modules else \
            systems._load("math_learning", ROOT / "scripts/math_learning.py").calculate
        tools = MEMORY_TOOL if self.memory != "none" else ""
        never = ("always start with search_memory; if memory does not have it, escalate." if self.memory != "none"
                 else "if you do not know it, escalate.")
        history, calls, done, t0 = "", [], False, time.perf_counter()
        self.reader.reset()
        if self.memory != "none":  # memory first: the task itself is looked up before the agent's first turn
            obs = self.search(task["task"])
            calls.append({"tool": "search_memory", "args": {"query": task["task"]}, "auto": True})
            history += f"\nACTION search_memory {json.dumps({'query': task['task']})}\nObservation: {obs[:900]}\n"
        for _ in range(MAX_STEPS):
            text = self.reader.generate(PROMPT.format(tools=tools, never=never, task=task["task"],
                                                      history=history)).text.strip()
            m = re.search(r"ACTION\s+(\w+)\s*(\{.*\})", text, re.S)
            if not m:
                if re.search(r"\bDONE\b", text):
                    history += f"\n{text[:300]}\n"
                    done = True
                    break
                history += f"\n{text[:300]}\nObservation: answer with ACTION <tool> <json> or DONE.\n"
                continue
            tool, raw = m.group(1), m.group(2)
            try:
                args = json.loads(raw[: raw.rfind("}") + 1])
            except ValueError:
                history += f"\nACTION {tool} {raw[:200]}\nObservation: the arguments are not valid JSON.\n"
                continue
            calls.append({"tool": tool, "args": args})
            if tool == "search_memory" and self.memory != "none":
                obs = self.search(str(args.get("query", "")))
            elif tool == "calculate":
                v = calc(str(args.get("expression", "")))
                obs = f"{v:g}" if v is not None else "could not evaluate"
            elif tool in ("create_invoice", "reply", "escalate"):
                obs = "done"
            else:
                obs = f"unknown tool {tool}"
            history += f"\nACTION {tool} {json.dumps(args)}\nObservation: {obs[:900]}\n"
            if tool in ("reply", "create_invoice", "escalate"):  # the task's outcome: the agent is done
                done = True
                break
        verdict = score(task, calls)
        return {"task": task["id"], "actions": calls, "done": done, "transcript": history[-3000:], **verdict, "steps": self.reader.calls,
                "wall_s": round(time.perf_counter() - t0, 2), **self.reader.usage()}


def _num(x) -> float | None:
    try:
        return float(str(x).replace(",", "").replace("$", ""))
    except ValueError:
        return None


def score(task: dict, calls: list[dict]) -> dict:
    from gateway import matches

    invoices = [c["args"] for c in calls if c["tool"] == "create_invoice"]
    replies = " ".join(str(c["args"].get("message", "")) for c in calls if c["tool"] == "reply")
    escalated = any(c["tool"] == "escalate" for c in calls)
    ok, hallucinated = True, False
    for kind, want in task["checks"]:
        if kind == "invoice_total":
            tot = [_num(i.get("total")) for i in invoices]
            good = any(t is not None and abs(t - want) <= 0.5 for t in tot)
            ok &= good
            hallucinated |= bool(invoices) and not good
        elif kind == "reply_contains":
            good = matches(replies, want)
            ok &= good
            hallucinated |= bool(replies) and not good
        elif kind == "escalated":
            ok &= escalated and not invoices and not replies
            hallucinated |= bool(invoices) or bool(replies and not escalated)
    return {"success": bool(ok), "hallucinated_action": bool(hallucinated), "escalated": escalated}
