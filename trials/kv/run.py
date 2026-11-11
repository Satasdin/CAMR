#!/usr/bin/env python3
"""KV trial: what a model fetched through Burrow comes back as its own cache, through MCP, with llama.cpp as the server.

This script plays the chat program (the part llama.cpp's web UI, OpenCode or LM Studio play). It starts `burrow mcp`,
hands Burrow's tools to Qwen3 4B on llama-server, and runs every tool call the model makes against Burrow. Burrow is
started with --llama, so what the lookups return is read into the model's cache on a spare slot afterwards (D-60).

  warm     a working session: the model answers questions with Burrow's tools; Burrow warms the folders it looked in
  reuse    the server is restarted (the next day, say). The program opens a conversation with the folder's pack as its
           system message, as `vault_pack` gives it. Burrow loads the saved cache; the model reads only the question.
  cold     the same as reuse, with Burrow started without --llama: the model reads the whole pack
  tg       speculation on the same opening, three ways: none, n-gram lookup in the context, and Burrow's lookup table
           built from the plain vault text (`burrow kv lookup`)

Run:  python3 trials/kv/run.py <vault> [warm reuse cold] [--out trials/results/kv-1]
Needs llama-server and the Qwen3 4B GGUF. Stdlib only.
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
BURROW = os.path.join(REPO, ".build", "debug", "burrow")
MODEL = os.path.expanduser("~/.ollama/models/blobs/sha256-85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9")  # qwen3:4b-instruct-2507-q4_K_M
PORT = 8092
BASE = f"http://127.0.0.1:{PORT}"
FOLDER = "Project/Sources/BurrowCore"
QUESTIONS = [
    "In Burrow's code, how does Retrieval.swift decide which files to show a model? Name the functions.",
    "Where in BurrowCore is a file split into chunks, and how big can a chunk be?",
    "Which file in BurrowCore opens the SQLite database, and what does it do when the schema is old?",
]
REUSE_QUESTION = "Which function in Chunker.swift splits a file, and what limit does it use? Cite file:line."


def post(path, body, timeout=1800):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read())


class Server:
    def __init__(self, vault, log, extra=()):
        os.makedirs(os.path.join(vault, ".burrow", "kv"), exist_ok=True)  # llama.cpp refuses a save path that isn't there
        self.proc = subprocess.Popen(["llama-server", "-m", MODEL, "-a", "qwen3-4b-instruct", "--jinja", "-c", "65536", "-np", "2",
                                      "--port", str(PORT), "--slot-save-path", os.path.join(vault, ".burrow", "kv"), *extra],
                                     stdout=open(log, "w"), stderr=subprocess.STDOUT)
        for _ in range(120):
            try:
                if get("/health").get("status") == "ok":
                    return
            except Exception:
                pass
            time.sleep(1)
        raise SystemExit("llama-server did not start")

    def stop(self):
        self.proc.terminate()
        self.proc.wait()
        time.sleep(2)


class Burrow:
    """A client of `burrow mcp`: one JSON-RPC message per line on stdin and stdout."""

    def __init__(self, vault, log, llama=True):
        args = [BURROW, "mcp", vault, "--vault", "--no-sessions"] + (["--llama", BASE] if llama else [])
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(log, "a"), text=True, bufsize=1)
        self.next = 0
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "kv-trial", "version": "1"}})
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        self.tools = self.request("tools/list", {})["tools"]

    def request(self, method, params):
        self.next += 1
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.next, "method": method, "params": params}) + "\n")
        while True:
            reply = json.loads(self.proc.stdout.readline())
            if reply.get("id") == self.next:
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                return reply["result"]

    def call(self, name, arguments):
        started = time.time()
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        return result["content"][0]["text"], time.time() - started

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=30)


def openai_tools(burrow):
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["inputSchema"]}}
            for t in burrow.tools if not t["name"].startswith("vault_session")]


def chat(burrow, messages, rounds=4, predict=400):
    """Runs the model with Burrow's tools until it answers. Returns the answer and the timings of every model call."""
    calls, tools_used = [], []
    for _ in range(rounds):
        started = time.time()
        out = post("/v1/chat/completions", {"model": "qwen3-4b-instruct", "messages": messages, "tools": openai_tools(burrow),
                                            "temperature": 0, "seed": 7, "max_tokens": predict})
        t = out.get("timings", {})
        calls.append({"prompt_n": t.get("prompt_n"), "prompt_ms": t.get("prompt_ms"), "cache_n": t.get("cache_n"),
                      "predicted_n": t.get("predicted_n"), "tg_per_s": t.get("predicted_per_second"),
                      "draft_n": t.get("draft_n", 0), "draft_accepted": t.get("draft_n_accepted", 0), "wall_s": time.time() - started})
        message = out["choices"][0]["message"]
        messages.append(message)
        if not message.get("tool_calls"):
            return message.get("content", ""), calls, tools_used
        for call in message["tool_calls"]:
            arguments = json.loads(call["function"]["arguments"] or "{}")
            text, seconds = burrow.call(call["function"]["name"], arguments)
            tools_used.append({"tool": call["function"]["name"], "arguments": arguments, "seconds": round(seconds, 3), "characters": len(text)})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": text})
    return "(no answer in time)", calls, tools_used


def shelf(vault):
    try:
        return json.load(open(os.path.join(vault, ".burrow", "kv", "shelf.json")))
    except FileNotFoundError:
        return []


