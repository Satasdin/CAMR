#!/usr/bin/env python3
"""Connect trial: chat programs use Burrow as their memory, through MCP and tool calls.

Burrow is only the database here. This script plays the chat program a person would use (the part LM Studio, Ollama's
apps, llama.cpp's server UI or Claude Code play): it starts `burrow mcp`, lists Burrow's tools, hands them to a model,
and runs every tool call the model makes against Burrow. Nothing in Burrow's own chat is used.

  T1 connect   each route opens the vault, lists the tools and makes one call
  T2 tools     vault questions; does the model call Burrow by itself, and is it right
  T3 handoff   model A holds a conversation that the client keeps in Burrow; model B, on another route, is asked about it
               three ways: fresh (nothing), paste (the transcript pasted in), burrow (B finds it with the session tools)
  T4 claude    Claude Code, through MCP, picks up a conversation a local model left in Burrow

Run:  /usr/bin/python3 trials/connect/run.py [t1 t2 t3 t4] [--quick]
Results go to trials/connect/results/<test>.json. Stdlib only.
"""
import json, os, re, shutil, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
BURROW = os.path.join(REPO, ".build", "release", "burrow")
SOURCE_VAULT = os.path.join(REPO, "trials", "gap", "vault")
WORK = os.path.join(HERE, "work")
VAULT = os.path.join(WORK, "vault")
RESULTS = os.path.join(HERE, "results")
TASKS = os.path.join(REPO, "trials", "gap", "tasks", "knowledge.jsonl")
QUICK = "--quick" in sys.argv

ROUTES = {
    # name: (protocol, base address)
    "ollama": ("ollama", "http://127.0.0.1:11434"),
    "openai": ("openai", "http://127.0.0.1:11434/v1"),   # Ollama's OpenAI route: the format LM Studio and llama.cpp serve
    "llamacpp": ("openai", "http://127.0.0.1:8080/v1"),  # llama-server --jinja -c 16384, the same GGUF as SMALL
    "lmstudio": ("openai", "http://127.0.0.1:1234/v1"),
}
SMALL, LARGE = "burrow-qwen3-4b-16k", "burrow-gemma4-12b-16k"   # 16,384-token aliases (modelfiles/): the OpenAI route cannot set the context itself


# ---------------------------------------------------------------- Burrow over MCP

class Burrow:
    """A client of `burrow mcp`: one JSON-RPC message per line on stdin and stdout."""

    def __init__(self, vault=VAULT):
        self.proc = subprocess.Popen([BURROW, "mcp", vault], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.next = 0
        started = time.time()
        hello = self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "connect-trial", "version": "1"}})
        self.instructions = hello.get("instructions", "")
        self.server = hello.get("serverInfo", {})
        self.notify("notifications/initialized")
        self.tools = self.request("tools/list", {})["tools"]
        self.handshake_seconds = time.time() - started

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
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        return "".join(part.get("text", "") for part in result.get("content", [])), bool(result.get("isError"))

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=10)


# ---------------------------------------------------------------- the model side of a chat program

def post(url, body, timeout=900):
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())

def visible(text):
    text = text or ""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()

