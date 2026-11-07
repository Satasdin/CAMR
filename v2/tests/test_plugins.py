"""Plugins: the page served on this Mac only, Playwright's check, and a plugin that need not ask."""

import json
import urllib.request

import pytest

from camr_engine.agentic.plugins import browser_check, review_tools
from camr_engine.agentic.serve import close_all, serving
from camr_engine.agentic.servers import Servers, Spec
from camr_engine.agentic.workspace import Workspace


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (root / "index.html").write_text("<h1>hi</h1>")
    (root / ".env").write_text("KEY=secret")
    (tmp_path / "outside.txt").write_text("private")
    (root / "out.txt").symlink_to(tmp_path / "outside.txt")
    yield Workspace(root, [])
    close_all()


def get(url):
    try:
        with urllib.request.urlopen(url) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""


def test_the_page_is_served_on_this_mac_only_and_nothing_else_is(site):
    srv = serving(site)
    assert srv.url().startswith("http://127.0.0.1:") and serving(site) is srv
    assert get(srv.url("index.html")) == (200, "<h1>hi</h1>")
    base = srv.url("")
    for bad in (".env", "out.txt", "../outside.txt", "%2e%2e/outside.txt", "nope.html"):
        assert get(base + bad)[0] == 404, bad
    assert get(base + "favicon.ico")[0] == 204


class Link:
    state = "connected"
    tools = [{"name": n} for n in ("browser_navigate", "browser_click", "browser_snapshot", "browser_evaluate",
                                    "browser_console_messages", "browser_type", "browser_run_code_unsafe")]

    def __init__(self):
        self.calls = []

    def show(self):
        return {"state": self.state, "error": None, "tools": [t["name"] for t in self.tools], "calls": 0,
                "failures": 0}

    def call(self, tool, args):
        self.calls.append((tool, args))
        if tool == "browser_evaluate":
            return {"ok": True, "text": "### Result\n" + json.dumps(json.dumps(
                {"text": "Shop", "failed": ['pressing "Add" changed nothing'], "runsOff": False}))}
        if tool == "browser_console_messages":
            return {"ok": True, "text": "Total messages: 1 (Errors: 1)\n- [ERROR] TypeError: Assignment to constant variable."}
        return {"ok": True, "text": "### Page\n- Page URL: x"}


def test_the_chrome_check_reads_the_page_presses_buttons_and_reads_chromes_errors():
    link = Link()
    got = browser_check(link, "http://127.0.0.1:1/index.html")
    assert got["failed"] == ['pressing "Add" changed nothing'] and got["by"] == "playwright"
    assert any("Assignment to constant variable" in e for e in got["errors"])
    assert [t for t, _ in link.calls] == ["browser_navigate", "browser_resize", "browser_evaluate",
                                          "browser_console_messages"]


def test_the_reviewer_is_offered_a_few_browser_tools_only_when_playwright_is_connected(tmp_path):
    servers = Servers(tmp_path / "mcp.json", tmp_path / "logs")
    assert review_tools(servers) == []
    servers.links["playwright"] = Link()
    got = review_tools(servers)
    assert "mcp__playwright__browser_click" in got and not any("run_code_unsafe" in t for t in got)
    assert len(got) == 5


def test_only_the_person_makes_a_plugin_stop_asking_and_it_is_kept(tmp_path):
    servers = Servers(tmp_path / "mcp.json", tmp_path / "logs")
    servers.add(Spec("playwright", "npx", ["@playwright/mcp@0.0.84"]))
    assert servers.spec("playwright").trusted is False
    servers.trust("playwright", True)
    assert Servers(tmp_path / "mcp.json", tmp_path / "logs").spec("playwright").trusted is True
    with pytest.raises(KeyError):
        servers.trust("nope", True)


def test_a_trusted_plugin_runs_without_asking_and_an_untrusted_one_asks(tmp_path):
    from camr_engine.agentic.gate import Gate
    from camr_engine.agentic.tools import Toolbox

    root = tmp_path / "w"
    root.mkdir()
    servers = Servers(tmp_path / "mcp.json", tmp_path / "logs")
    servers.add(Spec("playwright", "npx", []))
    link = Link()
    link.tools = [{"name": "browser_snapshot", "description": "page", "schema": {"type": "object", "properties": {}}}]
    servers.links["playwright"] = link
    box = Toolbox(Workspace(root, []), Gate(wait_s=0.2), servers=servers)
    asked = box.run("mcp__playwright__browser_snapshot", {}, owner="r")
    assert not asked.ok and "did not allow" in asked.text and link.calls == []
    assert "must allow" in box.specs()[-1]["function"]["description"]
    servers.trust("playwright", True)
    assert "must allow" not in box.specs()[-1]["function"]["description"]
    done = box.run("mcp__playwright__browser_snapshot", {}, owner="r")
    assert done.ok and link.calls == [("browser_snapshot", {})]
