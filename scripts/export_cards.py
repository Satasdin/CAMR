"""Export the skill cards of F32 as a card pack CAMR Personal can install (camr/app/tiers.py).

Each card (results/skills/stores/cards/<family>/e<card epoch>: a PEFT LoRA adapter for Qwen2.5-0.5B-Instruct, the one
the experiment chose) is converted to a GGUF adapter with llama.cpp's ``convert_lora_to_gguf.py``, so that Ollama can
attach it to ``qwen2.5:0.5b``. The pack also carries the corrections the cards were trained on (four per family,
as scripts/skill_cards.py), titled ``Correction: <family>``: that title is how memory names a card.

    python scripts/export_cards.py --llama-cpp ~/.cache/camr-tools/llama.cpp     # writes ~/.camr/cards/formulas/

The converter needs PyTorch and llama.cpp's own ``gguf-py`` (a sparse checkout of llama.cpp is enough); the base
model's Hugging Face files (config.json) must be in the local cache, where scripts/skill_cards.py left them.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("math_learning", ROOT / "scripts/math_learning.py")
ml = importlib.util.module_from_spec(_spec)
sys.modules["math_learning"] = ml
_spec.loader.exec_module(ml)

PREFIX = "Correction: "
HF_BASE = "Qwen/Qwen2.5-0.5B-Instruct"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def hf_snapshot(model_id: str) -> Path:
    root = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")) / "hub"
    snaps = sorted((root / f"models--{model_id.replace('/', '--')}" / "snapshots").glob("*/config.json"))
    if not snaps:
        raise SystemExit(f"{model_id} is not in the Hugging Face cache: run scripts/skill_cards.py first")
    return snaps[-1].parent


def corrections() -> list[dict]:
    """The notes the cards were trained from: the first four training problems of each family (skill_cards.py)."""
    fams = {f.key: f for f in ml.FAMILIES}
    per: dict[str, list[dict]] = {}
    for it in ml.problems()["train"]:
        per.setdefault(it["family"], []).append(it)
    return [{"title": f"{PREFIX}{fam}", "text": ml.correction_note(fams[fam], it)}
            for fam, items in per.items() for it in items[:4]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llama-cpp", required=True, help="a llama.cpp checkout with convert_lora_to_gguf.py and gguf-py")
    ap.add_argument("--out", default=str(Path.home() / ".camr/cards/formulas"))
    ap.add_argument("--base", default="qwen2.5:0.5b", help="the Ollama model the cards attach to")
    ap.add_argument("--outtype", default="f16", choices=["f32", "f16", "bf16", "q8_0"])
    a = ap.parse_args()

    res = json.loads((ROOT / "results/skills/skill_cards.json").read_text())
    epoch = res["card_epoch"]
    llama = Path(a.llama_cpp).expanduser()
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    base_hf = hf_snapshot(HF_BASE)
    env = {**os.environ, "PYTHONPATH": str(llama / "gguf-py")}
    cards = []
    for fam in sorted(res["card_training"]):
        adapter = ROOT / "results/skills/stores/cards" / fam / f"e{epoch}"
        gguf = out / f"{slug(fam)}.gguf"
        if not gguf.exists():
            done = subprocess.run([sys.executable, str(llama / "convert_lora_to_gguf.py"), "--base", str(base_hf),
                                   "--outtype", a.outtype, "--outfile", str(gguf), str(adapter)],
                                  env=env, capture_output=True, text=True)
            if done.returncode != 0 or not gguf.exists():
                raise SystemExit(f"{fam}: conversion failed\n{done.stderr[-2000:]}")
        cards.append({"skill": fam, "adapter": gguf.name, "model": f"camr-card-{slug(fam)}"})
        print(f"{fam:20s} {gguf.stat().st_size / 1e6:.1f} MB", flush=True)
    notes = corrections()
    (out / "pack.json").write_text(json.dumps({
        "name": "formulas", "title": "Formula skills (study demo)", "base": a.base, "prefix": PREFIX,
        "description": f"The ten skill cards of the study (F32): one adapter per formula family, trained on four "
                       f"corrections each for {HF_BASE} ({epoch} epochs), converted for Ollama ({a.outtype}).",
        "trained_for": HF_BASE, "card_epoch": epoch, "cards": cards, "notes": notes}, indent=1))
    print(f"wrote {out / 'pack.json'}: {len(cards)} cards, {len(notes)} corrections")


if __name__ == "__main__":
    main()
