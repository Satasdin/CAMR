"""The AI service the n8n automations call: one HTTP endpoint per action, for any of the answering systems.

n8n holds the business process (loop over tickets, reply or escalate, teach a human's resolution, publish a policy
change); this service only answers, learns and forgets, and keeps a log of what the process did so the run can be
scored afterwards.

  POST /reset    {"system"}                       a fresh system with the knowledge base taught
  GET  /events                                    the scenario's events in order (policy changes, tickets)
  POST /ask      {"system", "ticket", "question"}  answer; logged
  POST /teach    {"system", "doc_id", "title", "text"}
  POST /forget   {"system", "doc_id"}
  POST /log      {"system", "ticket", "action"}   what the workflow did (reply / escalate)
  GET  /score?system=...                          score the run, save results/agentic/helio_<system>.json

    python scripts/agentic/gateway.py --port 8765
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import systems  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "data/agentic/helio.json").read_text())
FRESH_PATH = ROOT / "data/agentic/fresh.json"
STATE: dict[str, dict] = {}
AGENTS: dict[str, dict] = {}
LOCK = threading.Lock()


def events() -> list[dict]:
    out = []
    for day in sorted({t["day"] for t in DATA["tickets"]}):
        for u in DATA["updates"]:
            if u["day"] == day:
                out.append({"type": "update", "day": day, "id": u["id"], "replaces": "kb:" + u["replaces"],
                            "doc_id": "kb2:" + u["id"], "title": u["title"], "text": u["text"]})
        for t in DATA["tickets"]:
            if t["day"] == day:
                res = DATA["resolutions"].get(t["teaches"]) if t["teaches"] else None
                out.append({"type": "ticket", "day": day, "id": t["id"], "question": t["text"], "kind": t["kind"],
                            "resolution": ({"doc_id": "res:" + t["teaches"], **res} if res else None)})
    return out


def matches(text: str, needles: list[str]) -> bool:
    for n in needles:
        pat = re.escape(n.lower())
        pat = (r"(?<![\w.])" if n[:1].isalnum() else "") + pat + (r"(?![\w])" if n[-1:].isalnum() else "")
        if re.search(pat, (text or "").lower()):
            return True
    return False


def score(spec: str) -> dict:
    st = STATE[spec]
    tickets = {t["id"]: t for t in DATA["tickets"]}
    rows = []
    for tid, rec in st["answers"].items():
        t = tickets[tid]
        ans, stated = rec["answer"], rec["stated"]
        gold = matches(ans, t["gold"]) if t["gold"] else False
        stale = (not gold) and bool(t["stale"]) and matches(ans, t["stale"])
        first_learn = bool(t["teaches"])  # nobody could know it yet: a person must answer
        if not stated:
            outcome = "escalated"
        elif gold:
            outcome = "correct"
        elif stale:
            outcome = "stale"
        else:
            outcome = "wrong"
        rows.append({"ticket": tid, "day": t["day"], "kind": t["kind"], "first_time": first_learn,
                     "question": t["text"], "answer": ans[:240], "stated": stated, "outcome": outcome,
                     "action": st["actions"].get(tid), **{k: rec.get(k) for k in ("calls", "prompt_tokens",
                                                                                   "gen_tokens", "model_ms",
                                                                                   "wall_ms", "cost_usd")}})
    n = len(rows) or 1
    should_escalate = [r for r in rows if r["kind"] == "unknown" or r["first_time"]]
    answerable = [r for r in rows if not (r["kind"] == "unknown" or r["first_time"])]
    by_kind = {}
    for k in ("kb", "learned", "update", "unknown"):
        sel = [r for r in rows if r["kind"] == k and not r["first_time"]]
        by_kind[k] = {o: sum(r["outcome"] == o for r in sel) for o in ("correct", "wrong", "stale", "escalated")}
        by_kind[k]["n"] = len(sel)
    summary = {
        "tickets": len(rows),
        "auto_resolved_correct": sum(r["outcome"] == "correct" for r in rows) / n,
        "wrong_replies": sum(r["outcome"] in ("wrong", "stale") for r in rows) / n,
        "escalated": sum(r["outcome"] == "escalated" for r in rows) / n,
        "answerable_correct": sum(r["outcome"] == "correct" for r in answerable) / max(1, len(answerable)),
        "unanswerable_escalated": sum(r["outcome"] == "escalated" for r in should_escalate) /
        max(1, len(should_escalate)),
        "by_kind": by_kind,
        "seconds_per_ticket": sum(r["wall_ms"] or 0 for r in rows) / n / 1000,
        "model_calls": sum(r["calls"] or 0 for r in rows),
        "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows),
        "gen_tokens": sum(r["gen_tokens"] or 0 for r in rows),
        "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 4),
    }
    summary["cost_usd_per_1000_tickets"] = round(summary["cost_usd"] / n * 1000, 2)
    out = {"system": spec, "summary": summary, "per_ticket": rows, "started": st["started"],
           "finished": time.time(), "teach_events": st["teaches"], "forget_events": st["forgets"]}
    path = ROOT / "results/agentic" / f"helio_{spec.replace(':', '_').replace('.', '_')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    return out


def agent_score(spec: str) -> dict:
    st = AGENTS[spec]
    rows = list(st["results"].values())
    n = len(rows) or 1
    summary = {"tasks": len(rows), "success": sum(r["success"] for r in rows) / n,
               "hallucinated_actions": sum(r["hallucinated_action"] for r in rows) / n,
               "escalated": sum(r["escalated"] for r in rows) / n,
               "steps_per_task": sum(r["steps"] for r in rows) / n,
               "seconds_per_task": sum(r["wall_s"] for r in rows) / n,
               "prompt_tokens": sum(r["prompt_tokens"] for r in rows), "gen_tokens": sum(r["gen_tokens"] for r in rows),
               "cost_usd": round(sum(r["cost_usd"] for r in rows), 4)}
    summary["cost_usd_per_1000_tasks"] = round(summary["cost_usd"] / n * 1000, 2)
    out = {"config": spec, "summary": summary, "per_task": rows}
    path = ROOT / "results/agentic" / f"agent_{spec.replace(':', '_').replace('.', '_').replace('+', '__')}.json"
    path.write_text(json.dumps(out, indent=1))
    return out


def fresh() -> dict:
    return json.loads(FRESH_PATH.read_text())


def fresh_score(spec: str) -> dict:
    st = STATE[spec]
    rows = []
    for q in fresh()["questions"]:
        rec = st["answers"].get(q["id"])
        if rec is None:
            continue
        ans, stated = rec["answer"], rec["stated"]
        outcome = "declined" if not stated else "correct" if matches(ans, q["gold"]) else "wrong"
        rows.append({"id": q["id"], "date": q["date"], "question": q["question"], "gold": q["gold"],
                     "answer": ans[:240], "stated": stated, "outcome": outcome,
                     **{k: rec.get(k) for k in ("calls", "prompt_tokens", "gen_tokens", "model_ms", "wall_ms",
                                                "cost_usd")}})
    n = len(rows) or 1
    summary = {"questions": len(rows), "correct": sum(r["outcome"] == "correct" for r in rows) / n,
               "wrong_stated": sum(r["outcome"] == "wrong" for r in rows) / n,
               "declined": sum(r["outcome"] == "declined" for r in rows) / n,
               "seconds_per_question": sum(r["wall_ms"] or 0 for r in rows) / n / 1000,
               "prompt_tokens": sum(r["prompt_tokens"] or 0 for r in rows),
               "gen_tokens": sum(r["gen_tokens"] or 0 for r in rows),
               "cost_usd": round(sum(r["cost_usd"] or 0 for r in rows), 4),
               "items_taught": st.get("items", 0), "pages_taught": st.get("pages", 0),
               "pages_live": st.get("pages_live", 0), "pages_cached": st.get("pages_cached", 0)}
    summary["cost_usd_per_1000_questions"] = round(summary["cost_usd"] / n * 1000, 2)
    out = {"system": spec, "scenario": "fresh", "summary": summary, "per_question": rows}
    path = ROOT / "results/agentic" / f"fresh_{spec.replace(':', '_').replace('.', '_')}.json"
    path.write_text(json.dumps(out, indent=1))
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code: int = 200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # quiet
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/events":
            return self._send(events())
        if u.path == "/fresh/pages":
            f = fresh()
            return self._send([{"page": p, "date": d} for p, d in zip(f["pages"], f["days"])])
        if u.path == "/fresh/questions":
            return self._send([{"id": q["id"], "question": q["question"]} for q in fresh()["questions"]])
        if u.path == "/fresh/score":
            spec = parse_qs(u.query).get("system", [""])[0]
            with LOCK:
                return self._send(fresh_score(spec)["summary"])
        if u.path == "/agent/tasks":
            import agent

            return self._send([{"id": t["id"], "task": t["task"]} for t in agent.TASKS])
        if u.path == "/agent/score":
            spec = parse_qs(u.query).get("config", [""])[0]
            with LOCK:
                return self._send(agent_score(spec)["summary"])
        if u.path == "/score":
            spec = parse_qs(u.query).get("system", [""])[0]
            with LOCK:
                return self._send(score(spec)["summary"])
        return self._send({"error": "not found"}, 404)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        spec = body.get("system", "")
        path = urlparse(self.path).path
        try:
            with LOCK:
                if path == "/agent/run":
                    import agent

                    spec = body["config"]
                    if spec not in AGENTS or body.get("reset"):
                        model, memory = spec.rsplit("+", 1) if "+" in spec else (spec, "none")
                        AGENTS[spec] = {"agent": agent.Agent(model, memory), "results": {}, "started": time.time()}
                    task = next(t for t in agent.TASKS if t["id"] == body["task"])
                    res = AGENTS[spec]["agent"].run(task)
                    AGENTS[spec]["results"][task["id"]] = res
                    return self._send(res)
                if path == "/reset":
                    s = systems.make(spec, body.get("scenario", "helio"))
                    if body.get("scenario", "helio") == "helio":
                        for d in DATA["kb"]:
                            s.teach("kb:" + d["title"], d["title"], d["text"])
                    STATE[spec] = {"system": s, "answers": {}, "actions": {}, "teaches": 0, "forgets": 0,
                                   "started": time.time()}
                    return self._send({"ok": True, "system": spec, "documents": len(DATA["kb"])})
                st = STATE[spec]
                if path == "/ask":
                    res = st["system"].ask(body["question"])
                    st["answers"][body["ticket"]] = res
                    return self._send({"ticket": body["ticket"], **{k: v for k, v in res.items()}})
                if path == "/teach_wikitext":  # a Current events page as fetched by the workflow: one note per item
                    import fresh_data

                    text = body.get("wikitext")
                    live = isinstance(text, str) and text.lstrip().startswith(("*", "{", "<", "="))
                    if not live:  # the live fetch failed (Wikimedia refused it): the page as cached when the
                        import datetime as dt  # questions were written

                        text = fresh_data.fetch(dt.date.fromisoformat(body["date"]))
                    st["pages_live" if live else "pages_cached"] = st.get("pages_live" if live else "pages_cached", 0) + 1
                    items = fresh_data.parse(text or "")
                    for k, item in enumerate(items):
                        st["system"].teach(f"{body['page']}#{k}", f"Current events, {body['date']}", item)
                    st["items"] = st.get("items", 0) + len(items)
                    st["pages"] = st.get("pages", 0) + 1
                    return self._send({"ok": True, "items": len(items)})
                if path == "/teach":
                    st["system"].teach(body["doc_id"], body["title"], body["text"])
                    st["teaches"] += 1
                    return self._send({"ok": True})
                if path == "/forget":
                    st["system"].forget(body["doc_id"])
                    st["forgets"] += 1
                    return self._send({"ok": True})
                if path == "/log":
                    st["actions"][body["ticket"]] = body["action"]
                    return self._send({"ok": True})
        except Exception as exc:  # noqa: BLE001  (reported to the workflow, which records it)
            return self._send({"error": f"{type(exc).__name__}: {exc}"}, 500)
        return self._send({"error": "not found"}, 404)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    print(f"gateway on http://127.0.0.1:{a.port}", flush=True)
    HTTPServer(("127.0.0.1", a.port), Handler).serve_forever()  # one thread: the stores are SQLite
