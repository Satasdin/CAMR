"""Plugins: MCP servers the app knows how to start, so a person adds one with a click instead of typing its command.
Each is an ordinary MCP server (camr_engine.agentic.servers): the person adds and connects it, every call waits at the
gate unless the person has said that plugin need not ask, and the agent can neither add nor start one.

Playwright drives a real Chrome. When it is connected, the page test (open_page) also runs a scripted check in it:
the page served from this Mac only (camr_engine.agentic.serve), at a phone's width, every button pressed, and Chrome's
own error messages. The scripted check is the app's own, so it runs without asking; the reviewer can also call a few
of Playwright's tools itself, which ask like any other.
"""

from __future__ import annotations

import json
import re

PLAYWRIGHT_VERSION = "0.0.84"  # pinned: what runs is what was checked
CATALOG = [
    {"id": "playwright", "name": "Playwright", "command": "npx",
     "args": [f"@playwright/mcp@{PLAYWRIGHT_VERSION}", "--headless", "--isolated", "--browser", "chrome"],
     "about": "Tests pages in a real Chrome, on its own empty profile: opens the page, presses every button, reads "
              "Chrome's errors. The page's scripts then run in Chrome, which, unlike the app's own preview, can reach "
              "the internet. Needs Node and Google Chrome.",
     # the few tools the reviewer is offered: 25 would bury a small model
     "review_tools": ["browser_navigate", "browser_snapshot", "browser_click", "browser_type",
                      "browser_console_messages"]},
]
BY_ID = {p["id"]: p for p in CATALOG}

CHECK = r"""() => {
  const out = {title: document.title, text: (document.body ? document.body.innerText.slice(0, 8000) : ''),
    runsOff: document.documentElement.scrollWidth > window.innerWidth + 1,
    brokenImages: [...document.images].filter(i => i.complete && !i.naturalWidth).map(i => i.getAttribute('src')).slice(0, 8),
    deadLinks: [...document.querySelectorAll('a[href^="#"]')].filter(a => a.getAttribute('href').length > 1
      && !document.getElementById(a.getAttribute('href').slice(1))).map(a => a.getAttribute('href')).slice(0, 8),
    failed: []};
  for (const b of [...document.querySelectorAll('button')].slice(0, 12)) {
    const before = document.body.innerText;
    try { b.click(); } catch (e) { out.failed.push('pressing "' + (b.innerText || b.id || 'a button').slice(0, 40) + '" threw ' + e.message); continue; }
    if (document.body.innerText === before) out.failed.push('pressing "' + (b.innerText || b.id || 'a button').slice(0, 40) + '" changed nothing');
  }
  return JSON.stringify(out);
}"""


def review_tools(servers) -> list[str]:
    """The ``mcp__<server>__<tool>`` names a reviewer may call: those of the connected plugins."""
    from camr_engine.agentic.servers import tool_name

    out = []
    for p in CATALOG:
        link = servers.link(p["id"]) if servers is not None else None
        if link is not None and link.state == "connected":
            have = {t["name"] for t in link.tools}
            out += [tool_name(p["id"], t) for t in p["review_tools"] if t in have]
    return out


def _result(text: str) -> str:
    """The value in a Playwright reply ("### Result" then the value), as text."""
    m = re.search(r"### Result\s*\n(.*?)(?:\n### |\Z)", text or "", re.S)
    got = (m.group(1) if m else text or "").strip()
    if got.startswith('"'):
        try:
            return json.loads(got)
        except ValueError:
            pass
    return got


def browser_check(link, url: str) -> dict:
    """The page at ``url`` checked in Playwright's Chrome, as the app's own browser reports it: {text, errors, failed,
    runsOff, brokenImages, deadLinks, scriptsRan, by}."""
    nav = link.call("browser_navigate", {"url": url})
    if not nav.get("ok"):
        return {"errors": [f"Playwright could not open the page: {str(nav.get('text'))[:300]}"], "by": "playwright"}
    link.call("browser_resize", {"width": 375, "height": 800})
    got = link.call("browser_evaluate", {"function": CHECK})
    try:
        report = json.loads(_result(got.get("text", "")))
    except ValueError:
        report = {"errors": [f"Playwright's check could not be read: {str(got.get('text'))[:300]}"]}
    msgs = link.call("browser_console_messages", {"level": "error"})
    errors = [x.strip("- ").strip() for x in str(msgs.get("text", "")).splitlines()
              if re.match(r"^\s*-?\s*\[(ERROR|error)\]", x) or "Error" in x and not x.startswith("Total")]
    report["errors"] = [*report.get("errors", []), *[e[:300] for e in errors[:10]]]
    report.update(scriptsRan=True, hasScripts=True, by="playwright")
    return report
