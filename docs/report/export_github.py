#!/usr/bin/env python3
"""Turns report Markdown (with the build's !tab, !widths, !include and !fig lines) into plain GitHub Markdown.

The report keeps the evidence a marker needs in the chapters and points to these pages for the rest: the full test
record, further results and the side trials. They are written from the same sources as the report, so the numbers in
both always agree.

    /usr/bin/python3 docs/report/export_github.py
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent.parent
OUT = REPO / "docs" / "evaluation"


def render(text: str, out_dir: Path) -> str:
    """The build's line forms as GitHub Markdown: captions in bold, tables with a header rule, figures as images."""
    lines = []
    pending_rule = False
    for raw in text.splitlines():
        if raw.startswith("!include "):
            parts = [p.strip() for p in raw[len("!include "):].split("|")]
            included = (HERE / parts[0].replace("chapters4/", "chapters4/")).read_text()
            if len(parts) > 1 and parts[1]:
                included = re.sub(r"^!tab Table [A-Z0-9.]+:", f"!tab {parts[1]}:", included, count=1, flags=re.M)
            lines.append(render(included, out_dir))
            continue
        if raw.startswith("!widths") or raw.startswith("!landscape"):
            continue
        if raw.startswith("!tab "):
            lines.append("")
            lines.append(f"**{raw[5:].strip()}**")
            lines.append("")
            pending_rule = True
            continue
        if raw.startswith("!fig "):
            parts = [p.strip() for p in raw[5:].split("|")]
            image = (HERE / parts[0]).resolve()
            relative = Path(*([".."] * len(out_dir.relative_to(REPO).parts))) / image.relative_to(REPO)
            caption = parts[1] if len(parts) > 1 else ""
            lines.append(f"![{caption}]({relative.as_posix()})")
            lines.append("")
            lines.append(f"*{caption}*")
            continue
        if pending_rule and raw.startswith("|"):
            lines.append(raw)
            lines.append("|" + "---|" * (raw.count("|") - 1))
            pending_rule = False
            continue
        lines.append(raw)
    return "\n".join(lines)


def page(name: str, title: str, intro: str, body_file: str) -> None:
    body = (HERE / "github" / body_file).read_text()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(f"# {title}\n\n{intro}\n\n{render(body, OUT)}\n")
    print("wrote", (OUT / name).relative_to(REPO))


if __name__ == "__main__":
    page("test-cases.md", "Test cases and results",
         "The full test record behind Section 5.6 of the report. Each case names the requirement it verifies; "
         "[traceability.md](traceability.md) traces each requirement to its component.", "test-cases.md")
    page("further-results.md", "Further results",
         "Tables and trials that support Section 5.5 of the report but are not needed to follow it.", "further-results.md")
    page("traceability.md", "Requirements traceability",
         "Each requirement of Chapter 4 traced to the component that implements it and the test that verifies it.", "traceability.md")
    page("user-guide.md", "User guide", "How to install and use Burrow: the app, the terminal, and other programs through MCP.", "user-guide.md")
    page("more-screens.md", "More screens of the system", "Screens of the Mac app and the terminal view beyond those in the report.",
         "more-screens.md")
