#!/usr/bin/env python3
"""Turns the verified APA list (chapters4/7-references.md) into reference-manager files:
burrow-references.json (CSL-JSON), burrow-references.ris and burrow-references.bib.
Author lists that APA shortens with an ellipsis are completed from the arXiv record of the same paper."""
import json, re, sys, urllib.request, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "chapters4" / "7-references.md"
CACHE = HERE / "arxiv-authors.json"
MONTHS = {m: i + 1 for i, m in enumerate("January February March April May June July August September October November December".split())}
AUTHOR = re.compile(r"\s*(?P<family>[^,&]+?), (?P<given>(?:[A-ZÀ-Ý]\.(?:-[A-Za-z]\.)?\s?)+)(?:,|$|\s&|\s\.)")

def authors(text):
    text = text.strip()
    if not re.search(r", [A-ZÀ-Ý]\.", text):
        return [{"literal": text.rstrip(".")}], False
    cut = ". . ." in text
    out = []
    pos = 0
    body = text.replace(". . .", "").replace("&", ",")
    for part in re.finditer(r"([^,]+), ((?:[A-ZÀ-Ý]\.(?:-[A-Za-z]\.)?\s?)+)", body):
        out.append({"family": part.group(1).strip(" ,"), "given": part.group(2).strip()})
    return out, cut

def arxiv_authors(ident, cache):
    if ident in cache: return cache[ident]
    xml = urllib.request.urlopen(f"http://export.arxiv.org/api/query?id_list={ident}", timeout=30).read().decode()
    names = re.findall(r"<name>(.*?)</name>", xml)
    people = []
    for name in names:
        bits = name.split()
        people.append({"family": bits[-1], "given": " ".join(bits[:-1])})
    people = [p for p in people if p["given"]]  # a collective name such as "Qwen" heads some records
    cache[ident] = people
    return people

def strip(text): return text.replace("*", "").strip()

def parse(line, cache):
    entry = line[2:].strip()
    url = re.search(r"(https?://\S+)$", entry)
    link = url.group(1) if url else ""
    entry = entry[: url.start()].strip() if url else entry
    item = {}
    if entry.startswith("Data Protection Act"):
        item = {"type": "report", "title": "Data Protection Act", "number": "No. 24 of 2019", "publisher": "Laws of Kenya", "author": [],
                "issued": {"date-parts": [[2019]]}, "URL": link, "_apa": line[2:]}
        return item
    m = re.match(r"(?P<auth>.+?) \((?P<date>\d{4}[a-z]?(?:, [A-Z][a-z]+(?: \d{1,2})?)?)\)\. (?P<rest>.*)$", entry)
    if not m: sys.exit("cannot parse: " + line[:90])
    people, cut = authors(m.group("auth"))
    date = m.group("date")
    year = int(date[:4]); parts = [year]
    dm = re.search(r", ([A-Z][a-z]+)(?: (\d{1,2}))?", date)
    if dm:
        parts.append(MONTHS[dm.group(1)])
        if dm.group(2): parts.append(int(dm.group(2)))
    rest = m.group("rest").strip()
    item["issued"] = {"date-parts": [parts]}
    doi = re.match(r"https?://doi\.org/(.+)", link)
    if doi: item["DOI"] = doi.group(1)
    if link: item["URL"] = link
    ax = re.search(r"arXiv\.(\d{4}\.\d{5})|arxiv\.org/abs/(\d{4}\.\d{5})", link)
    if not ax and entry.startswith("Borgeaud,"):   # the verified entry links to PMLR; the same paper is on arXiv
        ax = re.search(r"(2112\.04426)|(x)", "2112.04426")
    if cut:
        if not ax: sys.exit("shortened author list without an arXiv record: " + line[:80])
        short = people
        people = arxiv_authors(ax.group(1) or ax.group(2), cache)
        if people[0]["family"] != short[0]["family"] or people[-1]["family"] != short[-1]["family"]:
            sys.exit(f"arXiv authors do not match the verified entry: {short[0]} {short[-1]} against {people[0]} {people[-1]}")
    item["author"] = people
    if rest.startswith("*"):
        t = re.match(r"\*(?P<title>.+?)\*(?P<tail>.*)$", rest)
        title, tail = t.group("title"), t.group("tail").strip()
        item["title"] = title.rstrip(".")
        if tail.startswith("[Paper presentation]"):
            item["type"] = "speech"; item["genre"] = "Paper presentation"
            item["event-title"] = tail[len("[Paper presentation]."):].strip().rstrip(".")
        elif tail.startswith("[Computer software]"):
            item["type"] = "software"; item["genre"] = "Computer software"
        elif tail.strip(". ") == "arXiv":
            item["type"] = "article"; item["publisher"] = "arXiv"
        else:
            site = tail.strip(". ")
            item["type"] = "webpage" if (site or not doi) else "report"
            if site: item["container-title"] = site
    else:
        t = re.match(r"(?P<title>.+?[.?!]) (?P<tail>(?:In )?\*.*)$", rest)
        if not t: sys.exit("cannot split title: " + rest[:90])
        item["title"] = t.group("title").rstrip(".")
        tail = t.group("tail")
        if tail.startswith("In *"):
            c = re.match(r"In \*(?P<cont>.+?)\*(?: \((?P<paren>[^)]*)\))?\.(?: (?P<pub>.+?)\.)?$", tail)
            if not c: sys.exit("cannot parse proceedings: " + tail[:120])
            item["type"] = "paper-conference"; item["container-title"] = c.group("cont")
            paren = c.group("paren") or ""
            v = re.search(r"Vol\. (\d+)", paren); pg = re.search(r"pp\. ([\d–-]+)", paren)
            series = re.match(r"(.+?), Vol\.", paren)
            if series: item["collection-title"] = series.group(1)
            if v: item["volume"] = v.group(1)
            if pg: item["page"] = pg.group(1).replace("–", "-")
            if c.group("pub"): item["publisher"] = c.group("pub")
        else:
            j = re.match(r"\*(?P<j>.+?)\*(?:, \*(?P<vol>\d+)\*)?(?:\((?P<iss>\d+)\))?(?:, (?P<pg>[\d–-]+))?\.$", tail)
            if not j: sys.exit("cannot parse journal: " + tail[:120])
            item["type"] = "article-journal"; item["container-title"] = j.group("j").rstrip(",")
            if j.group("vol"): item["volume"] = j.group("vol")
            if j.group("iss"): item["issue"] = j.group("iss")
            if j.group("pg"): item["page"] = j.group("pg").replace("–", "-")
    item["_apa"] = line[2:]
    return item

