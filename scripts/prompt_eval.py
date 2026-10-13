"""Choose CAMR Personal's chat prompt on a development set and confirm it on a held-out set.

Each case is a question, the notes the engine would give (or none), and what a correct reply must do:
answer from the notes, answer from general knowledge, or say it does not know (a personal fact that is
not stored). The cases cover the failures found by the live scenarios (D-13): refusing general questions,
and refusing a question its notes answer.

    python scripts/prompt_eval.py --model llama3.2:3b --out docs/results/prompt_eval.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from camr.config import LocalModelConfig
from camr.models.runner import OllamaRunner

ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-10-13"

DEV = [
    ("general", "What is 17 × 23?", "", ["391"]),
    ("general", "What's the capital of Australia?", "", ["canberra"]),
    ("general", "How many days are in a leap year?", "", ["366"]),
    ("notes", "Which antibiotic am I allergic to?", f"- On {DAY} the user said: I'm allergic to penicillin, please keep that "
     "in mind.\n", ["penicillin"]),
    ("notes", "Which room is my supervisor's office in?", "- Dr. Achieng Otieno: Dr. Achieng Otieno's office is Room 4.12 "
     "on the third floor of the Science Complex.\n- Project CAMR: Project CAMR is supervised by Dr. Achieng Otieno.\n",
     ["4.12"]),
    ("unknown", "When is my dentist appointment?", "", ["don't know", "do not know", "not sure", "no information",
                                                        "don't have"]),
]
HELD_OUT = [
    ("general", "Who wrote Romeo and Juliet?", "", ["shakespeare"]),
    ("general", "What is 12 squared?", "", ["144"]),
    ("general", "At what temperature does water boil at sea level in Celsius?", "", ["100"]),
    ("notes", "Where does my sister live?", f"- On {DAY} the user said: My sister Wanjiru lives in Nakuru with her two "
     "kids.\n", ["nakuru"]),
    ("notes", "What time does the gym open on Saturdays?", "- Gym: The campus gym opens at 07:30 on Saturdays and 06:00 on "
     "weekdays.\n", ["07:30", "7:30"]),
    ("unknown", "What is my passport number?", "", ["don't know", "do not know", "not sure", "no information",
                                                    "don't have"]),
    ("unknown", "What did I name my cat?", "", ["don't know", "do not know", "not sure", "no information", "don't have"]),
]

# A second held-out set, written after prompt D and never used to design any prompt.
FRESH = [
    ("general", "How many continents are there?", "", ["7", "seven"]),
    ("general", "What is the chemical symbol for gold?", "", ["au"]),
    ("general", "What is 9 × 8?", "", ["72"]),
    ("notes", "What is my blood type?", f"- On {DAY} the user said: My blood type is O negative, write that down.\n",
     ["o negative", "o-negative", "o-"]),
    ("notes", "When is my car insurance due?", "- Car insurance: The car insurance with Jubilee renews on 3 November; "
     "the premium is KES 41,000.\n", ["3 november", "november 3"]),
    ("notes", "What medication do I take in the morning?", f"- On {DAY} the user said: I take 5 mg of amlodipine every "
     "morning for blood pressure.\n", ["amlodipine"]),
    ("unknown", "What is my landlord's phone number?", "", ["don't know", "do not know", "not sure", "no information",
                                                            "don't have"]),
    ("unknown", "Which hospital was I born in?", "", ["don't know", "do not know", "not sure", "no information",
                                                      "don't have"]),
]

PROMPTS = {
    "O (original)": """You are a personal assistant running privately on the user's own computer.
Below are notes from the user's personal memory that may be relevant, then the recent conversation.
Use the notes when they answer the question and prefer them over your own assumptions.
If the notes do not contain the answer and you are not sure, say you don't know rather than guessing.
Answer concisely.

### Notes from memory
{notes}

### Recent conversation
{history}

### User
{question}

### Assistant
""",
    "D (notes are true)": """You are a private personal assistant running on the user's own computer.

The notes below come from the user's personal memory and are about the user. "The user said …" means the user told you this earlier; "I" inside it is the user. Treat what the notes say about the user as true and answer from them directly.

How to answer:
1. If the notes contain the answer, give it from the notes.
2. If it is a general-knowledge question (facts, maths, definitions), answer it from your own knowledge.
3. Only if it asks about the user's own life and the notes do not say, reply that you don't know; never invent personal details.
Answer concisely.

### Notes from memory
{notes}

### Recent conversation
{history}

### User
{question}

### Assistant
""",
    "E (eager: ask to be taught)": """You are a private personal assistant running on the user's own computer.

The notes below come from the user's personal memory and are about the user. "The user said …" means the user told you this earlier; "I" inside it is the user. Treat what the notes say about the user as true and answer from them directly.

