---
source: https://github.com/ollama/ollama/releases
fetched: 2026-11-10
published: 2026-09-25 to 2026-11-09
title: Ollama release notes — v0.40.0 to v0.40.16 (17 releases)
---

# Ollama release notes: v0.40.0 to v0.40.16

## v0.40.0 (published 2026-09-25)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.0

### What's Changed

**Models run on MLX on Apple Silicon by default**

In this release, on Apple Silicon devices, model architectures supported by the MLX runtime will automatically run on MLX.

```
ollama pull qwen3.8
ollama run qwen3.8
```

Additional models include [gemma4](https://ollama.com/library/gemma4), [qwen3.6](https://ollama.com/library/qwen3.6) and [qwen3.5](https://ollama.com/library/qwen3.5)

Decision models are now available on MLX as well: [Nimble](https://ollama.com/library/nimble) [tev1](https://ollama.com/library/tev1)  [clef](https://ollama.com/library/clef) [clef-flash](https://ollama.com/library/clef-flash) 

MLX now has support for an embedding model: [embeddinggemma-2](https://ollama.com/library/embeddinggemma-2)

We will continue testing and enabling additional models.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.35.1...v0.40.0

## v0.40.1 (published 2026-10-07)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.1

### What's Changed
* server: proxy cloud usage and balance APIs by @drifkin in https://github.com/ollama/ollama/pull/18829
* llama: fix clef head reads past 2GiB on windows by @Gigrise in https://github.com/ollama/ollama/pull/18777
* cmd: remove account step from CLI onboarding by @hoyyeva in https://github.com/ollama/ollama/pull/18826
* manifest: avoid symlinks on Windows by @dhiltgen in https://github.com/ollama/ollama/pull/18852
* docs: fix 6 dead links in README community integrations list by @aniketkrs in https://github.com/ollama/ollama/pull/18814
* docs: fix broken download links in app README by @chenlichao in https://github.com/ollama/ollama/pull/18233
* mlx: drop carried metal residency patch now that it is upstream by @dhiltgen in https://github.com/ollama/ollama/pull/18854

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.0...v0.40.1-rc0

## v0.40.2 (published 2026-10-08)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.2

### Model upgrades

Models downloaded with earlier versions of Ollama are upgraded in the background the first time you run them, for better performance and compatibility when running on llama.cpp.

To make downgrading safe, Ollama keeps the original copy as a backup, so upgraded models are temporarily kept on disk. A future release will remove these backups automatically.

To remove backed up models now (requires `jq`):

```shell
curl -s localhost:11434/api/tags | jq -r '.models[].name' | while read -r m; do
  curl -s localhost:11434/api/show -d "{\"model\":\"$m\"}" | jq -r \
    'select(any(.manifests[]?; .runner == "llamacpp")) | .manifests[] | select(.runner == "ggml") | .digest'
done | sort -u | xargs -n1 ollama rm
```

This only deletes the backups. If you later downgrade to a version older than 0.40, you'll need to re-pull those models.

**Other changes**
* `ollama list` no longer shows duplicate entries for upgraded models by @dhiltgen in https://github.com/ollama/ollama/pull/18874
* `ollama launch claude` uses the model's full context length by @jberg5 in https://github.com/ollama/ollama/pull/18855
* README: add oxi to community integrations by @maziluiosif in https://github.com/ollama/ollama/pull/18739

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.1...v0.40.2-rc0

## v0.40.3 (published 2026-10-11)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.3

### What's Changed
* `ollama launch claude` no longer shows a warning about Claude connectors by @hoyyeva in https://github.com/ollama/ollama/pull/18878
* `ollama launch codex` no longer warns about service tiers by @hoyyeva in https://github.com/ollama/ollama/pull/18879
* Paused background model upgrade for embedding and other request performance, by @jmorganca in https://github.com/ollama/ollama/pull/18908

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.2...v0.40.3

## v0.40.4 (published 2026-10-12)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.4

### Decision models in the CLI
Decision models can now be used directly from the terminal with `ollama run` — ask yes/no questions, classify text into labels, or score against a rubric:
`ollama run nimble --ask "Is a refund being requested?" < ticket.txt`

 ## What's Changed
  * Kev decision models are now supported by the MLX runner on Apple silicon
  * `ollama launch` can now be used with usage credits without upgrading to a paid plan
  * `ollama launch codex` now includes locally installed Ollama models in its model picker. Use `/model` within the Codex CLI to swap models.
  * Improved inference performance by reusing verified manifests and already loaded models
  * Added support for multimodal embeddings through llama-server
  * Fixed loading multimodal embedding models with small context windows
  * Improved Gemma 4 prefill performance on NVIDIA GPUs with the MLX runner
  * MLX runner now clips long Laya states instead of rejecting them
  * Improved speculative decoding reliability in the MLX runner, including recurrent state handling after rollback
   * Updated llama.cpp with native decision model support
  * Updated README and documentation with clearer privacy and cloud-services wording

  
  **Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.3...v0.40.4

## v0.40.5 (published 2026-10-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.5

### NVIDIA Nemotron 3.5 Super

[NVIDIA Nemotron 3.5 Super](https://ollama.com/library/nemotron-3.5-super) is a vision-language model for coding, reasoning, tool use, and document understanding. It pairs a 120B-parameter hybrid Mamba-2/Transformer mixture-of-experts backbone (12B active per token) with a C-RADIO vision encoder, and supports tool calling, an on/off thinking mode, and context up to 1M tokens.

```
ollama run nemotron-3.5-super
```

A compact sibling, [Nemotron 3.5 Bolt](https://ollama.com/library/nemotron-3.5-bolt), distills Super down to 74B parameters (9B active) tuned to fit a 24 GB NVIDIA GPU for everyday agentic tasks, with speculative decoding via its included drafter.

### What's Changed
* Decision models are now available on cloud — use `clef:cloud` and `clef-flash:cloud` to run decision models through ollama.com cloud without pulling them locally
* Continuing an OpenAI-compatible Responses conversation that includes custom tool calls no longer fails with an error
* Clearer error messages when cloud access fails: sign-in problems, payment issues in the desktop app, and upstream access errors from the ChatGPT gateway now explain what went wrong
* Updated llama.cpp (adding Nemotron 3.5 support) and MLX

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.4...v0.40.5

## v0.40.6 (published 2026-10-16)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.6

### What's Changed
* win: prevent orphaned runners by @dhiltgen in https://github.com/ollama/ollama/pull/18500
* gguf: add the q2_0 tensor and file types by @jmorganca in https://github.com/ollama/ollama/pull/18967
* Launch clef in Ollama's cloud by @jberg5 in https://github.com/ollama/ollama/pull/19036
* use identifiers for --ask mode question keys by @jberg5 in https://github.com/ollama/ollama/pull/19041

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.5...v0.40.6-rc0

## v0.40.7 (published 2026-10-18)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.7

### What's Changed
* [pplx-decider](https://ollama.com/library/pplx-decider) is a 27B decision model from Perplexity, fine-tuned from
Qwen3.8-27B
* Continuing an OpenAI-compatible Responses conversation no longer fails when switching between models with and without
thinking, or when the history contains another provider's compaction items
* Fixed streaming Responses requests where client tool calls (e.g. Codex with web search) could emit before open
reasoning items, producing misordered/duplicate tool call events
* Requests routed to remote models are now cancelled on ollama.com when the client disconnects, instead of continuing
to run
* `ollama show` now reports which renderer and parser a model uses and where its chat template comes from; the API
exposes the same values in new `renderer`, `parser`, and `template_source` fields
* More draft models now work with speculative decoding: llama-server infers the draft type automatically instead of
requiring Ollama to identify it
* `ollama launch claude` now clamps `CLAUDE_CODE_AUTO_COMPACT_WINDOW` to Claude Code's supported range, avoiding a
"window too large" warning
* Updated llama.cpp and MLX

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.6...v0.40.7

## v0.40.8 (published 2026-10-21)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.8

<p align="center"><img width="160" alt="flint-logo" src="https://github.com/user-attachments/assets/3c1741a5-710c-4bde-8ac7-096e40b495bb" /></p>

### Recursive Flint

[Flint](https://ollama.com/library/flint) brings Recursive's coding model to Ollama. It is designed for the work coding agents do across a repository: understanding unfamiliar code, tracing bugs, implementing features, and adding tests. Reasoning, multi-turn tool use, and a 262K-token context window support longer tasks across files and tool interactions.

Flint is an Apache 2.0-licensed, 40B-parameter mixture-of-experts model with approximately 2.5B parameters active per token. In its [release evaluations](https://huggingface.co/RecursiveSI/flint#evaluation), Recursive reports 54.9% on Terminal-Bench 2.1 and 74.2% on SWE-bench Verified.

```sh
ollama run flint
```

Note: Flint is supported on MacOS.  Other GPU support will be enabled in a subsequent release.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.7...v0.40.8

## v0.40.9 (published 2026-10-22)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.9

### Flint on Linux and Windows

[Flint](https://ollama.com/library/flint) now runs on Linux and Windows as well as macOS.

### Other improvements

- Streaming OpenAI Responses and Anthropic Messages requests now report generation failures instead of ending silently after partial output.
- `ollama launch` now passes cloud models' context lengths and capabilities to coding tools, fixing incorrect context and compaction settings.
- Anthropic-compatible web search now uses the model's supported thinking setting in follow-up requests, preventing avoidable failures.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.8...v0.40.9

## v0.40.10 (published 2026-10-23)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.10

### NVIDIA Nemotron 3.5 Bolt E4B

[Nemotron 3.5 Bolt E4B](https://ollama.com/library/nemotron-3.5-bolt) is NVIDIA’s smaller, Gemma 4-based vision-language model for fast local conversations, image understanding, and tool use. It supports a 128K-token context window.

The model includes a DFlash draft for speculative decoding.

    ollama run nemotron-3.5-bolt:e4b

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.9...v0.40.10

## v0.40.11 (published 2026-10-24)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.11

### Speech

Ollama can now generate [speech](https://docs.ollama.com/capabilities/speech) on macOS. `ollama run` plays text or a chat model's reply aloud as the audio is generated, and apps can stream audio through the OpenAI-compatible `/v1/audio/speech` endpoint.

```sh
ollama run phonon "Hello from Ollama."
```

### d3 decision models

[d3](https://ollama.com/library/d3) brings vLLM Semantic Router's decision models to Ollama. Give a model text, structured state, or an image, and ask it to classify, answer yes or no, or score options with probabilities. The family includes 2B, 4B, 9B, and 27B sizes.

```sh
ollama run d3 "A customer says their card was charged twice." --ask "Is this a billing issue?"
```

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.10...v0.40.11

## v0.40.12 (published 2026-10-27)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.12

### Liquid AI LFM3

[LFM3](https://ollama.com/library/lfm3) is Liquid AI's new family of small models built for local agents, tool calling, and structured output, on Liquid's new tri-hybrid architecture. The family includes:

- [lfm3](https://ollama.com/library/lfm3): a 1.7B text model with a 256K-token context window
- [lfm3-vl](https://ollama.com/library/lfm3-vl): adds image understanding
- [lfm3-audio](https://ollama.com/library/lfm3-audio): speech recognition, translation, and text-to-speech in 18 languages
- [lfm3-omni](https://ollama.com/library/lfm3-omni): text, images, and audio in one model

```sh
ollama run lfm3
```

### d1 decision models

Liquid AI's d1 models now come in a 2B size, built on LFM3. [d1](https://ollama.com/library/d1) makes decisions about text and images, and [d1-omni](https://ollama.com/library/d1-omni) adds audio.

```sh
ollama run d1:2b "I was charged twice for order 4417." --ask "Is this a billing issue?"
```

Note: lfm3 and d1 2b are supported on Apple hardware in this release.  Support for Linux/Windows coming soon.

### What's Changed
- Faster prompt processing on Apple silicon for Gemma 4, Flint and Laguna models
- Speculative decoding now supports DFlash2 draft models on MLX
- Gemma 4 keeps more detail in small images
- `ollama launch` now works with OpenCode v2
- Fixed tool-only assistant turns from Kimi CLI
- Updated MLX and llama.cpp

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.11...v0.40.12

## v0.40.13 (published 2026-10-28)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.13

### LFM3 on Linux and Windows

Liquid AI's [LFM3](https://ollama.com/library/lfm3) models, including text-to-speech in [lfm3-audio](https://ollama.com/library/lfm3-audio) and [lfm3-omni](https://ollama.com/library/lfm3-omni), now run on Linux and Windows as well as Apple silicon.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.12...v0.40.13

## v0.40.14 (published 2026-11-03)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.14

### What's Changed
* `ollama launch claude` now applies the model's output token limit for Claude Code, so cloud models no longer run into the 128k default cap
* Cloud web search responses on `/api/chat` are now decoded correctly, including compressed responses
* OpenAI-compatible endpoints no longer override a model's packaged sampler defaults — clients that send no `temperature`/`top_p` get the model's own values instead of 1.0, matching `/api/chat`
* `/v1/responses` now preserves readable input content, including prior assistant refusals, instead of flattening it
* Ollama's app can now retry ChatGPT disconnect failures instead of leaving the connection in a broken state
* `ollama launch codex` verifies ChatGPT routing before configuring, and reports a clear error when routing is unavailable
* Faster top-k sampling on MLX for large vocabularies

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.13...v0.40.14

## v0.40.15 (published 2026-11-03)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.15

### MiMo V2.6

Xiaomi MiMo's [mimo-v2.6](https://ollama.com/library/mimo-v2.6), a 9B model built for code and agent workflows, is now supported in Ollama.

```sh
ollama run mimo-v2.6
```

### AutoTrust decision models

[AutoTrust](https://ollama.com/library/autotrust-jev) decision models read text and return choices, yes or no probabilities, and ratings for the questions you supply. The family includes 9b, 35b, and 27b-vl sizes — the 35b and 27b-vl sizes can also read images.

```sh
ollama run autotrust-jev "A customer says their card was charged twice." --ask "Is this a billing issue?"
```

Note: autotrust-jev is supported on Apple silicon in this release.

### What's Changed

 - ollama launch now supports Kimi Code CLI — the successor to kimi-cli — and offers to migrate existing kimi-cli setups
 - ollama launch now fills in Pi's model list automatically so models can be picked inside Pi, and Claude Desktop's model
   picker shows Ollama's actual model names
 - Recurrent and vision GGUF models can now serve more than one request at a time
 - Qwen3 and Qwen3.5 models using long-context (YaRN) scaling
 - Running ollama with no arguments opens the welcome launcher

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.14...v0.40.15

## v0.40.16 (published 2026-11-09)

Release page: https://github.com/ollama/ollama/releases/tag/v0.40.16

### Ripple Preview

[Ripple Preview](https://ollama.com/library/ripple-preview) from Ricursive Intelligence is a 65B dense model built for agentic coding.

```sh
ollama run ripple-preview
```

### What's Changed

- Qwen3.8 Flash Next uses about 27 GiB less memory on Apple silicon
- `ollama launch claude` always routes Claude Code to the selected model
- `ollama launch` explains when a cloud model has been retired
- `/v1/responses` respects `truncation` and no longer silently truncates by default
- `/v1/models` returns an empty list instead of `null` when no models are installed
- CUDA 13.5 support for Windows on ARM
- Updated llama.cpp

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.40.15...v0.40.16
