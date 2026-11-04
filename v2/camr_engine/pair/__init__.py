"""Pairings: CAMR's memory for model runtimes it does not run itself. There are two doors, to the same memory:

    camr ollama                         # camr_engine.pair.ollama: Ollama's own API, for the ollama CLI
    OLLAMA_HOST=127.0.0.1:11435 ollama run qwen3:1.7b

    camr serve --backend ollama         # camr_engine.pair.openai: the OpenAI API, in front of Ollama, LM Studio or
                                        # mlx_lm.server, for OpenCode, curl and any OpenAI SDK (127.0.0.1:11436/v1)

Through a pairing, memory reaches the model as words, since the runtime lets no outside code put tensors into it.
"""

from camr_engine.pair.provider import NoMemory, Provider, VaultWords

__all__ = ["NoMemory", "Provider", "VaultWords"]
