#!/usr/bin/env python3
"""Evaluation 3: memory any model can pick up (docs/report/evaluation-plan-3.md).

Burrow is only the database here. This script plays the chat program: it starts the frozen `burrow mcp`, offers its
tools to a model, and runs every call the model makes against Burrow.

  e1 resume   model A holds a conversation; model B carries it on: fresh, pasted transcript, today's session tools, Ledger
  e2 notes    Claude answers half A and leaves checked notes; Qwen3 4B answers half B with and without them
  e3 trust    unanswerable and answerable questions, with and without the trust line
  e4 door     the four-tool door against the twelve classic tools

Run:  /usr/bin/python3 trials/ledger/run.py e1 e2 e3 e4 [--quick]
Results go to trials/ledger/results/<test>.json, with the frozen binary's SHA-256 in meta.json. Stdlib only.
"""
import datetime, hashlib, json, os, random, re, shutil, subprocess, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
BURROW = os.path.join(HERE, "work", "bin", "burrow-evaluation-3")
SOURCE_VAULT = os.path.join(REPO, "trials", "gap", "vault")
WORK = os.path.join(HERE, "work")
RESULTS = os.path.join(HERE, "results")
KNOWLEDGE = os.path.join(REPO, "trials", "gap", "tasks", "knowledge.jsonl")
UNANSWERABLE = os.path.join(HERE, "tasks", "unanswerable.jsonl")
QUICK = "--quick" in sys.argv
SEED = 3

OLLAMA = "http://127.0.0.1:11434"
SMALL, LARGE = "burrow-qwen3-4b-16k", "burrow-gemma4-12b-16k"
CLOUD_MODEL = "claude-sonnet-5-5"
CLOUD_LIMIT = 3_000_000          # input tokens, all of Evaluation 3
KEY_FILE = os.path.expanduser("~/.config/camr/anthropic.env")


def say(*parts):
    print(*parts, flush=True)


def save(name, data):
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, name + ".json"), "w") as f:
        json.dump(data, f, indent=1)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------- Burrow over MCP

class Burrow:
    """A client of the frozen `burrow mcp`, with the flags each arm needs."""

    def __init__(self, vault, *flags, client="evaluation-3"):
        self.proc = subprocess.Popen([BURROW, "mcp", vault, *flags], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.next = 0
        hello = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": client, "version": "1"}})
        self.instructions = hello.get("instructions", "")
        self.notify("notifications/initialized")
        self.tools = self.request("tools/list", {})["tools"]

    def notify(self, method):
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")

    def request(self, method, params):
        self.next += 1
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.next, "method": method, "params": params}) + "\n")
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("burrow mcp closed")
            message = json.loads(line)
            if message.get("id") == self.next:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message["result"]

    def call(self, name, arguments):
        # A refused call (an unknown tool, bad arguments) goes back to the model as an error, as a chat program shows it.
        try:
            result = self.request("tools/call", {"name": name, "arguments": arguments})
        except RuntimeError as problem:
            return f"Error: {problem}", True
        return "".join(part.get("text", "") for part in result.get("content", [])), bool(result.get("isError"))

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)


# ---------------------------------------------------------------- local models (Ollama, 16k aliases)

def post(url, body, timeout=900, headers=None):
    request = urllib.request.Request(url, json.dumps(body).encode(), dict({"Content-Type": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def visible(text):
    text = text or ""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


class Local:
    def __init__(self, name):
        self.name = name

    label = property(lambda self: self.name)

    def run(self, system, question, burrow=None, tools=None, history=(), most_rounds=6):
        """One question through a chat program: Burrow's tools offered, every call run, until the model answers."""
        offered = (burrow.tools if tools is None else tools) if burrow else []
        schemas = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}}
                   for t in offered]
        messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": question}]
        calls, prompt_tokens, started = [], 0, time.time()
        for round_ in range(most_rounds):
            body = {"model": self.name, "messages": messages, "stream": False, "think": False,
                    "options": {"temperature": 0, "seed": 7, "num_ctx": 16384, "num_predict": 1024}}
            if schemas and round_ < most_rounds - 1:
                body["tools"] = schemas
            out = post(OLLAMA + "/api/chat", body)
            message = out["message"]
            prompt_tokens = max(prompt_tokens, out.get("prompt_eval_count", 0))
            wanted = message.get("tool_calls") or []
            if not wanted:
                return {"answer": visible(message.get("content")), "calls": calls, "rounds": round_ + 1,
                        "prompt_tokens": prompt_tokens, "seconds": round(time.time() - started, 2)}
            messages.append(message)
            for call in wanted:
                name, arguments = call["function"]["name"], call["function"].get("arguments") or {}
                content, failed = burrow.call(name, arguments) if burrow else ("No tools here.", True)
                calls.append({"name": name, "arguments": arguments, "failed": failed, "characters": len(content),
                              "ledger_notes": "Notes earlier sessions left in the Ledger" in content})
                messages.append({"role": "tool", "tool_name": name, "content": content[:12000]})
        return {"answer": "", "calls": calls, "rounds": most_rounds, "prompt_tokens": prompt_tokens,
                "seconds": round(time.time() - started, 2), "stopped": True}


