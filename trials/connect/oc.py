#!/usr/bin/env python3
"""Runs one question through OpenCode and prints its Burrow calls and answer.  oc.py MODEL AGENT "question" [--session ID]"""
import json, subprocess, sys, time, os
here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", "opencode")
model, agent, question = sys.argv[1:4]
extra = sys.argv[4:]
started = time.time()
done = subprocess.run(["opencode", "run", "--standalone", "--auto", "--format", "json", "-m", model, "--agent", agent, question, *extra],
                      capture_output=True, text=True, cwd=here, timeout=900,
                      env={**os.environ, "PWD": here})  # OpenCode finds its project from PWD, not the working folder
calls, text, session, error = [], "", None, None
for line in done.stdout.splitlines():
    try: e = json.loads(line)
    except json.JSONDecodeError: continue
    session = e.get("sessionID", session)
    p = e.get("part", {})
    if p.get("type") == "tool": calls.append(p.get("tool"))
    elif p.get("type") == "text": text += p.get("text", "")
    elif e.get("type") == "error": error = e["error"].get("message", "")[:200]
print(json.dumps({"model": model, "agent": agent, "calls": calls, "answer": text.strip(), "error": error,
                  "session": session, "seconds": round(time.time() - started, 1)}))
