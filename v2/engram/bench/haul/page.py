"""The page that grows: a design system set in week 1, a new main colour on day 61, and pages asked for at the end.

A page answer is checked with HTML and CSS rules (``html.parser`` from the standard library), and, when asked for,
by loading it in a headless browser. The browser check is skipped with a note when no browser is installed.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

OLD_COLOUR = "#0B5FFF"
NEW_COLOUR = "#7C3AED"
FONT = "Inter"
NAV = ["Home", "Menu", "Catering", "Contact"]
FOOTER = "© 2026 Mama Njeri's Kitchen · Nairobi"
SPACING = [0, 4, 8, 16, 24, 32, 48, 64]  # px; rem and em count as 16 px each
TEXT_COLOUR = "#1A1A1A"
ACCENT = "#F59E0B"
SURFACE = "#FFF8EE"

DESIGN_DAY, CHANGE_DAY = 4, 61

DESIGN_SYSTEM = (
    "Design system for the site, final, please stick to it everywhere from now on:\n"
    f"- main colour #0B5FFF (buttons, links, the nav bar)\n"
    f"- text {TEXT_COLOUR} on white, accent {ACCENT} for prices and badges, section background {SURFACE}\n"
    "- font Inter for everything, with system-ui as the fallback\n"
    "- spacing only from the scale 4, 8, 16, 24, 32, 48, 64 px (margins, paddings and gaps; nothing in between)\n"
    "- nav Home · Menu · Catering · Contact, in that order, on every page\n"
    "- footer \"© 2026 Mama Njeri's Kitchen · Nairobi\", exactly that text\n"
    "- and every image needs alt text, no exceptions (Mama Njeri's nephew uses a screen reader)")
DESIGN_TOKENS = (
    "Here are the tokens as CSS so every page shares them:\n\n```css\n:root {\n"
    f"  --main: {OLD_COLOUR};\n  --text: {TEXT_COLOUR};\n  --accent: {ACCENT};\n  --surface: {SURFACE};\n"
    "  --font: \"Inter\", system-ui, sans-serif;\n  --space-1: 4px;\n  --space-2: 8px;\n  --space-3: 16px;\n"
    "  --space-4: 24px;\n  --space-5: 32px;\n  --space-6: 48px;\n  --space-7: 64px;\n}\n"
    "body { font-family: var(--font); color: var(--text); margin: 0; }\n"
    "nav a { color: var(--main); padding: var(--space-2) var(--space-3); }\n"
    ".button { background: var(--main); color: #fff; padding: var(--space-2) var(--space-4); }\n```\n\n"
    "The nav and footer go in the base template, so every page gets them unchanged.")
COLOUR_CHANGE = "Main colour is now #7C3AED."
COLOUR_CHANGE_REPLY = (
    "Done: `--main` is now #7C3AED in the tokens, and the buttons, links and nav bar pick it up from there.\n\n"
    "```css\n:root {\n  --main: #7C3AED;\n}\n```\n\nNothing else in the design system changes.")

PAGES = [  # id, ask, the word its h1 must contain, sample
    ("page-catering", "Build the catering page.", "Catering", True),
    ("page-contact", "Build the contact page: the four branches with a map link each, and a short message form.",
     "Contact", False),
    ("page-about", "Build the about page: Mama Njeri's story, the kitchen team, and photos of the Westlands kitchen.",
     "About", False),
]


def spec(colour: str, old: list[str], h1: str) -> dict:
    return {"type": "page", "colour": colour, "old": old, "font": FONT, "nav": NAV, "footer": FOOTER,
            "spacing": SPACING, "h1": h1}


# --------------------------------------------------------------------------------------------------------------

class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nav_depth = self.footer_depth = self.h1_depth = 0
        self.link: list[str] | None = None
        self.nav_links: list[str] = []
        self.footer: list[str] = []
        self.footers: list[str] = []
        self.images: list[dict] = []
        self.css: list[str] = []
        self.h1: list[str] = []
        self.in_style = False
        self.tags = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags += 1
        a = {k: (v or "") for k, v in attrs}
        if a.get("style"):
            self.css.append("x{" + a["style"] + "}")
        if tag == "nav":
            self.nav_depth += 1
        elif tag == "footer":
            self.footer_depth += 1
            if self.footer_depth == 1:
                self.footer = []
        elif tag == "a" and self.nav_depth:
            self.link = []
        elif tag == "img":
            self.images.append(a)
        elif tag == "style":
            self.in_style = True
        elif tag == "h1":
            self.h1_depth += 1
            self.h1.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self.nav_depth = max(0, self.nav_depth - 1)
        elif tag == "footer" and self.footer_depth:
            self.footer_depth -= 1
            if self.footer_depth == 0:
                self.footers.append(" ".join(self.footer))
        elif tag == "a" and self.link is not None:
            self.nav_links.append(" ".join(self.link))
            self.link = None
        elif tag == "style":
            self.in_style = False
        elif tag == "h1" and self.h1_depth:
            self.h1_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_style:
            self.css.append(data)
            return
        if self.link is not None:
            self.link.append(data)
        if self.footer_depth:
            self.footer.append(data)
        if self.h1_depth and self.h1:
            self.h1[-1] += data


_FENCE = re.compile(r"```([\w+-]*)[ \t]*\n(.*?)```", re.S)


def extract_html(answer: str) -> str | None:
    """The page in an answer: its ```html blocks (plus any ```css blocks as a style tag), or the bare markup."""
    blocks = _FENCE.findall(answer)
    html = [b for lang, b in blocks if lang.lower() in ("html", "htm", "") and re.search(r"<[a-zA-Z!]", b)]
    css = [b for lang, b in blocks if lang.lower() == "css"]
    if not html and re.search(r"<(?:!doctype|html|body|nav|main|header|section)\b", answer, re.I):
        html = [answer]
    if not html:
        return None
    src = "\n".join(html)
    if css:
        src += "\n<style>\n" + "\n".join(css) + "\n</style>\n"
    return src


def _text(s: str) -> str:
    return " ".join(s.replace("’", "'").replace(" ", " ").split())


def colours(css_and_html: str) -> set[str]:
    """Every colour written as #rrggbb, #rgb or rgb(r, g, b), as upper-case #RRGGBB."""
    out = set()
    for h in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z])", css_and_html):
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        out.add("#" + h.upper())
    for r, g, b in re.findall(r"rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})", css_and_html):
        out.add("#%02X%02X%02X" % (int(r), int(g), int(b)))
    return out


