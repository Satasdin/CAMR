#!/usr/bin/env python3
"""Website trial: the same three briefs to a local model and a cloud model, each in three set-ups: alone; with what the Burrow engine
prepares (`burrow brief`); and with the skill and the note of known failures handed over by hand.

usage: run_web.py local <model> | cloud <model>     writes out/<task>-<setup>.html and out/log.jsonl"""
import json, os, re, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
BURROW = os.path.join(HERE, "..", "gap", "work", "bin", "burrow-evaluation-2")
TASKS = json.load(open(os.path.join(HERE, "tasks.json")))
PLAIN = "You write web pages. Reply with one complete HTML file in a single code block."
SKILL = open(os.path.join(HERE, "vault", "Skills", "Build a web page.md")).read().split("---", 2)[2].strip()
NOTES = open(os.path.join(HERE, "vault", "Web", "Failures seen in generated web pages.md")).read().split("---", 2)[2].strip()

def page(text):
    blocks = re.findall(r"```(?:html)?\s*\n(.*?)```", text, flags=re.S)
    if blocks:
        return max(blocks, key=len)
    start = text.find("<!DOCTYPE")
    return text[start:] if start >= 0 else text

def local(model, system, user):
    body = {"model": model, "stream": False, "think": False, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0, "seed": 7, "num_ctx": 16384, "num_predict": 8192}}
    call = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    reply = json.load(urllib.request.urlopen(call, timeout=1800))
    return reply["message"]["content"], reply.get("prompt_eval_count", 0), reply.get("eval_count", 0)

def cloud(model, system, user):
    key = None
    for line in open(os.path.expanduser("~/.config/camr/anthropic.env")):
        line = line.strip().removeprefix("export ").strip()
        if line.startswith("ANTHROPIC_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
    body = {"model": model, "max_tokens": 16000, "system": system, "messages": [{"role": "user", "content": user}]}
    call = urllib.request.Request("https://api.anthropic.com/v1/messages", data=json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    reply = json.load(urllib.request.urlopen(call, timeout=900))
    text = "".join(part.get("text", "") for part in reply["content"] if part.get("type") == "text")
    return text, reply["usage"]["input_tokens"], reply["usage"]["output_tokens"]

def brief(question):
    out = subprocess.run([BURROW, "brief", os.path.join(HERE, "vault"), question, "--vault", "--store", os.path.join(HERE, "store"), "--json"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out.strip().split("\n")[-1])

kind, model = sys.argv[1], sys.argv[2]
ask = local if kind == "local" else cloud
log = open(os.path.join(HERE, "out", "log.jsonl"), "a")
for task in TASKS:
    for setup in ("alone", "engine", "full"):
        target = os.path.join(HERE, "out", f"{task['id']}-{kind}-{setup}.html")
        if os.path.exists(target):
            continue
        record = {"task": task["id"], "kind": kind, "model": model, "setup": setup}
        if setup == "alone":
            system, user = PLAIN, task["brief"]
        elif setup == "engine":
            # Exactly what the frozen engine prepares for this brief, given to whichever model is answering.
            packed = brief(task["brief"])
            system, user = packed["system"] + "\n\nReply with one complete HTML file in a single code block.", packed["user"]
            record.update(route=packed["route"], skills=packed["skills"], excerpts=[e["path"] for e in packed["excerpts"]])
        else:
            # The skill and the note of known failures, both handed over by hand.
            system = PLAIN + "\n\nA method for this kind of task. Follow it where it fits:\n" + SKILL + "\n\nNotes from the project's own records:\n" + NOTES
            user = task["brief"]
        began = time.time()
        text, read, written = ask(model, system, user)
        record.update(seconds=round(time.time() - began, 1), tokens_read=read, tokens_written=written, characters=len(text))
        open(target, "w").write(page(text))
        log.write(json.dumps(record) + "\n"); log.flush()
        print(record, flush=True)
