"""The chat as an assistant: it keeps the conversation, answers from its own knowledge, reaches into memory only
when a question needs it, can think aloud when the model is a thinking one, and can look a question up online.

Memory's own answers are short and strict ("only the notes, else I don't know"), which is right for the user's own
facts and wrong for "what is the square root of 56?". The closeness of the nearest memory cannot tell them apart:
the Long Haul is full of chat, so "hello" sits as close to a remembered moment (0.81) as "What is Otieno's surname?"
(0.72). So the model routes each question itself (``route``): a one-word answer, MEMORY or GENERAL, reading the
last turns too, so a follow-up such as "show me step by step" stays with the conversation. Only MEMORY questions
fetch a room. The router's own word is never shown and never reported as an answer's words.

``research`` looks a question up on Wikipedia (its public API: a search, then the best page's plain text), so the
model can answer from what it read and the source can be kept on the Research shelf.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from camr_engine.live import reporting

ROUTER = ("Decide whether answering the user's last message needs the assistant's memory of the user: facts about "
          "the user's own life, work, people, projects, clients, prices, dates, files, or anything the user told "
          "the assistant before. General knowledge, maths, explanations, writing, code help and follow-ups to the "
          "conversation do not. Reply with one word: MEMORY or GENERAL.")
SYSTEM = ("You are CAMR, a helpful assistant running on the user's own Mac. Answer clearly and as fully as the "
          "question needs; show working for maths. If the user asks about their own life, work or project and you "
          "were not given notes that say, say you don't know rather than guess.")
MEMORY_RULES = ("This is a conversation, not only a question about the notes: the one-sentence rule above does not "
                "apply. Use the notes when they are about the question and say the answer plainly. If the question "
                "is about the user's own life or work and the notes do not say, answer: I don't know.")
WEB_RULES = ("Answer from the source below, in a few sentences, and say what the source is. If it does not answer "
             "the question, say so.")
TURNS = 6  # turns of the conversation the model reads
ANSWER_TOKENS = 700
THINK_TOKENS = 2400  # a thinking model writes its reasoning first
SOURCE_CHARS = 6000
AGENT = "CAMR/0.1 (a local assistant; one page fetched per question)"
THINKING_MODELS = ("Qwen3-1.7B", "Qwen3-8B", "Qwen3-4B-4bit", "Qwen3-0.6B", "Qwen3-14B")  # hybrid: thinking on or off


def can_think(repo: str | None) -> bool:
    """Whether the model is a hybrid thinking build (Qwen3 1.7B, 8B…); the 4B 2507 Instruct build never thinks."""
    return bool(repo) and "Instruct" not in repo and any(m in repo for m in THINKING_MODELS)


def history_lines(turns: list[dict], n: int = TURNS) -> list[dict]:
    """The last ``n`` turns as chat messages (the thinking left out)."""
    out = []
    for t in turns[-n:]:
        text = (t.get("reply") if t.get("who") == "camr" else t.get("text")) or ""
        if text:
            out.append({"role": "assistant" if t.get("who") == "camr" else "user", "content": text[:2000]})
    return out


def route(reader, question: str, turns: list[dict]) -> str:
    """MEMORY or GENERAL, as the model judges it. Nothing is reported to a Live: the router's word is not an
    answer."""
    last = "\n".join(f"{m['role']}: {m['content'][:300]}" for m in history_lines(turns, 2))
    user = (f"Conversation so far:\n{last}\n\n" if last else "") + f"Last message: {question}"
    with reporting(None):
        reply = reader.generate(reader.chat_ids(ROUTER, user), max_tokens=3)
    return "memory" if "MEMORY" in reply.text.upper() else "general"


def chat_ids(reader, system: str, turns: list[dict], question: str, *, thinking: bool) -> list[int]:
    msgs = [{"role": "system", "content": system}, *history_lines(turns), {"role": "user", "content": question}]
    text = reader.tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=thinking,
                                          tokenize=False)
    return reader.tok.encode(text)


def split_thinking(text: str) -> tuple[str, str]:
    """(thinking, answer) from a reply that may open with a <think> block."""
    m = re.match(r"\s*<think>(.*?)(</think>|$)(.*)", text, re.S)
    if not m:
        return "", text.strip()
    return m.group(1).strip(), m.group(3).strip()


def research(question: str, *, timeout: float = 8.0) -> dict | None:
    """The best Wikipedia page for ``question``: {title, url, text}, or None when nothing is found."""

    def get(params: dict) -> dict:
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
        req = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())

    hits = get({"action": "query", "list": "search", "srsearch": question, "srlimit": 1}).get("query", {})
    found = hits.get("search") or []
    if not found:
        return None
    title = found[0]["title"]
    pages = get({"action": "query", "prop": "extracts", "explaintext": 1, "titles": title, "redirects": 1})
    page = next(iter((pages.get("query", {}).get("pages") or {}).values()), {})
    text = (page.get("extract") or "").strip()
    if not text:
        return None
    return {"title": title, "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
            "text": text[:SOURCE_CHARS]}
