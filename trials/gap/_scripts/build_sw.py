import re, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import html2md
RAW = "../_raw/sw/"; OUT = "../vault/Software/"
def write(name, url, title, published, body):
    body = re.sub(r"\n{3,}", "\n\n", body.replace("\r\n", "\n")).strip()
    fm = f"---\nsource: {url}\nfetched: 2026-11-10\npublished: {published}\ntitle: {title}\n---\n\n"
    open(OUT + name, "w").write(fm + body + "\n")
    print(f"{name:58s} {len(body):6d} chars  published {published}")

# ---- SQLite
md = html2md.to_md(html2md.parse(open(RAW + "sqlite_changes.html").read()))
ents = [(m.group(1), m.group(2), m.start()) for m in re.finditer(r"^### (20\d\d-\d\d-\d\d) \((.*?)\)", md, re.M)]
def ent(ver):
    for i, (d, v, s) in enumerate(ents):
        if v == ver: return d, md[s:ents[i + 1][2]].strip()
U = "https://sqlite.org/changes.html"
e = [ent(v) for v in ("3.53.4", "3.53.3", "3.53.2", "3.53.1", "3.53.0", "3.51.3", "3.52.0", "3.51.2")]
write("sqlite-releases-2026-01-to-07-3.51.2-to-3.53.4.md", U, "SQLite Release History — releases 3.51.2, 3.52.0, 3.51.3 and 3.53.0 to 3.53.4 (January to July 2026)",
      "2026-01-09 to 2026-07-24", "# Release History Of SQLite (releases dated January to July 2026)\n\n" + "\n\n".join(b for _, b in e))
e = [ent(v) for v in ("3.54.1", "3.54.0")]
write("sqlite-releases-2026-10-3.54.0-and-3.54.1.md", U, "SQLite Release History — releases 3.54.0 and 3.54.1 (October 2026)",
      "2026-10-09 to 2026-10-16", "# Release History Of SQLite (releases dated October 2026)\n\n" + "\n\n".join(b for _, b in e))

# ---- Python 3.15
root = html2md.parse(open(RAW + "py315.html").read())
body = html2md.find(root, lambda n: n.attrs.get("role") == "main")
md = html2md.to_md(body)
def at(h):
    i = md.index("\n" + h + "\n"); return i + 1
cuts = [("python-3.15-whatsnew-01-highlights-lazy-imports-frozendict-tachyon.md", 0, "Summary, PEP 810 lazy imports, frozendict, sentinel, profiling and Tachyon"),
        ("python-3.15-whatsnew-02-new-features-continued.md", at("### PEP 831: Frame pointers enabled by default"), "New features continued: PEP 831, 798, 829, 803, 788 and improved error messages"),
        ("python-3.15-whatsnew-03-other-language-changes.md", at("## Other language changes"), "Other language changes, default interactive shell, new modules"),
        ("python-3.15-whatsnew-04-improved-modules-a-to-m.md", at("## Improved modules"), "Improved modules, argparse to mmap"),
        ("python-3.15-whatsnew-05-improved-modules-o-to-z.md", at("### os"), "Improved modules, os to zlib"),
        ("python-3.15-whatsnew-06-optimizations-and-removed.md", at("## Optimizations"), "Optimizations and Removed"),
        ("python-3.15-whatsnew-07-deprecated.md", at("## Deprecated"), "Deprecated and pending removals"),
        ("python-3.15-whatsnew-08-c-api-build-porting.md", at("## C API changes"), "C API changes, build changes, porting, notable changes in 3.15.2")]
PU = "https://docs.python.org/3.15/whatsnew/3.15.html"
for i, (name, start, t) in enumerate(cuts):
    end = cuts[i + 1][1] if i + 1 < len(cuts) else len(md)
    chunk = md[start:end]
    if i: chunk = f"# What’s new in Python 3.15 (continued: {t})\n\n" + chunk
    write(name, PU, f"What’s new in Python 3.15 — {t}", "2026-10-09", chunk)

# ---- MCP 2026-07-28
MB = "https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/docs/specification/2026-07-28/"
for f, slug in [("changelog", "changelog"), ("basic/versioning", "versioning"), ("basic/patterns/mrtr", "multi-round-trip-requests"),
                ("basic/patterns/subscriptions", "subscriptions"), ("server/discover", "server-discover"),
                ("server/utilities/caching", "caching"), ("basic/transports/stdio", "stdio-transport"), ("deprecated", "deprecated-features")]:
    s = open(RAW + "mcp/" + f.replace("/", "_") + ".mdx").read()
    m = re.match(r"---\n(.*?)\n---\n", s, re.S)
    title = re.search(r"^title:\s*(.*)$", m.group(1), re.M).group(1).strip().strip('"')
    rest = s[m.end():].replace('<div id="enable-section-numbers" />', "")
    write(f"mcp-2026-07-28-{slug}.md", MB + f + ".mdx", f"Model Context Protocol specification, revision 2026-07-28 — {title}", "2026-07-28", f"# {title}\n\n" + rest)

# ---- Ollama releases
rels = []
for p in (1, 2, 3):
    for r in json.load(open(RAW + f"ollama_{p}.json")):
        if r["prerelease"] or r["draft"] or not r["published_at"].startswith("2026"): continue
        rels.append(r)
def key(r): return tuple(int(x) for x in re.findall(r"\d+", r["tag_name"])[:3])
rels.sort(key=key)
def body(r):
    b = (r["body"] or "").replace("\r\n", "\n")
    b = re.sub(r"\n#+ New Contributors\n.*?(?=\n\*\*Full Changelog|\Z)", "\n", b, flags=re.S)
    b = re.sub(r"^(#+ )", r"#\1", b, flags=re.M)
    return f"## {r['tag_name']} (published {r['published_at'][:10]})\n\nRelease page: {r['html_url']}\n\n" + b.strip()
groups = [((0, 14), (0, 16)), ((0, 17), (0, 19)), ((0, 20), (0, 24)), ((0, 30), (0, 31)), ((0, 32), (0, 33)), ((0, 34), (0, 35)), ((0, 40), (0, 40))]
for lo, hi in groups:
    g = [r for r in rels if lo <= key(r)[:2] <= hi]
    dates = sorted(r["published_at"][:10] for r in g)
    a, b = g[0]["tag_name"], g[-1]["tag_name"]
    write(f"ollama-releases-{a}-to-{b}.md", "https://github.com/ollama/ollama/releases", f"Ollama release notes — {a} to {b} ({len(g)} releases)",
          f"{dates[0]} to {dates[-1]}", f"# Ollama release notes: {a} to {b}\n\n" + "\n\n".join(body(r) for r in g))
print(len(rels), "ollama releases")
