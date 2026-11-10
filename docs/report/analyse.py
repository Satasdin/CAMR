#!/usr/bin/env python3
"""Reads the saved results and writes the tables and numbers the report uses, so that nothing is copied by hand."""
import collections, json, statistics as st
from math import comb
from pathlib import Path
HERE = Path(__file__).parent
ROOT = HERE.parent.parent
R = ROOT / "trials/results"
MODELS = [("4b", "qwen3:4b instruct"), ("8b", "qwen3:8b"), ("1.7b", "qwen3:1.7b")]
PROJECTS = ["sacco", "clinic", "matatu"]
MODES = ["none", "search", "walk"]
REPOS = ["requests", "flask", "pytest", "django"]

def held():
    rows = []
    for p in PROJECTS:
        for m, _ in MODELS:
            for l in (R / f"held-{p}-{m}/sessions.jsonl").read_text().splitlines():
                x = json.loads(l); x["model"] = m; rows.append(x)
    return rows

def real():
    out = {}
    for r in REPOS:
        out[r] = [json.loads(l) for l in (R / f"real-1/{r}.jsonl").read_text().splitlines()]
    return out

def sign(b, w):
    n = b + w
    if n == 0: return 1.0
    k = min(b, w)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

def hits(x, mode):
    gold = set(x["gold"]); files = x[mode]["files"]
    return dict(first=bool(files) and files[0] in gold, any=bool(gold & set(files)), all=gold <= set(files), recall=len(gold & set(files)) / len(gold))

if __name__ == "__main__":
    H = held(); RR = real(); ALL = [x for r in REPOS for x in RR[r]]
    print("HELD rows", len(H))
    S = [x for x in H if x["category"] != "setup"]
    for m, name in MODELS:
        for mode in MODES:
            c = [x for x in S if x["model"] == m and x["mode"] == mode]
            d = [x for x in c if x["category"] == "depends"]
            print(m, mode, "pass", sum(x["task_passed"] for x in c), "/", len(c), "broken(all scored)", sum(x["decision_broken"] for x in c), "errored", sum(x["decision_check_errored"] for x in c),
                  "noedit", sum(1 for x in c if x["kind"]=="change" and not x["edits_applied"]), "files", round(st.mean(len(x["files_read"]) for x in c),2), "sec", round(st.mean(x["seconds"] for x in c),1), "ptok", round(st.mean(x["prompt_tokens"] for x in c)), "chars", round(st.mean(x["retrieved_characters"] for x in c)), "ret_s", round(st.mean(x["retrieve_seconds"] for x in c),3), "parsefail", sum(1 for x in c if x["parse_failures"]))
        for p in PROJECTS:
            print("  ", m, p, [sum(x["task_passed"] for x in S if x["model"]==m and x["mode"]==mo and x["project"]==p) for mo in MODES])
        for cat in ("plain","depends","unknown"):
            print("  ", m, cat, [sum(x["task_passed"] for x in S if x["model"]==m and x["mode"]==mo and x["category"]==cat) for mo in MODES], "of", sum(1 for x in S if x["model"]==m and x["mode"]=="none" and x["category"]==cat))
    setup=[x for x in H if x["category"]=="setup"]
    print("setup pass", {m:[sum(x["task_passed"] for x in setup if x["model"]==m and x["mode"]==mo) for mo in MODES] for m,_ in MODELS}, len([x for x in setup if x["model"]=="4b" and x["mode"]=="none"]))
    print("said_dont_know unknown", {m:[sum(x["said_dont_know"] for x in S if x["model"]==m and x["mode"]==mo and x["category"]=="unknown") for mo in MODES] for m,_ in MODELS})
    print("REAL", len(ALL))
    sizes = collections.Counter(len(x["gold"]) for x in ALL); print("gold sizes", sorted(sizes.items()))
    for label, f in [("one", lambda g: g==1), ("two+", lambda g: g>=2)]:
        c=[x for x in ALL if f(len(x["gold"]))]
        print(label, len(c), {m:(sum(hits(x,m)["any"] for x in c), sum(hits(x,m)["all"] for x in c), round(st.mean(hits(x,m)["recall"] for x in c),3)) for m in ("search","walk")})
    neither=[x["id"] for x in ALL if not hits(x,"search")["any"] and not hits(x,"walk")["any"]]; print("neither any", len(neither), neither[:40])
    print("walk better any", [x["id"] for x in ALL if hits(x,"walk")["any"] and not hits(x,"search")["any"]])
    print("search better any", [x["id"] for x in ALL if hits(x,"search")["any"] and not hits(x,"walk")["any"]])
    for m in ("search","walk"):
        t=[x[m]["seconds"] for x in ALL]; ch=[x[m]["characters"] for x in ALL]; nf=[len(x[m]["files"]) for x in ALL]
        print(m,"sec med",round(st.median(t),3),"mean",round(st.mean(t),3),"max",round(max(t),2),"chars mean",round(st.mean(ch)),"min",min(ch),"max",max(ch),"files mean",round(st.mean(nf),2), "files med", st.median(nf))
    for r in REPOS:
        for m in ("search","walk"):
            t=[x[m]["seconds"] for x in RR[r]]
            print(r,m,"med",round(st.median(t),3),"max",round(max(t),2),"files",round(st.mean(len(x[m]["files"]) for x in RR[r]),2))
        print(r,"refresh sec after first: median",round(st.median(x["refresh_seconds"] for x in RR[r][1:]),2), "answer", [round(x["answer_seconds"],1) if x.get("answer_seconds") else None for x in RR[r][:5]], [x.get("answer_error","")[:60] for x in RR[r][:5] if x.get("answer_error")])
