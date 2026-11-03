"""Pairings: engram's memory for model runtimes it does not run itself. Today there is one, Ollama.

    python -m engram.pair.ollama --memory ~/.engram/default
    OLLAMA_HOST=127.0.0.1:11435 ollama run qwen3:1.7b

Through a pairing, memory reaches the model as words, since the runtime lets no outside code put tensors into it.
"""

from engram.pair.provider import NoMemory, Provider, VaultWords

__all__ = ["NoMemory", "Provider", "VaultWords"]