def warm(vault, out):
    server = Server(vault, os.path.join(out, "server-warm.log"))
    burrow = Burrow(vault, os.path.join(out, "burrow-warm.log"))
    sessions = []
    for question in QUESTIONS:
        system = "You answer questions about the user's files. Use the vault tools to look things up before answering."
        answer, calls, used = chat(burrow, [{"role": "system", "content": system}, {"role": "user", "content": question}])
        sessions.append({"question": question, "tools": used, "calls": calls, "answer": answer[:600]})
        print(f"warm: {question[:50]}... tools {[u['tool'] for u in used]}", flush=True)
    # The program keeps the folder it worked in, as a person or a model would by reading it whole.
    burrow.call("vault_pack", {"folder": FOLDER, "part": 1})
    # Burrow warms after the replies, once the server is idle. Wait for it, with a limit.
    deadline = time.time() + 600
    while time.time() < deadline and not any((e.get("scope") == FOLDER and e.get("part") == 1) for e in shelf(vault)):
        time.sleep(3)
    time.sleep(5)
    burrow.close()
    server.stop()
    packs = [e for e in shelf(vault) if e.get("scope")]
    return {"sessions": sessions, "packs": packs, "burrow_log": open(os.path.join(out, "burrow-warm.log")).read()[-4000:]}


def opening(vault, out, label, llama, extra=()):
    """A new conversation that opens with the folder's pack, the way a program would after `vault_pack`."""
    server = Server(vault, os.path.join(out, f"server-{label}.log"), extra)
    burrow = Burrow(vault, os.path.join(out, f"burrow-{label}.log"), llama=llama)
    if llama:
        pack, seconds = burrow.call("vault_pack", {"folder": FOLDER, "part": 1})
    else:  # the same text, sized for the same window, with nothing loaded
        started = time.time()
        pack = subprocess.run([BURROW, "kv", vault, "pack", FOLDER, "--part", "1", "--window", "32768", "--vault"],
                              capture_output=True, text=True, check=True).stdout
        seconds = time.time() - started
    time.sleep(3)  # the person types the question; Burrow loads the cache meanwhile, without holding anything up
    answer, calls, used = chat(burrow, [{"role": "system", "content": pack}, {"role": "user", "content": REUSE_QUESTION}])
    slots = get("/slots")
    burrow.close()
    server.stop()
    first = calls[0]
    print(f"{label}: first call read {first['prompt_n']} tokens in {first['prompt_ms'] / 1000:.2f} s, "
          f"cached {first['cache_n']}, tg {first['tg_per_s']:.1f}/s, tools {[u['tool'] for u in used]}", flush=True)
    return {"pack_characters": len(pack), "pack_sha": __import__("hashlib").sha256(pack.encode()).hexdigest()[:12], "vault_pack_seconds": seconds, "calls": calls, "tools": used, "answer": answer[:800],
            "slots": [{"id": s["id"], "n_ctx": s["n_ctx"]} for s in slots]}


def collide(vault, out):
    """A client asks a plain question while Burrow builds another folder's pack, against the same question on an idle server."""
    server = Server(vault, os.path.join(out, "server-collide.log"))
    burrow = Burrow(vault, os.path.join(out, "burrow-collide.log"))
    question = [{"role": "user", "content": "In two sentences, what is a vault in Burrow?"}]
    post("/v1/chat/completions", {"messages": question, "max_tokens": 8})  # load the model
    quiet = post("/v1/chat/completions", {"messages": question, "max_tokens": 200, "temperature": 0, "seed": 7, "cache_prompt": False})["timings"]
    burrow.call("vault_pack", {"folder": "Law", "part": 1})   # Burrow starts building Law in the background
    time.sleep(2)
    busy = post("/v1/chat/completions", {"messages": question, "max_tokens": 200, "temperature": 0, "seed": 7, "cache_prompt": False})["timings"]
    deadline = time.time() + 300
    while time.time() < deadline and not any(e.get("scope") == "Law" and e.get("part") == 1 for e in shelf(vault)):
        time.sleep(2)
    burrow.close()
    server.stop()
    pick = lambda t: {"prompt_ms": t["prompt_ms"], "tg_per_s": t["predicted_per_second"], "predicted_ms": t["predicted_ms"]}
    print(f"collide: idle tg {quiet['predicted_per_second']:.1f}/s, during a build {busy['predicted_per_second']:.1f}/s", flush=True)
    return {"idle": pick(quiet), "during_build": pick(busy)}


def main():
    vault = os.path.abspath(sys.argv[1])
    wanted = [a for a in sys.argv[2:] if not a.startswith("--") and not os.sep in a] or ["warm", "reuse", "cold", "collide"]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(REPO, "trials", "results", "kv-1")
    os.makedirs(out, exist_ok=True)
    results = {"model": "qwen3:4b-instruct-2507-q4_K_M", "server": "llama-server -c 65536 -np 2 (32,768 tokens a slot)",
               "folder": FOLDER, "when": time.strftime("%Y-%m-%d %H:%M")}
    if "warm" in wanted:
        results["warm"] = warm(vault, out)
    if "reuse" in wanted:
        results["reuse"] = opening(vault, out, "reuse", llama=True)
    if "cold" in wanted:
        results["cold"] = opening(vault, out, "cold", llama=False)
    if "collide" in wanted:
        results["collide"] = collide(vault, out)
    path = os.path.join(out, "client.json")
    json.dump(results, open(path, "w"), indent=2)
    print("saved", path)


if __name__ == "__main__":
    main()
