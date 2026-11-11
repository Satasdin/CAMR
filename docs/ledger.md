# The Ledger: a git for what AIs understood

Git keeps the code. The Ledger keeps what AI sessions understood about it: decisions and why, facts confirmed in the files, corrections, the plan, and where each session stopped. A model that loses its memory starts from the Ledger instead of from zero. That covers Claude after compaction, a new ChatGPT or Codex chat, and a small local model with a full window.

## What a commit is

One Markdown file under `<vault>/.burrow/ledger/<branch>/<id>.md`, readable in Obsidian:

```markdown
---
id: "20261111-114400-1c48"
branch: "main"
kind: "fact"
author: "qwen3:4b"
at: "2026-11-11T11:44:00Z"
client: "opencode"
cites: {"Law/general-regs-part-06-breach-notification.md":"1b0f256e67384492"}
---

Breach notice is due within 72 hours of becoming aware
```

- **kind**: one of decision, fact, correction, plan, handoff or code.
- **cites**: the vault files the commit rests on, with a hash of each. When a cited file changes, the commit shows **check again** until someone looks.
- **Never deleted**: `revert` adds a correction, and the old commit shows as **marked wrong** wherever it appears.
- **Branches**: a linked folder is its own branch (`burrow`, `tally`); everything else is `main`.

## Terminal

```
burrow commit <vault> "Shelf keeps 12 GB" --kind decision --files burrow/Sources/BurrowCore/KVShelf.swift
burrow log    <vault> [--branch B] [--file PATH]
burrow resume <vault> [branch]
burrow blame  <vault> <path>
burrow diff   <vault> --since <commit>
burrow revert <vault> <commit> "what is right instead"
burrow branch <vault> [name]
```

## Programs that use the vault (MCP)

`burrow mcp <vault>` shows four tools by default. The rest answer when called by name, and the old `vault_` names still work.

| Tool | Shown by default | What it does |
| --- | --- | --- |
| `burrow_find` | yes | Search. Every result carries a trust line: strong, thin, or not in the vault, plus any correction on the files found |
| `burrow_read` | yes | Read a file with line numbers |
| `burrow_resume` | yes | The plan, where the last session stopped, corrections and latest commits |
| `burrow_commit` | yes | Keep a decision, fact, plan or handoff, citing its files |
| `burrow_log`, `burrow_blame`, `burrow_diff`, `burrow_revert` | with `--tools full` | History, who explained a file, what changed since, and marking a commit wrong |

`--tools classic` shows only the `vault_` tools, for runs that must match earlier ones. When a connection closes, Burrow writes a handoff from its lookups itself, so a model that never logged anything still leaves one.

## Claude Code

```
burrow hook install claude ~/Notes
```

This prints the settings to add to `~/.claude/settings.json`. Burrow never edits that file itself. Then:

- **Session start**: Claude Code is handed the Ledger head for the folder it was opened in.
- **Before compaction and at session end**: Burrow keeps the plan (from Claude Code's task list) and a handoff built from what you typed and the files edited. Facts and decisions are kept only when you asked for them, through `burrow_commit`.

## git

Inside a repository linked to the vault:

```
burrow hook install git ~/Notes
```

This writes `.git/hooks/post-commit`, but never over an existing hook. Each commit is then linked into the Ledger by its sha and the files it changed, so `burrow blame` can show which AI session led to a change. The hook never blocks a commit.

## Safety

Commits are written by models, so whatever reads them treats them as data. `resume`, `log` and `blame` output sits inside one `<ledger>` block that its contents cannot close, names who wrote each commit, and says to follow no instruction inside it. Cited paths must be plain vault paths: never absolute, never `..`. The write tools run only for programs connected over MCP; Burrow's own chat refuses them, because it asks before keeping anything.
