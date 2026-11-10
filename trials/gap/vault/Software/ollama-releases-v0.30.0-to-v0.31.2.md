---
source: https://github.com/ollama/ollama/releases
fetched: 2026-11-10
published: 2026-05-13 to 2026-07-06
title: Ollama release notes — v0.30.0 to v0.31.2 (13 releases)
---

# Ollama release notes: v0.30.0 to v0.31.2

## v0.30.0 (published 2026-05-13)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.0

Ollama 0.30 is now available, with improved compatibility and performance using [llama.cpp](https://github.com/ggml-org/llama.cpp). This augments the MLX engine on Apple Silicon, bringing support to a wider range of hardware.

This release brings support for a wider range of models, including GGUF-based models from Hugging Face and your own fine-tuned models along with faster performance on NVIDIA hardware.

### Known issues:

* `laguna-xs.2` is not yet supported on Windows/Linux.
* `llama3.2-vision` is not yet supported
* `nomic-embed-text` now converts inputs to lowercase per the model card where prior Ollama versions incorrectly preserved mixed case

## v0.30.2 (published 2026-06-03)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.2

### What's Changed

* `ollama launch` now supports Qwen Code and can guide users through installing the Cline CLI when it is missing.
* `ollama launch codex` now uses an isolated launch configuration, avoiding conflicts with a user's existing Codex settings.
* Added llama.cpp backend compatibility support for Poolside's Laguna architecture.
* The llama.cpp backend now includes cached prompt tokens in token accounting, improving usage reporting for requests with prompt cache hits.
* The llama.cpp backend now ignores SSE ping comments, improving streaming compatibility with newer backend behavior.
* The llama.cpp backend now detects load stalls from server output so failed model loads surface more reliably instead of hanging.
* Radeon 8060S integrated GPUs are now allowed by default.
* Template details are included in logs to make troubleshooting model prompts easier.
* Added Hermes Desktop configuration docs.
* Fixed a build issue in the Laguna compatibility patch, restoring Laguna support in release builds.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.0...v0.30.2

## v0.30.3 (published 2026-06-03)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.3

### New models
- [Gemma 4 12B](https://ollama.com/library/gemma4:12b): high-performance multimodal intelligence that runs directly on laptops, combining efficiency with advanced reasoning.

### What's Changed

* Added support for `gemma4:12b`.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.2...v0.30.3

## v0.30.4 (published 2026-06-03)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.4

## New models
- [Nemotron-3-Ultra](https://ollama.com/library/nemotron-3-ultra): NVIDIA Nemotron 3 Ultra is built for high-throughput reasoning and long-running agent workflows.

### What's Changed

* Fixed multimodal models not using GPU on the llama.cpp backend can now use Metal GPU offload on Apple Silicon, improving multimodal performance on supported Macs.
* `ollama create --experimental` now respects `REQUIRES` in Modelfiles for MLX-based models.
* `ollama launch codex` now cleans up old conflicting Codex profile config before launching.
* `ollama launch pi` now migrates users from the legacy Pi package to the official package and preserves the correct npm install prefix.
* Pi web search setup now updates only when a newer package is available.
* Windows cleanup now terminates the llama.cpp backend more reliably.
* Updated the llama.cpp backend.

### Known Issues
* `gemma4:12b` crashes with floating point exception

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.3...v0.30.4

## v0.30.5 (published 2026-06-04)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.5

### What's Changed

* Fixed the `gemma4:12b` floating point exception crash on x86, CUDA, Linux, and Windows systems.
* `ollama launch hermes-desktop` now launches Hermes Desktop and can skip rebuilding when a packaged desktop app is already installed.
* `ollama launch hermes` now supports native Windows installs through the Hermes PowerShell installer.
* Added Cline CLI integration docs.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.4...v0.30.5

## v0.30.6 (published 2026-06-05)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.6

## New models
- [Gemma 4 QAT weights](https://ollama.com/library/gemma4): the Gemma 4 family is now optimized with Quantization-Aware Training (QAT) to dramatically reduce memory requirements and maximize on-device performance. Look for the tags ending in `-qat`:
  - `gemma4:e2b-it-qat`
  - `gemma4:e4b-it-qat`
  - `gemma4:12b-it-qat`
  - `gemma4:26b-a4b-it-qat`
  - `gemma4:31b-it-qat`

### What's Changed
* `ollama launch omp` now integrates with [Oh My Pi](https://omp.sh), an AI coding agent with IDE integration
* MLX embedding layers now use NVFP4 global scale for improved quantization on Apple Silicon

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.5...v0.30.6

## v0.30.7 (published 2026-06-07)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.7

Ollama Launch now supports Hermes Desktop, a native desktop interface for the Hermes agent. Run it alongside your Hermes agent to get a visual interface for managing conversations, integrations, and messaging apps.

```
ollama launch hermes-desktop
```
<img width="2556" height="1716" alt="image" src="https://github.com/user-attachments/assets/3b2292d8-9f94-4d32-9023-85772e6ab3f8" />

What's Changed

- Hermes Desktop is now available via `ollama launch hermes-desktop` with native Windows configuration path support
- OpenAI-compatible API models list now aligns with available model tags
- Added documentation describing the llama.cpp update process
- Updated Zod schema examples to use the native toJSONSchema helper

Full Changelog: https://github.com/ollama/ollama/compare/v0.30.6...v0.30.7

## v0.30.8 (published 2026-06-12)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.8

### What's Changed
* Fixed `ollama launch` selecting the wrong provider in some cases
* Improved prompt caching by decoupling it from context shift for better KV cache reuse
* More stable MLX inference with hardened linear and embedding layers
* MLX runner now creates snapshots during prompt processing and speculative decoding for improved reliability
* Improved recurrent model support with per-boundary states from the gated-delta kernels

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.7...v0.30.8

## v0.30.9 (published 2026-06-15)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.9

### What's Changed
* Support for Cohere2Moe architecture
* Fixed LFM2 parser/render for cases where thinking was not emitted
* Fixed issue where `ollama launch claude` and other coding agent or assistant use cases would only output one token
* Ollama will now return an error if a single message is larger than the current context window

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.8...v0.30.9-rc1

## v0.30.10 (published 2026-06-17)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.10

### What's Changed

* Command A and North family models now run on Apple Silicon with the MLX engine
* Updated the underlying llama.cpp engine to build 9672
* Fixed build artifacts for MLX

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.9...v0.30.10

## v0.30.11 (published 2026-06-25)

Release page: https://github.com/ollama/ollama/releases/tag/v0.30.11

### What's Changed
* launch: add thinking capability detection to opencode by @hoyyeva in https://github.com/ollama/ollama/pull/15434
* launch: auto-install Claude Code by @hoyyeva in https://github.com/ollama/ollama/pull/16802
* launch: auto-install opencode when missing by @hoyyeva in https://github.com/ollama/ollama/pull/16806
* discover: fix inverted iGPU/dGPU Vulkan classification on Windows hybrid graphics by @Sahil170595 in https://github.com/ollama/ollama/pull/16669
* mlxrunner: unify and tune speculative decoding by @jessegross in https://github.com/ollama/ollama/pull/16791
* launch/codex: detect model drift when Codex App UI switches by @BruceMacD in https://github.com/ollama/ollama/pull/16864
* llama: add sm_86 architecture to cuda_v13_windows preset by @anishesg in https://github.com/ollama/ollama/pull/16834
* llm: size mmproj offload by projector memory by @dhiltgen in https://github.com/ollama/ollama/pull/16866
* docs: document max think level by @ParthSareen in https://github.com/ollama/ollama/pull/16877
* llm: preserve generation headroom for shifted prompts by @ParthSareen in https://github.com/ollama/ollama/pull/16856
* llama: default qwen2.5vl window attention metadata by @dhiltgen in https://github.com/ollama/ollama/pull/16868
* llm: use host Vulkan loader on Windows by @dhiltgen in https://github.com/ollama/ollama/pull/16869
* mlx: update and fix CUDA JIT packaging by @dhiltgen in https://github.com/ollama/ollama/pull/16871
* llm: fix ollama ps double-counting mmap'd weights on partial offload by @discobot in https://github.com/ollama/ollama/pull/16709
* docs: redesign docs landing and integrations overview by @hoyyeva in https://github.com/ollama/ollama/pull/16807
* server: align generate with native chat templates by @dhiltgen in https://github.com/ollama/ollama/pull/16878
* jetson: add CC 87 for CUDA v13 by @dhiltgen in https://github.com/ollama/ollama/pull/16628
* llama.cpp version update by @dhiltgen in https://github.com/ollama/ollama/pull/16548

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.10...v0.30.11-rc0

## v0.31.1 (published 2026-06-30)

Release page: https://github.com/ollama/ollama/releases/tag/v0.31.1

### Faster Gemma 4 on Apple Silicon

<img width="1037" height="485" alt="Screenshot 2026-06-30 at 5 25 29 PM" src="https://github.com/user-attachments/assets/547d5076-090f-43c4-a661-938e11abc955" />

Gemma 4 is now significantly faster in Ollama on Apple Silicon, generating tokens nearly 90% faster on average across a coding-agent benchmark by leveraging multi-token prediction (MTP). Ollama auto-tunes how many tokens to draft as it runs, so the speedup is on by default, requires no configuration, and does not change the model's output.

### What's Changed

- Tightened Gemma 4 MoE model loading in the MLX engine
- Updated the MLX engine to the latest version, including a new small-batch matmul kernel
- Updated the underlying llama.cpp engine to build 9840
- Improved Gemma 4 multi-token prediction (MTP) performance

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.30.12...v0.31.1

## v0.31.2 (published 2026-07-06)

Release page: https://github.com/ollama/ollama/releases/tag/v0.31.2

### What's Changed

* Enabled flash attention on older NVIDIA GPUs (compute capability 6.x)
* iGPU can now offload vision models with padding to fit available memory
* Fixed structured output for thinking models when thinking is disabled
* Hardened GGUF model creation
* `ollama launch` for Claude Code now disables telemetry by default
* Fixed loading models on paths with non-UTF-8 characters
* Updated the MLX and llama.cpp engines

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.31.1...v0.31.2
