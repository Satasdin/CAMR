"""Small HTML -> Markdown converter (text kept verbatim; inline formatting reduced to `code`)."""
import re
from html.parser import HTMLParser
VOID = {"img", "br", "hr", "input", "meta", "link", "wbr", "col"}
SKIP = {"script", "style", "nav", "noscript", "svg", "button", "form", "head"}
BLOCK = {"p", "div", "section", "article", "ul", "ol", "li", "pre", "table", "dl", "dt", "dd", "blockquote",
         "h1", "h2", "h3", "h4", "h5", "h6", "body", "html", "main", "aside", "details", "summary", "figure", "center", "tr", "td", "th", "tbody", "thead"}
class Node:
    def __init__(s, tag, attrs, parent): s.tag, s.attrs, s.parent, s.kids = tag, dict(attrs), parent, []
    def cls(s): return (s.attrs.get("class") or "").split()
class P(HTMLParser):
    def __init__(s):
        super().__init__(convert_charrefs=True); s.root = Node("root", [], None); s.cur = s.root
    def handle_starttag(s, tag, attrs):
        if tag == "li":  # implicit close of open <li> (sqlite style)
            c = s.cur
            while c is not s.root and c.tag not in ("ul", "ol", "li"): c = c.parent
            if c.tag == "li": s.cur = c.parent
        if tag == "p":
            if s.cur.tag == "p": s.cur = s.cur.parent
        n = Node(tag, attrs, s.cur); s.cur.kids.append(n)
        if tag not in VOID: s.cur = n
    def handle_endtag(s, tag):
        c = s.cur
        while c is not s.root and c.tag != tag: c = c.parent
        if c is not s.root: s.cur = c.parent
    def handle_data(s, d): s.cur.kids.append(d)
def parse(src):
    p = P(); p.feed(src); return p.root
def find(n, pred):
    if isinstance(n, str): return None
    if pred(n): return n
    for k in n.kids:
        r = find(k, pred)
        if r: return r
def rawtext(n):
    if isinstance(n, str): return n
    if n.tag in SKIP: return ""
    return "".join(rawtext(k) for k in n.kids)
def inline(n):
    if isinstance(n, str): return n
    if n.tag in SKIP or "headerlink" in n.cls(): return ""
    if n.tag == "br": return "\n"
    if n.tag in ("code", "tt", "kbd", "samp") or (n.tag == "span" and "pre" in n.cls() and n.parent.tag != "code" and False):
        t = rawtext(n).strip()
        return f"`{t}`" if t else ""
    return "".join(inline(k) for k in n.kids)
def ws(s): return re.sub(r"[ \t\r\n]+", " ", s).strip()
def is_block(n): return (not isinstance(n, str)) and n.tag in BLOCK
def blocks(n, out, depth=0):
    """Append markdown blocks for node n's children."""
    buf = []
    def flush():
        t = ws("".join(buf)); buf.clear()
        if t: out.append(t)
    for k in n.kids:
        if isinstance(k, str): buf.append(k); continue
        if k.tag in SKIP or "headerlink" in k.cls(): continue
        if k.tag == "hr": flush(); continue
        if not is_block(k) and not find(k, is_block): buf.append(inline(k)); continue
        flush()
        t = k.tag
        if t in ("h1", "h2", "h3", "h4", "h5", "h6"):
            h = ws(inline(k))
            if h: out.append("#" * int(t[1]) + " " + h)
        elif t == "pre":
            out.append("```\n" + rawtext(k).strip("\n") + "\n```")
        elif t in ("ul", "ol"):
            out.append(lst(k, depth))
        elif t == "table":
            out.append(table(k))
        elif t == "dt":
            h = ws(inline(k))
            if h: out.append(f"**{h}**")
        elif t == "blockquote":
            sub = []; blocks(k, sub, depth)
            out.append("\n\n".join("> " + s.replace("\n", "\n> ") for s in sub))
        else:
            blocks(k, out, depth)
    flush()
def lst(n, depth):
    lines = []; i = 0
    for k in n.kids:
        if isinstance(k, str) or k.tag != "li":
            if not isinstance(k, str) and k.tag in ("ul", "ol"): lines.append(lst(k, depth + 1))
            else:
                tmp = Node("div", [], None); tmp.kids = [k]; sub = []; blocks(tmp, sub, depth + 1)
                for s_ in sub: lines.append("  " * depth + s_)
            continue
        i += 1
        sub = []; blocks(k, sub, depth + 1)
        mark = f"{i}." if n.tag == "ol" else "-"
        if n.tag == "ol" and (n.attrs.get("type") == "a") and i <= 26: mark = "abcdefghijklmnopqrstuvwxyz"[i - 1] + "."
        pad = "  " * depth
        first = True
        for s in sub:
            if first:
                if s.lstrip().startswith(("- ", "1. ")) and not s.startswith(("- ", "1. ")) or re.match(r"\s+(-|\d+\.) ", s):
                    lines.append(f"{pad}{mark}"); lines.append(s)
                else:
                    lines.append(f"{pad}{mark} " + s.replace("\n", "\n" + pad + "  "))
                first = False
            elif re.match(r"\s*(-|\d+\.|[a-z]\.) ", s) and s.startswith("  " * (depth + 1)):
                lines.append(s)
            else:
                lines.append(pad + "  " + s.replace("\n", "\n" + pad + "  "))
    return "\n".join(l for l in lines if l.strip())
def table(n):
    rows = []
    def walk(x):
        if isinstance(x, str): return
        if x.tag == "tr":
            rows.append([ws(inline(c)).replace("|", "\\|") for c in x.kids if not isinstance(c, str) and c.tag in ("td", "th")])
        else:
            for k in x.kids: walk(k)
    walk(n)
    rows = [r for r in rows if any(r)]
    if not rows: return ""
    w = max(len(r) for r in rows); L = []
    for i, r in enumerate(rows):
        L.append("| " + " | ".join(r + [""] * (w - len(r))) + " |")
        if i == 0: L.append("|" + " --- |" * w)
    return "\n".join(L)
def to_md(node):
    out = []; blocks(node, out)
    return "\n\n".join(o for o in out if o.strip())
