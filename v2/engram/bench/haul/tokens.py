"""Token counts with the Qwen3 tokenizer, loaded alone from the local Hugging Face cache (never the model weights).

The count is the text's own tokens, with no chat template; a runner's prompt adds a few per message.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Callable

TOKENIZER = "mlx-community/Qwen3-1.7B-4bit"


@lru_cache(maxsize=1)
def _tokenizer():
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from huggingface_hub import try_to_load_from_cache
    from tokenizers import Tokenizer

    path = try_to_load_from_cache(TOKENIZER, "tokenizer.json")
    if not isinstance(path, str):
        raise FileNotFoundError(f"{TOKENIZER} tokenizer.json is not in the local Hugging Face cache")
    return Tokenizer.from_file(path)


def available() -> bool:
    try:
        _tokenizer()
        return True
    except Exception:
        return False


def counter() -> Callable[[str], int]:
    """A function giving the number of Qwen3 tokens in a text."""
    tok = _tokenizer()
    return lambda text: len(tok.encode(text, add_special_tokens=False).ids)


def count_many(texts: list[str]) -> list[int]:
    return [len(e.ids) for e in _tokenizer().encode_batch(texts, add_special_tokens=False)]
