---
source: https://github.com/ollama/ollama/releases
fetched: 2026-11-10
published: 2026-01-10 to 2026-02-19
title: Ollama release notes — v0.14.0 to v0.16.3 (15 releases)
---

# Ollama release notes: v0.14.0 to v0.16.3

## v0.14.0 (published 2026-01-10)

Release page: https://github.com/ollama/ollama/releases/tag/v0.14.0

### What's Changed
* `ollama run --experimental` CLI will now open a new Ollama CLI that includes an agent loop and the `bash` tool
* Anthropic API compatibility: support for the `/v1/messages` API
* A new `REQUIRES` command for the `Modelfile` allows declaring which version of Ollama is required for the model
* For older models, Ollama will avoid an integer underflow on low VRAM systems during memory estimation
* More accurate VRAM measurements for AMD iGPUs
* Ollama's app will now highlight swift source code
* An error will now return when embeddings return `NaN` or `-Inf`
* Ollama's Linux install bundles files now use `zst` compression
* New experimental support for image generation models, powered by MLX

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.13.5...v0.14.0-rc2

## v0.14.1 (published 2026-01-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.14.1

### Image generation models (experimental)

Experimental image generation models are available for **macOS** and **Linux (CUDA)** in Ollama:

#### Available models

- [Z-Image-Turbo](https://ollama.com/x/z-image-turbo)

```
ollama run x/z-image-turbo
```

> **Note**: [`x`](https://ollama.com/x) is a username on ollama.com where experimental models are uploaded

More models coming soon:

1. Qwen-Image-2512
2. Qwen-Image-Edit-2511
3. GLM-Image

### What's Changed
* fix macOS auto-update signature verification failure

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.14.0...v0.14.1

## v0.14.2 (published 2026-01-16)

Release page: https://github.com/ollama/ollama/releases/tag/v0.14.2

### New models

- [TranslateGemma](https://ollama.com/library/translategemma): A new collection of open translation models built on Gemma 3, helping people communicate across 55 languages.

### What's Changed
* <kbd>Shift</kbd> + <kbd>Enter</kbd> (or <kbd>Ctrl</kbd> + <kbd>j</kbd>) will now enter a newline in Ollama's CLI
* Improve `/v1/responses` API to better confirm to OpenResponses specification

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.14.1...v0.14.2

## v0.14.3 (published 2026-01-16)

Release page: https://github.com/ollama/ollama/releases/tag/v0.14.3

<img width="2904" height="1420" alt="Ollama screenshot 2026-01-20 at 23 41 54@2x" src="https://github.com/user-attachments/assets/ae16dbc5-5b2b-45fd-ae03-ba15f2721c3c" />

* [Z-Image Turbo](https://ollama.com/x/z-image-turbo): 6 billion parameter text-to-image model from Alibaba’s Tongyi Lab. It generates high-quality photorealistic images.
* [Flux.2 Klein](https://ollama.com/x/flux2-klein): Black Forest Labs’ fastest image-generation models to date.

### New models
* [GLM-4.7-Flash](https://ollama.com/library/glm-4.7-flash): As the strongest model in the 30B class, GLM-4.7-Flash offers a new option for lightweight deployment that balances performance and efficiency.
* [LFM2.5-1.2B-Thinking](https://ollama.com/library/lfm2.5-thinking): LFM2.5 is a new family of hybrid models designed for on-device deployment. 

### What's Changed
* Fixed issue where Ollama's macOS app would interrupt system shutdown
* Fixed `ollama create` and `ollama show` commands for experimental models
* The `/api/generate` API can now be used for image generation
* Fixed minor issues in Nemotron-3-Nano tool parsing
* Fixed issue where removing an image generation model would cause it to first load
* Fixed issue where `ollama rm` would only stop the first model in the list if it were running

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.14.2...v0.14.3

## v0.15.0 (published 2026-01-21)

Release page: https://github.com/ollama/ollama/releases/tag/v0.15.0

<img width="4502" height="2222" alt="An image of Ollama building rapidly on the computer. Build with Ollama!" src="https://github.com/user-attachments/assets/0810fb5c-6727-400a-b711-4ffc349d0bb5" />

### `ollama launch`

A new `ollama launch` command to use Ollama's models with Claude Code, Codex, OpenCode, and Droid without separate configuration.

### What's Changed
* New `ollama launch` command for Claude Code, Codex, OpenCode, and Droid 
* Fixed issue where creating multi-line strings with `"""` would not work when using `ollama run`
* <kbd>Ctrl</kbd>+<kbd>J</kbd> and <kbd>Shift</kbd>+<kbd>Enter</kbd> now work for inserting newlines in `ollama run`
* Reduced memory usage for GLM-4.7-Flash models

## v0.15.1 (published 2026-01-24)

Release page: https://github.com/ollama/ollama/releases/tag/v0.15.1

### What's Changed
* GLM-4.7-Flash performance and correctness improvements, fixing repetitive answers and tool calling quality
* Fixed performance issues on macOS and arm64 Linux
* Fixed issue where `ollama launch` would not detect `claude` and would incorrectly update `opencode` configurations

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.15.0...v0.15.1

## v0.15.2 (published 2026-01-27)

Release page: https://github.com/ollama/ollama/releases/tag/v0.15.2

<img width="1916" height="976" alt="Ollama screenshot 2026-01-26 at 17 53 40@2x (1)" src="https://github.com/user-attachments/assets/7937e607-e16e-46f5-a280-5cf9ce088a68" />

### What's Changed
* New `ollama launch clawdbot` command for launching Clawdbot using Ollama models

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.15.1...v0.15.2

## v0.15.3 (published 2026-02-01)

Release page: https://github.com/ollama/ollama/releases/tag/v0.15.3

### What's Changed
* Renamed `ollama launch clawdbot` to `ollama launch openclaw` to reflect the project's new name
* Improved tool calling for Ministral models
* docs: add clawdbot by @ParthSareen in https://github.com/ollama/ollama/pull/13925
* cmd/config: Use envconfig.Host() for base API in launch config packages by @gabe-l-hart in https://github.com/ollama/ollama/pull/13937
* `ollama launch` will now use the value of `OLLAMA_HOST` when running it

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.15.2...v0.15.3

## v0.15.4 (published 2026-02-01)

Release page: https://github.com/ollama/ollama/releases/tag/v0.15.4

### What's Changed
* `ollama launch openclaw` will now enter the standard OpenClaw onboarding flow if this has not yet been completed.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.15.3...v0.15.4

## v0.15.5 (published 2026-02-03)

Release page: https://github.com/ollama/ollama/releases/tag/v0.15.5

### New models
- [Qwen3-Coder-Next](https://ollama.com/library/qwen3-coder-next): a coding-focused language model from Alibaba's Qwen team, optimized for agentic coding workflows and local development.
- [GLM-OCR](https://ollama.com/library/glm-ocr): GLM-OCR is a multimodal OCR model for complex document understanding, built on the GLM-V encoder–decoder architecture.

### Improvements to `ollama launch`
* `ollama launch` can now be provided arguments, for example `ollama launch claude -- --resume`
* `ollama launch` will now work run subagents when using `ollama launch claude`
* Ollama will now set context limits for a set of models when using `ollama launch opencode`

### What's Changed
* Sub-agent support for `ollama launch` for planning, deep research, and similar tasks
* `ollama signin` will now open a browser window to make signing in easier
* Ollama will now default to the following context lengths based on VRAM:
  * < 24 GiB VRAM: 4,096 context
  * 24-48 GiB VRAM: 32,768 context
  * &gt;= 48 GiB VRAM: 262,144 context
* GLM-4.7-Flash support on Ollama's experimental MLX engine
* `ollama signin` will now open the browser to the connect page
* Fixed off by one error when using `num_predict` in the API
* Fixed issue where tokens from a previous sequence would be returned when hitting `num_predict`

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.15.4...v0.15.5

## v0.15.6 (published 2026-02-07)

Release page: https://github.com/ollama/ollama/releases/tag/v0.15.6

### What's Changed
* Fixed context limits when running `ollama launch droid`
* `ollama launch` will now download missing models instead of erroring
* Fixed bug where `ollama launch claude` would cause context compaction when providing images

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.15.5...v0.15.6

## v0.16.0 (published 2026-02-12)

Release page: https://github.com/ollama/ollama/releases/tag/v0.16.0

### New models
* [GLM-5](https://ollama.com/library/glm-5): A strong reasoning and agentic model from Z.ai with 744B total parameters (40B active), built for complex systems engineering and long-horizon tasks.
* [MiniMax-M2.5](https://ollama.com/library/minimax-m2.5): a new state-of-the-art large language model designed for real-world productivity and coding tasks.

### New `ollama`

The new `ollama` command makes it easy to launch your favorite apps with models using Ollama

<img width="1504" height="1114" alt="Ollama screenshot 2026-02-12 at 04 48 55@2x" src="https://github.com/user-attachments/assets/d693134d-5e80-471e-9d2d-5e1e26381beb" />

### What's Changed
* Launch Pi with `ollama launch pi`
* Improvements to Ollama's MLX runner to support GLM-4.7-Flash
* Ctrl+G will now allow for editing text prompts in a text editor when running a model

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.15.6...v0.16.0

## v0.16.1 (published 2026-02-12)

Release page: https://github.com/ollama/ollama/releases/tag/v0.16.1

### What's Changed
* Installing Ollama via the `curl` install script on macOS will now only prompt for your password if its required
* Installing Ollama via the `iem` install script in Windows will now show progress
* Image generation models will now respect the `OLLAMA_LOAD_TIMEOUT` variable

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.16.0...v0.16.1

## v0.16.2 (published 2026-02-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.16.2

### What's Changed
* `ollama launch claude` now supports searching the web when using `:cloud` models
* Fixed rendering issue when running `ollama` in PowerShell
* New setting in Ollama's app makes it easier to disable cloud models for sensitive and private tasks where data cannot leave your computer. For Linux or when running `ollama serve` manually, set `OLLAMA_NO_CLOUD=1`.
* Fixed issue where experimental image generation models would not run in 0.16.0 and 0.16.1

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.16.1...v0.16.2-rc0

## v0.16.3 (published 2026-02-19)

Release page: https://github.com/ollama/ollama/releases/tag/v0.16.3

### What's Changed
*  New `ollama launch cline` added for the Cline CLI
* `ollama launch <integration>` will now always show the model picker
* Added Gemma 3, Llama and Qwen 3 architectures to MLX runner

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.16.2...v0.16.3