class Model:
    def __init__(self, name, route):
        self.name, self.route = name, route
        self.protocol, self.base = ROUTES[route]

    @property
    def label(self):
        return f"{self.name} ({self.route})"

    def schemas(self, tools):
        return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                  "parameters": t["inputSchema"]}} for t in tools]

    def turn(self, messages, tools):
        """One reply: (text, [(id, name, arguments)], prompt tokens, the message to keep)."""
        if self.protocol == "ollama":
            body = {"model": self.name, "messages": messages, "stream": False, "think": False,
                    "options": {"temperature": 0, "seed": 7, "num_ctx": 16384, "num_predict": 1024}}
            if tools:
                body["tools"] = tools
            out = post(self.base + "/api/chat", body)
            message = out["message"]
            calls = [(None, c["function"]["name"], c["function"].get("arguments") or {}) for c in message.get("tool_calls") or []]
            return visible(message.get("content")), calls, out.get("prompt_eval_count", 0), message
        body = {"model": self.name, "messages": messages, "temperature": 0, "seed": 7, "max_tokens": 1024}
        if tools:
            body["tools"] = tools
        out = post(self.base + "/chat/completions", body)
        message = out["choices"][0]["message"]
        calls = []
        for c in message.get("tool_calls") or []:
            arguments = c["function"].get("arguments") or "{}"
            try:
                arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            except json.JSONDecodeError:
                arguments = {}
            calls.append((c.get("id"), c["function"]["name"], arguments))
        kept = {"role": "assistant", "content": message.get("content") or ""}
        if message.get("tool_calls"):
            kept["tool_calls"] = message["tool_calls"]
        return visible(message.get("content")), calls, out.get("usage", {}).get("prompt_tokens", 0), kept

    def tool_message(self, call_id, name, content):
        if self.protocol == "ollama":
            return {"role": "tool", "tool_name": name, "content": content}
        return {"role": "tool", "tool_call_id": call_id, "content": content}


def chat(model, burrow, question, history=(), tools=None, most_rounds=6):
    """What a chat program does with one question: the server's instructions as the system prompt, Burrow's tools
    offered, every call the model makes run against Burrow, until it answers."""
    offered = burrow.tools if tools is None else tools
    system = "You are a helpful assistant on the user's own computer.\n\n" + burrow.instructions
    messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": question}]
    schemas = model.schemas(offered) if offered else None
    calls, prompt_tokens, started = [], 0, time.time()
    for round_ in range(most_rounds):
        text, wanted, tokens, kept = model.turn(messages, schemas if round_ < most_rounds - 1 else None)
        prompt_tokens = max(prompt_tokens, tokens)
        if not wanted:
            return {"answer": text, "calls": calls, "rounds": round_ + 1, "prompt_tokens": prompt_tokens,
                    "seconds": round(time.time() - started, 2)}
        messages.append(kept)
        for call_id, name, arguments in wanted:
            content, failed = burrow.call(name, arguments)
            calls.append({"name": name, "arguments": arguments, "failed": failed, "characters": len(content)})
            messages.append(model.tool_message(call_id, name, content[:12000]))
    return {"answer": "", "calls": calls, "rounds": most_rounds, "prompt_tokens": prompt_tokens,
            "seconds": round(time.time() - started, 2), "stopped": True}


# ---------------------------------------------------------------- scoring

def tasks():
    items = [json.loads(line) for line in open(TASKS, encoding="utf-8") if line.strip()]
    return [t for t in items if t["type"] == "single"]

def correct(answer, task):
    low = answer.lower()
    return all(any(word.lower() in low for word in group) for group in task["must_include"])

def names_file(answer, task):
    stems = {os.path.splitext(os.path.basename(e["file"]))[0].lower() for e in task["evidence"]}
    low = answer.lower()
    return any(stem in low for stem in stems)

def save(name, data):
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, name + ".json"), "w") as f:
        json.dump(data, f, indent=1)

def say(*parts):
    print(*parts, flush=True)


# ---------------------------------------------------------------- setup

def prepare():
    if not os.path.exists(BURROW):
        subprocess.run(["swift", "build", "-c", "release", "--product", "burrow"], cwd=REPO, check=True)
    if not os.path.isdir(VAULT):
        shutil.copytree(SOURCE_VAULT, VAULT, ignore=shutil.ignore_patterns(".burrow"))
        subprocess.run([BURROW, "index", VAULT, "--vault"], check=True)
    sessions = os.path.join(VAULT, ".burrow", "sessions")
    shutil.rmtree(sessions, ignore_errors=True)


# ---------------------------------------------------------------- the tests

