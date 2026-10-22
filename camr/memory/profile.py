"""Profile notes (``profile``): what the user says about lasting traits, constraints and likes.

"I am vegetarian and I don't eat fish either" matters to "Can you suggest a dinner place for Friday?", which
shares no words with it and names no food: retrieval by similarity alone misses it, and the entity gate
withheld it. So at write time a statement of a lasting trait (diet, allergy, fear, health, likes and dislikes,
favourites, habits) is also kept as a profile note, and the read path offers the best-matching profile notes
to every question within a small budget, whatever the gates decide. By rule, model-free: only first-person
statements, only what the user said (not the assistant).
"""

from __future__ import annotations

import re

from camr.memory.timeframe import split_said

_TRAITS = [
    # diet, health and constraints
    r"\bI(?:'m| am)(?: a| an)?(?: strict| pure| mostly)? (?:vegetarian|vegan|pescatarian|teetotal\w*|diabetic|"
    r"coeliac|celiac|lactose[- ]intolerant|gluten[- ]free|pregnant|sober)\b",
    r"\bI(?:'m| am)(?: very| quite| a bit)? (?:allergic|intolerant|sensitive) to\b",
    r"\bI (?:don't|do not|never|can't|cannot|won't|no longer) (?:eat|drink|fly|drive|smoke|take|touch|stand)\b",
    r"\b(?:upsets?|hurts?|bothers?|irritates?) my (?:stomach|back|knee|knees|eyes|skin|chest)\b",
    r"\bI(?:'m| am)(?: very| quite| a bit| really)? (?:afraid|scared|terrified|frightened) of\b",
    r"\bI get(?: very| quite| really| a bit)? (?:anxious|nervous|sick|carsick|airsick|seasick|motion sick|migraines)\b",
    r"\bI(?:'m| am) lactose\b",
    # likes, dislikes, favourites
    r"\bI (?:really |absolutely |just )?(?:love|adore|hate|dislike|detest|can't stand|prefer|avoid|enjoy)\b",
    r"\bmy (?:favou?rite|preferred|go-to)\b",
    r"\bI(?:'m| am)(?: really| very)? (?:into|passionate about|a (?:big |huge )?fan of|not a fan of|keen on)\b",
    r"\bI (?:usually|always|tend to|normally) (?:prefer|go for|choose|pick|use|buy|order|eat|drink|avoid)\b",
    # habits and pursuits
    r"\bI(?:'ve| have) been (?:using|learning|practi[cs]ing|playing|collecting|training|studying|following)\b",
    r"\bI(?:'m| am) (?:learning|studying|training for|trying to)\b",
]
_TRAIT = re.compile("|".join(_TRAITS), re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
MAX_WORDS = 40


def profile_statements(text: str) -> list[str]:
    """The sentences of ``text`` that state a lasting trait of the user (none from what the assistant said)."""
    _, role, body = split_said(text)
    if role == "assistant":
        return []
    out = []
    for sent in _SENTENCE.split(body.strip()):
        sent = " ".join(sent.split())
        if sent and _TRAIT.search(sent) and len(sent.split()) <= MAX_WORDS:
            out.append(sent)
    return list(dict.fromkeys(out))