How to answer:
1. If the notes contain the answer, give it from the notes.
2. If it is a general-knowledge question (facts, maths, definitions), answer it from your own knowledge.
3. Only if it asks about the user's own life and the notes do not say, say that you don't know that yet and ask the user to tell you, so you can remember it; never invent personal details.
Answer concisely.

### Notes from memory
{notes}

### Recent conversation
{history}

### User
{question}

### Assistant
""",
    "A (D-13 fix)": """You are a personal assistant running privately on the user's own computer.
Below are notes from the user's personal memory that may be relevant, then the recent conversation.
Use the notes when they answer the question and prefer them over your own assumptions.
If the question is about the user, their plans or their notes and the notes do not contain the answer,
say you don't know rather than guessing. For general questions, answer from your own knowledge.
Answer concisely.

### Notes from memory
{notes}

### Recent conversation
{history}

### User
{question}

### Assistant
""",
    "B (explicit cases)": """You are a private personal assistant running on the user's own computer.

The notes below come from the user's personal memory. They describe the user: "the user said …" means the user told you this earlier, and "I" inside those quotes is the user.

How to answer:
1. If the notes contain the answer, answer from the notes.
2. If it is a general-knowledge question (facts, maths, definitions), answer it from your own knowledge.
3. Only if it asks about the user's own life (their appointments, belongings, people, plans) and the notes do not say, reply that you don't know.
Answer concisely.

### Notes from memory
{notes}

### Recent conversation
{history}

### User
{question}

### Assistant
""",
    "C (notes first, short)": """You are a private personal assistant on the user's computer.
Notes from the user's memory (written about the user; "the user said" means the user told you earlier):
{notes}
Recent conversation:
{history}
Answer the user's message concisely. Use the notes if they answer it. For general questions, use your own knowledge. If it is about the user's personal life and the notes don't say, say you don't know.

User: {question}
Assistant:""",
}


def judge(kind: str, answer: str, expected: list[str]) -> bool:
    a = answer.lower().replace("’", "'")
    if kind == "unknown":
        return any(x in a for x in expected)
    return any(x.lower() in a for x in expected) and not re.match(r"^\s*i (don't|do not) know", a)


_INVITES = re.compile(r"\b(tell me|let me know|share|teach me|remember it|i'll remember|i can remember|could you tell|"
                      r"can you tell|would you like to tell|if you tell)\b", re.I)


def invites_teaching(answer: str) -> bool:
    """An unknown personal fact answered by asking the user to teach it (the eager behaviour)."""
    return bool(_INVITES.search(answer.replace("’", "'")))


def run(model: str, prompt: str, cases) -> list[dict]:
    runner = OllamaRunner(LocalModelConfig(name=model, host="http://127.0.0.1:11434", max_tokens=200, num_ctx=4096))
    out = []
    for kind, q, notes, expected in cases:
        g = runner.generate(prompt.format(notes=notes or "(no relevant notes)", history="(none)", question=q))
        out.append({"kind": kind, "question": q, "answer": g.text.strip()[:240], "correct": judge(kind, g.text, expected),
                    "invites_teaching": kind == "unknown" and invites_teaching(g.text)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="llama3.2:3b,qwen2.5:1.5b")
    ap.add_argument("--fresh", action="store_true", help="also score the second held-out set")
    ap.add_argument("--only", help="comma-separated prompt names to run (results are merged into --out)")
    ap.add_argument("--out", default=str(ROOT / "docs/results/prompt_eval.json"))
    a = ap.parse_args()
    out = Path(a.out)
    res = json.loads(out.read_text())["results"] if out.exists() else {}
    names = a.only.split(",") if a.only else list(PROMPTS)
    for model in a.models.split(","):
        for name in names:
            prompt = PROMPTS[name]
            dev, held = run(model, prompt, DEV), run(model, prompt, HELD_OUT)
            entry = {"dev": dev, "held_out": held, "dev_correct": sum(x["correct"] for x in dev),
                     "held_out_correct": sum(x["correct"] for x in held),
                     "unknown_invites_teaching": sum(x["invites_teaching"] for x in dev + held)}
            if a.fresh:
                fresh = run(model, prompt, FRESH)
                entry.update({"fresh": fresh, "fresh_correct": sum(x["correct"] for x in fresh)})
            res.setdefault(model, {})[name] = entry
            print(model, name, "dev", res[model][name]["dev_correct"], "/", len(DEV), "held-out",
                  res[model][name]["held_out_correct"], "/", len(HELD_OUT),
                  *(("fresh", res[model][name]["fresh_correct"], "/", len(FRESH)) if a.fresh else ()), flush=True)
    Path(a.out).write_text(json.dumps({"dev_n": len(DEV), "held_out_n": len(HELD_OUT), "fresh_n": len(FRESH),
                                       "results": res}, indent=2,
                                      ensure_ascii=False))


if __name__ == "__main__":
    main()
