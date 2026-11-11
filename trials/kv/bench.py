"""PP/TG bench on a llama.cpp server: a folder pack read cold vs restored from a saved slot, and TG on answer tasks.

usage: python3 bench.py <port> <label> <out.json> [--slot N] [--no-restore]
"""
import json, os, sys, time, urllib.request

VAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault")
PORT, LABEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SLOT = int(sys.argv[sys.argv.index("--slot") + 1]) if "--slot" in sys.argv else 1
BASE = f"http://127.0.0.1:{PORT}"


def call(path, body=None):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())


def pack(paths):
    parts = ["The user's documents from their Burrow vault follow. Answer from them and name the file and line for each fact.\n"]
    for p in paths:
        text = open(os.path.join(VAULT, p), encoding="utf-8").read()
        numbered = text if "--plain" in sys.argv else "\n".join(f"{i + 1}: {line}" for i, line in enumerate(text.split("\n")))
        parts.append(f'<excerpt file="{p}">\n{numbered}\n</excerpt>\n')
    return "\n".join(parts) + "\n"


def chat_prefix(text):
    # Pack is the start of the first user turn, so the template's opening is a fixed prefix.
    return "<|im_start|>user\n" + text


def ask(prefix, question, predict=400):
    prompt = prefix + "Question: " + question + "<|im_end|>\n<|im_start|>assistant\n"
    out = call("/completion", {"prompt": prompt, "n_predict": predict, "cache_prompt": True, "id_slot": SLOT,
                               "temperature": 0, "seed": 7})
    t = out["timings"]
    return {"prompt_n": t["prompt_n"], "prompt_ms": t["prompt_ms"], "predicted_n": t["predicted_n"],
            "predicted_ms": t["predicted_ms"], "tg_per_s": t["predicted_per_second"],
            "pp_per_s": t.get("prompt_per_second"), "draft_n": t.get("draft_n", 0),
            "draft_accepted": t.get("draft_n_accepted", 0), "answer_head": out["content"][:160]}


CORE = ["Project/Sources/BurrowCore/" + f for f in
        ["Ask.swift", "Chunker.swift", "Database.swift", "Links.swift", "Ollama.swift", "Retrieval.swift", "Scanner.swift",
         "Standing.swift", "Vault.swift"]]
LAW = ["Law/act-part-04a-principles-and-rights.md", "Law/act-part-04b-obligations-and-breach.md",
       "Law/act-part-05-sensitive-personal-data.md"]
TASKS = [
    ("code-copy", CORE, "Copy the function that splits a file into pieces in Chunker.swift exactly as written, then say in one sentence what it does."),
    ("code-edit", CORE, "Rewrite Scanner.swift's digest function so it also accepts a String, showing the whole new function."),
    ("code-explain", CORE, "Explain in five sentences how Retrieval.swift ranks files. Cite file:line."),
    ("prose-explain", LAW, "What must a data controller do after a personal data breach? Answer in five sentences citing file:line."),
]

results = {"label": LABEL, "server": call("/props")["model_alias"], "tasks": []}
for name, paths, question in TASKS:
    text = chat_prefix(pack(paths))
    key = f"bench-{name}.bin"
    call(f"/slots/{SLOT}?action=erase", {})
    cold = ask(text, question)                         # reads the pack and the question
    call(f"/slots/{SLOT}?action=erase", {})
    built = call("/completion", {"prompt": text, "n_predict": 0, "cache_prompt": True, "id_slot": SLOT})["timings"]
    saved = call(f"/slots/{SLOT}?action=save", {"filename": key})
    call(f"/slots/{SLOT}?action=erase", {})
    start = time.time()
    call(f"/slots/{SLOT}?action=restore", {"filename": key})
    restore_s = time.time() - start
    warm = ask(text, question)                         # only the question is read
    row = {"task": name, "pack_tokens": built["prompt_n"], "build_s": built["prompt_ms"] / 1000,
           "file_mb": saved.get("n_written", 0) / 1e6, "restore_s": restore_s, "cold": cold, "warm": warm}
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "answer_head"}) for k, v in row.items()}), flush=True)
    results["tasks"].append(row)

json.dump(results, open(OUT, "w"), indent=2)
