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
_RELATION_HEADS = {"director", "producer", "composer", "screenwriter", "writer", "author", "father", "mother",
                   "occupation", "genre", "religion", "sport", "country", "color", "colour", "creator", "founder",
                   "spouse", "wife", "husband", "son", "daughter", "population", "language", "birthplace", "owner",
                   "headquarters", "publisher", "editor", "illustrator", "narrator", "star", "lyricist", "architect",
                   "designer", "developer", "manufacturer", "inventor", "parent", "parents", "child", "children",
                   "sibling", "brother", "sister", "leader", "president", "mayor", "head", "member", "cast"}
_VERBS = {"wrote", "write", "writes", "directed", "direct", "produced", "composed", "invented", "invent", "discovered",
          "discover", "founded", "found", "painted", "created", "create", "built", "designed", "played", "sang",
          "won", "owns", "owned", "starred", "developed", "made", "make", "makes", "killed", "led", "ruled",
          "married", "named", "published", "released", "recorded", "sung", "plays", "stars", "leads", "rules"}
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
    # "director of Emma" is no article title, and searching for it finds people called Emma who direct (D-25):
    # an of-phrase headed by a relation word is looked up as its subject only
    out += [m.group(1) for m in _OF_NP.finditer(q) if m.group(1).split()[0].lower() not in _RELATION_HEADS]
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
    relation_phrase = bool(re.match(r"(\w+) of ", stripped)) and stripped.split()[0].lower() in _RELATION_HEADS
    if relation_phrase and not out:  # "who is the director of emma" (no capitals): look up "emma"
        out.append(stripped.split(" of ", 1)[1])
    elif stripped and stripped.lower() != q.lower() and len(stripped.split()) <= 6 and not relation_phrase and not out:
        verb, _, rest = stripped.partition(" ")
        if verb.lower() in _VERBS and rest:  # "who wrote the odyssey": the odyssey
            out.append(re.sub(r"^(?:the|a|an) ", "", rest) if len(rest.split()) > 1 else rest)
        out.append(stripped)  # only without a name: "genre is Covers" finds "Video game genre" (D-28)
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
    facts: str = ""  # the article's infobox as "Label: value" lines (director, born, capital, ...)


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
                 patient_s: float = 0.0, rank=None, user_agent: str = USER_AGENT, facts: bool = True):
        self.http = session or requests.Session()
        # Wikimedia requires a descriptive User-Agent and throttles generic ones; a Session's default
        # ("python-requests/x") must be replaced, not kept (defect D-21: setdefault never replaced it)
        if not str(self.http.headers.get("User-Agent", "")).startswith("CAMR"):
            self.http.headers["User-Agent"] = user_agent
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
        # Also read each article's infobox (one more request per page): the facts people ask about most (director,
        # born, capital, genre) are often there and not in the lead.
        self.facts = facts
        self._last = 0.0
        self._blocked_until: dict[str, float] = {}  # host -> time it may be asked again (Retry-After)
        self._backoff: dict[str, float] = {}  # host -> next pause after an empty or 429 reply (doubles, max 5 min)
        self._lock = threading.Lock()

    # ------------------------------------------------------------ HTTP
    def _get(self, url: str, params: dict | None, res: Lookup, parse=None,
             patient: float | None = None) -> tuple[int, dict | None]:
        """GET with cache, politeness and rate-limit handling. ``parse(text) -> dict`` replaces JSON decoding (and
        what is cached is its result, e.g. the lead of an HTML page rather than the page)."""
        key = url + ("?" + urllib.parse.urlencode(sorted(params.items())) if params else "")
        hit = self.cache.get(key)
        if hit is not None:
            res.cached += 1
            status, body = hit
            return status, (json.loads(body) if body else None)
        if self.offline:
            return 0, None
        host = urllib.parse.urlparse(url).netloc + ("/search" if "/search/" in url else "")
        patient_s = self.patient_s if patient is None else patient
        waited = 0.0
        while True:
            blocked = self._blocked_until.get(host, 0) - time.time()
            if blocked > 0:
                if waited + blocked > patient_s:
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
                if waited + pause > patient_s:
                    res.errors.append(f"{host}: rate limited")
                    return 429, None
                continue
            self._backoff.pop(host, None)
            break
        try:
            body = parse(r.text) if parse else r.json()
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

    def page_lead(self, title: str, res: Lookup) -> dict | None:
        """The lead paragraphs of a Wikipedia article read from its ordinary page (used when the API is rate
        limited). Only the extracted lead is cached; disambiguation pages give None."""
        t = urllib.parse.quote(title.strip().replace(" ", "_"), safe="()',")
        status, body = self._get(f"{self.wiki}/wiki/{t}", None, res, parse=_lead_from_html)
        if status != 200 or not body or not body.get("extract"):
            return None
        body.setdefault("url", f"{self.wiki}/wiki/{t}")
        return body

    def duckduckgo(self, query: str, res: Lookup) -> dict | None:
        status, body = self._get(DDG, {"q": query, "format": "json", "no_html": 1, "skip_disambig": 0,
                                       "no_redirect": 1}, res)
        return body if status in (200, 202) and body else None

    def wiki_search(self, query: str, res: Lookup, limit: int = 3) -> list[str]:
        """Article titles for a query: the search API when it answers at once, else the ordinary search page.

        Wikimedia rate limits its APIs per address, and a shared address (a proxy, a campus) can stay limited for
        hours; waiting it out cost two minutes a question (D-27). The search page is an ordinary page view."""
        status, body = self._get(f"{self.wiki}/w/rest.php/v1/search/page", {"q": query, "limit": limit}, res,
                                 patient=0.0)
        if status == 200 and body:
            return [p["title"] for p in body.get("pages", [])][:limit]
        status, body = self._get(f"{self.wiki}/w/index.php", {"search": query, "fulltext": "1", "ns0": "1",
                                                              "limit": max(limit, 5)}, res, parse=_search_titles)
        if status == 200 and body:
            return body.get("titles", [])[:limit]
        return []

    def article(self, name: str, res: Lookup) -> tuple[WebPage | None, list[tuple[str, str]]]:
        """The article a name refers to, or (None, [(title, description), ...]) when the name is ambiguous."""
        page, options = self._article(name, res)
        if page is not None and self.facts and not page.facts:
            lead = self.page_lead(page.title, res)
            if lead:
                page.facts = lead.get("facts", "")
        return page, options

    def _article(self, name: str, res: Lookup) -> tuple[WebPage | None, list[tuple[str, str]]]:
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
        lead = self.page_lead(name[:1].upper() + name[1:], res) if not (ddg and ddg.get("Type") == "D") else None
        if lead:
            return WebPage(title=lead.get("title", name), url=lead["url"], text=lead["extract"], source="wikipedia",
                           query=name, facts=lead.get("facts", "")), []
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

        found_names: list[str] = []  # names whose own article was found
        for query in subjects(question)[:max_queries]:
            if len(res.pages) >= max_pages:
                break
            if any(f" {norm(query)} " in f" {n} " for n in found_names):
                continue  # a fragment of a name already found ("The Baby" of "The Baby on the Barge", D-26)
            res.queries.append(query)
            page, options = self.article(query, res)
            if add(page):
                t, nq = base_title(page.title), base_title(query)
                if t == nq or t.startswith(nq + " "):  # "..., BWV 18" is still the name's own article
                    found_names.append(norm(query))
                continue
            if options:  # ambiguous: meanings named exactly what was asked first (D-24), then the closest to the question
                if self.rank is not None:
                    scores = self.rank(question, [f"{t}. {d}" for t, d in options])
                else:
                    scores = [len(qwords & set(norm(t + " " + d).split())) for t, d in options]
                named = base_title(query)
                ranked = [o for _, o in sorted(zip(scores, options), key=lambda x: (base_title(x[1][0]) != named,
                                                                                    -x[0]))]
                for title, _ in ranked[:2]:
                    add(self.article(title, res)[0])
                continue
            for title in self.wiki_search(query, res, limit=2):
                add(self.article(title, res)[0])
        res.ms = (time.perf_counter() - t0) * 1000
        return res

    def topic_pages(self, topic: str, limit: int = 20, min_relevance: float = 0.8) -> Lookup:
        """Pages about a topic, for harvesting a pack: the topic's article (or, for an ambiguous name, the meanings
        closest to the topic), related articles, then (snowballing) the articles for the names those pages mention
        most. A page is kept, and snowballed from, only if it is about the topic: its relevance (``rank``, else words
        shared with the topic) is at least ``min_relevance`` of the best seed's."""
        res = Lookup(question=topic, queries=[topic])
        t0 = time.perf_counter()
        twords = set(norm(topic).split())

        def relevance(texts: list[str]) -> list[float]:
            if self.rank is not None:
                return list(self.rank(topic, texts))
            return [len(twords & set(norm(t).split())) / max(1, len(twords)) for t in texts]

        seen: set[str] = set()
        candidates: list[WebPage] = []

        def fetch(title: str) -> WebPage | None:
            if norm(title) in seen:
                return None
            seen.add(norm(title))
            p, _ = self.article(title, res)
            if p is None or norm(p.title) in {norm(c.title) for c in candidates}:
                return None
            seen.add(norm(p.title))
            candidates.append(p)
            return p

        page, options = self.article(topic, res)
        seen.add(norm(topic))
        if page:
            candidates.append(page)
            seen.add(norm(page.title))
        if options:  # ambiguous: the meanings closest to the topic (an exact title first)
            scores = relevance([f"{t}. {d}" for t, d in options])
            ranked = sorted(zip(scores, options), key=lambda x: (norm(x[1][0]) != norm(topic), -x[0]))
            for _, (t, _) in ranked[:3]:
                fetch(t)
            if norm(topic) not in {norm(c.title) for c in candidates}:  # the name itself, from Wikipedia
                s_ = self.summary(topic[:1].upper() + topic[1:], res) or self.page_lead(topic[:1].upper() + topic[1:],
                                                                                           res)
                if s_:
                    candidates.insert(0, WebPage(title=s_.get("title", topic), url=s_.get("url") or _page_url(
                        s_, self.wiki, topic), text=" ".join(s_["extract"].split()), source="wikipedia", query=topic))
        ddg = self.duckduckgo(topic, res)
        for t in _flatten((ddg or {}).get("RelatedTopics") or [])[:limit]:
            url = t.get("FirstURL") or ""
            if url.startswith("https://duckduckgo.com/") and "/c/" not in url:
                fetch(urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("_", " "))
        for t in self.wiki_search(topic, res, limit=min(limit, 20)):
            fetch(t)
        kept: list[WebPage] = []
        scored: dict[str, float] = {}

        def admit() -> None:
            new = [c for c in candidates if norm(c.title) not in scored]
            if not new:
                return
            for c, sc in zip(new, relevance([f"{c.title}. {c.text}" for c in new])):
                scored[norm(c.title)] = sc
            best = max(scored.values())
            kept[:] = [c for c in candidates if scored[norm(c.title)] >= min_relevance * best][:limit]

        admit()
        frontier = 0
        while len(kept) < limit and frontier < len(kept):  # snowball over names that on-topic pages mention
            counts: dict[str, int] = {}
            for p in kept[frontier:]:
                for m in _CAP_RUN.finditer(p.text):
                    run = m.group(1).strip(" .,'’")
                    for name in [run, *run.split(" and ")] if " and " in run else [run]:  # "Jupiter and Saturn"
                        if (len(name) >= 4 and " " in name) or len(name) >= 6:
                            counts[name] = counts.get(name, 0) + 1
            frontier = len(kept)
            for name, _ in sorted(counts.items(), key=lambda kv: -kv[1])[: 2 * limit]:
                if len(kept) >= limit:
                    break
                if fetch(name):
                    admit()
        res.pages = kept[:limit]
        res.ms = (time.perf_counter() - t0) * 1000
        return res


