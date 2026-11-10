---
source: https://github.com/ollama/ollama/releases
fetched: 2026-11-10
published: 2026-07-11 to 2026-09-02
title: Ollama release notes — v0.32.0 to v0.33.3 (18 releases)
---

# Ollama release notes: v0.32.0 to v0.33.3

## v0.32.0 (published 2026-07-11)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.0

### What's Changed

  - New interactive agent experience: running `ollama` now launches an agent to help you code and delegate work
```
❯ ollama
Ollama 0.32.0

▸ Chat, Code, & Work (glm-5.2:cloud)
    Chat with models, code, search the web, and delegate real work
```
  - Renamed the Codex App integration to ChatGPT: use ollama launch chatgpt (and --restore to return to your usual ChatGPT profile)
  - Simplified integration selection: the ollama launch menu now only offers the most popular integrations (other integrations can be accessed through `ollama launch`
  - Warns before launching older agent models: CodeLlama, Qwen2.5(-coder), Llama 3.x, Mistral, StarCoder, and the base DeepSeek-R1 tags now prompt a deprecation warning before ollama launch continues

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.31.2...v0.32.0

## v0.32.1 (published 2026-07-16)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.1

### What's Changed
- Improved Gemma 4 tool calling and multi-turn reasoning, including more reliable tool-response continuations
- Fixed a recurrent MLX model cache leak that could increase memory use across requests, and improved cache snapshot performance
- MLX text model loading now respects `OLLAMA_LOAD_TIMEOUT`
- Agent web search and fetch now tell users to run `ollama signin` when authentication is required
- The interactive agent now receives the current working directory for better project context
- Fixed `ollama launch` so choosing **Pick another model** for a deprecated model passed with `--model` opens the model picker
- Updated VS Code setup documentation for the official Ollama extension

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.0...v0.32.1-rc0

## v0.32.3 (published 2026-07-23)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.3

### What's Changed

- Fixed model downloads that stall before sending data.
- Improved integrations: restored Claude Code Channels, fixed Anthropic thinking streams, and made Hermes Desktop respect `--force-build`.
- Expanded GPU support with CUDA on Windows ARM64, B200 support through CUDA 12, and lower memory use on Linux CUDA/ROCm iGPUs.
- Added chat, thinking, and tool calling support for Laguna 2.1 models, including a Metal inference fix.
- Fixed GLM tool calls being silently dropped at the end of generation.
- Updated the MLX and llama.cpp engines.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.1...v0.32.3

## v0.32.4 (published 2026-07-25)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.4

### What's Changed
- Support Laguna on Apple GPUs via the MLX engine
- Quantize draft-model output heads at the requested type when creating speculative-decoding drafts.
- Fixed Qwen3 MoE decoding for differently-quantized experts, plus faster packed gate/up projection (~4–9% on M5 Max).

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.3...v0.32.4

## v0.32.5 (published 2026-07-27)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.5

### What's Changed

* Fixed an MLX Metal bug that could reduce output quality for NVFP4 models, particularly Laguna.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.4...v0.32.5

## v0.32.6 (published 2026-08-04)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.6

### What's Changed
  - Qwen3.5 is faster on Apple GPUs: the MLX engine now uses the model's MTP head for speculative decoding automatically
  - `/v1/chat/completions` streaming now matches OpenAI's wire format: `role` only on the first chunk, `finish_reason` on its own chunk,
  and usage in a separate chunk with `stream_options.include_usage`.
  - Truncated OpenAI responses now report `finish_reason: "length"` instead of `"tool_calls"`.
  - `ollama run kimi-k3` now offers `kimi-k3:cloud` for cloud-only models that publish no default tag, instead of failing.
  - TUI fixes: pipe-delimited prose no longer renders as a table, Enter accepts the highlighted `@` file completion, and `/prompt`
  scrolling is no longer laggy.
  - Experimental image generation has been temporarily removed. Continue using 0.32.5 for image generation support
  - Updated the MLX and llama.cpp engines.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.5...v0.32.6-rc0

## v0.32.7 (published 2026-08-10)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.7

### Muse Glimmer

> Note: Muse Glimmer is currently available via initial support via Ollama's MLX engine on Apple Silicon. Additional support and optimizations for Apple Silicon, NVIDIA, AMD, and other platforms will be available in the coming days.

**Muse Glimmer**, Meta's newest open model and the first released by Meta Superintelligence Labs, is now available on Ollama. It's a 30B multimodal model purpose-built for agent workloads that run locally.

With Ollama, you can now use Muse Glimmer to power coding agent applications such as Claude Code, Codex, Pi and more, as well as long-running personal assistants such as OpenClaw and Hermes.

Ollama's MLX engine provides state-of-the-art performance on Apple Silicon for this model, with support for DFlash and image input as of Ollama 0.32.7.

To download and run Muse Glimmer locally:

```bash
ollama run muse-glimmer:30b-mlx
```

To run Muse Glimmer on Apple Silicon with Claude Code, [download Ollama](https://ollama.com/download) and run:

```bash
ollama launch claude --model muse-glimmer:30b-mlx
```

For a lighter-weight coding agent, try [Pi](https://pi.dev):

```bash
ollama launch pi --model muse-glimmer:30b-mlx
```

For personal assistant frameworks such as OpenClaw and Hermes, use:

```bash
ollama launch openclaw --model muse-glimmer:30b-mlx
```

```bash
ollama launch hermes --model muse-glimmer:30b-mlx
```

## v0.32.8 (published 2026-08-10)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.8

### Muse Glimmer

Muse Glimmer is now available on all platforms. Muse Glimmer can power coding agent applications such as Claude Code, Codex, Pi and more, as well as long-running personal assistants such as OpenClaw and Hermes.

Ollama's MLX engine provides state-of-the-art performance on Apple Silicon for this model, with support for DFlash and image input as of Ollama 0.32.7.

To download and run Muse Glimmer locally:

```bash
ollama run muse-glimmer
```

To run Muse Glimmer with Claude Code, [download Ollama](https://ollama.com/download) and run:

```bash
ollama launch claude --model muse-glimmer
```

For a lighter-weight coding agent, try [Pi](https://pi.dev):

```bash
ollama launch pi --model muse-glimmer
```

For personal assistant frameworks such as OpenClaw and Hermes, use:

```bash
ollama launch openclaw --model muse-glimmer
```

```bash
ollama launch hermes --model muse-glimmer
```

### What's Changed
* Add Muse Glimmer support for NVIDIA, AMD, and additional platforms

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.7...v0.32.8

## v0.32.9 (published 2026-08-11)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.9

### NVIDIA Nemotron 3.5 Lightning

[NVIDIA Nemotron 3.5 Lightning](https://ollama.com/library/nemotron-3.5-lightning) is an open 30B mixture-of-experts (MoE) model with 3B active parameters built for that execution layer of always-on agents. It is designed for harnesses like OpenClaw and Hermes Agent – all supported by the [NVIDIA NemoClaw](https://github.com/NVIDIA/NemoClaw) open source security and management stack for running always-on AI agents.

```
ollama run nemotron-3.5-lightning
```

### What's Changed
* Added the Nemotron 3 architecture
* Handle boundary condition in Muse Glimmer function calling parser

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.8...v0.32.9

## v0.32.11 (published 2026-08-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.11

### What's Changed
* `ollama launch dsh` now supports DeepSeek Harness, [DeepSeek's open-source agent harness](https://deepseek.com/harness/en/)
* `ollama launch muse` now supports [Muse Code](https://developer.meta.com/ai/products/muse-code/), Meta's agentic coding CLI
* The OpenAI-compatible Responses API now supports web search
* Muse Glimmer template updates

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.10...v0.32.11

## v0.32.12 (published 2026-08-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.12

<img width="600" alt="ollama and qwen capybara" src="https://github.com/user-attachments/assets/5fa5e93b-d48b-4a6a-b72a-25379ab9429c" />

### Qwen 3.8 27B

This release adds the support of [Qwen 3.8 27B](https://ollama.com/library/qwen3.8). Qwen3.8 delivers substantial gains across coding, professional work, research, and long-horizon agentic tasks.

```
ollama run qwen3.8:27b
```

For Apple Silicon devices, Ollama has in particular optimized for maximum performance and output quality suitable for repeated tasks and coding agents.

```
ollama run qwen3.8:27b-mlx
```

## v0.32.13 (published 2026-08-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.13

### What's Changed
* qwen3.8: support developer instructions 

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.12...v0.32.13

## v0.32.14 (published 2026-08-15)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.14

### What's Changed
* llm: transcode WebP images for llama-server 
* renderers/qwen: tolerate non-leading system messages

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.13...v0.32.14

## v0.32.15 (published 2026-08-19)

Release page: https://github.com/ollama/ollama/releases/tag/v0.32.15

### What's Changed
* New desktop onboarding flow on first launch
* Caches resolved model metadata between requests, cutting time-to-first-token by roughly half (TTFT dropped from ~995 ms to ~524 ms in benchmarks)
* Fixes a bug where chat and generate could wedge after a mid-stream parser error
* **Qwen 3.8** system messages are now normalized so non-leading system messages are handled consistently
* MLX and llama.cpp dependency updates

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.14...v0.32.15

## v0.33.0 (published 2026-08-21)

Release page: https://github.com/ollama/ollama/releases/tag/v0.33.0

### What's Changed

#### Claude Desktop

Developers can now easily configure Claude Desktop to seamlessly work with Ollama as a third-party gateway provider. 

<img width="1298" height="780" alt="image" src="https://github.com/user-attachments/assets/c02fd93b-f599-40a9-83c3-d0555c0ac182" />

#### Improved caching

* Fixed a hang where agent clients that cancel long prefills
* Prefill restore points are now trustworthy by construction: a cancelled prefill keeps every restore point it crossed, so retries resume where they stopped instead of restarting from scratch
* Resumed prefills no longer record restore points that fail to cover what they claim; on models with recurrent layers this previously forced a request matching 46k of 47k tokens to reprocess from zero
* Disabled Claude Code's "tokens left" token-countdown system message, which Ollama moved to the front of the prompt and broke the KV cache on every request

#### Other improvements

* DeepSeek Harness launcher now falls back to `npx` when the global npm install fails, with Windows command-shim support
* MLX dependency update (#17886)
* Fixed broken default packaging caused by macOS-specific assumptions affecting Linux/Windows builds

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.32.15...v0.33.0

## v0.33.1 (published 2026-08-26)

Release page: https://github.com/ollama/ollama/releases/tag/v0.33.1

### What's Changed
* MLX: Qwen3.8 Flash Next support
* cmake: make external compat patches idempotent
* MLX and llama.cpp update
* mlxrunner: add structured output support
* mlxrunner: avoid Metal GPU timeouts when loading models from slow storage

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.33.0...v0.33.1

## v0.33.2 (published 2026-08-27)

Release page: https://github.com/ollama/ollama/releases/tag/v0.33.2

### What's Changed

* Ollama's app now follows the system appearance again, restoring dark mode support
* Fixed the macOS app to properly hand off to an already-running instance instead of starting a second one
* The Claude Desktop proxy no longer interrupts in-flight requests when the model catalog updates

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.33.1...v0.33.2

## v0.33.3 (published 2026-09-02)

Release page: https://github.com/ollama/ollama/releases/tag/v0.33.3

### What's Changed
* gemma4 now supports images and audio on MLX engine
* Report cached prompt tokens
* Honor GGUF model defined default parameters
* MLX, MLX-C, llama.cpp update

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.33.2...v0.33.3
