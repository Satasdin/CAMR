"""Engram as an agent's memory: a task arrives, the room it is about is laid on the desk, and the model calls one tool
with arguments taken from what it was told.

The tasks come from a life's quiz: each question becomes an everyday errand whose tool needs that very fact (a
ride needs the address, a reminder needs the birthday). A task about someone never told should end in ``ask_user``,
not a guess. The tools are pretend: they only echo what they were asked to do.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

THEN = ("This request is a task. Do it with exactly one tool call. Take the tool's arguments only from the notes "
        "above. If the notes do not say what the tool needs, call ask_user instead of guessing.")


def _tool(name: str, description: str, **params: str) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": {k: {"type": "string", "description": v} for k, v in params.items()},
        "required": list(params)}}}


TOOLS = [
    _tool("book_ride", "Book a ride to a place.", destination="the town or place to go to"),
    _tool("set_reminder", "Set a reminder on a date.", person="who it is for", date="the date, e.g. 10 October"),
    _tool("order_food", "Order a dish for delivery.", dish="the dish to order"),
    _tool("book_car_service", "Book a car in for a service.", car="the make and model of the car"),
    _tool("order_phone_case", "Order a case for a phone.", phone="the phone brand"),
    _tool("buy_team_scarf", "Buy a football team's scarf.", team="the football team"),
    _tool("find_gift", "Find a gift that suits someone's work.", work="what they do for work"),
    _tool("book_dog_groomer", "Book a groomer for a dog.", dog_name="the dog's name"),
    _tool("write_diary", "Write a diary entry for a day.", date="the date it happened", event="what happened"),
    _tool("ask_user", "Ask the user for something the notes do not say.", question="what to ask"),
]

# each quiz question, as the errand that needs its answer: (question pattern, task, tool, argument holding the fact)
FORMS = [
    (r"Where does my (.+) live\?", "Book me a ride to my {}'s home.", "book_ride", "destination"),
    (r"When is my (.+)'s birthday\?", "Set a reminder for my {}'s birthday.", "set_reminder", "date"),
    (r"What is my (.+)'s favourite food\?", "Order my {}'s favourite food for dinner tonight.", "order_food", "dish"),
    (r"What car does my (.+) drive\?", "Book my {}'s car in for a service.", "book_car_service", "car"),
    (r"What phone brand does my (.+) use\?", "Order a case for my {}'s phone.", "order_phone_case", "phone"),
    (r"Which football team does my (.+) support\?", "Buy my {} a scarf of the team they support.", "buy_team_scarf", "team"),
    (r"What does my (.+) do for work\?", "Find a gift for my {} that suits their work.", "find_gift", "work"),
    (r"What is the name of my (.+)'s dog\?", "Book a groomer for my {}'s dog.", "book_dog_groomer", "dog_name"),
    (r"What date was it when I (.+)\?", "Write a diary entry for the day I {}.", "write_diary", "date"),
]


@dataclass
class Task:
    question: object  # the life's Question it was made from (for grading)
    text: str
    tool: str
    arg: str


def tasks(life) -> list[Task]:
    out = []
    for q in life.questions:
        for pattern, task, tool, arg in FORMS:
            m = re.fullmatch(pattern, q.text)
            if m:
                out.append(Task(q, task.format(m.group(1)), tool, arg))
                break
    return out


def parse(text: str) -> tuple[str | None, dict]:
    """The tool call in a reply: (tool name, arguments), or (None, {}) when there is none."""
    m = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        return None, {}
    try:
        call = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None, {}
    args = call.get("arguments", {})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    return call.get("name"), args if isinstance(args, dict) else {}


def done(tool: str | None, args: dict) -> str:
    """What the pretend tool says back."""
    if tool is None:
        return "No tool was called."
    if tool == "ask_user":
        return f"Asked you: {args.get('question', '')}".strip()
    shown = ", ".join(f"{k} = {v}" for k, v in args.items())
    return f"{tool.replace('_', ' ').capitalize()}: {shown}"


def grade(task: Task, tool: str | None, args: dict, day: int) -> str:
    """The quiz's verdicts, for a tool call: asking counts as declining, a wrong tool as a wrong answer."""
    from engram.ruler.grade import grade as quiz_grade

    if tool == "ask_user":
        return quiz_grade(task.question, "I don't know.", day)
    if tool != task.tool:
        return quiz_grade(task.question, "I don't know.", day) if tool is None else "wrong"
    return quiz_grade(task.question, str(args.get(task.arg, "")), day)


def act(memory, task_text: str, today, **log) -> tuple[str | None, dict, object]:
    """Engram doing one task: the desk as usual, then one tool call. Returns (tool, arguments, reply)."""
    reply = memory.answer(task_text, today, then=THEN, tools=TOOLS, max_tokens=120, kind="agent", **log)
    tool, args = parse("".join(reply.pieces))
    if memory.log:
        memory.log.write("tool", task=task_text, tool=tool, args=args, result=done(tool, args))
    return tool, args, reply
