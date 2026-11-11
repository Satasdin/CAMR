# Connecting a model to Burrow

Burrow is the memory. The chat program is whatever you already use: Claude Code, OpenCode, LM Studio, or a model served
by Ollama or llama.cpp. They all reach Burrow the same way, as an MCP server:

```
burrow mcp ~/Notes
```

That one command gives the program eleven tools: search, read, links, list, folders, remember, ask, prepare, and three
for conversations (`vault_session_list`, `vault_session_resume`, `vault_session_log`).

Each connection is kept in the vault as a session. Burrow writes down what the program searched for and which files it
read as it happens, so another program can pick the conversation up later even if the model never saves anything. When
the model does call `vault_session_log`, its questions and answers are kept too. A program that reconnects within 30
minutes, as one-shot runs like `opencode run` and `claude -p` do for every message, carries on the same session.

To pick a conversation up anywhere, ask: *"Pick up my last conversation; it is saved in Burrow."*

## Claude Code

```
claude mcp add burrow -- burrow mcp ~/Notes
```

## OpenCode

In `opencode.json` (in the project, or `~/.config/opencode/opencode.json`):

```json
{
  "mcp": { "burrow": { "type": "local", "command": ["burrow", "mcp", "/Users/you/Notes"], "enabled": true } },
  "agent": {
    "burrow": {
      "description": "Answers from the Burrow vault only",
      "mode": "primary",
      "prompt": "You answer from the user's Burrow vault. Use the burrow tools; name the file for each fact. If the vault does not hold the answer, say so.",
      "tools": { "*": false, "burrow_*": true }
    }
  }
}
```

Use the `burrow` agent with small local models. OpenCode's own agent sends about 25,000 tokens of prompt and tools
before the question, which overflows a 16k context and buries Burrow among twenty other tools: in testing, a 4B model
on the default agent searched the web five times, never called Burrow, and made an answer up. On the `burrow` agent the
same model called Burrow first every time.

To use a local server as OpenCode's model, add it as a provider:

```json
"provider": {
  "llamacpp": { "npm": "@ai-sdk/openai-compatible", "options": { "baseURL": "http://127.0.0.1:8080/v1" },
                "models": { "qwen3-4b": { "tools": true } } },
  "ollama":   { "npm": "@ai-sdk/openai-compatible", "options": { "baseURL": "http://127.0.0.1:11434/v1" },
                "models": { "gemma4:12b": { "tools": true } } },
  "lmstudio": { "npm": "@ai-sdk/openai-compatible", "options": { "baseURL": "http://127.0.0.1:1234/v1" },
                "models": { "qwen2.5-coder-7b-instruct": { "tools": true } } }
}
```

## LM Studio

In `~/.lmstudio/mcp.json` (or Program, then Install, then Edit mcp.json):

```json
{ "mcpServers": { "burrow": { "command": "/opt/homebrew/bin/burrow", "args": ["mcp", "/Users/you/Notes"] } } }
```

## llama.cpp

Serve the model with its chat template and room for tools:

```
llama-server -m model.gguf --jinja -c 32768
```

`--jinja` is what makes tool calls work. Then use it from any MCP program above, for example OpenCode's `llamacpp`
provider.

## Ollama

Ollama serves the model; the MCP program is OpenCode (above) or Burrow's own `burrow chat`. One thing to know: Ollama's
OpenAI-format route (`/v1`) ignores the context size a program asks for and loads the model with its full window. For
Qwen3 4B that was 262,144 tokens, 43 GB, and 90 to 140 seconds an answer. Make a copy with a set context instead:

```
printf 'FROM qwen3:4b-instruct-2507-q4_K_M\nPARAMETER num_ctx 16384\n' > Modelfile
ollama create qwen3-4b-16k -f Modelfile
```

## What a vault can hold

Notes and code are read as text. Documents are read into Markdown with a heading per page, using only what macOS
already has, and kept in `~/Library/Caches/Burrow/extracted` by content so each is read once:

| Kind | Read with | Excerpts say |
| --- | --- | --- |
| PDF | PDFKit; pages with no text layer are read by Vision text recognition | the page |
| Word (.docx, .doc), RTF, OpenDocument | the system's text readers | the document |
| Images (PNG, JPEG, HEIC, TIFF, GIF, WebP) | Vision text recognition | text in the image |

## Working memory on disk (llama.cpp)

Text is the format every model reads. A KV cache is the format one model loads: the work it already did reading a
document. Burrow keeps both, filed by model and by the exact files it was built from, so a cache is never loaded into
another model or after its files changed.

```
llama-server -m model.gguf --jinja -c 32768 --slot-save-path ~/Notes/.burrow/kv
burrow kv ~/Notes save Documents/proposal.pdf --vault          read it once and keep the cache
burrow kv ~/Notes ask Documents/proposal.pdf "What are the research questions?" --vault
burrow kv ~/Notes ask Documents/proposal.pdf "..." --vault --cold   read everything again, to compare
burrow kv ~/Notes list --vault
```

## The Burrow skill

`skills/burrow/SKILL.md` teaches an agent how to use the vault: search first, cite file and line, carry conversations
between models, write only when asked. Claude Code: link it into `~/.claude/skills/burrow`. OpenCode reads skills from
`.opencode/skills/` in the project.
