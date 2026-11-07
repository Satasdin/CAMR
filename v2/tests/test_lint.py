"""What the page test sees in a page's own files without running them."""

import shutil

import pytest

from camr_engine.agentic.lint import page_problems

PAGE = '<button id="add" onclick="go()">Add</button><p id="total"></p><script src="app.js" defer></script>'


def site(tmp_path, html, js):
    (tmp_path / "index.html").write_text(html)
    (tmp_path / "app.js").write_text(js)
    return page_problems(tmp_path, "index.html")


def test_a_clean_page_has_no_problems(tmp_path):
    got = site(tmp_path, PAGE.replace(' onclick="go()"', ""),
               "const t = document.getElementById('total');\ndocument.querySelector('#add').addEventListener('click', "
               "() => { t.textContent = '1'; });")
    assert got == []


def test_code_that_only_runs_outside_a_browser_is_found(tmp_path):
    got = site(tmp_path, PAGE, "const { read_file } = require('mcp');\nlet x = 1;")
    assert any("require()" in p for p in got)


def test_ids_the_script_looks_for_must_be_on_the_page(tmp_path):
    got = site(tmp_path, PAGE, "document.getElementById('total-price').textContent = 0;")
    assert any("#total-price" in p and "does not have" in p for p in got)


def test_handlers_written_into_the_page_are_sent_to_the_script(tmp_path):
    got = site(tmp_path, PAGE, "function go() {}")
    assert any("onclick" in p and "addEventListener" in p for p in got)


@pytest.mark.skipif(shutil.which("node") is None, reason="no Node here")
def test_a_script_that_does_not_parse_is_found(tmp_path):
    got = site(tmp_path, PAGE, "function go( {")
    assert any("does not parse" in p for p in got)


def test_scripts_outside_the_project_or_remote_are_left_alone(tmp_path):
    (tmp_path / "index.html").write_text('<script src="https://x.org/a.js"></script><script src="../b.js"></script>')
    assert page_problems(tmp_path, "index.html") == []