def key_of(item, used):
    first = item["author"][0] if item["author"] else {"literal": "".join(item["title"].split())}
    name = first.get("family") or first["literal"]
    base = re.sub(r"[^A-Za-z]", "", name.split()[0] if "literal" in first and len(name.split()) > 3 else name) + str(item["issued"]["date-parts"][0][0])
    key = base; n = 0
    while key in used:
        n += 1; key = base + "abcdefgh"[n]
    used.add(key)
    return key

def ris(item):
    kind = {"article-journal": "JOUR", "paper-conference": "CONF", "article": "GEN", "speech": "CPAPER", "software": "COMP", "webpage": "ELEC", "report": "RPRT"}[item["type"]]
    rows = [("TY", kind)]
    for a in item["author"]:
        rows.append(("AU", a["literal"] if "literal" in a else f'{a["family"]}, {a["given"]}'))
    rows.append(("TI", item["title"]))
    d = item["issued"]["date-parts"][0]
    rows.append(("PY", str(d[0])))
    if len(d) > 1: rows.append(("DA", "/".join(f"{x:02d}" if i else str(x) for i, x in enumerate(d))))
    ct = item.get("container-title") or item.get("event-title")
    if ct: rows.append(("JO" if kind == "JOUR" else "T2", ct))
    for tag, field in (("VL", "volume"), ("IS", "issue"), ("PB", "publisher"), ("DO", "DOI"), ("UR", "URL")):
        if item.get(field): rows.append((tag, item[field]))
    if item.get("page"):
        a, _, b = item["page"].partition("-"); rows.append(("SP", a));
        if b: rows.append(("EP", b))
    rows.append(("ER", ""))
    return "\n".join(f"{t}  - {v}" for t, v in rows)

def bib(item):
    kind = {"article-journal": "article", "paper-conference": "inproceedings", "article": "misc", "speech": "inproceedings", "software": "misc", "webpage": "misc", "report": "techreport"}[item["type"]]
    names = " and ".join("{" + a["literal"] + "}" if "literal" in a else f'{a["family"]}, {a["given"]}' for a in item["author"])
    fields = [("author", names), ("title", "{" + item["title"] + "}"), ("year", str(item["issued"]["date-parts"][0][0]))]
    ct = item.get("container-title") or item.get("event-title")
    if ct: fields.append(("journal" if kind == "article" else ("booktitle" if kind == "inproceedings" else "howpublished"), ct))
    for name in ("volume", "publisher"):
        if item.get(name): fields.append((name, item[name]))
    if item.get("issue"): fields.append(("number", item["issue"]))
    if item.get("page"): fields.append(("pages", item["page"].replace("-", "--")))
    if item.get("DOI"): fields.append(("doi", item["DOI"]))
    if item.get("URL"): fields.append(("url", item["URL"]))
    return "@" + kind + "{" + item["id"] + ",\n" + ",\n".join(f"  {k} = {{{v}}}" for k, v in fields) + "\n}"

def main():
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    items, used = [], set()
    for line in SRC.read_text().split("\n"):
        if not line.startswith("@ "): continue
        item = parse(line, cache)
        item["id"] = key_of(item, used)
        items.append(item)
    CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    (HERE / "burrow-references.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))
    cited = HERE / "cited-keys.json"   # written by build_word.py: the sources the report actually cites
    keep = set(json.loads(cited.read_text())) if cited.exists() else {i["id"] for i in items}
    chosen = [i for i in items if i["id"] in keep]
    (HERE / "burrow-references.ris").write_text("\n\n".join(ris(i) for i in chosen) + "\n")
    (HERE / "burrow-references.bib").write_text("\n\n".join(bib(i) for i in chosen) + "\n")
    print(len(chosen), "written to the .ris and .bib files")
    print(len(items), "references")
    for i in items:
        a = i["author"]
        print(f'{i["id"]:22} {i["type"]:17} {len(a):3} {i["title"][:50]!r} | {i.get("container-title", i.get("event-title", i.get("publisher", "")))[:40]} | {i.get("volume","")}({i.get("issue","")}) {i.get("page","")}')

main()