def t1():
    say("T1 connect")
    rows = []
    burrow = Burrow()
    first, _ = burrow.call("vault_search", {"query": "breach notification hours"})
    say(f"  burrow mcp: {burrow.server.get('name')} {burrow.server.get('version')}, {len(burrow.tools)} tools, "
        f"handshake {burrow.handshake_seconds:.2f} s, first search {len(first)} characters")
    for route in ROUTES:
        model = Model(SMALL, route)
        out = chat(model, burrow, "Search my vault for what it says about breach notification, then tell me in one sentence.")
        ok = any(c["name"].startswith("vault_") and not c["failed"] for c in out["calls"])
        rows.append({"route": route, "model": SMALL, "tool_called": ok, **out})
        say(f"  {model.label}: {'connected' if ok else 'NO TOOL CALL'}, calls {[c['name'] for c in out['calls']]}, {out['seconds']} s")
    burrow.close()
    save("t1", {"tools": [t["name"] for t in burrow.tools], "routes": rows})


def t2():
    say("T2 tool calling")
    picked = tasks()
    picked = [t for t in picked if t["subject"] == "law"][:4 if QUICK else 8] + [t for t in picked if t["subject"] == "software"][:4 if QUICK else 8]
    burrow = Burrow()
    rows = []
    for model in [Model(SMALL, "ollama"), Model(SMALL, "openai"), Model(LARGE, "openai")]:
        for task in picked:
            out = chat(model, burrow, task["question"])
            rows.append({"model": model.label, "task": task["id"], "called": bool(out["calls"]),
                         "right": correct(out["answer"], task), **out})
        mine = [r for r in rows if r["model"] == model.label]
        say(f"  {model.label}: called Burrow on {sum(r['called'] for r in mine)}/{len(mine)}, "
            f"right {sum(r['right'] for r in mine)}/{len(mine)}, "
            f"median {sorted(r['seconds'] for r in mine)[len(mine) // 2]} s")
    burrow.close()
    save("t2", rows)


PROBES = ["first", "second", "third"]

def t3():
    say("T3 handoff between models")
    picked = tasks()
    law = [t for t in picked if t["subject"] == "law"]
    software = [t for t in picked if t["subject"] == "software"]
    count = 2 if QUICK else 5
    conversations = [[law[3 * i], software[3 * i + 1], law[3 * i + 2]] for i in range(count)]
    pairs = [(Model(SMALL, "ollama"), Model(LARGE, "openai")), (Model(LARGE, "openai"), Model(SMALL, "ollama"))]
    burrow = Burrow()
    no_sessions = [t for t in burrow.tools if not t["name"].startswith("vault_session")]
    rows = []
    for a, b in pairs:
        for conversation in conversations:
            # Model A talks; the chat program keeps each turn in Burrow, as a client wired to it would.
            session, transcript, history = "new", [], []
            for task in conversation:
                out = chat(a, burrow, task["question"], history=history)
                text, _ = burrow.call("vault_session_log", {"session": session, "question": task["question"],
                                                           "answer": out["answer"], "model": a.label})
                session = re.search(r"session (\S+?),", text).group(1)
                history += [{"role": "user", "content": task["question"]}, {"role": "assistant", "content": out["answer"]}]
                transcript.append(f"User: {task['question']}\nAssistant: {out['answer']}")
            # Model B, on another route, is asked about each turn. It never saw them.
            for which, task in zip(PROBES, conversation):
                ask = (f"We talked earlier, with another assistant. What did you answer to my {which} question back then? "
                       f"Give the figure and the file it came from.")
                ways = {
                    "fresh": dict(question=ask, tools=no_sessions),
                    "paste": dict(question="Here is our earlier conversation:\n\n" + "\n\n".join(transcript) + "\n\n" + ask, tools=no_sessions),
                    "burrow": dict(question="Carry on our last conversation; it is saved in Burrow. " + ask, tools=None),
                }
                for way, given in ways.items():
                    out = chat(b, burrow, given["question"], tools=given["tools"])
                    rows.append({"from": a.label, "to": b.label, "way": way, "session": session, "probe": which,
                                 "task": task["id"], "right": correct(out["answer"], task), "file": names_file(out["answer"], task),
                                 "used_sessions": any(c["name"].startswith("vault_session") for c in out["calls"]), **out})
        for way in ["fresh", "paste", "burrow"]:
            mine = [r for r in rows if r["from"] == a.label and r["way"] == way]
            say(f"  {a.label} -> {b.label}  {way:6}: right {sum(r['right'] for r in mine)}/{len(mine)}, "
                f"file named {sum(r['file'] for r in mine)}/{len(mine)}, "
                f"prompt tokens median {sorted(r['prompt_tokens'] for r in mine)[len(mine) // 2]}, "
                f"session tools used {sum(r['used_sessions'] for r in mine)}/{len(mine)}")
    burrow.close()
    save("t3", rows)


