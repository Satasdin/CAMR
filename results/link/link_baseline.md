# The link learns: baseline

Reward: right +1, wrong -1.0, declined 0 (+1 when the question cannot be answered), escalating to Kimi K3 costs 0.3. Mean over 10 random half/half splits.

| Reader | policy | right | wrong (stated as fact) | declined | sent to Kimi K3 | reward |
|---|---|---|---|---|---|---|
| qwen2.5:0.5b (n=287) | link, no feedback yet | 37% | 50% | 14% | 0% | -0.13 |
| qwen2.5:0.5b (n=287) | link after 142 answers' feedback | 49% | 6% | 45% | 53% | +0.26 |
| qwen2.5:0.5b (n=287) | always keep | 37% | 50% | 14% | 0% | -0.13 |
| qwen2.5:0.5b (n=287) | always escalate | 73% | 11% | 16% | 100% | +0.32 |
| qwen2.5:0.5b (n=287) | always decline | 12% | 0% | 88% | 0% | +0.12 |
| qwen2.5:0.5b (n=287) | best possible (oracle) | 75% | 0% | 25% | 31% | +0.66 |
| qwen2.5:1.5b (n=287) | link, no feedback yet | 48% | 38% | 14% | 0% | +0.11 |
| qwen2.5:1.5b (n=287) | link after 142 answers' feedback | 56% | 10% | 34% | 56% | +0.30 |
| qwen2.5:1.5b (n=287) | always keep | 48% | 38% | 14% | 0% | +0.11 |
| qwen2.5:1.5b (n=287) | always escalate | 73% | 11% | 16% | 100% | +0.32 |
| qwen2.5:1.5b (n=287) | always decline | 12% | 0% | 88% | 0% | +0.12 |
| qwen2.5:1.5b (n=287) | best possible (oracle) | 76% | 0% | 24% | 23% | +0.69 |
| qwen2.5:3b (n=287) | link, no feedback yet | 55% | 30% | 15% | 0% | +0.25 |
| qwen2.5:3b (n=287) | link after 142 answers' feedback | 58% | 12% | 30% | 48% | +0.32 |
| qwen2.5:3b (n=287) | always keep | 55% | 30% | 15% | 0% | +0.25 |
| qwen2.5:3b (n=287) | always escalate | 73% | 11% | 16% | 100% | +0.32 |
| qwen2.5:3b (n=287) | always decline | 12% | 0% | 88% | 0% | +0.12 |
| qwen2.5:3b (n=287) | best possible (oracle) | 75% | 0% | 25% | 18% | +0.69 |

## The trade-off: the learned link at other prices for one cloud call

| Reader | cloud cost | right | wrong (stated as fact) | declined | sent to Kimi K3 |
|---|---|---|---|---|---|
| qwen2.5:0.5b | 0.1 | 57% | 9% | 34% | 69% |
| qwen2.5:0.5b | 0.3 | 49% | 6% | 45% | 53% |
| qwen2.5:0.5b | 0.5 | 35% | 5% | 59% | 29% |
| qwen2.5:0.5b | 0.8 | 20% | 3% | 76% | 9% |
| qwen2.5:0.5b | 1.2 | 14% | 3% | 83% | 0% |
| qwen2.5:1.5b | 0.1 | 68% | 11% | 22% | 84% |
| qwen2.5:1.5b | 0.3 | 56% | 10% | 34% | 56% |
| qwen2.5:1.5b | 0.5 | 47% | 8% | 45% | 36% |
| qwen2.5:1.5b | 0.8 | 23% | 4% | 72% | 7% |
| qwen2.5:1.5b | 1.2 | 22% | 6% | 72% | 0% |
| qwen2.5:3b | 0.1 | 66% | 11% | 23% | 72% |
| qwen2.5:3b | 0.3 | 58% | 12% | 30% | 48% |
| qwen2.5:3b | 0.5 | 53% | 11% | 36% | 30% |
| qwen2.5:3b | 0.8 | 40% | 9% | 52% | 7% |
| qwen2.5:3b | 1.2 | 39% | 12% | 49% | 0% |

## Learning curves (held-out reward as feedback accumulates)

- **qwen2.5:0.5b**: 0: -0.13 · 20: +0.20 · 40: +0.22 · 60: +0.22 · 80: +0.23 · 100: +0.25 · 120: +0.26 · 140: +0.26 · 142: +0.26
- **qwen2.5:1.5b**: 0: +0.11 · 20: +0.25 · 40: +0.25 · 60: +0.28 · 80: +0.27 · 100: +0.29 · 120: +0.29 · 140: +0.30 · 142: +0.30
- **qwen2.5:3b**: 0: +0.25 · 20: +0.27 · 40: +0.28 · 60: +0.31 · 80: +0.31 · 100: +0.32 · 120: +0.32 · 140: +0.33 · 142: +0.32
