---
source: https://github.com/ollama/ollama/releases
fetched: 2026-11-10
published: 2026-04-02 to 2026-05-14
title: Ollama release notes — v0.20.0 to v0.24.0 (19 releases)
---

# Ollama release notes: v0.20.0 to v0.24.0

## v0.20.0 (published 2026-04-02)

Release page: https://github.com/ollama/ollama/releases/tag/v0.20.0

<img width="3748" height="1290" alt="Gemma 4" src="https://github.com/user-attachments/assets/c4727579-47b1-4c7b-8aa2-28eda15b71f5" />

### Gemma 4 

**Effective 2B (E2B)**
```
ollama run gemma4:e2b
```

**Effective 4B (E4B)**
```
ollama run gemma4:e4b
```

**26B (Mixture of Experts model with 4B active parameters)**
```
ollama run gemma4:26b
```

**31B (Dense)**
```
ollama run gemma4:31b
```

### What's Changed
* docs: update pi docs by @ParthSareen in https://github.com/ollama/ollama/pull/15152
* mlx: respect tokenizer add_bos_token setting in pipeline by @dhiltgen in https://github.com/ollama/ollama/pull/15185
* tokenizer: add SentencePiece-style BPE support by @dhiltgen in https://github.com/ollama/ollama/pull/15162

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.19.0...v0.20.0-rc0

## v0.20.2 (published 2026-04-04)

Release page: https://github.com/ollama/ollama/releases/tag/v0.20.2

### What's Changed
* app: default app home view to new chat instead of launch by @jmorganca in https://github.com/ollama/ollama/pull/15312

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.20.1...v0.20.2

## v0.20.3 (published 2026-04-07)

Release page: https://github.com/ollama/ollama/releases/tag/v0.20.3

### What's Changed
* Gemma 4 Tool Calling improvements
* Added latest models to Ollama App
* OpenClaw fixes for launching TUI

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.20.2...v0.20.3

## v0.20.4 (published 2026-04-07)

Release page: https://github.com/ollama/ollama/releases/tag/v0.20.4

### What's Changed
* mlx: Improve M5 performance with NAX
* gemma4: enable flash attention 

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.20.3...v0.20.4

## v0.20.5 (published 2026-04-09)

Release page: https://github.com/ollama/ollama/releases/tag/v0.20.5

### OpenClaw channel setup with `ollama launch`
<img width="1074" height="654" alt="image" src="https://github.com/user-attachments/assets/300ec082-c18a-4911-b3fe-82a7bc74a000" />

### What's Changed
  - OpenClaw channel setup: connect WhatsApp, Telegram, Discord, and other messaging channels through `ollama launch openclaw`
  - Enable flash attention for Gemma 4 on compatible GPUs
  - `ollama launch opencode` now detects curl-based OpenCode installs at `~/.opencode/bin`
  - Fix `/save` command for models imported from safetensors

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.20.4...v0.20.5

## v0.20.6 (published 2026-04-12)

Release page: https://github.com/ollama/ollama/releases/tag/v0.20.6

