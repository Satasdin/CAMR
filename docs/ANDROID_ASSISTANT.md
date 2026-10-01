# Pitch: CAMR on Android, a personal assistant that gets smarter the more it knows you

> **A phone assistant whose model never changes, but whose knowledge grows with
> you, privately, on the device. It answers what it knows in about a second,
> says when it doesn't know, and asks the cloud only when it has to.**

This document is the application case for the research. It says what the
measured results already support, what an Android build needs, and what still
has to be tested on a phone. Numbers marked *measured* come from
[`FINDINGS.md`](FINDINGS.md) (CPU laptop-class machine, real models, real
benchmarks). Nothing in this document was measured on a phone yet; §6 is the plan for doing that.

---

## 1. The problem

| Today's options | Weakness |
|---|---|
| Cloud assistants (Kimi, GPT, Gemini, Claude) | They know the world but not *you*. Every personal question leaves the phone. Answers take 7–19 s *(measured, Kimi K3)* and cost per call. |
| On-device small models (Gemini Nano, Qwen, Llama, Gemma 1–4B) | Fast and private, but weak on facts: 7–23% on long-tail questions *(measured)*. They make answers up. |
| Fine-tuning the small model on the user's data | Needs a GPU, retrains on every change, can forget, and can't show where an answer came from. |

## 2. The idea: freeze the model, grow the memory

CAMR keeps the model's weights fixed and puts knowledge in a small external
memory (one SQLite file). Every note, message, document or fact the user saves
becomes retrievable evidence. Accuracy grows with what the memory holds, not
with retraining.

**What the research already shows (measured):**

| Claim | Evidence |
|---|---|
| Accuracy grows as knowledge is added, with frozen weights | 0.5B model on long-tail facts: 6.7% → 16.7% → 33.3% → **66.7%** as memory went 0 → 25% → 50% → 100% (F2) |
| A small model with memory matches or beats the cloud on facts | From 1.5B, small model + CAMR scored **73–80%** vs Kimi K3's 66.7% on PopQA (F10) |
| It is much faster than the cloud | 0.5B + CAMR answered in **1.5 s** vs Kimi K3's 7.7 s on the same questions (F9) |
| The engine itself is cheap | Retrieval took **29 ms** (embed 21.5 ms, search 6.2 ms) on 4 CPU cores (F12); engine and model together peaked at about 2.7 GB of RAM (F8) |
| It knows when it doesn't know | Gating abstains when no note is relevant; the assistant demo admitted 0 notes for an off-topic question ([`SETUP.md`](SETUP.md) §4) |
| It learns when to ask the cloud | The learned router plus the grounding cascade reached **65.3%** vs always-Kimi's 63.9%, while **71%** of questions never left the device, with 4.0× lower mean latency (F11b) |
| Personal recall works end to end | Demo: "When is my dentist appointment?" gave "next Monday" (invented) without memory and "Thursday 9 October at 14:30" with it ([`SETUP.md`](SETUP.md) §4) |

**What it does not solve (measured):** maths and multi-step reasoning. Memory
did not help the 0.5B model on GSM8K (33% → 17%). The residual gap on
reasoning stays at 83 points (F8). The assistant must route those questions to
a stronger model, and the learned router already does this (12 of 12 maths
questions sent to the cloud, all answered correctly, F11).

## 3. Product: "grows with you"

```
 Day 1        Week 2                     Month 6
 ───────────  ─────────────────────────  ─────────────────────────────────
 empty memory notes, chats, calendar,    thousands of notes; most personal
 → mostly     receipts saved → personal  and long-tail questions answered
   cloud        questions answered on      on-device in ~1 s; cloud only
                device                     for reasoning-heavy questions
```

| Feature | How CAMR provides it |
|---|---|
| **Remember this** (share sheet, voice, screenshot) | Write path: screen → embed → store, with the source kept (provenance) |
| **Ask anything** | Read path: retrieve → gate → pack ≤ 128–512 tokens → small model |
| **"Where did you get that?"** | Every answer shows the notes it used (Query Trace, in miniature) |
| **"I don't know" instead of a guess** | Gating abstains; the grounding check flags answers not supported by the notes |
| **Escalate with consent** | The router picks the cloud only for questions it predicts it will get wrong. The user approves the call, and only the question (no notes) is sent unless the user allows more |
| **Growth meter** | Share of questions answered on-device this week, from the router's own log |
| **Forget** | Delete a note or a source; it is gone from the single file, with no retraining |

## 4. Android architecture

```
┌────────────────────────── Android app (Kotlin) ───────────────────────────┐
│  UI: chat · "remember" share target · memory browser · settings           │
│                                                                           │
│  CAMR engine (ported)                                                     │
│   write path:  Screener ─▶ Embedder ─▶ Store                              │
│   read path:   Embedder ─▶ kNN ─▶ Gate ─▶ Bridge ─▶ Budgeter ─▶ Prompt     │
│   policy:      Router (11 features, ridge) ─▶ Grounding cascade           │
│                                                                           │
│  Embedder: EmbeddingGemma-300M or BGE-small, on LiteRT / ONNX Runtime     │
│  Store:    SQLite + sqlite-vec (one file in app-private storage)          │
│  LLM:      LiteRT-LM (Gemma) │ llama.cpp (GGUF: Qwen2.5-1.5B, Llama-3.2-3B)│
│            │ ML Kit GenAI Prompt API (Gemini Nano, where available)       │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ only on escalation, with consent
                                   ▼
                      Cloud model (OpenAI-compatible API, e.g. Kimi)
```