def base_title(title: str) -> str:
    """'The Bench (film)' -> 'bench': the name an article title gives, without its qualifier or article."""
    t = norm(re.sub(r"\s*\([^)]*\)\s*$", "", title))
    return re.sub(r"^(?:the|a|an) ", "", t)


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


_P = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
# a tag whose quoted attributes may contain ">" (Wikipedia's data-mw='{...}' attributes do)
_TAG = re.compile(r"""<(?:[^>"']|"[^"]*"|'[^']*')*>""")
_REF = re.compile(r"\[(?:\d+|[a-z]|note \d+|citation needed)\]")


_ATTRS = r"""(?:[^>"']|"[^"]*"|'[^']*')*"""  # attributes, whose quoted values may contain ">"
_ROW = re.compile(rf"<tr\b{_ATTRS}>(.*?)</tr>", re.S)
_TH = re.compile(rf"<th\b{_ATTRS}>(.*?)</th>", re.S)
_TD = re.compile(rf"<td\b{_ATTRS}>(.*?)</td>", re.S)


def _infobox(html: str) -> str:
    """The first infobox of an article as 'Label: value' lines. Infoboxes hold the facts people ask about
    (directed by, born, capital, genre...), which the lead paragraphs often leave out."""
    import html as _html

    start = html.find('class="infobox')
    if start < 0:
        return ""
    start = html.rfind("<table", 0, start)
    depth, i = 0, start
    for m in re.finditer(r"<(/?)table\b", html[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            i = start + m.end()
            break
    box = html[start:i]
    lines = []
    for row in _ROW.findall(box):
        th, td = _TH.search(row), _TD.search(row)
        if not th or not td:
            continue
        def clean(x: str) -> str:
            x = re.sub(r"<(br|/li|/p)[^>]*>", ", ", x)
            x = re.sub(r"<(style|sup)\b.*?</\1>", " ", x, flags=re.S)
            x = _REF.sub("", _html.unescape(_TAG.sub(" ", x)))
            x = re.sub(r"\(\s*\d{4}-\d{2}-\d{2}\s*\)", "", x)  # "9 February 1970 ( 1970-02-09 )": the ISO copy
            return " ".join(x.replace(" ,", ",").split()).strip(" ,;")
        label, value = clean(th.group(1)), clean(td.group(1))
        if label and value and len(label) <= 40:
            lines.append(f"{label}: {value[:160]}")
        if len(lines) >= 24:
            break
    return "; ".join(lines)


_HIT = re.compile(r'<div class="mw-search-result-heading"><a href="/wiki/[^"]+" title="([^"]+)"')


def _search_titles(html: str) -> dict:
    """Result titles of Wikipedia's search page (or the article itself, when the search went straight to it)."""
    import html as _html

    titles = [_html.unescape(t) for t in _HIT.findall(html)]
    if not titles and 'id="mw-content-text"' in html:  # an exact title match redirects to the article
        t = re.search(r"<title>(.*?) - Wikipedia</title>", html)
        titles = [_html.unescape(t.group(1))] if t else []
    return {"titles": titles}


def _lead_from_html(html: str, max_chars: int = 1200) -> dict:
    """Title, lead paragraphs and infobox facts of a Wikipedia article page; {} for a disambiguation page."""
    import html as _html

    title = re.search(r"<title>(.*?) - Wikipedia</title>", html)
    facts = _infobox(html)
    body = html.split('id="mw-content-text"', 1)[-1]
    body = re.split(r'<div class="mw-heading|<h2', body, maxsplit=1)[0]  # the lead ends at the first section
    if 'id="disambigbox"' in html or "may refer to:" in body[:3000]:
        return {}
    body = re.sub(r"<(table|style|sup|figure)\b.*?</\1>", " ", body, flags=re.S)
    paras = []
    for m in _P.finditer(body):
        t = _REF.sub("", _html.unescape(_TAG.sub("", m.group(1))))
        t = " ".join(t.split())
        if len(t) > 60:
            paras.append(t)
        if sum(len(p) for p in paras) > max_chars:
            break
    text = " ".join(paras)[:max_chars]
    return {"title": _html.unescape(title.group(1)) if title else "", "extract": text, "facts": facts} if text else {}


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
