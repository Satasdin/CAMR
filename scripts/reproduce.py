"""Reproduce the key results from committed caches, and check every number.

    python scripts/reproduce.py              # all checks, offline (no network, no model): must match exactly
    python scripts/reproduce.py --twice      # and run each check twice: the two runs must agree byte for byte
    python scripts/reproduce.py --only verified-test,bulk

Every web response and every model answer the results were scored on is cached by its exact
request (results/verified/web_cache_*.sqlite, results/verified/answers.sqlite), so a replay
reads exactly what the original run read and gets exactly the answers it got. What is left to
recompute (retrieval, ranking, compression, verification, scoring, ingestion) is recomputed.
A check passes only if its numbers equal the committed ones. Exit status 0 means all passed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(cmd: list[str], env_extra: dict | None = None, timeout: int = 7200) -> tuple[int, str]:
    import os

    env = {**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", **(env_extra or {})}
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)[-3000:]


# ---------------------------------------------------------------------- what is compared
def _verified_summary(d: dict) -> dict:
    """The deterministic part of a verified_qa result: metrics and each question's outcome (no timings)."""
    out = {}
    for name, v in d["variants"].items():
        out[name] = {"verified": v["verified"], "stated": v["stated"], "notes": v["notes"],
                     "per_question": [(x["i"], x["status"], x["by"], x["claim"], x["correct"], x["first_answer"])
                                      for x in v["per_question"]]}
    return out


