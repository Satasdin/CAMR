#!/usr/bin/env python3
"""Ask the same questions of several set-ups and keep every answer.

    python run.py --tasks tasks/knowledge.jsonl tasks/project.jsonl \
        --setups local_alone local_database local_engine --model gemma4:12b \
        --vault vault --out results/<name>

One file per set-up is written in the out folder, one line per question. Stop it and start it
again whenever you like: questions already answered are skipped. See README.md.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request

from scoring import is_correct, visible

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BURROW = "/Users/p3wrky/Developer/burrow/.build/release/burrow"
OLLAMA = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
KEY_FILE = os.path.expanduser("~/.config/camr/anthropic.env")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# set-up -> the words after "burrow ask <vault> <question>"
BURROW_MODES = {"local_alone": ["--mode", "none"], "local_database": ["--mode", "search"],
                "local_engine": ["--mode", "engine"],
                "local_engine_noskills": ["--mode", "engine", "--no-skills"],     # ablation: no method files
                "local_engine_nocheck": ["--mode", "engine", "--no-check"],       # ablation: no answer check
                # the budget sweep for research question iv: the engine with a fixed amount of the vault shown
                "local_engine_c2000": ["--mode", "engine", "--characters", "2000"],
                "local_engine_c4000": ["--mode", "engine", "--characters", "4000"],
                "local_engine_c8000": ["--mode", "engine", "--characters", "8000"],
                "local_engine_c32000": ["--mode", "engine", "--characters", "32000"]}
SETUPS = ["local_alone", "local_database", "local_engine", "local_engine_noskills", "local_engine_nocheck",
          "local_engine_c2000", "local_engine_c4000", "local_engine_c8000", "local_engine_c32000",
          "chroma", "cloud_alone", "cloud_engine"]
USES_BURROW = set(BURROW_MODES) | {"cloud_engine"}
USES_CLOUD = {"cloud_alone", "cloud_engine"}
USES_LOCAL_MODEL = set(BURROW_MODES) | {"chroma"}

CALL_TIMEOUT = 300
CLOUD_SYSTEM = "Answer the question. If you cannot know the answer, say you don't know. Be brief."
CHROMA_SYSTEM = "Answer from the excerpts below. If they do not contain the answer, say you don't know."
REASONING_SUFFIX = "\n\nShow your working briefly, then give the final answer as a number on the last line."

# Chroma baseline
EMBED_MODEL = "qwen3-embedding:0.6b"
CHUNK_CHARS = 1200
CHUNK_OVERLAP = 150
EXCERPT_BUDGET = 12000
# The query wording the embedding model's card asks for; passages are embedded as they are.
EMBED_QUERY_PREFIX = "Instruct: Given a question, retrieve passages that answer the question\nQuery: "
TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".rst", ".org", ".tex", ".csv", ".tsv", ".json", ".jsonl", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".xml", ".html", ".htm", ".css", ".scss", ".sql", ".sh", ".zsh", ".bash",
    ".py", ".swift", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".java", ".kt", ".c", ".h", ".cc", ".cpp", ".hpp",
    ".m", ".mm", ".rs", ".go", ".rb", ".php", ".cs", ".dart", ".lua", ".r", ".pl", ".gradle", ".plist",
}
# "Skills" holds the engine's method files, which are not vault content, so the baseline does not index it.
SKIP_FOLDERS = {"skills", ".git", ".burrow", ".obsidian", ".build", ".swiftpm", ".venv", "node_modules", "__pycache__",
                "deriveddata", ".trash"}


class Stop(Exception):
    """The run must end now, cleanly."""


# ---------------------------------------------------------------- small helpers

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as error:
                raise SystemExit("%s line %d is not JSON: %s" % (path, number, error))
    return rows


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_tasks(paths):
    tasks, seen = [], set()
    for path in paths:
        for row in read_jsonl(path):
            for field in ("id", "subject", "type", "question"):
                if field not in row:
                    raise SystemExit("%s: a task has no %r: %s" % (path, field, json.dumps(row)[:120]))
            if row["type"] not in ("single", "multi", "reasoning"):
                raise SystemExit("%s: task %s has unknown type %r" % (path, row["id"], row["type"]))
            if row["type"] == "reasoning" and "answer" not in row:
                raise SystemExit("%s: reasoning task %s has no answer" % (path, row["id"]))
            if row["type"] != "reasoning" and not row.get("must_include"):
                raise SystemExit("%s: task %s has no must_include" % (path, row["id"]))
            if row["id"] in seen:
                raise SystemExit("task id %s appears twice" % row["id"])
            seen.add(row["id"])
            tasks.append(row)
    return tasks


def http_json(url, payload, timeout, headers=None):
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers=dict({"Content-Type": "application/json"}, **(headers or {})))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def norm_path(path):
    path = unicodedata.normalize("NFC", str(path)).replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def unique(items):
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def asked(task, args):
    """The text put to every set-up for this task."""
    if task["type"] == "reasoning" and not args.no_reasoning_suffix:
        return task["question"] + REASONING_SUFFIX
    return task["question"]


# ---------------------------------------------------------------- burrow

def burrow_json(args, words, timeout=CALL_TIMEOUT):
    """Run burrow and return the one JSON line it prints."""
    command = [args.burrow] + words + ["--json", "--vault", "--store", args.store]
    done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        detail = (done.stderr.strip() or done.stdout.strip())[-400:]
        raise RuntimeError("burrow exited %d: %s" % (done.returncode, detail))
    for line in reversed(done.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise RuntimeError("burrow printed no JSON: %s" % done.stdout.strip()[-300:])


def burrow_index(args):
    print("indexing %s into %s" % (args.vault, args.store), flush=True)
    started = time.time()
    done = subprocess.run([args.burrow, "index", args.vault, "--vault", "--store", args.store],
                          capture_output=True, text=True, timeout=6 * 3600)
    if done.returncode != 0:
        raise SystemExit("burrow index failed: %s" % (done.stderr.strip() or done.stdout.strip())[-600:])
    last = done.stdout.strip().splitlines()[-1] if done.stdout.strip() else ""
    print("  %s (%.1f s)" % (last.strip(), time.time() - started), flush=True)
    return last.strip()


def excerpt_fields(reply):
    excerpts = reply.get("excerpts") or []
    return {"excerpt_paths": unique(norm_path(e.get("path", "")) for e in excerpts), "excerpts": excerpts}


def run_burrow_ask(task, args, mode_words):
    reply = burrow_json(args, ["ask", args.vault, asked(task, args)] + mode_words + ["--model", args.model])
    known = {"answer", "total_s", "first_word_s", "retrieve_s", "prompt_tokens", "answer_tokens", "characters",
             "excerpts"}
    row = {"answer": reply.get("answer", ""), "seconds": reply.get("total_s"),
           "first_word_s": reply.get("first_word_s"), "retrieve_s": reply.get("retrieve_s"),
           "prompt_tokens": reply.get("prompt_tokens"), "answer_tokens": reply.get("answer_tokens"),
           "characters": reply.get("characters")}
    row.update(excerpt_fields(reply))
    row["extra"] = {key: value for key, value in reply.items() if key not in known}
    return row


# ---------------------------------------------------------------- ollama, directly

def ollama_chat(model, system, user, timeout=CALL_TIMEOUT):
    """One answer from a local model, with the same switches Burrow uses."""
    if "qwen3" in model.lower():
        user = user + "\n\n/no_think"      # as Burrow does: Qwen3 can ignore "think": false
    payload = {"model": model, "stream": False, "think": False,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
               "options": {"num_ctx": 8192, "temperature": 0, "seed": 7, "num_predict": 2048}}
    try:
        reply = http_json(OLLAMA + "/api/chat", payload, timeout)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        if error.code == 400 and "think" in body.lower():      # a model with no thinking switch
            payload.pop("think")
            reply = http_json(OLLAMA + "/api/chat", payload, timeout)
        else:
            raise RuntimeError("ollama %d: %s" % (error.code, body[:300]))
    return reply


def ollama_embed(texts, timeout=CALL_TIMEOUT):
    reply = http_json(OLLAMA + "/api/embed", {"model": EMBED_MODEL, "input": texts}, timeout)
    return reply["embeddings"]


# ---------------------------------------------------------------- chroma baseline

def vault_files(vault, leave_out=()):
    """Every text file in the vault, without dot folders, Skills folders, and the folders in leave_out."""
    leave_out = {os.path.realpath(path) for path in leave_out}
    found = []
    for folder, names, files in os.walk(vault):
        names[:] = sorted(n for n in names if n.lower() not in SKIP_FOLDERS and not n.startswith(".")
                          and os.path.realpath(os.path.join(folder, n)) not in leave_out)
        for name in sorted(files):
            if name.startswith(".") or os.path.splitext(name)[1].lower() not in TEXT_SUFFIXES:
                continue
            found.append(os.path.join(folder, name))
    return found


def chunks_of(text):
    """Pieces of about CHUNK_CHARS characters, each starting CHUNK_OVERLAP before the last one ended."""
    pieces, start = [], 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):                      # prefer to stop at a line or a space
            for mark in ("\n", " "):
                cut = text.rfind(mark, start + CHUNK_CHARS // 2, end)
                if cut != -1:
                    end = cut + 1
                    break
        if text[start:end].strip():
            pieces.append((start, end, text[start:end]))
        if end >= len(text):
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return pieces


class ChromaBaseline:
    """An ordinary vector-database pipeline: chunk, embed, nearest pieces, paste, ask."""

    def __init__(self, args):
        import chromadb
        from chromadb.config import Settings
        self.args = args
        self.vault = os.path.abspath(args.vault)
        os.makedirs(args.chroma_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=args.chroma_dir, settings=Settings(anonymized_telemetry=False))
        self.chroma_version = chromadb.__version__
        files = vault_files(self.vault, leave_out=[args.store, args.chroma_dir])
        manifest = hashlib.sha256()
        for path in files:
            manifest.update(os.path.relpath(path, self.vault).encode("utf-8"))
            manifest.update(sha256_file(path).encode("ascii"))
        manifest.update(("%s|%d|%d" % (EMBED_MODEL, CHUNK_CHARS, CHUNK_OVERLAP)).encode("ascii"))
        self.manifest = manifest.hexdigest()
        name = "vault-" + self.manifest[:24]         # a changed vault gets a new collection
        self.collection = self.client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})
        self.build_s = 0.0
        wanted = self._pieces(files)
        if self.collection.count() != len(wanted):
            self._build(wanted)
        self.pieces = self.collection.count()

    def _pieces(self, files):
        wanted = []
        for path in files:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            relative = norm_path(os.path.relpath(path, self.vault))
            for index, (start, end, piece) in enumerate(chunks_of(text)):
                line = text.count("\n", 0, start) + 1
                wanted.append({"id": "%s#%d" % (relative, index), "text": piece,
                               "meta": {"path": relative, "start_char": start, "end_char": end,
                                        "start": line, "end": line + piece.rstrip("\n").count("\n")}})
        return wanted

    def _build(self, wanted):
        print("chroma: embedding %d pieces with %s" % (len(wanted), EMBED_MODEL), flush=True)
        started = time.time()
        have = set()
        if self.collection.count():
            have = set(self.collection.get(include=[])["ids"])
        todo = [piece for piece in wanted if piece["id"] not in have]
        for at in range(0, len(todo), 16):
            batch = todo[at:at + 16]
            vectors = ollama_embed([piece["text"] for piece in batch], timeout=600)
            self.collection.add(ids=[p["id"] for p in batch], embeddings=vectors,
                                documents=[p["text"] for p in batch], metadatas=[p["meta"] for p in batch])
            if (at // 16) % 25 == 0:
                print("  %d of %d" % (min(at + 16, len(todo)), len(todo)), flush=True)
        self.build_s = time.time() - started
        print("chroma: built in %.1f s" % self.build_s, flush=True)

    def retrieve(self, question):
        vector = ollama_embed([EMBED_QUERY_PREFIX + question])[0]
        found = self.collection.query(query_embeddings=[vector], n_results=min(40, max(1, self.pieces)),
                                      include=["documents", "metadatas", "distances"])
        chosen, used = [], 0
        for text, meta, distance in zip(found["documents"][0], found["metadatas"][0], found["distances"][0]):
            if used + len(text) > EXCERPT_BUDGET:
                break
            used += len(text)
            chosen.append({"path": meta["path"], "start": meta["start"], "end": meta["end"],
                           "reason": "cosine", "distance": round(float(distance), 4), "text": text})
        return chosen, used

    def answer(self, task):
        question = asked(task, self.args)
        started = time.time()
        chosen, used = self.retrieve(task["question"])
        retrieve_s = time.time() - started
        blocks = ["[%s lines %d-%d]\n%s" % (c["path"], c["start"], c["end"], c["text"].strip()) for c in chosen]
        user = "Excerpts:\n\n" + "\n\n---\n\n".join(blocks) + "\n\nQuestion: " + question
        reply = ollama_chat(self.args.model, CHROMA_SYSTEM, user,
                            timeout=max(5, CALL_TIMEOUT - retrieve_s))
        total = time.time() - started
        excerpts = [{key: value for key, value in c.items() if key != "text"} for c in chosen]
        return {"answer": visible((reply.get("message") or {}).get("content", "")).strip(),
                "seconds": total, "retrieve_s": retrieve_s,
                "prompt_tokens": reply.get("prompt_eval_count"), "answer_tokens": reply.get("eval_count"),
                "characters": used, "excerpt_paths": unique(c["path"] for c in chosen), "excerpts": excerpts,
                "extra": {"ollama_total_s": (reply.get("total_duration") or 0) / 1e9,
                          "ollama_load_s": (reply.get("load_duration") or 0) / 1e9}}


# ---------------------------------------------------------------- cloud

class Cloud:
    """The Anthropic Messages API, with a running count of tokens. The key never leaves this object."""

    def __init__(self, args, already_in, already_out):
        self.model = args.cloud_model
        self.limit = args.max_cloud_tokens
        self.input_tokens = already_in
        self.output_tokens = already_out
        self.usage_path = os.path.join(args.out, "cloud_usage.json")
        self.send_temperature = True      # dropped if the model answers that it no longer takes one
        self.__key = self._read_key()

    @staticmethod
    def _read_key():
        try:
            with open(KEY_FILE, encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[len("export "):].strip()
                    if line.startswith("ANTHROPIC_API_KEY="):
                        value = line.split("=", 1)[1].strip().strip("'\"")
                        if value:
                            return value
        except OSError:
            pass
        raise SystemExit("no ANTHROPIC_API_KEY line found in %s" % KEY_FILE)

    def scrub(self, text):
        return str(text).replace(self.__key, "[key]")

    def ask(self, system, user):
        guess = (len(system) + len(user)) // 3 + 50          # a careful over-estimate of the input tokens
        if self.input_tokens + guess > self.limit:
            raise Stop("cloud token limit: %d input tokens used, the next call needs about %d, the limit is %d"
                       % (self.input_tokens, guess, self.limit))
        payload = {"model": self.model, "max_tokens": 4000, "system": system,
                   "messages": [{"role": "user", "content": user}]}
        if self.send_temperature:
            payload["temperature"] = 0
        headers = {"x-api-key": self.__key, "anthropic-version": "2023-06-01"}
        started, wait = time.time(), 4
        while True:
            left = CALL_TIMEOUT - (time.time() - started)
            if left <= 1:
                raise TimeoutError("cloud call passed %d s" % CALL_TIMEOUT)
            try:
                reply = http_json(ANTHROPIC_URL, payload, left, headers)
                break
            except urllib.error.HTTPError as error:
                body = self.scrub(error.read().decode("utf-8", "replace"))[:600]
                if error.code == 400 and "temperature" in body and "temperature" in payload:
                    # Newer models refuse the setting ("`temperature` is deprecated for this model.").
                    self.send_temperature = False
                    del payload["temperature"]
                    continue
                if error.code in (429, 500, 502, 503, 529) and time.time() - started + wait < CALL_TIMEOUT:
                    time.sleep(wait)
                    wait = min(wait * 2, 60)
                    continue
                raise RuntimeError("anthropic %d: %s" % (error.code, body))
        seconds = time.time() - started
        usage = reply.get("usage") or {}
        tokens_in = (usage.get("input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0) \
            + (usage.get("cache_read_input_tokens") or 0)
        tokens_out = usage.get("output_tokens") or 0
        self.input_tokens += tokens_in
        self.output_tokens += tokens_out
        with open(self.usage_path, "w", encoding="utf-8") as handle:
            json.dump({"cloud_model": self.model, "input_tokens": self.input_tokens,
                       "output_tokens": self.output_tokens, "limit_input_tokens": self.limit,
                       "updated": datetime.datetime.now().isoformat(timespec="seconds")}, handle, indent=1)
        text = "".join(block.get("text", "") for block in reply.get("content") or [] if block.get("type") == "text")
        return {"answer": text.strip(), "cloud_s": seconds, "prompt_tokens": tokens_in, "answer_tokens": tokens_out,
                "extra": {"stop_reason": reply.get("stop_reason"), "served_model": reply.get("model"),
                          "temperature_sent": self.send_temperature}}


def run_cloud_alone(task, args, cloud):
    row = cloud.ask(CLOUD_SYSTEM, asked(task, args))
    row.update({"seconds": row["cloud_s"], "excerpt_paths": [], "excerpts": []})
    return row


def run_cloud_engine(task, args, cloud):
    started = time.time()
    brief = burrow_json(args, ["brief", args.vault, asked(task, args)])
    brief_wall = time.time() - started
    if not brief.get("user"):
        raise RuntimeError("burrow brief returned no user text")
    row = cloud.ask(brief.get("system") or CLOUD_SYSTEM, brief["user"])
    retrieve_s = brief.get("retrieve_s")
    row.update({"seconds": row["cloud_s"] + (retrieve_s if retrieve_s is not None else brief_wall),
                "retrieve_s": retrieve_s, "characters": brief.get("characters")})
    row.update(excerpt_fields(brief))
    for key, value in brief.items():
        if key not in ("system", "user", "retrieve_s", "characters", "excerpts"):
            row["extra"][key] = value
    return row


# ---------------------------------------------------------------- the run

def tool_version(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def identity(setup, args, burrow_sha):
    """What a set-up's results depend on. A results file is only ever continued with the same identity."""
    ident = {}
    if setup in USES_LOCAL_MODEL:
        ident["model"] = args.model
    if setup in USES_CLOUD:
        ident["cloud_model"] = args.cloud_model
    if setup in USES_BURROW:
        ident["burrow_sha256"] = burrow_sha
    if setup == "chroma":
        ident["embed_model"] = EMBED_MODEL
    ident["vault"] = os.path.abspath(args.vault) if setup not in ("local_alone", "cloud_alone") else None
    ident["reasoning_suffix"] = not args.no_reasoning_suffix
    return ident


