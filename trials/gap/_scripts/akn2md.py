"""Convert a saved Kenya Law AKN HTML fragment into Markdown chunks (verbatim text)."""
import re, sys, html
from html.parser import HTMLParser

class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs), parent, []
    @property
    def cls(self): return (self.attrs.get("class") or "").split()

VOID = {"img", "br", "hr", "input", "meta", "link"}
class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", [], None); self.cur = self.root
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur); self.cur.kids.append(n)
        if tag not in VOID: self.cur = n
    def handle_endtag(self, tag):
        c = self.cur
        while c is not self.root and c.tag != tag: c = c.parent
        if c is not self.root: self.cur = c.parent
    def handle_data(self, d): self.cur.kids.append(d)

def text(n):
    if isinstance(n, str): return n
    if n.tag == "img": return ""
    if n.tag == "br": return " "
    return "".join(text(k) for k in n.kids)
def clean(s): return re.sub(r"\s+", " ", s).strip()

def table(n, out):
    rows = []
    def walk(x):
        if isinstance(x, str): return
        if x.tag == "tr":
            rows.append([clean(text(c)).replace("|", "\\|") for c in x.kids if not isinstance(c, str) and c.tag in ("td", "th")])
        else:
            for k in x.kids: walk(k)
    walk(n)
    rows = [r for r in rows if any(r)]
    if not rows: return
    w = max(len(r) for r in rows)
    if w == 1:
        for r in rows: out.append(r[0])
        return
    lines = []
    for i, r in enumerate(rows):
        r = r + [""] * (w - len(r))
        lines.append("| " + " | ".join(r) + " |")
        if i == 0: lines.append("|" + " --- |" * w)
    out.append("\n".join(lines))

def render(n, out, pend):
    """pend: list holding pending number prefixes to attach to next paragraph."""
    if isinstance(n, str):
        t = clean(n)
        if t: out.append(" ".join(pend + [t])); pend.clear()
        return
    c = n.cls
    if n.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        t = clean(text(n))
        if t:
            lvl = {"h1": "#", "h2": "##", "h3": "###"}.get(n.tag, "####")
            out.append(f"{lvl} {t}")
        return
    if "akn-num" in c:
        t = clean(text(n))
        if t: pend.append(t)
        return
    if n.tag == "table":
        if pend: out.append(" ".join(pend)); pend.clear()
        table(n, out); return
    if "akn-p" in c or n.tag in ("li", "p"):
        # a paragraph may contain a nested table
        if any((not isinstance(k, str)) and k.tag in ("table", "div") for k in n.kids):
            for k in n.kids: render(k, out, pend)
            return
        t = clean(text(n))
        if t:
            if n.tag == "li": t = "- " + t
            out.append(" ".join(pend + [t])); pend.clear()
        return
    if n.tag in ("img", "hr", "la-decorate-terms", "la-decorate-internal-refs", "la-decorate-external-refs"): return
    for k in n.kids: render(k, out, pend)

def find(n, pred, acc):
    if isinstance(n, str): return acc
    if pred(n): acc.append(n); return acc
    for k in n.kids: find(k, pred, acc)
    return acc

def chunks(src):
    p = P(); p.feed(src)
    tops = find(p.root, lambda n: "coverpage" in n.cls or "akn-preface" in n.cls or "akn-part" in n.cls
                or "akn-attachment" in n.cls or "akn-wrapUp" in n.cls
                or ("akn-section" in n.cls), [])
    res = []
    for t in tops:
        out = []; render(t, out, [])
        kind = [c for c in t.cls if c in ("coverpage", "akn-preface", "akn-part", "akn-attachment", "akn-wrapUp", "akn-section")][0]
        res.append((kind, "\n\n".join(out)))
    return res

if __name__ == "__main__":
    for kind, md in chunks(open(sys.argv[1]).read()):
        print(kind, len(md), repr(md[:90]))
