# Burrow

Private project memory for local language models. Burrow keeps a software project's code linked, along with the decisions, rejected fixes and past bugs the code can't show, and hands a local Ollama model only the parts it needs. Nothing leaves the Mac.

Burrow is a private vault for everything: notes in Markdown, with code folders linked in read-only, and any local Ollama model can read it. There is a Mac app, a terminal version and an MCP server, all on the same engine. Pick a folder as your vault, and an Obsidian vault works as it is. Build the app with `app/build.sh`, then open `app/build/Burrow.app`. It needs macOS 26 or later.

## Install

On Apple silicon with macOS 14 or later, from the [landing page](https://satasdin.github.io/CAMR/) or with:

```bash
curl -fsSL https://github.com/Satasdin/CAMR/releases/latest/download/install.sh | sh
```

Add `-s -- --app` after `sh` to install the desktop app as well.

## Needs to build from source

- A Mac with Xcode
- [Ollama](https://ollama.com) with a chat model and the embedding model:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

```bash
ollama pull qwen3-embedding:0.6b
```

## Build and test

```bash
swift build -c release
```

```bash
swift test
```

## Use

```bash
.build/release/burrow index ~/code/my-project
```

```bash
.build/release/burrow ask ~/code/my-project "Where is a payment retried?"
```

```bash
.build/release/burrow note ~/code/my-project "We rejected caching sessions in app/auth.py because logout must be instant." --kind rejected
```

Other commands: `find` shows what would be read without asking a model, `links` shows what a file connects to, and `stats` shows the size of the memory. Add `--mode none`, `--mode search` or `--mode walk` to compare the three ways of giving a model memory.

## The engine

Burrow does more than find excerpts. On every question it decides whether the vault is needed, fits what it shows to the model, checks what the answer cites, and can hand the model a method for the task.

```
.build/release/burrow fit ~/vault --vault --model gemma4:12b        # measure a model once
.build/release/burrow skills ~/vault --vault --install               # add the starter skills to <vault>/Skills
.build/release/burrow ask ~/vault "When is rent due?" --mode engine --model gemma4:12b --vault
.build/release/burrow brief ~/vault "When is rent due?" --vault --json   # the same question packed for any other model
.build/release/burrow learn ~/vault conversation.json --vault        # keep what a conversation decided
```

`ask --mode engine` prints what it decided, the skill it used, what it read, and how many cited places were not among what it read. A skill is a Markdown file in the vault's `Skills` folder with a `when:` line; edit them or add your own. In `burrow chat`, `/keep` proposes notes from the conversation and asks before writing each one. MCP clients get the same preparation from the `vault_prepare` tool.

## In the terminal

A vault is a folder of Markdown notes, with code folders linked in read-only. The first command below is once per code folder and the second builds the index with meaning search.

```bash
.build/release/burrow link ~/notes ~/code/my-project
```

```bash
.build/release/burrow index ~/notes --vault
```

Full-screen view. Press `?` inside for every key. With no arguments it opens the folder you are in if it has a `.burrow` index, or else the last vault you opened.

```bash
.build/release/burrow tui ~/notes
```

A code folder in iCloud Drive has to be downloaded to be indexed, and the index waits for it, so keep linked folders outside iCloud or set them to stay downloaded.

It needs a real terminal of at least 40 by 12, with UTF-8. Colour is optional and `NO_COLOR` is respected. Right-to-left text is passed through unchanged, so it depends on your terminal.

Terminal chat with a local model. It streams the answer and prints each tool call on a dim line. `ollama run` has no tool support, so this talks to Ollama directly.

```bash
.build/release/burrow chat ~/notes --folder my-project
```

By default the chat searches the vault before the model is asked, and labels that search, because small models often skip their tools (see D-32). `--tools-only` leaves it entirely to the model. Add `--model NAME` for another model.

## Connect an MCP client

`burrow mcp <vault-folder>` is an MCP server on stdin and stdout, with seven tools: `vault_search`, `vault_read`, `vault_links`, `vault_list`, `vault_folders`, `vault_remember` and `vault_ask`. Only `vault_remember` writes, and it only adds a note. Point a client at the built binary, using full paths:

```json
{
  "mcpServers": {
    "burrow": {
      "command": "/full/path/to/burrow/.build/release/burrow",
      "args": ["mcp", "/full/path/to/your/vault"]
    }
  }
}
```

Excerpts are marked as project content, so a client shouldn't take instructions from them. Search uses meaning when the vault has vectors and falls back to words if Ollama is off. Logs go to stderr.

## Where it lives

The memory lives in `.burrow` inside the project. Notes are ordinary Markdown files. The index can be deleted and rebuilt at any time.

See [DECISIONS.md](DECISIONS.md) for why it works this way.
