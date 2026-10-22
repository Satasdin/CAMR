# The link learns: phase2b

Reward: right +1, wrong -1.0, declined 0 (+1 when the question cannot be answered), escalating to Kimi K3 costs 0.3. Mean over 10 random half/half splits.

| Reader | policy | right | wrong (stated as fact) | declined | sent to Kimi K3 | reward |
|---|---|---|---|---|---|---|
| qwen2.5:0.5b (n=287) | link, no feedback yet | 38% | 44% | 19% | 0% | -0.06 |
| qwen2.5:0.5b (n=287) | link after 142 answers' feedback | 57% | 10% | 33% | 59% | +0.29 |
| qwen2.5:0.5b (n=287) | always keep | 38% | 44% | 19% | 0% | -0.06 |
| qwen2.5:0.5b (n=287) | always escalate | 78% | 10% | 12% | 100% | +0.38 |
| qwen2.5:0.5b (n=287) | always decline | 12% | 0% | 88% | 0% | +0.12 |
| qwen2.5:0.5b (n=287) | best possible (oracle) | 80% | 0% | 20% | 37% | +0.69 |
| qwen2.5:1.5b (n=287) | link, no feedback yet | 52% | 33% | 15% | 0% | +0.19 |
| qwen2.5:1.5b (n=287) | link after 142 answers' feedback | 60% | 11% | 29% | 55% | +0.33 |
| qwen2.5:1.5b (n=287) | always keep | 52% | 33% | 15% | 0% | +0.19 |
| qwen2.5:1.5b (n=287) | always escalate | 78% | 10% | 12% | 100% | +0.38 |
| qwen2.5:1.5b (n=287) | always decline | 12% | 0% | 88% | 0% | +0.12 |
| qwen2.5:1.5b (n=287) | best possible (oracle) | 81% | 0% | 19% | 26% | +0.73 |
| qwen2.5:3b (n=287) | link, no feedback yet | 57% | 27% | 17% | 0% | +0.30 |
| qwen2.5:3b (n=287) | link after 142 answers' feedback | 58% | 14% | 28% | 39% | +0.33 |
| qwen2.5:3b (n=287) | always keep | 57% | 27% | 17% | 0% | +0.30 |
| qwen2.5:3b (n=287) | always escalate | 78% | 10% | 12% | 100% | +0.38 |
| qwen2.5:3b (n=287) | always decline | 12% | 0% | 88% | 0% | +0.12 |
| qwen2.5:3b (n=287) | best possible (oracle) | 81% | 0% | 19% | 22% | +0.74 |

## The trade-off: the learned link at other prices for one cloud call

| Reader | cloud cost | right | wrong (stated as fact) | declined | sent to Kimi K3 |
|---|---|---|---|---|---|
| qwen2.5:0.5b | 0.1 | 74% | 10% | 16% | 90% |
| qwen2.5:0.5b | 0.3 | 57% | 10% | 33% | 59% |
| qwen2.5:0.5b | 0.5 | 45% | 11% | 45% | 39% |
| qwen2.5:0.5b | 0.8 | 25% | 7% | 68% | 8% |
| qwen2.5:0.5b | 1.2 | 18% | 6% | 76% | 0% |
| qwen2.5:1.5b | 0.1 | 70% | 10% | 21% | 80% |
| qwen2.5:1.5b | 0.3 | 60% | 11% | 29% | 55% |
| qwen2.5:1.5b | 0.5 | 51% | 11% | 38% | 35% |
| qwen2.5:1.5b | 0.8 | 37% | 12% | 51% | 8% |
| qwen2.5:1.5b | 1.2 | 32% | 11% | 58% | 0% |
| qwen2.5:3b | 0.1 | 71% | 13% | 16% | 74% |
| qwen2.5:3b | 0.3 | 58% | 14% | 28% | 39% |
| qwen2.5:3b | 0.5 | 57% | 15% | 28% | 27% |
| qwen2.5:3b | 0.8 | 41% | 13% | 46% | 8% |
| qwen2.5:3b | 1.2 | 48% | 17% | 35% | 0% |

## Learning curves (held-out reward as feedback accumulates)

- **qwen2.5:0.5b**: 0: -0.06 · 20: +0.27 · 40: +0.27 · 60: +0.29 · 80: +0.29 · 100: +0.30 · 120: +0.29 · 140: +0.30 · 142: +0.29
- **qwen2.5:1.5b**: 0: +0.19 · 20: +0.30 · 40: +0.32 · 60: +0.31 · 80: +0.33 · 100: +0.32 · 120: +0.32 · 140: +0.33 · 142: +0.33
- **qwen2.5:3b**: 0: +0.30 · 20: +0.33 · 40: +0.32 · 60: +0.32 · 80: +0.32 · 100: +0.32 · 120: +0.33 · 140: +0.32 · 142: +0.33