def t4():
    say("T4 Claude Code picks up a local model's conversation")
    picked = [t for t in tasks() if t["subject"] == "law"][10:13]
    local = Model(SMALL, "ollama")
    burrow = Burrow()
    session, history = "new", []
    for task in picked:
        out = chat(local, burrow, task["question"], history=history)
        text, _ = burrow.call("vault_session_log", {"session": session, "question": task["question"], "answer": out["answer"], "model": local.label})
        session = re.search(r"session (\S+?),", text).group(1)
        history += [{"role": "user", "content": task["question"]}, {"role": "assistant", "content": out["answer"]}]
    burrow.close()
    config = os.path.join(WORK, "mcp.json")
    json.dump({"mcpServers": {"burrow": {"command": BURROW, "args": ["mcp", VAULT]}}}, open(config, "w"))
    rows = []
    for which, task in zip(PROBES, picked):
        prompt = (f"Carry on my last conversation; it is saved in Burrow. What did the assistant answer to my {which} question? "
                  f"Give the figure and the file. Then log this question and your answer to the same session.")
        started = time.time()
        done = subprocess.run(["claude", "-p", prompt, "--mcp-config", config, "--strict-mcp-config",
                               "--allowedTools", "mcp__burrow", "--output-format", "json"],
                              capture_output=True, text=True, timeout=600, cwd=WORK)
        try:
            out = json.loads(done.stdout)
        except json.JSONDecodeError:
            out = {"result": done.stdout + done.stderr}
        answer = out.get("result", "")
        rows.append({"probe": which, "task": task["id"], "right": correct(answer, task), "file": names_file(answer, task),
                     "answer": answer, "turns": out.get("num_turns"), "seconds": round(time.time() - started, 1)})
        say(f"  {which}: right {rows[-1]['right']}, file {rows[-1]['file']}, {rows[-1]['turns']} turns, {rows[-1]['seconds']} s")
    burrow = Burrow()
    text, _ = burrow.call("vault_session_list", {})
    burrow.close()
    save("t4", {"session": session, "probes": rows, "sessions_after": text})
    say("  sessions after Claude:\n" + "\n".join("    " + line for line in text.splitlines()[:8]))


def opencode(model, question, agent="burrow", session=None):
    """One message through OpenCode, with Burrow wired in as an MCP server (work/opencode/opencode.json)."""
    here = os.path.join(WORK, "opencode")
    command = ["opencode", "run", "--standalone", "--auto", "--format", "json", "-m", model, "--agent", agent, question]
    if session:
        command += ["--session", session]
    started = time.time()
    try:
        done = subprocess.run(command, capture_output=True, text=True, cwd=here, timeout=300, env={**os.environ, "PWD": here})
    except subprocess.TimeoutExpired:
        return {"answer": "", "calls": [], "session": None, "error": "no answer in 300 s", "seconds": 300.0}
    calls, text, sid, error = [], "", None, None
    for line in done.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = event.get("sessionID", sid)
        part = event.get("part", {})
        if part.get("type") == "tool":
            calls.append(part.get("tool"))
        elif part.get("type") == "text":
            text += part.get("text", "")
        elif event.get("type") == "error":
            error = str(event["error"].get("message", ""))[:200]
    return {"answer": text.strip(), "calls": calls, "session": sid, "error": error, "seconds": round(time.time() - started, 1)}


