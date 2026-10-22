"""Profile notes (``profile``): what the user says about lasting traits and constraints.

"I am vegetarian and I don't eat fish either" matters to "Can you suggest a dinner place for Friday?", which
shares no words with it and names no food: retrieval by similarity alone misses it, and the entity gate
withheld it. So at write time a statement of a lasting trait (diet, allergy, intolerance, fear, a standing
preference or habit, who the user is) is also kept as a profile note, and the read path offers the
best-matching profile notes to every question within a small budget, whatever the gates decide.

By rule and model-free, and strict, since every profile note reaches every question: only first-person
statements the user made (not the assistant), never a question or a request ("can you ...", "I was
wondering ..."), never a plan or a passing state ("I'm trying to ...", "this weekend"), never a reaction ("I love
the idea!", "That's a great list", anything said with an exclamation mark). A first version also took likes and recent pursuits ("I love ...", "I've been
using ..."): on LongMemEval histories that put about two such lines into nearly every context, mostly passing
remarks, so the list below keeps only lasting traits.
"""

from __future__ import annotations

import re

from camr.memory.timeframe import split_said

_TRAITS = [
    # diet, health and who the user is
    r"\bI(?:'m| am)(?: a| an)?(?: strict| pure| mostly| lifelong)? (?:vegetarian|vegan|pescatarian|teetotal\w*|"
    r"diabetic|coeliac|celiac|lactose[- ]intolerant|gluten[- ]free|pregnant|sober|left[- ]handed|colou?r[- ]?blind)\b",
    r"\bI(?:'m| am)(?: very| quite| a bit| severely| mildly)? (?:allergic|intolerant|sensitive) to\b",
    r"\blactose[- ]intolerant\b",
    r"\b(?:upsets?|hurts?|bothers?|irritates?) my (?:stomach|back|knees?|eyes|skin|chest)\b",
    r"\bI (?:don't|do not|never|can't|cannot|no longer) (?:eat|drink|fly|drive|smoke|touch)\b",
    r"\bI(?:'m| am)(?: very| really| quite| a bit)? (?:afraid|scared|terrified|frightened) of\b",
    r"\bI get(?: very| quite| really| a bit)? (?:anxious|nervous|airsick|seasick|carsick|motion sick)\b",
    r"\bI(?:'m| am) an? (?:big |huge |massive |lifelong )?fan of\b",
    r"\bI (?:work|worked) as an?\b",
    r"\bI(?:'m| am) an? (?:[\w-]+ ){0,2}(?:nurse|teacher|doctor|engineer|developer|designer|student|lawyer|accountant|"
    r"chef|farmer|driver|manager|analyst|artist|writer|musician|scientist|researcher|consultant|freelancer|pharmacist|"
    r"veterinarian|programmer|photographer|mother|father|mom|mum|dad|parent|grandparent|retiree|vegetarian|vegan)\b",
    # standing preferences and habits
    r"\bI (?:really |strongly |usually |always |generally |tend to )?(?:prefer|avoid)\b",
    r"\bI(?:'d| would) rather\b",
    r"\bI (?:always|never|usually) (?:eat|drink|take|wear|use|buy|order|go|travel|cook|sleep|wake|walk|run|read|"
    r"skip|book|fly|drive|cycle|pay|shop|carry|bring|sit|stay)\b",
    # "my favourite tea is ...", "shrimp is my favourite protein", "it's one of my favourite films"
    r"\bmy (?:all-time )?favou?rite(?: [\w'-]+){0,4} (?:is|are)\b",
    r"(?:\bis|'s|\bare) (?:one of )?my (?:all-time )?favou?rites?\b",
]
_TRAIT = re.compile("|".join(_TRAITS), re.I)
# not a statement of a lasting trait
_REQUEST = re.compile(r"\b(?:can|could|would|will) you\b|\bplease\b|\bI(?:'d| would) like (?:to ask|you|some)\b|"
                      r"\bI was wondering\b|\bwonder if\b|\bhelp me\b|\bremind me\b|\btell me\b|"
                      r"\bany (?:tips|ideas|suggestions|advice|recommendations)\b|\brecommend\b|\bsuggest\b", re.I)
_PASSING = re.compile(r"\bI(?:'m| am) (?:trying|planning|thinking|looking|hoping|going|about|getting ready) to\b|"
                      r"\bI was thinking\b|\bI(?:'d| would) (?:also )?(?:like|love) to\b|\bI (?:need|want) to\b|"
                      r"\brecently\b|\bjust (?:finished|bought|got)\b|\bback then\b|"
                      r"\bI(?:'m| am) (?:planning|thinking of|looking for|working on)\b|"
                      r"\b(?:this|next|last) (?:week|weekend|month|year)\b|\btoday\b|\btomorrow\b|\btonight\b|"
                      r"\b(?:the idea|that's|that is|this is|sounds|thanks|thank you)\b|^(?:oh|wow|yes|yeah|ok|okay)\b",
                      re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
MAX_WORDS = 30


def profile_statements(text: str) -> list[str]:
    """The sentences of ``text`` that state a lasting trait of the user (none from what the assistant said)."""
    _, role, body = split_said(text)
    if role == "assistant":
        return []
    out = []
    for sent in _SENTENCE.split(body.strip()):
        sent = " ".join(sent.split())
        if (sent and not sent.endswith(("?", "!")) and len(sent.split()) <= MAX_WORDS and _TRAIT.search(sent)
                and not _REQUEST.search(sent) and not _PASSING.search(sent)):
            out.append(sent)
    return list(dict.fromkeys(out))
