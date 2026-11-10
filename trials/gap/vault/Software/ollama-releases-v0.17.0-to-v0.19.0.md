---
source: https://github.com/ollama/ollama/releases
fetched: 2026-11-10
published: 2026-02-21 to 2026-03-27
title: Ollama release notes — v0.17.0 to v0.19.0 (15 releases)
---

# Ollama release notes: v0.17.0 to v0.19.0

## v0.17.0 (published 2026-02-21)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.0

### OpenClaw

OpenClaw can now be installed and configured automatically via Ollama, making it the easiest way to get up and running with OpenClaw with open models like Kimi-K2.5, GLM-5, and Minimax-M2.5.

#### Get started

`ollama launch openclaw`

<img width="2368" height="1830" alt="oc1" src="https://github.com/user-attachments/assets/cb9443d6-92cc-4c13-b26b-87e5f6c09b4e" />

#### Web search in OpenClaw

When using cloud models, websearch is enabled - allowing OpenClaw to search the internet.

<img width="2368" height="1830" alt="oc3" src="https://github.com/user-attachments/assets/a4400e6d-e4c4-485b-bd11-823a624962a2" />

### What's Changed
* Improved tokenizer performance
* Ollama's macOS and Windows apps will now default to a context length based on available VRAM

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.16.3...v0.17.0

## v0.17.1 (published 2026-02-24)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.1

### What's Changed
* Nemotron architecture support in Ollama's engine
* MLX engine now has improved memory usage
* Ollama's app will now allow models that support tools to use web search capabilities
* Improved LFM2 and LFM2.5 models in Ollama's engine
* `ollama create` will no longer default to affine quantization for unquantized models when using the MLX engine
* Added configuration for disabling automatic update downloading

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.0...v0.17.1

## v0.17.2 (published 2026-02-26)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.2

### What's Changed
* Fixed issue where Ollama's app on Windows would crash when a new update has been downloaded

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.1...v0.17.2

## v0.17.3 (published 2026-02-27)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.3

### What's Changed
* Fixed issue where tool calls in the Qwen 3 and Qwen 3.5 model families would not be parsed correctly if emitted during thinking

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.2...v0.17.3

## v0.17.4 (published 2026-02-27)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.4