# ---------------------------------------------------------------- Claude (the cloud model), with Burrow's tools

class Cloud:
    """The Anthropic Messages API with tool use. The key never leaves this object; tokens are counted against a limit."""

    def __init__(self):
        self.input_tokens = self.output_tokens = 0
        self.__key = None
        for line in open(KEY_FILE, encoding="utf-8"):
            line = line.strip().removeprefix("export ").strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                self.__key = line.split("=", 1)[1].strip().strip("'\"")
        if not self.__key:
            raise SystemExit("no ANTHROPIC_API_KEY in %s" % KEY_FILE)

    def _send(self, payload):
        headers = {"x-api-key": self.__key, "anthropic-version": "2023-06-01"}
        wait = 4
        while True:
            try:
                return post("https://api.anthropic.com/v1/messages", payload, timeout=300, headers=headers)
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", "replace").replace(self.__key, "[key]")[:500]
                if error.code == 400 and "temperature" in body and "temperature" in payload:
                    del payload["temperature"]
                    continue
                if error.code in (429, 500, 502, 503, 529) and wait < 120:
                    time.sleep(wait)
                    wait *= 2
                    continue
                raise RuntimeError("anthropic %d: %s" % (error.code, body))

    def run(self, system, question, burrow=None, most_rounds=8):
        tools = [{"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]} for t in (burrow.tools if burrow else [])]
        messages = [{"role": "user", "content": question}]
        calls, started = [], time.time()
        for _ in range(most_rounds):
            if self.input_tokens > CLOUD_LIMIT:
                raise SystemExit("cloud token limit reached: %d" % self.input_tokens)
            payload = {"model": CLOUD_MODEL, "max_tokens": 2000, "system": system, "messages": messages, "temperature": 0}
            if tools:
                payload["tools"] = tools
            reply = self._send(payload)
            usage = reply.get("usage") or {}
            self.input_tokens += usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)
            content = reply.get("content") or []
            uses = [block for block in content if block.get("type") == "tool_use"]
            if not uses:
                text = "".join(block.get("text", "") for block in content if block.get("type") == "text").strip()
                return {"answer": text, "calls": calls, "seconds": round(time.time() - started, 2)}
            messages.append({"role": "assistant", "content": content})
            results = []
            for use in uses:
                text, failed = burrow.call(use["name"], use.get("input") or {})
                calls.append({"name": use["name"], "arguments": use.get("input") or {}, "failed": failed, "text": text})
                results.append({"type": "tool_result", "tool_use_id": use["id"], "content": text[:20000], "is_error": failed})
            messages.append({"role": "user", "content": results})
        return {"answer": "", "calls": calls, "seconds": round(time.time() - started, 2), "stopped": True}


# ---------------------------------------------------------------- tasks and scoring

def knowledge():
    return [json.loads(line) for line in open(KNOWLEDGE, encoding="utf-8") if line.strip()]


def correct(answer, task):
    low = (answer or "").lower()
    return all(any(word.lower() in low for word in group) for group in task["must_include"])


NOT_HELD = re.compile(r"(not|n't|no)\s+(in|inside|within|contain|cover|hold|mention|say|state|include|appear|found|find|information|record|have)|"
                      r"(vault|notes|documents|excerpts)\s+(do|does|did)\s*(not|n't)|unable to find|could ?n[o']t find|no (information|mention|record|data)|"
                      r"isn't covered|is not covered|nothing (in|about)|doesn't hold|does not hold", re.I)


def declines(answer):
    """True when an answer says the vault does not hold it. The pattern was written before any run and is not tuned."""
    return bool(NOT_HELD.search(answer or ""))


SYSTEM = "You are a helpful assistant on the user's own computer."


def system_for(burrow):
    return SYSTEM + "\n\n" + burrow.instructions if burrow else SYSTEM


# ---------------------------------------------------------------- setup

def fresh_vault(name):
    """A copy of the evaluation vault, indexed by the frozen binary, with no sessions and no Ledger."""
    target = os.path.join(WORK, name)
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(SOURCE_VAULT, target, ignore=shutil.ignore_patterns(".burrow"))
    subprocess.run([BURROW, "index", target, "--vault"], check=True, capture_output=True)
    return target


def meta():
    info = {"binary": BURROW, "sha256": sha256(BURROW), "seed": SEED, "quick": QUICK, "small": SMALL, "large": LARGE,
            "cloud_model": CLOUD_MODEL, "started": datetime.datetime.now().isoformat(timespec="seconds")}
    save("meta", info)
    return info


# ---------------------------------------------------------------- E1: carrying on a conversation

PROBES = ["first", "second", "third"]


def e1():
    say("E1 resume: a model that lost its memory carries on a conversation")
    vault = fresh_vault("vault-e1")
    singles = [t for t in knowledge() if t["type"] == "single"]
    law = [t for t in singles if t["subject"] == "law"]
    software = [t for t in singles if t["subject"] == "software"]
    count = 2 if QUICK else 5
    conversations = [[law[3 * i], software[3 * i + 1], law[3 * i + 2]] for i in range(count)]
    pairs = [(Local(SMALL), Local(LARGE)), (Local(LARGE), Local(SMALL))]
    rows = []
    for a, b in pairs:
        for number, conversation in enumerate(conversations):
            # Model A talks in its own connection; the chat program keeps each turn in Burrow. Closing the connection
            # is where Burrow writes the Ledger handoff, as it would when a real program quits.
            # A program that reconnects within 30 minutes carries on its last session, so each test conversation
            # names itself apart; otherwise five separate conversations would merge into one.
            talk = Burrow(vault, "--tools", "classic", client=f"{a.label} conversation {number + 1}")
            session, transcript, history = "new", [], []
            for task in conversation:
                out = a.run(system_for(talk), task["question"], burrow=talk, history=history)
                text, _ = talk.call("vault_session_log", {"session": session, "question": task["question"], "answer": out["answer"], "model": a.label})
                session = re.search(r"session (\S+?),", text).group(1)
                history += [{"role": "user", "content": task["question"]}, {"role": "assistant", "content": out["answer"]}]
                transcript.append(f"User: {task['question']}\nAssistant: {out['answer']}")
            talk.close()
            # Model B never saw it. Its own connections keep no session, so they leave no handoff of their own.
            classic = Burrow(vault, "--tools", "classic", "--no-sessions", client=b.label)
            door = Burrow(vault, "--tools", "door", "--no-sessions", "--no-ledger-notes", client=b.label)
            no_memory_tools = [t for t in classic.tools if not t["name"].startswith("vault_session")]
            for which, task in zip(PROBES, conversation):
                ask = (f"We talked earlier, with another assistant. What did you answer to my {which} question back then? "
                       f"Give the figure and the file it came from.")
                arms = {
                    "fresh": (classic, ask, no_memory_tools),
                    "paste": (classic, "Here is our earlier conversation:\n\n" + "\n\n".join(transcript) + "\n\n" + ask, no_memory_tools),
                    "sessions": (classic, "Carry on our last conversation; it is saved in Burrow. " + ask, None),
                    "ledger": (door, "Carry on our last conversation; it is saved in Burrow. " + ask, None),
                }
                for arm, (server, question, tools) in arms.items():
                    out = b.run(system_for(server), question, burrow=server, tools=tools)
                    rows.append({"from": a.label, "to": b.label, "arm": arm, "probe": which, "task": task["id"],
                                 "right": correct(out["answer"], task),
                                 "used_memory": any(c["name"] in ("burrow_resume", "vault_session_resume", "vault_session_list") for c in out["calls"]),
                                 **out})
            classic.close()
            door.close()
        for arm in ["fresh", "paste", "sessions", "ledger"]:
            mine = [r for r in rows if r["from"] == a.label and r["arm"] == arm]
            say(f"  {a.label} -> {b.label}  {arm:8}: right {sum(r['right'] for r in mine)}/{len(mine)}, "
                f"prompt tokens median {sorted(r['prompt_tokens'] for r in mine)[len(mine) // 2]}, "
                f"memory tool used {sum(r['used_memory'] for r in mine)}/{len(mine)}")
        save("e1", rows)
    save("e1", rows)


# ---------------------------------------------------------------- E2: notes from a bigger model

def e2():
    say("E2 notes: a small model reads checked notes a bigger model left")
    vault = fresh_vault("vault-e2")
    tasks = knowledge()
    random.Random(SEED).shuffle(tasks)
    half_a, half_b = tasks[: len(tasks) // 2], tasks[len(tasks) // 2:]
    if QUICK:
        half_a, half_b = half_a[:4], half_b[:4]
    save("e2-split", {"a": [t["id"] for t in half_a], "b": [t["id"] for t in half_b]})
    cloud = Cloud()
    ledger_dir = os.path.join(vault, ".burrow", "ledger")
    # Claude answers half A with the four-tool door and keeps what it confirmed.
    teacher = Burrow(vault, "--tools", "door", "--no-ledger-notes", client="claude-api")
    keep = ("\n\nAfter you answer, keep up to two facts you confirmed in the excerpts with burrow_commit "
            "(kind fact, model claude), naming the files they rest on. Only facts you read, never guesses.")
    a_rows, dropped = [], []
    for task in half_a:
        out = cloud.run(system_for(teacher), task["question"] + keep, burrow=teacher)
        shown = set()
        for call in out["calls"]:
            if call["name"] in ("burrow_find", "burrow_read"):
                shown.update(re.findall(r'<excerpt file="([^"]+)"', call["text"]))
        for call in out["calls"]:
            if call["name"] == "burrow_commit" and not call["failed"]:
                cited = {p.strip() for p in str(call["arguments"].get("files", "")).split(",") if p.strip()}
                commit_id = re.search(r"Kept as \w+ (\S+) on", call["text"])
                # A note that cites a file Claude was not shown is dropped, as the plan says.
                if commit_id and not cited <= shown:
                    for root, _, names in os.walk(ledger_dir):
                        for name in names:
                            if name.startswith(commit_id.group(1)):
                                os.remove(os.path.join(root, name))
                    dropped.append({"task": task["id"], "commit": commit_id.group(1), "cited": sorted(cited), "shown": sorted(shown)})
        a_rows.append({"task": task["id"], "right": correct(out["answer"], task),
                       "commits": sum(c["name"] == "burrow_commit" and not c["failed"] for c in out["calls"]),
                       **{k: v for k, v in out.items() if k != "calls"}, "calls": [{k: v for k, v in c.items() if k != "text"} for c in out["calls"]]})
    teacher.close()
    notes = sum(len(names) for _, _, names in os.walk(ledger_dir))
    say(f"  Claude on half A: right {sum(r['right'] for r in a_rows)}/{len(a_rows)}, notes kept {notes}, dropped {len(dropped)}")
    save("e2-teacher", {"rows": a_rows, "dropped": dropped, "cloud_tokens": [cloud.input_tokens, cloud.output_tokens]})

    small = Local(SMALL)
    with_notes = Burrow(vault, "--tools", "door", "--no-sessions", client="evaluation-3")
    without = Burrow(vault, "--tools", "door", "--no-sessions", "--no-ledger-notes", client="evaluation-3")
    rows = []
    for task in half_b:
        arms = {"alone": (None, small), "engine": (without, small), "engine+notes": (with_notes, small)}
        for arm, (server, model) in arms.items():
            out = model.run(system_for(server), task["question"], burrow=server)
            rows.append({"arm": arm, "model": model.label, "task": task["id"], "type": task["type"], "right": correct(out["answer"], task),
                         "saw_notes": any(c.get("ledger_notes") for c in out["calls"]), **out})
        cloud_out = cloud.run(SYSTEM + " Answer the question. If you cannot know the answer, say you don't know. Be brief.", task["question"])
        rows.append({"arm": "claude-alone", "model": CLOUD_MODEL, "task": task["id"], "type": task["type"],
                     "right": correct(cloud_out["answer"], task), **{k: v for k, v in cloud_out.items() if k != "calls"}})
        save("e2", rows)
    with_notes.close()
    without.close()
    for arm in ["alone", "engine", "engine+notes", "claude-alone"]:
        mine = [r for r in rows if r["arm"] == arm]
        by_type = {kind: f"{sum(r['right'] for r in mine if r['type'] == kind)}/{sum(r['type'] == kind for r in mine)}" for kind in ["single", "multi"]}
        say(f"  {arm:13}: right {sum(r['right'] for r in mine)}/{len(mine)}  {by_type}")
    save("e2", rows)
    save("e2-cloud-usage", {"input_tokens": cloud.input_tokens, "output_tokens": cloud.output_tokens})


# ---------------------------------------------------------------- E3: saying the vault does not hold it

def e3():
    say("E3 trust: does the small model say when the vault does not hold the answer")
    vault = fresh_vault("vault-e3")
    unanswerable = [json.loads(line) for line in open(UNANSWERABLE, encoding="utf-8") if line.strip()]
    singles = [t for t in knowledge() if t["type"] == "single"]
    random.Random(SEED).shuffle(singles)
    answerable = singles[:30]
    if QUICK:
        unanswerable, answerable = unanswerable[:4], answerable[:4]
    small = Local(SMALL)
    arms = {"trust": Burrow(vault, "--tools", "door", "--no-sessions", "--no-ledger-notes"),
            "no-trust": Burrow(vault, "--tools", "door", "--no-sessions", "--no-ledger-notes", "--no-trust")}
    rows = []
    for arm, server in arms.items():
        for task in unanswerable:
            out = small.run(system_for(server), task["question"], burrow=server)
            rows.append({"arm": arm, "kind": "unanswerable", "task": task["id"], "declined": declines(out["answer"]), **out})
        for task in answerable:
            out = small.run(system_for(server), task["question"], burrow=server)
            rows.append({"arm": arm, "kind": "answerable", "task": task["id"], "declined": declines(out["answer"]),
                         "right": correct(out["answer"], task), **out})
        save("e3", rows)
    for server in arms.values():
        server.close()
    for arm in arms:
        nope = [r for r in rows if r["arm"] == arm and r["kind"] == "unanswerable"]
        yes = [r for r in rows if r["arm"] == arm and r["kind"] == "answerable"]
        say(f"  {arm:8}: said not in vault {sum(r['declined'] for r in nope)}/{len(nope)} unanswerable; "
            f"answerable right {sum(r['right'] for r in yes)}/{len(yes)}, wrongly declined {sum(r['declined'] and not r['right'] for r in yes)}/{len(yes)}")
    save("e3", rows)


# ---------------------------------------------------------------- E4: four tools or twelve

LOOKUPS = {"burrow_find", "burrow_read", "vault_search", "vault_read", "vault_ask", "vault_prepare", "vault_links", "vault_list", "vault_pack"}


def e4():
    say("E4 door: four tools against twelve")
    vault = fresh_vault("vault-e4")
    singles = [t for t in knowledge() if t["type"] == "single"]
    picked = [t for t in singles if t["subject"] == "law"][:4 if QUICK else 8] + [t for t in singles if t["subject"] == "software"][:4 if QUICK else 8]
    rows = []
    for model in [Local(SMALL), Local(LARGE)]:
        for arm in ["door", "classic"]:
            server = Burrow(vault, "--tools", arm, "--no-sessions", "--no-ledger-notes")
            for task in picked:
                out = model.run(system_for(server), task["question"], burrow=server)
                rows.append({"model": model.label, "arm": arm, "task": task["id"],
                             "looked_up": any(c["name"] in LOOKUPS and not c["failed"] for c in out["calls"]),
                             "bad_calls": sum(c["failed"] for c in out["calls"]),
                             "right": correct(out["answer"], task), **out})
            server.close()
            mine = [r for r in rows if r["model"] == model.label and r["arm"] == arm]
            say(f"  {model.label} {arm:7}: looked up {sum(r['looked_up'] for r in mine)}/{len(mine)}, right {sum(r['right'] for r in mine)}/{len(mine)}, "
                f"failed calls {sum(r['bad_calls'] for r in mine)}")
            save("e4", rows)
    save("e4", rows)


if __name__ == "__main__":
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")] or ["e1", "e2", "e3", "e4"]
    if not os.path.exists(BURROW):
        raise SystemExit("freeze the binary first: " + BURROW)
    info = meta()
    say(f"frozen binary {info['sha256'][:16]}…, seed {SEED}{', quick' if QUICK else ''}")
    for name in wanted:
        globals()[name]()
