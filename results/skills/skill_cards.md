# Skill cards against one merged adapter (Qwen/Qwen2.5-0.5B-Instruct, mps, bfloat16)

Problem draw seed 47 (F27's fresh draw); training seed 13; LoRA rank 16, lr 0.0003; merged adapter 6 epochs (F27's choice); cards 12 epochs, chosen on validation from [6, 12, 24] (validation: {'6': 0.6, '12': 0.9, '24': 0.9}).

| Condition | seen | held-out | reworded | derived | GSM8K (unrelated) | memory picked the right card |
|---|---|---|---|---|---|---|
| Base model | 27.5% | 20.0% | 26.7% | 7.5% | 6.7% | — |
| Memory notes | 85.0% | 55.0% | 40.0% | 22.5% | 10.0% | — |
| One merged LoRA | 87.5% | 85.0% | 45.0% | 2.5% | 3.3% | — |
| Skill card, routed by memory | 100.0% | 90.0% | 50.0% | 5.0% | 10.0% | 96.0% (mean of splits) |
| Skill card, right family given | 100.0% | 90.0% | 53.3% | 5.0% | 6.7% | — |
| Notes + skill card | 90.0% | 81.7% | 70.0% | 5.0% | 10.0% | 96.0% (mean of splits) |

Sizes: {'train': 40, 'test': 60, 'rephrased': 60, 'derived': 40, 'gsm8k': 30, 'val': 20}. Run time 1927.9 s.

## Unrelated control at size: 200 GSM8K problems (cards attached to 26)

| Condition | accuracy | 95% bootstrap interval | lost vs base | gained vs base | answers changed | exact McNemar p |
|---|---|---|---|---|---|---|
| Base model | 16.0% | 11.0-21.0% | 0 | 0 | 0 | — |
| One merged LoRA | 10.0% | 6.0-14.5% | 24 | 12 | 36 | 0.065 |
| Skill card, routed by memory | 15.5% | 10.5-20.5% | 4 | 3 | 7 | 1.000 |
