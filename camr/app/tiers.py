"""The two tiers beside the notes in CAMR Personal (docs/FINDINGS.md F32 and F36).

* **Skill cards.** A card is a small adapter for one model, trained on the corrections of one skill (a formula
  family). Its corrections stay in memory as notes titled ``Correction: <skill>``; when the best note memory admits
  for a question is one of them, that card answers (camr/memory/skills.py). A card writes the formula and one
  expression after ``####``, and the calculator does the arithmetic, exactly as the experiment measured
  (scripts/skill_cards.py, camr/learn/calc.py). Cards come in packs: a folder with ``pack.json``, the cards'
  GGUF adapters and the corrections; installing one registers each card with Ollama as the base model plus the
  adapter. The model's own weights never change.
* **The link.** A handful of numbers per model that decide, after a local answer, whether to state it, decline, or
  ask the second-opinion model with the same notes (camr/learn/link.py). It starts from the link learned on the
  reader bench for the nearest model size (camr/app/links/, ``scripts/link_learning.py export``) and keeps learning
  from the user's thumbs, one answer at a time.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from camr.learn.calc import read_answer

CARD_PREFIX = "Correction: "  # the title a skill's corrections share: it names the card (scripts/skill_cards.py)
BUNDLED_CARDS = Path(__file__).resolve().parent / "cards"
LINK_PRIORS = Path(__file__).resolve().parent / "links"

# What the link says instead of an answer it does not trust.
DECLINE_PERSONAL = "I'm not sure about this, so I won't guess. If you tell me, I'll remember it."
DECLINE_GENERAL = "I'm not sure about this one, so I won't guess."

# The price of asking the second-opinion model, in units of one right answer: the price the bench links were
# learned at (F36), so the app's own feedback continues the same reward.
ESCALATION_COST = 0.3


def link_reward(action: str, helpful: bool, declined: bool, cost: float = ESCALATION_COST) -> float:
    """The reward a thumb gives the link's action: the reader bench's reward (camr.learn.link.Rewards) read from
    feedback. A right answer +1 and a wrong one -1; saying "I don't know" earns +1 when the user agrees (thumbs up)
    and 0 otherwise, never -1, because a decline states nothing false; an escalation pays ``cost``."""
    if action == "decline" or declined:
        reward = 1.0 if helpful else 0.0
    else:
        reward = 1.0 if helpful else -1.0
    return reward - cost if action == "escalate" else reward


# ---------------------------------------------------------------------- the link's starting point
_SIZE = re.compile(r"(\d+(?:\.\d+)?)\s*([MB])", re.I)


def params_b(text: str | None) -> float | None:
    """'494.03M' -> 0.494, '1.5B' -> 1.5, 'qwen2.5:3b' -> 3.0 (None if no size is named)."""
    m = _SIZE.search(text or "")
    if not m:
        return None
    v = float(m.group(1))
    return v / 1000 if m.group(2).upper() == "M" else v


def priors() -> list[dict]:
    out = []
    for f in sorted(LINK_PRIORS.glob("*.json")) if LINK_PRIORS.exists() else []:
        try:
            meta = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        out.append({"path": f, "reader": meta.get("reader"), "params_b": meta.get("params_b")})
    return out


def prior_for(model: str, size_b: float | None = None) -> dict | None:
    """The bench link to start from: the same model if the bench measured it, else the nearest size."""
    ps = priors()
    for p in ps:
        if p["reader"] == model or (p["reader"] and model.startswith(p["reader"] + "-")):
            return p
    size = size_b if size_b is not None else params_b(model.split(":")[-1] if ":" in model else model)
    sized = [p for p in ps if p["params_b"]]
    if size is None or not sized:
        return None
    return min(sized, key=lambda p: abs(p["params_b"] - size))


# ---------------------------------------------------------------------- skill cards
def read_pack(folder: Path) -> dict:
    """A card pack's manifest, checked: {name, title, base, prefix, cards: [{skill, adapter, model}], notes}."""
    man = json.loads((folder / "pack.json").read_text())
    for key in ("name", "title", "base", "cards", "notes"):
        if key not in man:
            raise ValueError(f"card pack {folder.name}: no {key!r}")
    man.setdefault("prefix", CARD_PREFIX)
    for card in man["cards"]:
        if not (folder / card["adapter"]).exists():
            raise ValueError(f"card pack {man['name']}: {card['adapter']} is missing")
    man["folder"] = folder
    return man


def card_packs(home: Path) -> list[dict]:
    """Card packs on disk: bundled with the app, or exported into ``<home>/cards`` (scripts/export_cards.py)."""
    out = []
    for root in (BUNDLED_CARDS, home / "cards"):
        for f in sorted(root.glob("*/pack.json")) if root.exists() else []:
            try:
                out.append(read_pack(f.parent))
            except (OSError, ValueError, KeyError):
                continue
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def card_answer(text: str, question: str) -> tuple[str, dict]:
    """A card's answer, with the calculator's value: the formula line the card wrote, then the result. Returns
    (answer shown to the user, {"expression", "value"})."""
    value, _ = read_answer(text, "calc", question)
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    formula = next((ln for ln in lines if not ln.startswith("####")), "")
    expr = next((ln[4:].strip() for ln in reversed(lines) if ln.startswith("####")), "")
    if value is None:
        return text.strip(), {"expression": expr, "value": None}
    shown = f"{value:,.2f}".rstrip("0").rstrip(".") if abs(value) < 1e15 else f"{value:g}"
    answer = (f"{formula}\n\n" if formula else "") + f"**{shown}**" + (f" (calculated: {expr})" if expr else "")
    return answer, {"expression": expr, "value": value}
