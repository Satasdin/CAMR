# camr-memory

CAMR is a lightweight memory engine for language models that run on your Mac. With it, a small local model answers
a 2M–4M-token project history about as well as Claude Sonnet does without memory. Its first word comes in about 0.3 s, in
about 7.5 GB of RAM.

This package installs the engine (Python, into `~/.camr/engine`) the first time it runs. Then it starts CAMR's
OpenAI-compatible endpoint with memory, in front of Ollama, LM Studio or MLX:

```sh
npx camr-memory                            # camr serve --backend ollama, on http://127.0.0.1:11436/v1
npx camr-memory serve --backend lmstudio   # in front of LM Studio's server (lms server start)
npx camr-memory doctor                     # what is installed and what is listening
```

Point any OpenAI client at `http://127.0.0.1:11436/v1`, with any API key.

It needs an Apple-silicon Mac, and Python 3.11 or newer, or [uv](https://docs.astral.sh/uv/). Everything stays on the
Mac. Docs: https://github.com/Satasdin/CAMR (v2/docs/site/install.md). MIT licence.