def claude_code(prompt):
    config = os.path.join(WORK, "mcp.json")
    json.dump({"mcpServers": {"burrow": {"command": BURROW, "args": ["mcp", VAULT]}}}, open(config, "w"))
    started = time.time()
    try:
        done = subprocess.run(["claude", "-p", prompt, "--mcp-config", config, "--strict-mcp-config", "--allowedTools", "mcp__burrow",
                               "--output-format", "json"], capture_output=True, text=True, timeout=300, cwd=WORK)
    except subprocess.TimeoutExpired:
        return {"answer": "", "turns": None, "seconds": 300.0, "error": "no answer in 300 s"}
    try:
        out = json.loads(done.stdout)
    except json.JSONDecodeError:
        out = {"result": (done.stdout + done.stderr)[-400:]}
    return {"answer": out.get("result", ""), "turns": out.get("num_turns"), "seconds": round(time.time() - started, 1)}


def t5():
    say("T5 one conversation, four programs: OpenCode starts it, the others pick it up from Burrow")
    shutil.rmtree(os.path.join(VAULT, ".burrow", "sessions"), ignore_errors=True)
    picked = [t for t in tasks() if t["subject"] == "law"][:3]
    first = []
    oc_session = None
    for task in picked:
        out = opencode("llamacpp/qwen3-4b", task["question"] + " Then save this question and your answer with vault_session_log (session new, model qwen3-4b on llama.cpp).", session=oc_session)
        oc_session = out["session"] or oc_session
        out.update(task=task["id"], right=correct(out["answer"], task), logged="burrow_vault_session_log" in out["calls"])
        first.append(out)
        say(f"  OpenCode + qwen3-4b on llama.cpp: {task['id']} right {out['right']}, logged {out['logged']}, calls {out['calls']}, {out['seconds']} s")
    probe = "Pick up my last OpenCode conversation; it is saved in Burrow. What was the answer to my {which} question? Give the figure."
    resumers = {
        "Claude Code (Claude, MCP)": lambda q: claude_code(q),
        "OpenCode + qwen3 4b (llama.cpp)": lambda q: opencode("llamacpp/qwen3-4b", q),
        "OpenCode + gemma4 12b (Ollama)": lambda q: opencode("ollama/burrow-gemma4-12b-16k", q),
        "gemma4 12b, Ollama OpenAI route": lambda q: chat(Model(LARGE, "openai"), Burrow(), q),
        "qwen3 4b, llama.cpp": lambda q: chat(Model("qwen3-4b", "llamacpp"), Burrow(), q),
    }
    rows = []
    for name, ask in resumers.items():
        for which, task, before in zip(PROBES, picked, first):
            try:
                out = ask(probe.format(which=which))
            except Exception as problem:  # one program failing must not lose the others' results
                out = {"answer": "", "calls": [], "seconds": 0, "error": repr(problem)[:200]}
            used = [c if isinstance(c, str) else c["name"] for c in out.get("calls", [])]
            rows.append({"resumer": name, "probe": which, "task": task["id"], "first_was_right": before["right"],
                         "right": correct(out["answer"], task), "used_sessions": any("session" in c for c in used), **out})
        mine = [r for r in rows if r["resumer"] == name]
        say(f"  {name}: recalled {sum(r['right'] for r in mine)}/3 (first model was right on {sum(r['first_was_right'] for r in mine)}/3), "
            f"session tools used {sum(r['used_sessions'] for r in mine)}/3, median {sorted(r['seconds'] for r in mine)[1]} s")
    record = SessionStoreView.latest("opencode")
    save("t5", {"first": first, "resumers": rows, "opencode_session": record})
    if record:
        say(f"  Burrow kept {record['id']} for opencode: {len(record['turns'])} logged turns, {len(record.get('trail') or [])} lookups")


class SessionStoreView:
    @staticmethod
    def latest(client):
        folder = os.path.join(VAULT, ".burrow", "sessions")
        found = [json.load(open(os.path.join(folder, f))) for f in os.listdir(folder)] if os.path.isdir(folder) else []
        found = [r for r in found if r.get("client") == client]
        return max(found, key=lambda r: r["updated"]) if found else None


if __name__ == "__main__":
    prepare()
    chosen = [a for a in sys.argv[1:] if not a.startswith("--")] or ["t1", "t2", "t3", "t4"]
    for name in chosen:
        globals()[name]()
