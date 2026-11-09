# Install and integrate

CAMR installs as one command, `camr`. Its OpenAI-compatible endpoint puts memory in front of the runtime you
already use: Ollama, LM Studio or mlx_lm.server. OpenCode, curl and any OpenAI SDK then point at one URL. It needs an
Apple-silicon Mac (M1 or later), and Python 3.11 or newer, or uv.

## Install

Every route puts the engine in an environment of its own. None touches the Python you already have.

| Route | Command | Tested |
| --- | --- | --- |
| curl | `curl -fsSL https://raw.githubusercontent.com/Satasdin/CAMR/camr-build/packaging/install.sh \| sh` | yes, into a temp HOME, with uv and with `python3 -m venv` |
| uv | `uv tool install "camr-engine @ git+https://github.com/Satasdin/CAMR.git@camr-build#subdirectory=v2"` | yes, from a local folder |
| pipx | `pipx install "git+https://github.com/Satasdin/CAMR.git@camr-build#subdirectory=v2"` | no: pipx was not installed |
| Homebrew | `packaging/homebrew/camr.rb`, from a clone (below) | no: Homebrew was not installed; there is no public tap |
| npm | `npm install -g ./packaging/npm`, then `camr-memory` | yes, `npm pack` and from a clone, into a temp prefix; not on the registry |

`packaging/install.sh` installs into `~/.camr/engine` and links `camr` into `~/.local/bin`. It uses uv when uv is
installed, else `python3 -m venv`. Running it again updates the engine. Three settings change what it does:
- `CAMR_SOURCE`: what to install, a pip requirement or a local folder;
- `CAMR_HOME`: where the engine goes (default `~/.camr`);
- `CAMR_BIN`: where the command is linked.

The older CAMR Personal installer (`install/install.sh`) uses `~/.camr/venv`, so the two do not collide.

Homebrew, from a clone:

```sh
brew tap-new $USER/camr
cp packaging/homebrew/camr.rb "$(brew --repo $USER/camr)/Formula/"
brew install --HEAD $USER/camr/camr
brew services start camr          # camr serve --backend ollama, kept running
```

The npm package `camr-memory` installs the engine with the same `install.sh` the first time it runs. Then it runs
`camr` with your arguments, or `camr serve` when you give none.

## The command

| Command | What it does |
| --- | --- |
| `camr serve [--backend ollama\|lmstudio\|mlx] [--port 11436]` | the OpenAI-compatible endpoint with memory |
| `camr ollama [--port 11435]` | the [Ollama pairing](ollama.md), for the `ollama` CLI |
| `camr app` | the engine behind CAMR for Mac |
| `camr doctor` | what is installed and what is listening; loads no model |
| `camr bench` | where the benchmarks and their records are |
| `camr version` | the engine's version |

The old CAMR baseline also installs a command named `camr`. Keep the two in separate environments, as every
route above does.

## The endpoint

`camr serve` listens on `http://127.0.0.1:11436/v1`:

| Route | What it does |
| --- | --- |
| `POST /v1/chat/completions` | streaming or not. Notes on the last user message are put in front of it; the exchange is remembered once the answer ends |
| `GET /v1/models` | the backend's models, passed through |
| other `/v1/` paths | passed through as they are, with no memory |
| `GET /camr_engine/metrics` | what each request cost: `recall_ms`, `added_ms`, `first_byte_ms`, tokens |

The backends:

| `--backend` | Runtime | Upstream |
| --- | --- | --- |
| `ollama` (default) | Ollama's OpenAI-style API | 127.0.0.1:11434 |
| `lmstudio` | LM Studio's server (`lms server start`) | 127.0.0.1:1234 |
| `mlx` | `mlx_lm.server` | 127.0.0.1:8080 |

`--upstream` points at another port on this Mac. Through each backend, memory goes in as words. The memory folder
(`--memory`, default `~/.camr/default`) is the Ollama pairing's. The same notes come back whichever door they came in
by.

- **Agents:** an answer that ends by calling a tool (`finish_reason` "tool_calls") is not remembered. The notes stay
  with the question through the tool loop, and the answer that ends the turn is remembered with it.
- **Memory off:** a request with `X-CAMR-Memory: off` gets no notes, and nothing is remembered.
- **Security:** as in the [Ollama pairing](ollama.md). The endpoint listens on 127.0.0.1 only, and a request must
  name that host. A request a web page sends is refused. The backend must be on this Mac.

## Integrations

Ready-to-paste files are in `packaging/configs/`.

**OpenCode**: `opencode.json`, in your project or `~/.config/opencode/`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "camr": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "CAMR (local model with memory)",
      "options": { "baseURL": "http://127.0.0.1:11436/v1", "apiKey": "camr" },
      "models": { "qwen3:4b": { "name": "Qwen3 4B with CAMR memory" } }
    }
  },
  "model": "camr/qwen3:4b"
}
```

**LM Studio**: start its server, put CAMR in front of it, and change only the base URL in your client:

```sh
lms server start
camr serve --backend lmstudio      # http://localhost:1234/v1  ->  http://127.0.0.1:11436/v1
```

**Ollama**: two doors to the same memory:

```sh
camr serve --backend ollama                         # OpenAI clients: http://127.0.0.1:11436/v1
camr ollama                                          # the ollama CLI:
OLLAMA_HOST=127.0.0.1:11435 ollama run qwen3:4b
```

**curl**, or any OpenAI SDK, with any API key:

```sh
curl http://127.0.0.1:11436/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model": "qwen3:4b", "stream": true,
  "messages": [{"role": "user", "content": "What main colour did the client pick?"}]
}'
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:11436/v1", api_key="camr")
reply = client.chat.completions.create(model="qwen3:4b", messages=[{"role": "user", "content": "Hello"}])
```

## What was tested, 4 November 2026

- The endpoint's tests (`tests/test_pair_openai.py`) run against a stand-in backend, with no model.
- Against the real Ollama with `qwen3:1.7b`, one fact was told and then asked back, streaming. The answer came back
  right, from memory.
- Two clients were run against the endpoint and the stand-in, whole answers and streamed: the OpenAI Python SDK
  (3.45), and the AI SDK provider that OpenCode's config names (`@ai-sdk/openai-compatible` 3.0). Both got their
  answers, and both exchanges were remembered.
- LM Studio and mlx_lm.server were tried only through the stand-in, since neither server was running. OpenCode itself
  is not installed, so the config file was not loaded by OpenCode.
