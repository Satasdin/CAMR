"""n8n workflows for the support-desk scenario, one per answering system, and a runner that executes them headless.

The workflow is the business process; the answering system is the only thing that changes between runs:

  Start -> Reset system -> Get events -> Loop over events
     policy change:  Withdraw old policy -> Publish new policy -> (next event)
     ticket:         Answer ticket -> Verified?
                        yes: Send reply                        -> (next event)
                        no:  Escalate to agent -> Agent resolved? -> Teach resolution -> (next event)
  (loop done) -> Score run

    python scripts/agentic/n8n_workflows.py write
    python scripts/agentic/n8n_workflows.py run --systems camr:llama3.2:3b,rag:llama3.2:3b
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/agentic/n8n"
GW = "http://127.0.0.1:8765"  # default; --gateway overrides
N8N = "/root/n8n/node_modules/.bin/n8n"
NODE24 = "/root/node24/bin"
LOOP = "Loop over events"


def wid(spec: str) -> str:
    return hashlib.sha1(spec.encode()).hexdigest()[:16]


def http(name, pos, method, path, body=None):
    p = {"method": method, "url": GW + path, "options": {"timeout": 900000}}
    if body is not None:
        p.update(sendBody=True, specifyBody="json", jsonBody=body)
    return {"id": hashlib.sha1(name.encode()).hexdigest()[:8] + "-0000-4000-8000-000000000000", "name": name,
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos, "parameters": p}


def if_node(name, pos, left, operator, right=None):
    cond = {"id": hashlib.sha1((name + "c").encode()).hexdigest()[:8] + "-1111-4000-8000-000000000000",
            "leftValue": left, "operator": operator}
    if right is not None:
        cond["rightValue"] = right
    return {"id": hashlib.sha1(name.encode()).hexdigest()[:8] + "-0000-4000-8000-000000000000", "name": name,
            "type": "n8n-nodes-base.if", "typeVersion": 2, "position": pos,
            "parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "",
                                                      "typeValidation": "loose"},
                                          "conditions": [cond], "combinator": "and"}, "options": {}}}


def workflow(spec: str) -> dict:
    s = json.dumps(spec)
    ev = f"$('{LOOP}').item.json"
    nodes = [
        {"id": "00000001-0000-4000-8000-000000000000", "name": "Start", "type": "n8n-nodes-base.manualTrigger",
         "typeVersion": 1, "position": [0, 300], "parameters": {}},
        http("Reset system", [220, 300], "POST", "/reset", f"={{{{ JSON.stringify({{system: {s}}}) }}}}"),
        http("Get events", [440, 300], "GET", "/events"),
        {"id": "00000002-0000-4000-8000-000000000000", "name": LOOP, "type": "n8n-nodes-base.splitInBatches",
         "typeVersion": 3, "position": [660, 300], "parameters": {"batchSize": 1, "options": {}}},
        if_node("Policy change?", [880, 300], "={{ $json.type }}", {"type": "string", "operation": "equals"},
                "update"),
        http("Withdraw old policy", [1100, 120], "POST", "/forget",
             f"={{{{ JSON.stringify({{system: {s}, doc_id: $json.replaces}}) }}}}"),
        http("Publish new policy", [1320, 120], "POST", "/teach",
             f"={{{{ JSON.stringify({{system: {s}, doc_id: {ev}.doc_id, title: {ev}.title, text: {ev}.text}}) }}}}"),
        http("Answer ticket", [1100, 420], "POST", "/ask",
             f"={{{{ JSON.stringify({{system: {s}, ticket: $json.id, question: $json.question}}) }}}}"),
        if_node("Verified?", [1320, 420], "={{ $json.stated }}", {"type": "boolean", "operation": "true",
                                                                  "singleValue": True}),
        http("Send reply", [1540, 320], "POST", "/log",
             f"={{{{ JSON.stringify({{system: {s}, ticket: {ev}.id, action: 'reply'}}) }}}}"),
        http("Escalate to agent", [1540, 540], "POST", "/log",
             f"={{{{ JSON.stringify({{system: {s}, ticket: {ev}.id, action: 'escalate'}}) }}}}"),
        if_node("Agent resolved?", [1760, 540], f"={{{{ {ev}.resolution ? 'yes' : 'no' }}}}",
                {"type": "string", "operation": "equals"}, "yes"),
        http("Teach resolution", [1980, 480], "POST", "/teach",
             f"={{{{ JSON.stringify({{system: {s}, doc_id: {ev}.resolution.doc_id, title: {ev}.resolution.title, "
             f"text: {ev}.resolution.text}}) }}}}"),
        http("Score run", [880, 60], "GET", f"/score?system={quote(spec)}"),
    ]

    def to(*names):
        return [[{"node": n, "type": "main", "index": 0} for n in names]]

    conn = {
        "Start": {"main": to("Reset system")},
        "Reset system": {"main": to("Get events")},
        "Get events": {"main": to(LOOP)},
        LOOP: {"main": [[{"node": "Score run", "type": "main", "index": 0}],
                        [{"node": "Policy change?", "type": "main", "index": 0}]]},
        "Policy change?": {"main": [[{"node": "Withdraw old policy", "type": "main", "index": 0}],
                                    [{"node": "Answer ticket", "type": "main", "index": 0}]]},
        "Withdraw old policy": {"main": to("Publish new policy")},
        "Publish new policy": {"main": to(LOOP)},
        "Answer ticket": {"main": to("Verified?")},
        "Verified?": {"main": [[{"node": "Send reply", "type": "main", "index": 0}],
                               [{"node": "Escalate to agent", "type": "main", "index": 0}]]},
        "Send reply": {"main": to(LOOP)},
        "Escalate to agent": {"main": to("Agent resolved?")},
        "Agent resolved?": {"main": [[{"node": "Teach resolution", "type": "main", "index": 0}],
                                     [{"node": LOOP, "type": "main", "index": 0}]]},
        "Teach resolution": {"main": to(LOOP)},
    }
    return {"id": wid(spec), "name": f"Helio support desk ({spec})", "nodes": nodes, "connections": conn,
            "settings": {"executionOrder": "v1"}, "active": False, "pinData": {}}


def agent_workflow(config: str, gw: str) -> dict:
    """Agent tasks: Start -> Get tasks -> Loop -> Run agent -> Completed? (yes: Record success / no: Hand to a
    person) -> (next task); loop done -> Score agent."""
    c = json.dumps(config)
    loop = "Loop over tasks"

    def h(name, pos, method, path, body=None):
        n = http(name, pos, method, path, body)
        n["parameters"]["url"] = gw + path
        return n

    nodes = [
        {"id": "00000011-0000-4000-8000-000000000000", "name": "Start", "type": "n8n-nodes-base.manualTrigger",
         "typeVersion": 1, "position": [0, 300], "parameters": {}},
        h("Get tasks", [220, 300], "GET", "/agent/tasks"),
        {"id": "00000012-0000-4000-8000-000000000000", "name": loop, "type": "n8n-nodes-base.splitInBatches",
         "typeVersion": 3, "position": [440, 300], "parameters": {"batchSize": 1, "options": {}}},
        h("Run agent on task", [660, 380], "POST", "/agent/run",
          f"={{{{ JSON.stringify({{config: {c}, task: $json.id}}) }}}}"),
        if_node("Completed by the agent?", [880, 380], "={{ $json.escalated }}",
                {"type": "boolean", "operation": "false", "singleValue": True}),
        {"id": "00000013-0000-4000-8000-000000000000", "name": "Record completion", "type": "n8n-nodes-base.noOp",
         "typeVersion": 1, "position": [1100, 300], "parameters": {}},
        {"id": "00000014-0000-4000-8000-000000000000", "name": "Hand to a person", "type": "n8n-nodes-base.noOp",
         "typeVersion": 1, "position": [1100, 460], "parameters": {}},
        h("Score agent", [660, 120], "GET", f"/agent/score?config={quote(config)}"),
    ]
    conn = {"Start": {"main": [[{"node": "Get tasks", "type": "main", "index": 0}]]},
            "Get tasks": {"main": [[{"node": loop, "type": "main", "index": 0}]]},
            loop: {"main": [[{"node": "Score agent", "type": "main", "index": 0}],
                            [{"node": "Run agent on task", "type": "main", "index": 0}]]},
            "Run agent on task": {"main": [[{"node": "Completed by the agent?", "type": "main", "index": 0}]]},
            "Completed by the agent?": {"main": [[{"node": "Record completion", "type": "main", "index": 0}],
                                                 [{"node": "Hand to a person", "type": "main", "index": 0}]]},
            "Record completion": {"main": [[{"node": loop, "type": "main", "index": 0}]]},
            "Hand to a person": {"main": [[{"node": loop, "type": "main", "index": 0}]]}}
    return {"id": wid("agent:" + config), "name": f"Helio operations agent ({config})", "nodes": nodes,
            "connections": conn, "settings": {"executionOrder": "v1"}, "active": False, "pinData": {}}

def fresh_workflow(spec: str) -> dict:
    """Real data: Start -> Reset -> Get pages -> Loop over days -> Fetch page from Wikipedia (live, with retries)
    -> Teach page -> (next day); days done -> Get questions -> Loop over questions -> Answer -> (next); done -> Score."""
    s = json.dumps(spec)
    days, qs = "Loop over days", "Loop over questions"
    fetch = {"id": "00000021-0000-4000-8000-000000000000", "name": "Fetch page from Wikipedia",
             "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [880, 380],
             "retryOnFail": True, "maxTries": 5, "waitBetweenTries": 5000,
             "parameters": {"method": "GET", "url": "https://en.wikipedia.org/w/index.php",
                            "sendQuery": True, "queryParameters": {"parameters": [
                                {"name": "title", "value": "={{ $json.page }}"}, {"name": "action", "value": "raw"}]},
                            "sendHeaders": True, "headerParameters": {"parameters": [
                                {"name": "User-Agent", "value": "CAMR/0.4 (research prototype; n8n workflow)"}]},
                            "options": {"timeout": 60000, "response": {"response": {"responseFormat": "text",
                                                                                    "outputPropertyName": "wikitext"}},
                                        "batching": {"batch": {"batchSize": 1, "batchInterval": 1500}}}}}
    nodes = [
        {"id": "00000020-0000-4000-8000-000000000000", "name": "Start", "type": "n8n-nodes-base.manualTrigger",
         "typeVersion": 1, "position": [0, 300], "parameters": {}},
        http("Reset system", [220, 300], "POST", "/reset",
             f"={{{{ JSON.stringify({{system: {s}, scenario: 'fresh'}}) }}}}"),
        http("Get pages", [440, 300], "GET", "/fresh/pages"),
        {"id": "00000022-0000-4000-8000-000000000000", "name": days, "type": "n8n-nodes-base.splitInBatches",
         "typeVersion": 3, "position": [660, 300], "parameters": {"batchSize": 1, "options": {}}},
        fetch,
        http("Teach page", [1100, 380], "POST", "/teach_wikitext",
             f"={{{{ JSON.stringify({{system: {s}, page: $('{days}').item.json.page, "
             f"date: $('{days}').item.json.date, wikitext: $json.wikitext}}) }}}}"),
        http("Get questions", [880, 120], "GET", "/fresh/questions"),
        {"id": "00000023-0000-4000-8000-000000000000", "name": qs, "type": "n8n-nodes-base.splitInBatches",
         "typeVersion": 3, "position": [1100, 120], "parameters": {"batchSize": 1, "options": {}}},
        http("Answer question", [1320, 200], "POST", "/ask",
             f"={{{{ JSON.stringify({{system: {s}, ticket: $json.id, question: $json.question}}) }}}}"),
        http("Score", [1320, 20], "GET", f"/fresh/score?system={quote(spec)}"),
    ]
    one = lambda n: [[{"node": n, "type": "main", "index": 0}]]  # noqa: E731
    conn = {"Start": {"main": one("Reset system")}, "Reset system": {"main": one("Get pages")},
            "Get pages": {"main": one(days)},
            days: {"main": [[{"node": "Get questions", "type": "main", "index": 0}],
                            [{"node": "Fetch page from Wikipedia", "type": "main", "index": 0}]]},
            "Fetch page from Wikipedia": {"main": one("Teach page")}, "Teach page": {"main": one(days)},
            "Get questions": {"main": one(qs)},
            qs: {"main": [[{"node": "Score", "type": "main", "index": 0}],
                          [{"node": "Answer question", "type": "main", "index": 0}]]},
            "Answer question": {"main": one(qs)}}
    return {"id": wid("fresh:" + spec), "name": f"Current events digest ({spec})", "nodes": nodes,
            "connections": conn, "settings": {"executionOrder": "v1"}, "active": False, "pinData": {}}

def write(a) -> list[Path]:
    global GW
    GW = a.gateway  # every HTTP node of the written workflows calls this gateway
    OUT.mkdir(parents=True, exist_ok=True)
    paths = []
    for spec in a.systems.split(","):
        if a.kind == "fresh":
            p = OUT / f"fresh_{spec.replace(':', '_').replace('.', '_')}.json"
            p.write_text(json.dumps(fresh_workflow(spec), indent=1))
        elif a.kind == "agent":
            p = OUT / f"agent_{spec.replace(':', '_').replace('.', '_').replace('+', '__')}.json"
            p.write_text(json.dumps(agent_workflow(spec, a.gateway), indent=1))
        else:
            p = OUT / f"helio_{spec.replace(':', '_').replace('.', '_')}.json"
            p.write_text(json.dumps(workflow(spec), indent=1))
        paths.append(p)
        print(p)
    return paths


def n8n(*args, timeout=7200, broker_port=5679) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": f"{NODE24}:{os.environ['PATH']}", "N8N_DIAGNOSTICS_ENABLED": "false",
           "N8N_RUNNERS_BROKER_PORT": str(broker_port),
           "N8N_RUNNERS_ENABLED": "false", "N8N_LOG_LEVEL": "warn", "N8N_BLOCK_ENV_ACCESS_IN_NODE": "false"}
    return subprocess.run([N8N, *args], capture_output=True, text=True, env=env, timeout=timeout, cwd="/root/n8n")


def run(a) -> None:
    for p in write(a):
        wf = json.loads(p.read_text())
        r = n8n("import:workflow", f"--input={p}", broker_port=a.broker_port)
        if r.returncode != 0:
            print("import failed", r.stdout[-800:], r.stderr[-800:])
            continue
        t0 = time.time()
        r = n8n("execute", f"--id={wf['id']}", "--rawOutput", broker_port=a.broker_port)
        log = OUT / (p.stem + ".log")
        log.write_text((r.stdout or "") + "\n--- stderr ---\n" + (r.stderr or ""))
        print(f"{wf['name']}: n8n exit {r.returncode} in {time.time() - t0:.0f}s (log {log.name})", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["write", "run"])
    ap.add_argument("--kind", default="helio", choices=["helio", "agent", "fresh"])
    ap.add_argument("--gateway", default=GW)
    ap.add_argument("--broker-port", type=int, default=5679)
    ap.add_argument("--systems", default="llm:llama3.2:3b,stuff:llama3.2:3b,rag:llama3.2:3b,camr:llama3.2:3b,"
                                        "camr:qwen2.5:0.5b,llm:kimi-k3,stuff:kimi-k3,camr:kimi-k3")
    a = ap.parse_args()
    {"write": write, "run": run}[a.part](a)
