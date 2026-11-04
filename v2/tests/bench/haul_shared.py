"""One Long Haul build shared by the haul tests (a build takes a few seconds). Skips when the Qwen3 tokenizer is
not in the local Hugging Face cache."""

from __future__ import annotations

from functools import lru_cache

import pytest

from camr_engine.bench.haul import tokens


def need_tokenizer() -> None:
    if not tokens.available():
        pytest.skip("the Qwen3 tokenizer is not in the local Hugging Face cache")


@lru_cache(maxsize=None)
def _build(seed: int):
    from camr_engine.bench.haul import build
    return build(seed)


def built(seed: int = 1):
    need_tokenizer()
    return _build(seed)


GOOD_PAGE = """Here is the page.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{h1} | Mama Njeri's Kitchen</title>
  <style>
    :root {{ --main: {colour}; --space-2: 8px; --space-3: 16px; }}
    body {{ font-family: "Inter", system-ui, sans-serif; margin: 0; color: #1A1A1A; }}
    nav a {{ color: var(--main); padding: 8px 16px; }}
    .hero {{ background: {colour}; padding: 32px 24px; gap: 1rem; }}
  </style>
</head>
<body>
  <nav><a href="/">Home</a><a href="/menu">Menu</a><a href="/catering">Catering</a><a href="/contact">Contact</a></nav>
  <main>
    <h1>{h1}</h1>
    <img src="trays.jpg" alt="Trays of pilau ready for a wedding">
  </main>
  <footer>&copy; 2026 Mama Njeri&#39;s Kitchen &middot; Nairobi</footer>
</body>
</html>
```"""


def good_page(colour: str = "#7C3AED", h1: str = "Catering") -> str:
    return GOOD_PAGE.format(colour=colour, h1=h1)


def perfect(p: dict) -> str:
    """An answer that should be graded right for probe ``p`` (as asked at its cut)."""
    f = p["family"]
    if f == "never":
        return "I don't know; that was never mentioned."
    if f == "maths":
        return f"Working it through step by step. Answer: {p['answer']}"
    if f == "code":
        return "```python\n" + p["reference"] + "```"
    if f == "page":
        return good_page(p["grader"]["colour"], p["grader"]["h1"])
    return f"It's {p['answer']}."
