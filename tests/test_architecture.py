"""Package-diagram constraints (Figure 4.6) and inspector read-only-ness (TC-15)."""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "camr"


def imports_of(package: str) -> set[str]:
    found = set()
    for py in (ROOT / package).rglob("*.py"):
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("camr."):
                found.add(node.module.split(".")[1])
            elif isinstance(node, ast.Import):
                found |= {a.name.split(".")[1] for a in node.names if a.name.startswith("camr.")}
    return found - {package}


@pytest.mark.parametrize(
    "package,forbidden",
    [
        ("memory", {"harness", "eval", "cli", "inspect"}),  # engine usable as a library
        ("eval", {"memory", "harness", "cli", "inspect"}),  # scoring cannot see engine internals
        ("models", {"memory", "harness", "eval", "cli", "inspect"}),
        ("harness", {"cli", "inspect"}),
    ],
)
def test_package_dependencies_are_acyclic(package, forbidden):
    assert not (imports_of(package) & forbidden)


def test_nothing_depends_on_inspect():
    for pkg in ("memory", "models", "harness", "eval", "cli"):
        assert "inspect" not in imports_of(pkg)


def test_inspector_cannot_write(tmp_path):
    from camr.inspect import queries as Q

    db = tmp_path / "x.sqlite"
    sqlite3.connect(db).execute("CREATE TABLE note(note_id INTEGER)").connection.commit()
    conn = Q.connect_ro(db)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("INSERT INTO note VALUES (1)")


def test_inspector_does_not_import_runners():
    src = (ROOT / "inspect").rglob("*.py")
    for py in src:
        text = py.read_text()
        assert "camr.models" not in text and "camr.harness" not in text, py