### New models
- [Qwen 3.5](https://ollama.com/library/qwen3.5): a family of open-source multimodal models that delivers exceptional utility and performance.
- [LFM 2](https://ollama.com/library/lfm2): LFM2 is a family of hybrid models designed for on-device deployment. LFM2-24B-A2B is the largest model in the family, scaling the architecture to 24 billion parameters while keeping inference efficient.

> Note: for users on 0.17.1, this version will not automatically update. [Re-downloading](https://ollama.com/download) is required to receive the latest version of Ollama.

### What's Changed
* Tool call indices will now be included in parallel tool calls

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.3...v0.17.4

## v0.17.5 (published 2026-03-02)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.5

### New models
- [Qwen3.5](https://ollama.com/library/qwen3.5): the small Qwen 3.5 model series is now available in 0.8B, 2B, 4B and 9B parameter sizes.

### What's Changed
* Fixed crash in Qwen 3.5 models when split over GPU & CPU
* Fixed issue where Qwen 3.5 models would repeat themselves due to no presence penalty (note: you may have to redownload the `qwen3.5` models:  `ollama pull qwen3.5:35b` for example)
* `ollama run --verbose` will now show peak memory usage when using Ollama's MLX engine
* Fixed memory issues and crashes in MLX runner
* Fixed issue where Ollama would not be able to run models imported from Qwen3.5 GGUF files

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.4...v0.17.5

## v0.17.6 (published 2026-03-04)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.6

### What's Changed
* Fixed issue where GLM-OCR would not work due to incorrect prompt rendering
* Fixed tool calling parsing and rendering for Qwen 3.5 models

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.5...v0.17.6

## v0.17.7 (published 2026-03-05)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.7

### What's Changed
* Allow thinking levels such as `"medium"` to correctly interpreted in Ollama's API for all thinking models
* Add context length to support compaction when using `ollama launch`

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.6...v0.17.7

## v0.17.8-rc4 (published 2026-03-10)

Release page: https://github.com/ollama/ollama/releases/tag/v0.17.8-rc4

### What's Changed
* parsers: repair unclosed arg_value tags in GLM tool calls by @BruceMacD in https://github.com/ollama/ollama/pull/14656
* Reapply "don't require pulling stubs for cloud models" again by @jmorganca in https://github.com/ollama/ollama/pull/14608
* docs: format compat docs by @mxyng in https://github.com/ollama/ollama/pull/14678
* create: fix localhost handling by @dhiltgen in https://github.com/ollama/ollama/pull/14681
* build: smarter docker parallelism by @dhiltgen in https://github.com/ollama/ollama/pull/14653
* mlx: int4 groupsize 64 by @pdevine in https://github.com/ollama/ollama/pull/14682
* cloud_proxy: handle stream disconnects gracefully by @drifkin in https://github.com/ollama/ollama/pull/14685
* x/mlxrunner: replace sampler interface chain with single stateful Sampler by @pdevine in https://github.com/ollama/ollama/pull/14652
* rocm: update linux to v7.2 by @dhiltgen in https://github.com/ollama/ollama/pull/14391
* app: fix reset to defaults disabling auto-update by @hoyyeva in https://github.com/ollama/ollama/pull/14741
* mlx: get parameters from modelfile during model creation by @pdevine in https://github.com/ollama/ollama/pull/14747
* MLX: add header vendoring and remove go build tag by @dhiltgen in https://github.com/ollama/ollama/pull/14642
* ci: Fix windows build by @dhiltgen in https://github.com/ollama/ollama/pull/14754

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.7...v0.17.8-rc1

## v0.18.0 (published 2026-03-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.18.0

Ollama 0.18 includes improved performance for OpenClaw and Ollama’s [cloud models](https://ollama.com/search?c=cloud), including the new Nemotron-3-Super model by NVIDIA designed for high-performance agentic reasoning tasks.

#### Improved OpenClaw performance with Kimi-K2.5

This release of Ollama improves performance of cloud models and their reliability.

- Up to 2x faster speeds with Kimi-K2.5
- Tool calling accuracy has been improved

```
ollama launch openclaw --model kimi-k2.5
```

#### Ollama is now a provider in OpenClaw

Ollama can now be selected as an authentication and model provider during OpenClaw onboarding (thanks @BruceMacD for contributing and @steipete for reviewing!)

```
openclaw onboard --auth-choice ollama
```

More information: [https://docs.openclaw.ai/providers/ollama](https://docs.openclaw.ai/providers/ollama)

#### Nemotron-3-Super

[Nemotron-3-Super](https://ollama.com/library/nemotron-3-super): is a new 122B parameter model with strong reasoning and tool calling capability, while having top performance when run on modern hardware:

- `ollama run nemotron-3-super:cloud`
- `ollama run nemotron-3-super` to run locally (requires 96GB+ of VRAM)

Nemotron-3-Super scores highest of any open model on PinchBench, a benchmark suite that measures how successful models are at completing tasks when used with OpenClaw.

```
ollama launch openclaw --model nemotron-3-super:cloud
```

Or using OpenClaw’s onboarding:

```
openclaw onboard \
	--auth-choice ollama \
	--custom-model-id nemotron-3-super:cloud
```

#### Non-interactive task support

`ollama launch` now supports non-interactive tasks by passing in `--yes`. This enables using Claude, Codex, Pi and more in scripts, GitHub Actions, and other non-interactive environments.

```
ollama launch claude \
	--model glm-5:cloud \
	--yes \
	-- "Do a quick code review of this pull request and respond on GitHub with a comment summarizing your feedback."
```

#### Lower latency on MiniMax-M2.5 and Qwen3.5 on Ollama’s cloud

For customers in North America, MiniMax-M2.5 and Qwen3.5 on Ollama’s cloud now respond much faster, up to 10x and up to 2x faster respectively, and often in less than a second. This is ideal for tasks that require a fast Time To First Token (TTFT) when needing quick answers from OpenClaw or quick back-to-back coding tasks.

```
ollama launch claude --model minimax-m2.5
```

#### Driver updates required for ROCm 7

This version of Ollama ships with [ROCm 7](https://www.amd.com/en/products/software/rocm/whats-new.html), and requires updating drivers to the latest version for continued support.

### What's Changed
* Ollama's cloud models no longer require downloading via `ollama pull`. Setting `:cloud` as a tag will now automatically connect to cloud models.
* New `--yes` flag for `ollama launch` that skips all prompts, making it possible to run AI assistants and other tools in non-interactive environments
* Fixed issue where "Reset to Defaults" in Ollama's app would disable downloading automatic updates.
* Ollama will now ensure context compaction occurs at the correct context length for each model when using `ollama launch claude`

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.17.7...v0.18.0

## v0.18.1 (published 2026-03-17)

Release page: https://github.com/ollama/ollama/releases/tag/v0.18.1

#### Web Search and Fetch in OpenClaw

Ollama now ships with web search and web fetch plugin for OpenClaw. This allows Ollama's models (local or cloud) to search the web for the latest content and news. This also allows OpenClaw with Ollama to be able to fetch the web and extract readable content for processing. This feature does not execute JavaScript.

When using local models with web search in OpenClaw, ensure you are signed into Ollama with `ollama signin`

```
ollama launch openclaw
```

You can install web search directly into OpenClaw as a plugin if you already have OpenClaw configured and working:

#### Ollama web search plugin
```
openclaw plugins install @ollama/openclaw-web-search
```
#### Non-interactive (headless) mode for ollama launch

`ollama launch` can now run in non-interactive mode.

Perfect for:

- Docker/containers: spin up an integration as a pipeline step to run evals, test prompts, or validate model behavior as part of your build. Tear it down when the job ends.

- CI/CD: Generate code reviews, security checks, and other tasks within your CI                              

- Scripts/automation: Kick off automated tasks with Ollama and claude code

- `--model`  must be specified to run in headless mode         
-  `--yes` flag will auto-pull the model and skip any selectors

Try with: `ollama launch claude --model kimi-k2.5:cloud --yes -- -p "how does this repository work?"`

#### Use non-interactive mode in OpenClaw

You can ask your OpenClaw to run tasks using claude with subagents:
```
ollama launch claude --model kimi-k2.5:cloud --yes -- -p "how does this repository work?" using a subagent
```

### What's Changed
* `ollama launch openclaw` will now use the official Ollama auth and model provider for OpenClaw
* Improvements to Ollama's benchmarking tool in `./cmd/bench`
* `ollama launch openclaw` will now skip `--install-daemon` when systemd is unavailable

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.18.0...v0.18.1

## v0.18.2 (published 2026-03-18)

Release page: https://github.com/ollama/ollama/releases/tag/v0.18.2

### What's Changed
* Add extra check to ensure `npm` and `git` are installed before installing OpenClaw
* Claude Code will now be faster when run locally, due to preventing cache breakages
* Fix to correctly support `ollama launch openclaw --model <model>`
* Register Ollama's websearch package correctly for OpenClaw

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.18.1...v0.18.2

## v0.18.3 (published 2026-03-25)

Release page: https://github.com/ollama/ollama/releases/tag/v0.18.3

### Visual Studio Code 

Microsoft Visual Studio Code now directly integrates with Ollama via GitHub Copilot.

If you have Ollama installed, any local or cloud model from Ollama can be selected for use within visual studio code. 

<img width="3410" height="2076" alt="Ollama screenshot 2026-03-26 at 01 43 57@2x" src="https://github.com/user-attachments/assets/4f9edc73-af3d-475c-924e-93334a4d88c5" />

### What's Changed
* GLM parser improvements for tool calls
* OpenClaw integration improvements for gateway checks

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.18.2...v0.18.3

## v0.18.4-rc0 (published 2026-03-26)

Release page: https://github.com/ollama/ollama/releases/tag/v0.18.4-rc0

### What's Changed
* ggml: force flash attention off for grok by @rick-github in https://github.com/ollama/ollama/pull/15050
* mlx: fix KV cache snapshot memory leak by @jessegross in https://github.com/ollama/ollama/pull/15065
* mlxrunner: schedule periodic snapshots during prefill by @jessegross in https://github.com/ollama/ollama/pull/15058
* doc: update vscode doc by @hoyyeva in https://github.com/ollama/ollama/pull/15064

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.18.3...v0.18.4-rc0

## v0.19.0 (published 2026-03-27)

Release page: https://github.com/ollama/ollama/releases/tag/v0.19.0

<img width="480" alt="image" src="https://github.com/user-attachments/assets/1b5ca980-b9d5-490e-99b9-f0f7b9af2c32" />

### Ollama is now powered by MLX on Apple Silicon in preview

Ollama on Apple silicon [is now built](https://ollama.com/blog/mlx) on top of Apple’s machine learning framework, MLX, to take advantage of its unified memory architecture.

https://github.com/user-attachments/assets/600297b0-3167-46a5-8e3a-fefda3a51b84

Read more: https://ollama.com/blog/mlx

### What's Changed
* Ollama's app will now no longer incorrectly show "model is out of date"
* `ollama launch pi` now includes web search plugin that uses Ollama's web search
* Improved KV cache hit rate when using the Anthropic-compatible API
* Fixed tool call parsing issue with Qwen3.5 where tool calls would be output in thinking
* MLX runner will now create periodic snapshots during prompt processing
* Fixed KV cache snapshot memory leak in MLX runner
* Fixed issue where flash attention would be incorrectly enabled for `grok` models
* Fixed `qwen3-next:80b` not loading in Ollama

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.18.3...v0.19.0