_SPACE_DECL = re.compile(r"(?<![\w-])(margin|padding|gap|row-gap|column-gap|--[\w-]*(?:space|gap|pad|margin)[\w-]*)"
                         r"(?:-[a-z-]+)?\s*:\s*([^;{}]+)", re.I)
_LENGTH = re.compile(r"(?<![\w.#-])(-?\d*\.?\d+)([a-z%]*)", re.I)


def off_scale(css: str, scale: list[int]) -> list[str]:
    """Spacing values in margins, paddings, gaps and spacing variables that are not on the scale."""
    bad = []
    for prop, value in _SPACE_DECL.findall(css):
        value = re.sub(r"var\([^)]*\)", " ", value)
        for num, unit in _LENGTH.findall(value):
            unit = unit.lower()
            if unit in ("", "px"):
                px = float(num)
            elif unit in ("rem", "em"):
                px = float(num) * 16
            else:
                continue  # %, vh, vw and the like are layout, not spacing steps
            if unit == "" and float(num) != 0:
                continue
            if abs(px) not in scale:
                bad.append(f"{prop}: {num}{unit}")
    return bad


def check(src: str, s: dict) -> dict[str, bool | str]:
    """Each rule of the design system on the page source ``src``: True when it holds, or a short failure."""
    p = _Page()
    try:
        p.feed(src)
        p.close()
    except Exception as e:  # html.parser is lenient; this is only for truly broken input
        return {"parses": f"the HTML does not parse ({e})"}
    css = "\n".join(p.css)
    found = colours(src)
    out: dict[str, bool | str] = {}
    out["parses"] = True if p.tags else "no HTML tags"
    out["colour"] = True if s["colour"].upper() in found else f"main colour {s['colour']} is not used"
    old = [c for c in s["old"] if c.upper() in found]
    out["no_old_colour"] = True if not old else f"uses the old main colour {', '.join(old)}"
    out["font"] = True if re.search(r"font(?:-family)?\s*:[^;{}]*\b" + re.escape(s["font"]) + r"\b", css, re.I) \
        else f"font {s['font']} is not set"
    want = [w.casefold() for w in s["nav"]]
    got = [_text(t).casefold() for t in p.nav_links]
    seq = [t for t in got if t in want]
    out["nav"] = True if seq == want else (f"nav reads {' · '.join(_text(t) for t in p.nav_links)}"
                                           if p.nav_links else "no <nav> links")
    footer = _text(p.footers[-1]) if p.footers else ""
    out["footer"] = True if footer.replace(" ", "") == _text(s["footer"]).replace(" ", "") else \
        (f"footer reads \"{footer}\"" if p.footers else "no <footer>")
    missing = [img.get("src", "?") for img in p.images if not img.get("alt", "").strip()]
    out["alt_text"] = True if not missing else f"{len(missing)} image(s) without alt text"
    bad = off_scale(css, s["spacing"])
    out["spacing"] = True if not bad else "spacing off the scale: " + ", ".join(bad[:4])
    h1 = " ".join(_text(t) for t in p.h1)
    out["heading"] = True if s["h1"].casefold() in h1.casefold() else f"no <h1> naming {s['h1']}"
    return out


