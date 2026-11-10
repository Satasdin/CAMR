---
source: https://github.com/ollama/ollama/releases
fetched: 2026-11-10
published: 2026-09-05 to 2026-09-29
title: Ollama release notes — v0.34.0 to v0.35.1 (7 releases)
---

# Ollama release notes: v0.34.0 to v0.35.1

## v0.34.0 (published 2026-09-05)

Release page: https://github.com/ollama/ollama/releases/tag/v0.34.0

### Use Ollama models in ChatGPT Desktop

Ollama models can now be used directly in ChatGPT Desktop, so you can keep your existing workflow while running open models. Setup is available from the Ollama app on MacOS.

<img width="1374" height="1300" alt="CleanShot 2026-09-08 at 11 04 07 AM@2x" src="https://github.com/user-attachments/assets/e10e299d-c11f-447d-9234-afa855824efe" />

This release also improves structured output performance on Apple Silicon, adds support for OpenAI-compatible client tool search and response compaction.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.33.3...v0.34.0

## v0.34.1 (published 2026-09-14)

Release page: https://github.com/ollama/ollama/releases/tag/v0.34.1

### What's Changed
* MLX safetensors `ollama create` no longer experimental.  GGUF model creation now requires using llama.cpp tooling for safetensor conversion and quantization.
* Improved MLX memory handling on Apple Silicon
* Runaway repeat token detection now requires 100 repeat tokens for reduced false positives (e.g. OCR)
* `/api/tags` is much faster on large model libraries (3.1 s → 294 ms cold in testing), and model capabilities are now reported consistently.
* Deprecated `typical_p`: it can no longer be set when creating new models, existing GGUF models retain support.
* MLX and llama.cpp updates

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.34.0...v0.34.1-rc1

## v0.34.2 (published 2026-09-15)

Release page: https://github.com/ollama/ollama/releases/tag/v0.34.2

### What's Changed

- Added first-run setup when running `ollama`, with options to sign in or continue locally. Setup completion is shared with the desktop app on macOS and Windows.
- Added `ollama://apps` to open the desktop app’s Apps page directly on macOS and Windows.
- Fixed excessive memory growth during long generations with MLX speculative decoding.
- Updated llama.cpp.

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.34.1...v0.34.2

## v0.34.3 (published 2026-09-19)

Release page: https://github.com/ollama/ollama/releases/tag/v0.34.3

### What's Changed

`GET /api/show` now advertises each model's thinking controls and default:

Available in the CLI with:
```
ollama show gemma4
```

```
    thinking
        levels     false, true
        default    true
```

Available in the API with:
```sh 
curl http://localhost:11434/api/show -d '{"model": "glm-5.3-flash:cloud"}'
```

```json
{
  "thinking": {
    "values": ["low", "high", "max"],
    "default": "max"
  }
}
```

Also available on ollama.com directly for cloud models.

* **Nemotron H** vision models are now supported on Apple Silicon with MLX
* Ollama's macOS app will now no longer reopen windows you've closed when activating it
* Fix for model pulls from HuggingFace

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.34.2...v0.34.3

## v0.34.4 (published 2026-09-23)

Release page: https://github.com/ollama/ollama/releases/tag/v0.34.4

### What's Changed

- Structured outputs on thinking models now apply in a single pass, making them faster and more reliable.
- Fixed intermittent "model not found" errors with a large local library
- Fixed the macOS app becoming unresponsive when checking if ChatGPT or Codex is running.
- Qwen 3.8 prompt processing is faster on Apple Silicon.
- Gemma 4 on Apple Silicon now picks the best image resolution per image, keeping more detail in high-resolution images.
- Updated llama.cpp, MLX, and XGrammar.
 

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.34.3...v0.34.4

## v0.35.0 (published 2026-09-28)

Release page: https://github.com/ollama/ollama/releases/tag/v0.35.0

### Decision models

Ollama now supports decision models through `/v1/systemone`, based on [TypeSafe’s Jev API](https://typesafe.ai).

Decision models return choices, probabilities, and scores instead of text. Use them for tasks such as ticket triage, model routing, and content classification.

Available models:
- [**Nimble**](https://ollama.com/library/nimble) from Bespoke Labs
- [**Tev1**](https://ollama.com/library/tev1) from Together AI

```sh
ollama pull nimble
```

Send context and one or more questions:

```sh
curl http://localhost:11434/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "nimble",
    "state": "Our checkout has returned 500 errors since 9am.",
    "questions": {
      "label": {
        "type": "choice",
        "instructions": "Which label fits this ticket?",
        "criteria": {
          "billing": "Payments and refunds",
          "bug": "Software errors",
          "account": "Login and account access"
        }
      }
    }
  }'
```

Example response:

```json
{
  "model": "nimble",
  "answers": {
    "label": {
      "type": "choice",
      "choice": "bug",
      "probabilities": {
        "billing": 0.0125,
        "bug": 0.9781,
        "account": 0.0093
      },
      "confidence": 0.8906
    }
  },
  "usage": {
    "input_tokens": 174,
    "output_tokens": 1
  }
}
```

The API supports three question types:
- `choice`: Select an option and return probabilities for each.
- `noul`: Return the probability that a condition is true.
- `score`: Return a score across an ordered set of criteria

### What's Changed

- Settings now opens without waiting for model discovery.
- Fixed the macOS update menu and icon not reflecting an available update at startup.
- Fixed stalled MLX model downloads hanging indefinitely.
- Requests containing the deprecated `typical_p` parameter now log a warning instead of failing.

**Full Changelog:** https://github.com/ollama/ollama/compare/v0.34.4...v0.35.0

## v0.35.1 (published 2026-09-29)

Release page: https://github.com/ollama/ollama/releases/tag/v0.35.1

### Clef decision models

Ollama now supports [Clef](https://ollama.com/library/clef) and [Clef Flash](https://ollama.com/library/clef), Cloudflare's new open-source decision models, through `/v1/systemone`.

Clef (27B) and Clef Flash (9B) are multimodal: requests can now include images alongside the text state, shared by all questions and scored jointly with it.

```sh
curl http://localhost:11434/v1/systemone -d '{
  "model": "clef-flash",
  "state": "The user took this screenshot.",
  "images": ["<base64-encoded image>"],
  "questions": {
    "has_ollama": {"type": "noul", "instructions": "Does this image contain Ollama?"}
  }
}'
```

```
{
  "model": "clef-flash",
  "answers": {
    "has_ollama": {
      "type": "noul",
      "noul": 0.958
    }
  },
  "usage": {
    "input_tokens": 548,
    "output_tokens": 0
  }
}
```
### What's Changed
* Models using web search can now perform up to ten searches per response, up from three
* Modelfiles now support `CAPABILITY` declarations, so model creators can explicitly declare what a model can do. Declarations are preserved when creating from GGUF or safetensors, through model inheritance, and on Modelfile export
* `ollama show` and the model list now report only `decision` as the capability for decision models, so clients no longer offer them for general chat, tools, or thinking
* Updated llama.cpp and the MLX engine

**Full Changelog**: https://github.com/ollama/ollama/compare/v0.35.0...v0.35.1