def refuse_if_different(setup, path, ident):
    for row in read_jsonl(path):
        old = row.get("identity") or {}
        for key, value in ident.items():
            if old.get(key) != value:
                raise SystemExit(
                    "REFUSED: %s already holds %s results made with %s = %r, and this run has %r.\n"
                    "Results are never overwritten or mixed. Use a new --out folder."
                    % (path, setup, key, old.get(key), value))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", nargs="+", required=True, help="task files (JSONL)")
    parser.add_argument("--setups", nargs="+", required=True, choices=SETUPS)
    parser.add_argument("--model", default="qwen3:4b-instruct-2507-q4_K_M", help="the local Ollama model")
    parser.add_argument("--cloud-model", default="claude-sonnet-5-5")
    parser.add_argument("--vault", required=True)
    parser.add_argument("--out", required=True, help="results folder")
    parser.add_argument("--burrow", default=DEFAULT_BURROW, help="path of the burrow binary")
    parser.add_argument("--store", default=os.path.join(HERE, "work", "store"), help="where Burrow keeps its index")
    parser.add_argument("--chroma-dir", default=os.path.join(HERE, "work", "chroma"))
    parser.add_argument("--max-cloud-tokens", type=int, default=3000000,
                        help="stop cloud calls before this many input tokens (counted over the out folder)")
    parser.add_argument("--limit", type=int, default=0, help="only the first N tasks (for a trial run)")
    parser.add_argument("--ids", nargs="+", help="only these task ids")
    parser.add_argument("--only-types", nargs="+", choices=["single", "multi", "reasoning"],
                        help="only tasks of these types")
    parser.add_argument("--only-subjects", nargs="+", help="only tasks of these subjects")
    parser.add_argument("--retry-errors", action="store_true",
                        help="ask again the questions whose last record is an error (a new line is added)")
    parser.add_argument("--no-index", action="store_true", help="do not run burrow index first")
    parser.add_argument("--no-reasoning-suffix", action="store_true",
                        help="do not add 'give the final answer as a number on the last line' to reasoning tasks")
    parser.add_argument("--max-consecutive-errors", type=int, default=5,
                        help="give up on a set-up after this many errors in a row")
    args = parser.parse_args()

    args.vault = os.path.abspath(args.vault)
    args.out = os.path.abspath(args.out)
    args.store = os.path.abspath(args.store)
    args.chroma_dir = os.path.abspath(args.chroma_dir)
    if not os.path.isdir(args.vault):
        raise SystemExit("no vault folder at %s" % args.vault)

    tasks = load_tasks(args.tasks)
    if args.ids:
        tasks = [task for task in tasks if task["id"] in set(args.ids)]
    if args.only_types:
        tasks = [task for task in tasks if task["type"] in set(args.only_types)]
    if args.only_subjects:
        wanted = {subject.lower() for subject in args.only_subjects}
        tasks = [task for task in tasks if task["subject"].lower() in wanted]
    if args.limit:
        tasks = tasks[:args.limit]
    if not tasks:
        raise SystemExit("no tasks to run")

    needs_burrow = any(setup in USES_BURROW for setup in args.setups)
    burrow_sha = None
    if needs_burrow:
        if not os.path.isfile(args.burrow):
            raise SystemExit("no burrow binary at %s" % args.burrow)
        burrow_sha = sha256_file(args.burrow)

    os.makedirs(args.out, exist_ok=True)
    idents = {setup: identity(setup, args, burrow_sha) for setup in args.setups}
    for setup in args.setups:                      # refuse before anything is run or written
        refuse_if_different(setup, os.path.join(args.out, setup + ".jsonl"), idents[setup])

    # meta.json: what this folder was made with. Earlier invocations are kept.
    meta_path = os.path.join(args.out, "meta.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    task_shas = {os.path.relpath(os.path.abspath(path), HERE): sha256_file(path) for path in args.tasks}
    invocation = {"date": now, "setups": args.setups, "model": args.model, "cloud_model": args.cloud_model,
                  "burrow": args.burrow if needs_burrow else None, "burrow_sha256": burrow_sha,
                  "ollama_version": tool_version(["ollama", "--version"]),
                  "task_files": task_shas, "vault": args.vault, "store": args.store,
                  "tasks_selected": len(tasks), "python": sys.version.split()[0],
                  "reasoning_suffix": None if args.no_reasoning_suffix else REASONING_SUFFIX,
                  "argv": sys.argv[1:]}
    meta.setdefault("created", now)
    meta.update({"model": args.model, "cloud_model": args.cloud_model, "date": now,
                 "ollama_version": invocation["ollama_version"]})
    if needs_burrow:
        meta.update({"burrow": args.burrow, "burrow_sha256": burrow_sha})
    meta.setdefault("task_files", {}).update(task_shas)
    meta.setdefault("setups", {}).update(idents)
    meta.setdefault("invocations", []).append(invocation)

    def save_meta():
        with open(meta_path, "w", encoding="utf-8") as handle:
            json.dump(meta, handle, indent=1, ensure_ascii=False)

    save_meta()

    if needs_burrow and not args.no_index and any(s != "local_alone" for s in args.setups if s in USES_BURROW):
        invocation["index"] = burrow_index(args)
        save_meta()

    cloud = None
    if any(setup in USES_CLOUD for setup in args.setups):
        used_in = used_out = 0
        for name in sorted(USES_CLOUD):
            for row in read_jsonl(os.path.join(args.out, name + ".jsonl")):
                used_in += row.get("prompt_tokens") or 0
                used_out += row.get("answer_tokens") or 0
        cloud = Cloud(args, used_in, used_out)

    chroma = None
    stopped = None
    for setup in args.setups:
        path = os.path.join(args.out, setup + ".jsonl")
        last = {}
        for row in read_jsonl(path):
            last[row["id"]] = row
        todo = [task for task in tasks
                if task["id"] not in last or (args.retry_errors and last[task["id"]].get("error"))]
        print("\n== %s: %d to do, %d already there" % (setup, len(todo), len(tasks) - len(todo)), flush=True)
        if not todo:
            continue
        if setup == "chroma" and chroma is None:
            chroma = ChromaBaseline(args)
            meta["chroma"] = {"version": chroma.chroma_version, "embed_model": EMBED_MODEL, "pieces": chroma.pieces,
                              "chunk_chars": CHUNK_CHARS, "overlap": CHUNK_OVERLAP, "budget_chars": EXCERPT_BUDGET,
                              "vault_sha256": chroma.manifest, "build_s": round(chroma.build_s, 1)}
            save_meta()
        right = failed_in_a_row = 0
        for number, task in enumerate(todo, 1):
            row = {"id": task["id"], "subject": task["subject"], "type": task["type"], "setup": setup,
                   "identity": idents[setup], "evidence": [norm_path(p) for p in task.get("evidence") or []]}
            started = time.time()
            try:
                if setup in BURROW_MODES:
                    row.update(run_burrow_ask(task, args, BURROW_MODES[setup]))
                elif setup == "chroma":
                    row.update(chroma.answer(task))
                elif setup == "cloud_alone":
                    row.update(run_cloud_alone(task, args, cloud))
                else:
                    row.update(run_cloud_engine(task, args, cloud))
                failed_in_a_row = 0
            except Stop as stop:
                stopped = str(stop)
                break
            except KeyboardInterrupt:
                stopped = "interrupted"
                break
            except subprocess.TimeoutExpired:
                row["error"] = "timeout after %d s" % CALL_TIMEOUT
            except Exception as error:  # noqa: BLE001 - every failure is recorded and the run goes on
                text = "%s: %s" % (type(error).__name__, error)
                row["error"] = (cloud.scrub(text) if cloud else text)[:800]
            row["wall_s"] = round(time.time() - started, 3)
            if "error" in row:
                failed_in_a_row += 1
                row.setdefault("answer", "")
                row.setdefault("seconds", row["wall_s"])
                row.setdefault("excerpt_paths", [])
            row["correct"] = bool(is_correct(task, row.get("answer", ""))) and "error" not in row
            row["tokens"] = (row.get("prompt_tokens") or 0) + (row.get("answer_tokens") or 0)
            row["date"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            append_jsonl(path, row)
            right += row["correct"]
            shown = "ERROR " + row["error"][:90] if "error" in row else re.sub(r"\s+", " ", row["answer"])[:70]
            print("  %3d/%d %-12s %s %5.1fs  %s" % (number, len(todo), task["id"], "✓" if row["correct"] else "·",
                                                    row.get("seconds") or 0, shown), flush=True)
            if failed_in_a_row >= args.max_consecutive_errors:
                print("  %d errors in a row: leaving %s. Fix the cause, then run again with --retry-errors."
                      % (failed_in_a_row, setup), flush=True)
                break
        print("  %s: %d right of %d asked this time" % (setup, right, number if todo else 0), flush=True)
        if stopped:
            break

    if cloud:
        meta["cloud_tokens"] = {"input": cloud.input_tokens, "output": cloud.output_tokens}
        meta["cloud_temperature_sent"] = cloud.send_temperature
        print("\ncloud tokens used in this folder: %d in, %d out" % (cloud.input_tokens, cloud.output_tokens))
    if stopped:
        invocation["stopped"] = stopped
        print("\nSTOPPED: %s\nEverything answered so far is saved; run the same command to continue." % stopped)
    save_meta()


if __name__ == "__main__":
    main()