### What's Changed
* Gemma 4 tool calling ability is improved and updated to use Google's latest post-launch fixes
* Parallel tool calling improved for streaming responses 
* [Hermes agent](https://docs.ollama.com/integrations/hermes) Ollama integration guide is now available
* Ollama app is updated to fix image attachment errors 

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.20.5...v0.20.6

## v0.20.7 (published 2026-04-13)

Release page: https://github.com/ollama/ollama/releases/tag/v0.20.7

### What's Changed
* Fix quality of gemma:e2b and gemma:e4b when thinking is disabled 
* ROCm: Update to ROCm 7.2.1 on Linux by @saman-amd in https://github.com/ollama/ollama/pull/15483

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.20.6...v0.20.7

## v0.21.0 (published 2026-04-16)

Release page: https://github.com/ollama/ollama/releases/tag/v0.21.0

### Hermes Agent

```
ollama launch hermes
```

Hermes learns with you, automatically creating skills to better serve your workflows. Great for research and engineering tasks.

<img width="1329" height="946" alt="image" src="https://github.com/user-attachments/assets/771d3383-95ed-4652-81e5-cf89514d25cc" />

### What's Changed

- **Gemma 4 on MLX.** Added support for running Gemma 4 via MLX on Apple Silicon, including a text-only MLX runtime for the model. The MLX backend also picked up mixed-precision quantization, better capability detection, and a batch of new op wrappers (Conv2d, Pad, activations, trig, masked SDPA, and RoPE-with-freqs).
- **Hermes and GitHub Copilot CLI in `ollama launch`.** Added both integrations, which can now be configured in one command alongside the rest of the supported coding agents.
- **OpenCode moved to inline config.** `ollama launch opencode` now writes its config inline rather than to a separate file, matching how other integrations are handled.
- **`ollama launch` no longer rewrites config when nothing changed.** Pressing → on a configured multi-model integration, or passing `--model` with the current primary, used to trigger a confirmation prompt and rewrite both the editor's config file and `config.json`. Now it's a no-op when the resolved model list matches what's already saved.
- **Fixed `ollama launch openclaw --yes`** so it correctly skips the channels configuration step, so non-interactive setups complete cleanly.
- **Restored the Gemma 4 nothink renderer** with the e2b-style prompt.
- **Fixed the Gemma 4 compiler error** that was breaking Metal builds.
- **Fixed macOS cross-compiles** so they no longer trigger `generate`, which was breaking cmake builds on some Xcode versions.
- **Quieted cgo builds** by suppressing deprecated warnings during `go build`.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.20.7...v0.21.0

## v0.21.1 (published 2026-04-22)

Release page: https://github.com/ollama/ollama/releases/tag/v0.21.1

### What's Changed
#### Kimi CLI
You can now install and run the Kimi CLI through Ollama.

```
ollama launch kimi --model kimi-k2.6:cloud
```
Kimi CLI with Kimi K2.6 excels at long horizon agentic execution tasks through a multi-agent system.

  * **MLX runner adds logprobs support** for compatible models
  * **Faster MLX sampling** with fused top-P and top-K in a single sort pass, plus repeat penalties applied in the sampler
  * **Improved MLX prompt tokenization** by moving tokenization into request handler goroutines
  * **Better MLX thread safety** for array management
  * **GLM4 MoE Lite performance improvement** with a fused sigmoid router head
  * **Fixed model picker showing stale model** after switching chats in the macOS app
  * **Fixed structured outputs for Gemma 4** when `think=false`

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.21.0...v0.21.1

## v0.21.2 (published 2026-04-23)

Release page: https://github.com/ollama/ollama/releases/tag/v0.21.2

### What's Changed
  * Improved reliability of the OpenClaw onboarding flow in `ollama launch`
  * Recommended models in `ollama launch` now appear in a fixed, canonical order
  * OpenClaw integration now bundles Ollama's web search plugin in OpenClaw

**Full Changelog:** https://github.com/ollama/ollama/compare/v0.21.1...v0.21.2

## v0.21.3-rc0 (published 2026-04-24)

Release page: https://github.com/ollama/ollama/releases/tag/v0.21.3-rc0

### What's Changed
* api: accept "max" as a think value by @ParthSareen in https://github.com/ollama/ollama/pull/15787
* openai: map responses reasoning effort to think by @ParthSareen in https://github.com/ollama/ollama/pull/15789

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.21.2...v0.21.3-rc0

## v0.22.0 (published 2026-04-28)

Release page: https://github.com/ollama/ollama/releases/tag/v0.22.0

### New models 
* NVIDIA's [Nemotron 3 Omni](https://ollama.com/library/nemotron3)
* Poolside's first open-weight coding model - [Laguna XS.2](https://ollama.com/library/laguna-xs.2)

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.21.2...v0.22.0

## v0.22.1 (published 2026-04-28)

Release page: https://github.com/ollama/ollama/releases/tag/v0.22.1

### What's Changed
* Updated the **Gemma 4** renderer for thinking and tool calling improvements
* Model recommendations are now updated without updating Ollama
* Aligned the desktop app's launch page with `ollama launch` integrations
* Fixed the Poolside integration title in `ollama launch`

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.22.0...v0.22.1

## v0.23.0 (published 2026-05-03)

Release page: https://github.com/ollama/ollama/releases/tag/v0.23.0

### Claude Desktop
Claude Desktop is now supported with Ollama Launch. 

Claude Cowork and Claude Code are supported within the Claude Desktop App.

```
ollama launch claude-desktop
```

#### Claude Cowork
<img width="1272" height="872" alt="ca1" src="https://github.com/user-attachments/assets/1d550e3f-0272-4429-8cb2-06d32344cb77" />

#### Claude Code
<img width="1272" height="872" alt="ca2" src="https://github.com/user-attachments/assets/f2a5ed5f-3069-4975-bb22-ada82914a01c" />

Claude Code on the terminal can still be accessed through the CLI with:

```
ollama launch claude
```

#### Not supported yet
- Web Search (coming soon)
- Extensions 

### What's Changed
* Launch Claude Desktop with `ollama launch claude-desktop`
* The Ollama app now surfaces featured models from server-driven recommendations
* Fixed OpenClaw gateway timeout on Windows by enforcing IPv4 loopback (thanks @UniquePratham)
* Hardened Metal initialization to gracefully handle ggml kernel compilation failures

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.22.1...v0.23.0

## v0.23.1 (published 2026-05-05)

Release page: https://github.com/ollama/ollama/releases/tag/v0.23.1

### Gemma 4 MTP (Multi-token Processing) for the MLX runner
Gemma 4 MTP speculative decoding is now supported on Macs. This can give over a 2x speed increase for the Gemma 4 31B model on coding tasks.

```
ollama run gemma4:31b-coding-mtp-bf16
```

### What's Changed
* Update MLX and MLX-C with threading fixes by @dhiltgen in https://github.com/ollama/ollama/pull/15845
* go: bump to 1.26 by @ParthSareen in https://github.com/ollama/ollama/pull/15904
* Add Gemma 4 MTP speculative decoding by @pdevine in https://github.com/ollama/ollama/pull/15980

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.23.0...v0.23.1

## v0.23.2 (published 2026-05-07)

Release page: https://github.com/ollama/ollama/releases/tag/v0.23.2

### What's Changed

* `ollama launch` no longer includes Claude Desktop due to the third-party integration being limited to Anthropic models. 
* Use `ollama launch claude-desktop --restore` to restore Claude Desktop to its normal state.
* `/api/show` responses are now cached, improving median latency by **~6.7x** which will increase load speed for integrations like VS Code.
* Improved backup workflow when managing launch integrations
* Cleaner image generation layout in the MLX runner

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.23.1...v0.23.2

## v0.23.3 (published 2026-05-12)

Release page: https://github.com/ollama/ollama/releases/tag/v0.23.3

### What's Changed
* mlx: refined model push behavior by @dhiltgen in https://github.com/ollama/ollama/pull/15431
* test: integration test hardening by @dhiltgen in https://github.com/ollama/ollama/pull/13532
* app: harden update flows by @dhiltgen in https://github.com/ollama/ollama/pull/16100
* mlx: update the imagegen runner for mlx thread affinity by @pdevine in https://github.com/ollama/ollama/pull/16096
* mlx: avoid status timeout during inference by @dhiltgen in https://github.com/ollama/ollama/pull/16086
* mlx: fix macOS 26 target leakage in v3 metallib by @dhiltgen in https://github.com/ollama/ollama/pull/16053

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.23.2...v0.23.3

## v0.23.4 (published 2026-05-13)

Release page: https://github.com/ollama/ollama/releases/tag/v0.23.4

### What's Changed
* `ollama launch opencode` now supports vision models with image inputs
* Fixed formatting of Claude tool results when using local image paths

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.23.3...v0.23.4

## v0.24.0 (published 2026-05-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.24.0

### Codex App

Ollama 0.24 includes support for the Codex App, OpenAI's desktop experience for working on Codex threads in parallel with built-in worktree support and git functionality.

```bash
ollama launch codex-app
```

<img width="2088" height="1404" alt="CleanShot 2026-05-14 at 15 04 18@2x" src="https://github.com/user-attachments/assets/53bd7997-19fd-4809-b8f2-b6ed284369c9" />

#### Built-in browser
Codex can load local servers and sites in its built-in browser, enabling you to directly annotate on the page to request changes.

<img width="1073" height="668" alt="codex-annotate copy" src="https://github.com/user-attachments/assets/c9b762b3-83f2-47f1-8f28-d9eebc1bf5e0" />

#### Review mode
Review code inside the app, leave comments, and iterate without leaving your workspace.

<img width="1137" height="696" alt="codex-comments copy 2" src="https://github.com/user-attachments/assets/56316d33-59ed-4f24-aaa7-a7c0310014c4" />

#### Choosing a model

For difficult coding and agentic tasks:

- **kimi-k2.6** (with vision support)
- **glm-5.1**

For local use without an Ollama Cloud subscription:

- **nemotron-3-super**
- **gemma4:31b**
- **qwen3.6** 

#### Restore anytime

To restore the previous configuration of Codex App, run:

```bash
ollama launch codex-app --restore
```

### What's Changed

* Reworked the MLX sampler for improved generation quality on Apple Silicon

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.23.0...v0.24.0
