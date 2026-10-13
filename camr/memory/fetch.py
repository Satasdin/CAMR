"""Learning from the web when memory has nothing to offer (eager learning).

When the read path abstains, the assistant does not stop at "I don't know". For a
general-knowledge question it looks the subject up, stores what it read as notes with
their source, and answers from those notes; the next time a question needs them they
come from memory, offline. The frozen model never changes: what grows is the memory.

Two keyless public sources, chained:

* DuckDuckGo Instant Answers (``api.duckduckgo.com``): the lead of the Wikipedia
  article a name refers to, or the list of articles an ambiguous name could mean
  (each of which is then looked up by its exact title);
* Wikipedia page summaries (``/api/rest_v1/page/summary/<title>``): the lead section
  of a named article, when DuckDuckGo has nothing (its index lags new articles).

Wikipedia's search endpoint is used only while it is not rate limiting this machine
(it honours ``Retry-After`` and then stays away). Every response is cached, so an
experiment can be replayed offline with exactly the text it read.

Privacy: a question about the user's own life ("my", "I", "we", ...) is never sent
anywhere (``is_personal``); only the subject strings of a general question are.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests

from camr.memory.entities import norm

USER_AGENT = "CAMR/0.3 (https://github.com/Satasdin/CAMR; local personal assistant)"
DDG = "https://api.duckduckgo.com/"
WIKI = "https://{lang}.wikipedia.org"

_PERSONAL = re.compile(r"\b(my|mine|me|myself|i|i'm|i've|i'd|i'll|our|ours|we|us)\b", re.I)
_WH = re.compile(r"^\s*(?:what|who|whom|whose|which|where|when|why|how(?: many| much| old| long)?)\b"
                 r"(?:\s+(?:is|are|was|were|does|do|did|has|have|had|can|could|will|would))?"
                 r"(?:\s+(?:a|an|the))?\s+", re.I)
_OF_NP = re.compile(r"\b([a-z]{3,} of (?:the )?[A-Z][\w'’.&-]*(?:\s+(?:[A-Z0-9][\w'’.&-]*|of|the|de|da|von|van))*)")
_CAP_RUN = re.compile(r"(?<![\w'’])((?:[A-Z0-9][\w'’.&-]*)(?:\s+(?:(?:of|the|de|da|di|del|la|le|von|van|der|du|and)\s+)*"
                      r"[A-Z0-9][\w'’.&-]*)*)")
_TAIL = re.compile(r"\bof\s+((?:\S+\s+){0,5}\S+)$")
_LEAD_WORDS = {"what", "who", "whom", "whose", "which", "when", "where", "why", "how", "is", "are", "was", "were",
               "do", "does", "did", "can", "could", "would", "should", "will", "tell", "name", "in", "the", "a", "an"}


def is_personal(question: str) -> bool:
    """True when the question is about the user (never looked up online)."""
    return bool(_PERSONAL.search(question))


def subjects(question: str, limit: int = 4) -> list[str]:
    """Strings worth looking up for a question, most specific first.

    "What color is flag of Zimbabwe?" -> ["flag of Zimbabwe", "Zimbabwe"];
    "Who was the director of Doomwatch?" -> ["director of Doomwatch", "Doomwatch"];
    "what is photosynthesis?" -> ["photosynthesis"].
    """
    q = question.strip().rstrip("?.! ")
    out: list[str] = []
    out += [m.group(1) for m in _OF_NP.finditer(q)]
    tail = _TAIL.search(q)  # "producer of Son contento" -> "Son contento" (titles may contain lower-case words)
    if tail and tail.group(1)[:1].isupper() or tail and tail.group(1)[:1].isdigit():
        out.append(tail.group(1))
    caps = []
    for m in _CAP_RUN.finditer(q):
        span = re.sub(r"['’]s$", "", m.group(1)).strip()
        words = span.split()
        if not q[: m.start()].strip():  # only a run that opens the question starts with "What", "Who", ...
            while words and words[0].lower() in _LEAD_WORDS - {"the", "a", "an"}:  # "The Rookie" keeps its article
                words = words[1:]
        span = " ".join(words)
        if len(span) >= 3 and span.lower() not in _LEAD_WORDS:
            caps.append(span)
    out += sorted(caps, key=lambda s: -len(s))
    stripped = _WH.sub("", q).strip()
    stripped = re.sub(r"['’]s\b", "", stripped)
    if stripped and stripped.lower() != q.lower() and len(stripped.split()) <= 6:
        out.append(stripped)
    elif not out and q:
        out.append(q)
    seen, uniq = set(), []
    for s in out:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq[:limit]


@dataclass
class WebPage:
    title: str
    url: str
    text: str
    source: str  # "wikipedia" or "wikipedia via duckduckgo"
    query: str   # what was looked up to find it


@dataclass
class Lookup:
    question: str
    queries: list[str] = field(default_factory=list)
    pages: list[WebPage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    requests: int = 0
    cached: int = 0
    ms: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


class _Cache:
    """Response cache in a small SQLite file, safe across threads."""

    def __init__(self, path: Path | None):
        self.path = path
        self._lock = threading.Lock()
        self._mem: dict[str, tuple[int, str]] = {}
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path, check_same_thread=False)
            self.conn.execute("CREATE TABLE IF NOT EXISTS web_cache (key TEXT PRIMARY KEY, status INTEGER, body TEXT,"
                              " at REAL)")
            self.conn.commit()
        else:
            self.conn = None

    def get(self, key: str) -> tuple[int, str] | None:
        with self._lock:
            if self.conn is None:
                return self._mem.get(key)
            row = self.conn.execute("SELECT status, body FROM web_cache WHERE key=?", (key,)).fetchone()
            return (row[0], row[1]) if row else None

    def put(self, key: str, status: int, body: str) -> None:
        with self._lock:
            if self.conn is None:
                self._mem[key] = (status, body)
                return
            self.conn.execute("INSERT OR REPLACE INTO web_cache VALUES (?,?,?,?)", (key, status, body, time.time()))
            self.conn.commit()


class WebLookup:
    """Keyless lookup chain: DuckDuckGo Instant Answers, then Wikipedia summaries (and search when allowed)."""

    name = "web"

    def __init__(self, session: requests.Session | None = None, *, cache_path: str | Path | None = None,
                 lang: str = "en", min_interval_s: float = 1.0, timeout: float = 10.0, offline: bool = False,
                 patient_s: float = 0.0, rank=None, user_agent: str = USER_AGENT):
        self.http = session or requests.Session()
        self.http.headers.setdefault("User-Agent", user_agent)
        self.cache = _Cache(Path(cache_path) if cache_path else None)
        self.wiki = WIKI.format(lang=lang)
        self.min_interval_s = min_interval_s
        self.timeout = timeout
        self.offline = offline  # replay from the cache only
        # How long a batch job may wait out a rate limit (Retry-After) before giving up on a source; the app uses 0
        # (it skips a rate-limited source at once and tries the next).
        self.patient_s = patient_s
        # How the meanings of an ambiguous name are ordered: None = words shared with the question; or a function
        # (question, [descriptions]) -> scores, e.g. the memory embedder's cosine similarity (``embedding_rank``).
        self.rank = rank
        self._last = 0.0
        self._blocked_until: dict[str, float] = {}  # host -> time it may be asked again (Retry-After)
        self._backoff: dict[str, float] = {}  # host -> next pause after an empty or 429 reply (doubles, max 5 min)
        self._lock = threading.Lock()

    # ------------------------------------------------------------ HTTP
    def _get(self, url: str, params: dict | None, res: Lookup) -> tuple[int, dict | None]:
        key = url + ("?" + urllib.parse.urlencode(sorted(params.items())) if params else "")
        hit = self.cache.get(key)
        if hit is not None:
            res.cached += 1
            status, body = hit
            return status, (json.loads(body) if body else None)
        if self.offline:
            return 0, None
        host = urllib.parse.urlparse(url).netloc + ("/search" if "/search/" in url else "")
        waited = 0.0
        while True:
            blocked = self._blocked_until.get(host, 0) - time.time()
            if blocked > 0:
                if waited + blocked > self.patient_s:
                    return 429, None
                time.sleep(blocked)
                waited += blocked
            with self._lock:  # polite: one request at a time, at most one per min_interval_s
                wait = self._last + self.min_interval_s - time.time()
                if wait > 0:
                    time.sleep(wait)
                try:
                    r = self.http.get(url, params=params, timeout=self.timeout)
                except requests.RequestException as exc:
                    res.errors.append(f"{host}: {type(exc).__name__}")
                    return 0, None
                finally:
                    self._last = time.time()
            res.requests += 1
            # Wikimedia answers 429 (Retry-After); DuckDuckGo answers an empty body when asked too fast. Either way:
            # back off, and never cache the non-answer (an empty reply cached as "nothing known" poisons the cache).
            limited = r.status_code == 429 or (r.status_code == 403 and "too many requests" in r.text.lower()) or (
                r.status_code in (200, 202) and not r.text.strip())
            if limited:
                pause = float(r.headers.get("Retry-After") or 0) or self._backoff.get(host, 15.0)
                self._backoff[host] = min(2 * pause, 300.0)
                self._blocked_until[host] = time.time() + pause
                if waited + pause > self.patient_s:
                    res.errors.append(f"{host}: rate limited")
                    return 429, None
                continue
            self._backoff.pop(host, None)
            break
        try:
            body = r.json()
        except ValueError:
            body = None
        if r.status_code in (200, 202, 404) and body is not None:
            self.cache.put(key, r.status_code, json.dumps(body))
        elif r.status_code not in (200, 202, 404):
            res.errors.append(f"{host}: HTTP {r.status_code}")
        return r.status_code, body

    # ------------------------------------------------------------ sources
    def summary(self, title: str, res: Lookup) -> dict | None:
        """Lead section of a Wikipedia article (redirects followed); None for missing or disambiguation pages."""
        t = urllib.parse.quote(title.strip().replace(" ", "_"), safe="()',")
        status, body = self._get(f"{self.wiki}/api/rest_v1/page/summary/{t}", None, res)
        if status != 200 or not body or body.get("type") != "standard" or not body.get("extract"):
            return None
        return body

    def duckduckgo(self, query: str, res: Lookup) -> dict | None:
        status, body = self._get(DDG, {"q": query, "format": "json", "no_html": 1, "skip_disambig": 0,
                                       "no_redirect": 1}, res)
        return body if status in (200, 202) and body else None

    def wiki_search(self, query: str, res: Lookup, limit: int = 3) -> list[str]:
        status, body = self._get(f"{self.wiki}/w/rest.php/v1/search/page", {"q": query, "limit": limit}, res)
        if status != 200 or not body:
            return []
        return [p["title"] for p in body.get("pages", [])]

    def article(self, name: str, res: Lookup) -> tuple[WebPage | None, list[tuple[str, str]]]:
        """The article a name refers to, or (None, [(title, description), ...]) when the name is ambiguous."""
        ddg = self.duckduckgo(name, res)
        if ddg and ddg.get("AbstractText") and "wikipedia.org" in (ddg.get("AbstractURL") or ""):
            title = urllib.parse.unquote(ddg["AbstractURL"].rsplit("/", 1)[-1]).replace("_", " ")
            return WebPage(title=title, url=ddg["AbstractURL"], text=" ".join(ddg["AbstractText"].split()),
                           source="wikipedia via duckduckgo", query=name), []
        if ddg and ddg.get("Type") == "D":
            options = []
            for t in _flatten(ddg.get("RelatedTopics") or []):
                url = t.get("FirstURL") or ""
                if url.startswith("https://duckduckgo.com/") and "/c/" not in url:
                    options.append((urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("_", " "), t.get("Text", "")))
            if options:
                return None, options
        s = self.summary(name[:1].upper() + name[1:], res)
        if s:
            title = s.get("title", name)
            return WebPage(title=title, url=_page_url(s, self.wiki, title), text=" ".join(s["extract"].split()),
                           source="wikipedia", query=name), []
        return None, []

    # ------------------------------------------------------------ lookup
    def lookup(self, question: str, max_pages: int = 3, max_queries: int = 3) -> Lookup:
        """Find up to ``max_pages`` article leads for the question's subjects."""
        res = Lookup(question=question)
        t0 = time.perf_counter()
        seen: set[str] = set()
        qwords = set(norm(question).split())

        def add(page: WebPage | None) -> bool:
            if page is None or norm(page.title) in seen or not page.text or len(res.pages) >= max_pages:
                return False
            seen.add(norm(page.title))
            res.pages.append(page)
            return True

        for query in subjects(question)[:max_queries]:
            if len(res.pages) >= max_pages:
                break
            res.queries.append(query)
            page, options = self.article(query, res)
            if add(page):
                continue
            if options:  # ambiguous: the meanings closest to the question first
                if self.rank is not None:
                    scores = self.rank(question, [f"{t}. {d}" for t, d in options])
                    ranked = [o for _, o in sorted(zip(scores, options), key=lambda x: -x[0])]
                else:
                    ranked = sorted(options, key=lambda o: -len(qwords & set(norm(o[0] + " " + o[1]).split())))
                for title, _ in ranked[:2]:
                    add(self.article(title, res)[0])
                continue
            for title in self.wiki_search(query, res, limit=2):
                add(self.article(title, res)[0])
        res.ms = (time.perf_counter() - t0) * 1000
        return res

    def topic_pages(self, topic: str, limit: int = 20) -> Lookup:
        """Pages about a topic, for harvesting a pack: the topic's own article, the articles related to it, then
        (snowballing) the articles for the names those pages mention most, until ``limit`` pages are read."""
        res = Lookup(question=topic, queries=[topic])
        t0 = time.perf_counter()
        pages: list[WebPage] = []
        seen: set[str] = set()

        def take(title: str) -> None:
            if len(pages) >= limit or norm(title) in seen:
                return
            seen.add(norm(title))
            p, _ = self.article(title, res)
            if p and norm(p.title) not in {norm(x.title) for x in pages}:
                pages.append(p)
                seen.add(norm(p.title))

        page, options = self.article(topic, res)
        if page:
            pages.append(page)
            seen |= {norm(topic), norm(page.title)}
        for t, _ in options[:limit]:
            take(t)
        ddg = self.duckduckgo(topic, res)
        for t in _flatten((ddg or {}).get("RelatedTopics") or []):
            url = t.get("FirstURL") or ""
            if url.startswith("https://duckduckgo.com/") and "/c/" not in url:
                take(urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("_", " "))
        for t in self.wiki_search(topic, res, limit=min(limit, 20)):
            take(t)
        frontier = 0
        while len(pages) < limit and frontier < len(pages):  # snowball over the names the pages mention
            counts: dict[str, int] = {}
            for p in pages[frontier:]:
                for m in _CAP_RUN.finditer(p.text):
                    name = m.group(1).strip(" .,'’")
                    if len(name) >= 4 and " " in name or len(name) >= 6:
                        counts[name] = counts.get(name, 0) + 1
            frontier = len(pages)
            for name, _ in sorted(counts.items(), key=lambda kv: -kv[1])[: 2 * limit]:
                take(name)
        res.pages = pages[:limit]
        res.ms = (time.perf_counter() - t0) * 1000
        return res


def embedding_rank(embedder):
    """Order meanings by the embedder's cosine similarity between the question and each meaning's description."""
    import numpy as np

    def rank(question: str, texts: list[str]) -> list[float]:
        q = np.asarray(embedder.encode_one(question, is_query=True), dtype=np.float32)
        d = np.asarray(embedder.encode(texts), dtype=np.float32)
        q /= np.linalg.norm(q) or 1.0
        d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
        return (d @ q).tolist()

    return rank


def _flatten(topics: list[dict]) -> list[dict]:
    out = []
    for t in topics:
        if "Topics" in t:
            out += _flatten(t["Topics"])
        else:
            out.append(t)
    return out


def _page_url(summary: dict, wiki: str, title: str) -> str:
    try:
        return summary["content_urls"]["desktop"]["page"]
    except (KeyError, TypeError):
        return f"{wiki}/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