| Layer | Choice | Why |
|---|---|---|
| Local LLM runtime | [LiteRT-LM](https://developers.googleblog.com/on-device-genai-in-chrome-chromebook-plus-and-pixel-watch-with-litert-lm/) for Gemma models, or llama.cpp for GGUF models | Google recommends LiteRT-LM because the [MediaPipe LLM Inference API](https://developers.google.com/edge/mediapipe/solutions/genai/llm_inference/android) is in maintenance-only mode. llama.cpp runs the exact Qwen and Llama models benchmarked here. |
| System model (optional) | [ML Kit GenAI Prompt API](https://android-developers.googleblog.com/2025/10/ml-kit-genai-prompt-api-alpha-release.html) (Gemini Nano) | No model download on supported devices. CAMR supplies the knowledge Nano lacks. |
| Embedder | [EmbeddingGemma](https://developers.google.com/edge/mediapipe/solutions/genai/rag/android) (308M, under 200 MB quantised, 100+ languages) or BGE-small (the one measured here) | Multilingual matters for users who mix languages (e.g. Swahili/English). Its Matryoshka embeddings can be truncated to 256 dimensions to save storage. |
| Store | SQLite + sqlite-vec, one file | The same design as the research engine. Exact kNN is fast at personal scale (tens of thousands of notes); the 24,475-note store searched in about 6 ms on CPU (F1, F12). |
| Policy | The 11-feature router and the grounding cascade from `camr/learn/bandit.py` | Small linear models (a few hundred numbers) that can be updated on-device from the user's own feedback (thumbs up/down = reward). This is the "learns over runs" loop. |

**Model choice by device, from the measured size sweep (F10):**

| Device RAM | Model | Measured with CAMR (CPU) |
|---|---|---|
| 4–6 GB | qwen2.5:0.5b or gemma3:1b | Facts 66.7% (= Kimi K3); multi-hop 30–40% |
| 6–8 GB | qwen2.5:1.5b | Facts **80.0%** (> Kimi K3); multi-hop 50.0% |
| 8–12 GB | llama3.2:3b or phi4-mini:3.8b | Facts 73–80%; multi-hop **56.7%** (llama3.2:3b, > Kimi K3); phi4-mini with exemplar memory scored **91.7%** on GSM8K |

The machine B and D results (7–14B models) will show whether larger local models
are worth the RAM on high-end phones. They will be added to F10.

## 5. Privacy and safety by design

- **Personal data stays on the phone.** The local runner refuses any host but
  loopback. Escalation is opt-in and sends the question, not the notes, unless
  the user allows it.
- **Single-file memory.** It is easy to export, back up (encrypted) and delete. "Forget" is a SQL delete, with no retraining.
- **Poisoned or injected notes.** The screener rejects degenerate, duplicate and
  injection-like notes at write time (FR-03). Saved web content gets the same
  check, and answers always show their sources.
- **No silent invention.** Abstention and the grounding check make "I don't
  know" a normal answer.

## 6. What must be tested on a phone (not yet done)

| Question | Test | Success threshold |
|---|---|---|
| Is retrieval fast on a mid-range phone? | Embed + search latency on a 6 GB Android phone, 10k notes | Retrieval ≤ 10% of answer time (NFR-02) |
| Is the RAM footprint acceptable? | Peak memory of model + embedder + store | ≤ 3 GB for the 1.5B configuration |
| Battery cost | Energy per answer, local vs cloud | Report mAh per 100 questions |
| Does it grow on *personal* data? | A 4-week diary study: users save notes and ask real questions; log on-device answer rate per week | On-device share rises week over week |
| Does on-device learning help? | Router updated from thumbs up/down vs a frozen router | Higher reward on later weeks' questions |

## 7. Roadmap

1. **Port** (4–6 weeks): Kotlin wrapper over sqlite-vec; embedder on LiteRT;
   llama.cpp or LiteRT-LM runner; the router as a small linear model with JSON
   weights exported from `camr learn`.
2. **Prototype app**: chat, "remember" share target, sources view, growth meter.
3. **Phone benchmark**: rerun `camr` PopQA/HotpotQA samples on the device to compare with the CPU numbers in FINDINGS.
4. **Diary study** with consenting users (with ethics approval).
5. **Optional sync**: encrypted, user-held backup of the memory file between
   devices.

## 8. One-line pitch

**"The model stays small; what it knows grows with you."** On long-tail facts, a
1.5B on-device model with a few hundred tokens of the right memory already beats
a frontier cloud model (80% vs 67%, measured). It answers in about a second,
keeps data on the device, and calls the cloud only for the questions that need
reasoning.

---

*Imagery prompt for the pitch deck:* "A dark, minimalist phone mock-up on a
near-black background. On screen, a chat bubble answers 'Thursday 9 October,
14:30', with a small source chip below it reading 'from your note · 2 Sep'.
Thin teal light lines run from a glowing memory-crystal icon into the phone.
High contrast, soft rim lighting, product-photography style."