# --------------------------------------------------------------------------------------------------------------

_BROWSERS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Chromium.app/Contents/MacOS/Chromium",
             "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]


def find_browser() -> str | None:
    """A Chromium-family browser to load pages headless: $HAUL_BROWSER, then the usual places."""
    env = os.environ.get("HAUL_BROWSER")
    if env:
        return env if Path(env).exists() or shutil.which(env) else None
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return next((b for b in _BROWSERS if Path(b).exists()), None)


# Errors that only the switched-off network causes: a page that fetches its data on load is not broken for that.
_OFFLINE = re.compile(r"Failed to fetch|NetworkError|net::ERR_|Load failed|Fetch API cannot load|"
                      r"Not allowed to load local resource|blocked by CORS policy")


def load_check(src: str, timeout: float = 30.0) -> tuple[bool | None, str]:
    """Load the page headless with the network switched off. (True, note) when it loads with no script errors,
    (False, why) when it does not, and (None, note) when there is no browser to try. Errors that only the missing
    network causes (a fetch that fails) do not count."""
    browser = find_browser()
    if not browser:
        return None, "skipped: no headless browser installed"
    with tempfile.TemporaryDirectory(prefix="haul-page-") as tmp:
        page = Path(tmp) / "page.html"
        page.write_text(src, encoding="utf-8")
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", f"--user-data-dir={tmp}/profile", "--host-resolver-rules=MAP * ~NOTFOUND",
               "--enable-logging=stderr", "--v=0", "--virtual-time-budget=3000", "--dump-dom", page.as_uri()]
        try:
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return False, "the browser timed out loading the page"
        except OSError as e:
            return None, f"skipped: the browser would not start ({e})"
    errors = [ln for ln in run.stderr.splitlines() if "CONSOLE" in ln and "Uncaught" in ln
              and not _OFFLINE.search(ln)]
    if run.returncode != 0:
        return False, f"the browser exited with {run.returncode}"
    if "<body" not in run.stdout.lower():
        return False, "the browser produced no page"
    if errors:
        return False, "script error: " + errors[0].split("\"", 1)[-1].split("\", source")[0][:120]
    return True, "loaded in a headless browser with no script errors"
