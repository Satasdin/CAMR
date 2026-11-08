"""A whole file must be the kind its name says (small models send a sentence about index.html as index.html), a
script that does not parse says so on the write that made it, and every kind of page request is a website."""

import shutil

import pytest

from camr_engine.agentic.gate import Gate
from camr_engine.agentic.loop import WEBSITE
from camr_engine.agentic.tools import Toolbox, js_syntax, shape_problem
from camr_engine.agentic.workspace import Workspace

NODE = shutil.which("node") is not None


def test_a_sentence_about_the_file_is_not_written_as_the_file(tmp_path):
    box = Toolbox(Workspace(tmp_path, []), Gate())
    said = "The provided index.html file is complete and meets all the requirements of the task."
    done = box.run("write_file", {"path": "index.html", "content": said}, owner="b")
    assert not done.ok and "Not written" in done.text and "sentence about the file" in done.text
    assert not (tmp_path / "index.html").exists()
    done = box.run("write_file", {"path": "style.css", "content": ""}, owner="d")
    assert not done.ok and not (tmp_path / "style.css").exists()
    done = box.run("write_file", {"path": "index.html", "content": "<!doctype html>\n<h1>Hi</h1>\n"}, owner="b")
    assert done.ok and (tmp_path / "index.html").exists()


def test_shape_problem_lets_real_files_through():
    assert shape_problem("a.html", "<!DOCTYPE html><html><body></body></html>") == ""
    assert shape_problem("a.css", "body { margin: 0; }") == ""
    assert shape_problem("a.js", "export const x = 1;") == ""
    assert shape_problem("notes.md", "") == ""
    assert "no CSS rules" not in shape_problem("a.css", "") and shape_problem("a.css", "")
    assert shape_problem("a.js", "  \n")


@pytest.mark.skipif(not NODE, reason="node is not on this Mac")
def test_a_script_that_does_not_parse_is_reported_with_its_line(tmp_path):
    assert js_syntax("import * as THREE from 'three';\nconst a = 1;\n") == ""
    assert js_syntax("var x = 1;\nfunction f() { return 2 }\n") == ""
    err = js_syntax("import x from 'y';\nconst a = 1;\nconst a = 2;\n")
    assert err.startswith("line 3:") and "already been declared" in err
    box = Toolbox(Workspace(tmp_path, []), Gate())
    done = box.run("write_file", {"path": "motion.js", "content": "const a = 1;\nconst a = 2;\n"}, owner="m")
    assert done.ok and "does not run: line 2" in done.text
    done = box.run("edit_file", {"path": "motion.js", "old_text": "const a = 2;", "new_text": "a + 1;"}, owner="m")
    assert done.ok and "does not run" not in done.text


def test_every_kind_of_page_is_a_website():
    for asked in ("A product page for a small satellite", "a pricing page with physics-like motion",
                  "A scroll-told story page about the first launch", "a landing page", "my home page"):
        assert WEBSITE.search(asked), asked
    for asked in ("a one-page report on sales", "turn the page of this notebook", "write a sorting function"):
        assert not WEBSITE.search(asked), asked


def test_editing_a_file_that_is_not_there_says_to_write_it_whole(tmp_path):
    box = Toolbox(Workspace(tmp_path, []), Gate())
    done = box.run("edit_file", {"path": "motion.js", "old_text": "a", "new_text": "b"}, owner="m")
    assert not done.ok and "make it with write_file" in done.text and not (tmp_path / "motion.js").exists()