def _diff(a, b, path="") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'expected' if k in a else 'replay'}")
            else:
                out += _diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return [f"{path}: {len(a)} items expected, {len(b)} in replay"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _diff(x, y, f"{path}[{i}]")
        return out[:20]
    return [] if a == b else [f"{path}: expected {a!r}, replay {b!r}"]


# ---------------------------------------------------------------------- checks
def check_tests(tmp: Path) -> tuple[bool, str]:
    code, out = run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    last = [ln for ln in out.splitlines() if ln.strip()][-1] if out.strip() else ""
    return code == 0, last


def _verified(set_name: str, tmp: Path) -> tuple[bool, str]:
    """Replay every committed results file of a set (answers_<set>.json, answers_<set>_<tag>.json), offline."""
    files = sorted((ROOT / "results/verified").glob(f"answers_{set_name}*.json"))
    if not files:
        return False, f"no results for {set_name} (run scripts/verified_qa.py answer --set {set_name})"
    lines = []
    for committed in files:
        tag = committed.stem[len(f"answers_{set_name}"):]
        exp = json.loads(committed.read_text())
        first = next(iter(exp["variants"].values()))
        cmd = [PY, "scripts/verified_qa.py", "answer", "--set", set_name, "--offline", "--offline-answers",
               "--variants", ",".join(exp["variants"]), "--out", str(tmp), "--tag", tag,
               "--budget", str(first.get("budget", 128)), "--min-coverage", str(first.get("min_coverage", 1.0))]
        cmd += ["--typed"] if first.get("typed") else []
        cmd += ["--relation-cue"] if first.get("relation_cue") else []
        cmd += ["--by-name"] if first.get("by_name") else []
        cmd += ["--hybrid"] if first.get("hybrid") else []
        code, out = run(cmd)
        if code != 0:
            return False, f"{committed.name}: replay failed:\n" + out
        got = json.loads((tmp / committed.name).read_text())
        d = _diff(_verified_summary(exp), _verified_summary(got))
        if d:
            return False, f"{committed.name} differs:\n" + "\n".join(d[:12])
        lines.append(f"{committed.name}: {len(got['variants'])} variants identical")
    return True, "; ".join(lines)


def check_verified_dev(tmp: Path):
    return _verified("dev", tmp)


def check_verified_test(tmp: Path):
    return _verified("test", tmp)


def check_lookup_dev(tmp: Path) -> tuple[bool, str]:
    exp = json.loads((ROOT / "results/verified/lookup_dev.json").read_text())
    # replay every lookup from the cache, offline, into a scratch copy of the result
    code, out = run([PY, "-c", f"""
import json, sys
sys.argv = ['x']
sys.path.insert(0, 'scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('v', 'scripts/verified_qa.py'); v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
from camr.config import Config
from camr.memory.embedder import build_embedder
class A: set='dev'; patient=0; offline=True
emb = build_embedder(Config.load('results/learn/config.yaml').embedder)
lk = v.lookup_for(A, emb)
rows = []
for it in v.load_set('dev'):
    r = lk.lookup(it['question'], max_pages=3)
    rows.append([it['i'], [p.title for p in r.pages], v.contains(' '.join(p.text for p in r.pages), it['answers']),
                 v.contains(' '.join(p.facts for p in r.pages), it['answers'])])
json.dump(rows, open('{tmp}/lookups.json', 'w'))
"""])
    if code != 0:
        return False, out
    got = json.loads((tmp / "lookups.json").read_text())
    want = [[x["i"], [p["title"] for p in x["pages"]], x["in_lead"], x["in_facts"]] for x in exp["per_question"]]
    d = _diff(want, got)
    return not d, ("\n".join(d[:12]) if d else f"{len(got)} lookups replayed offline, identical pages and hits")


def check_bulk(tmp: Path) -> tuple[bool, str]:
    exp_path = ROOT / "results/bulk/reproduce_expected.json"
    code, out = run([PY, "-c", f"""
import json, sys, itertools
sys.argv = ['x']
import importlib.util
spec = importlib.util.spec_from_file_location('ld', 'scripts/large_data.py'); ld = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ld)
from pathlib import Path
from camr.memory.bulk import bulk_ingest, read_jsonl
q = json.loads(ld.QUESTIONS.read_text())
engine, store = ld.engine_at(Path('{tmp}') / 'store.sqlite')
rep = bulk_ingest(engine, read_jsonl(ld.CORPUS, dataset='bulk:hotpot+2wiki'), limit=q['paragraphs_first'],
                  batch_docs=512)
m = ld.measure(engine, q['items'], hybrid=True)
json.dump({{'notes': store.count(), 'dense': m['dense']['recall@10'], 'dense_all': m['dense']['all_gold@10'],
           'hybrid': m['hybrid']['recall@10'], 'hybrid_all': m['hybrid']['all_gold@10']}},
          open('{tmp}/bulk.json', 'w'))
"""])
    if code != 0:
        return False, out
    got = json.loads((tmp / "bulk.json").read_text())
    if not exp_path.exists():
        exp_path.write_text(json.dumps(got, indent=1))
        return True, f"first run: recorded {got}"
    d = _diff(json.loads(exp_path.read_text()), got)
    return not d, ("\n".join(d) if d else f"ingest + retrieval identical: {got}")


def check_governor(tmp: Path) -> tuple[bool, str]:
    code, out = run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_device.py"])
    last = [ln for ln in out.splitlines() if ln.strip()][-1] if out.strip() else ""
    return code == 0, "device limits, stop and resume: " + last


CHECKS = {"tests": check_tests, "lookup-dev": check_lookup_dev, "verified-dev": check_verified_dev,
          "verified-test": check_verified_test, "bulk": check_bulk, "governor": check_governor}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--twice", action="store_true", help="run every check twice; both runs must pass")
    a = ap.parse_args()
    names = [n for n in CHECKS if not a.only or n in a.only.split(",")]
    results = []
    for rnd in range(2 if a.twice else 1):
        for name in names:
            tmp = Path(tempfile.mkdtemp(prefix=f"repro-{name}-"))
            t0 = time.perf_counter()
            try:
                ok, msg = CHECKS[name](tmp)
            except Exception as exc:  # noqa: BLE001
                ok, msg = False, f"{type(exc).__name__}: {exc}"
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            secs = time.perf_counter() - t0
            results.append((rnd + 1, name, ok, secs, msg))
            print(f"[{'PASS' if ok else 'FAIL'}] run {rnd + 1} {name:14s} {secs:6.1f}s  {msg.splitlines()[0] if msg else ''}",
                  flush=True)
            if not ok and len(msg.splitlines()) > 1:
                print("        " + "\n        ".join(msg.splitlines()[1:12]))
    bad = [r for r in results if not r[2]]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
