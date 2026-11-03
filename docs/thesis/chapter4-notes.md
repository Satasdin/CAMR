# Chapter 4: points to check before submission

The draft describes the two repositories as they stood on 3 November 2026, about 22:00 (CAMR v2 at commit `b651b7a`; CAMR v1 on branch `thesis/updates` with uncommitted changes). Nothing outside `docs/thesis/` was changed.

## Check these

1. **Length.** The chapter is about 7,600 words: roughly 4,150 of prose and 3,450 in tables. If tables count towards the 4,500–6,500 limit, move Tables 4.2 to 4.5 (the full catalogues) to an appendix and keep a summary in the chapter.
2. **Cloud reference model.** Every measured ceiling run used Kimi K3 through Moonshot (`configs/pilot_kimi.yaml`; FINDINGS F0, F9), and the chapter says Kimi K3. However, `configs/default.yaml` still pins `claude-opus-5-5` (Anthropic backend), and DESIGN_NOTES §E and the v1 README's install section describe that model. Align these files and Chapter 3 §3.6.3.
3. **NFR-06 (retrieval ≤ 10% of answer time).** The 10% comes from FINDINGS F8 ("target ≤ 10%"). Chapters 1–3 say only "a small fraction". Check that 10% was in an earlier proposal Chapter 4. If it was not, drop the number.
4. **Requirement IDs are renumbered.** The v1 code docstrings and README cite an older catalogue (FR-01 to FR-18, NFR-01 to NFR-09, DR-01 to DR-09, IR-01 to IR-07). This mapping follows the README's TC table, so Chapter 5 and the code can be reconciled:

   | Old (v1 README) | New (this chapter) |
   |---|---|
   | FR-01 | FR-01 |
   | FR-02/03, DR-06 | FR-02, FR-03 |
   | FR-04 | FR-03 |
   | FR-05, IR-04, NFR-03 | FR-04 |
   | FR-06/07 | FR-05 |
   | FR-08 | FR-08 |
   | FR-09, IR-01 | FR-09, IR-01 |
   | FR-10, IR-02, NFR-09 | IR-02 |
   | FR-11, DR-02 | FR-10, DR-04 |
   | FR-12 | FR-12 |
   | FR-13, NFR-08 | NFR-15 |
   | FR-14, NFR-07 | FR-13 |
   | FR-15 | FR-12 |
   | FR-17, IR-06 | IR-07 |
   | NFR-04, IR-05 | IR-04, NFR-15 |
   | NFR-05 | NFR-09 |
   | NFR-06 | NFR-11 |
   | DR-03/04 | DR-02, DR-03 |
   | IR-07 | IR-03 |
   | NFR-02 | NFR-06 |

5. **The app has four tabs.** The Simulation tab arrived in commit `0c27183`, after E-24 was written. E-24 still lists three tabs and the README lists four; the chapter follows the code and uses four. Consider updating E-24.
6. **27B contender.** Commit `b651b7a` adds a 27B contender (`scripts/big27b.sh`). Its first records were still arriving while this was drafted (student life, 21:58–22:04), and it has no DECISIONS entry, so the chapter leaves it out. Add it to Table 4.1 and Figure 4.3 once it is written up.
7. **Crash window in the v2 store (Section 4.4.6).** I found this while reading `rooms.py`. `add()` appends with `O_APPEND` but takes each moment's `start` from the in-memory index. If the process dies between an append and `save()`, the reopened room carries bytes the index does not know of, and later moments get the wrong offsets. One possible fix is to truncate each room file to `tokens × token_bytes` when the memory opens. The code was not changed. Decide whether to fix it or keep it as a stated limitation.
8. **Verification gaps.**
   - No automated test covers the v2 server's host, origin and key checks, so NFR-12 is verified by inspection and demonstration only.
   - The v2 page has had no accessibility audit, so NFR-18 is verified for CAMR Personal only.
   - IR-13 lists user acceptance (U), but no user session has been run.
9. **"Peak RAM" for v2** is MLX's peak-memory counter (`mx.get_peak_memory`), not the process's RSS. The chapter says "as MLX reports it"; confirm this wording matches Chapter 6.
10. **Diagrams are not rendered.** Graphviz is not installed on this machine. To render them, run `for f in docs/thesis/diagrams/*.dot; do dot -Tpng -Gdpi=170 "$f" -o "${f%.dot}.png"; done` (the same DPI as `make_diagrams.py`). Then check each figure:
    - Figures 4.8 and 4.9 use HTML-like labels and crow's-foot arrowheads.
    - Figure 4.6 has seven lanes. Put it on a landscape page or at full width so its labels stay readable.
    - The use case actors are «actor» boxes, because Graphviz has no stick-figure shape.
11. **The guide's use case exercise (pp. 76–78) is still needed.** Figure 4.2 was drafted with AI. The guide still requires your own manual diagram, two AI-tool versions, a comparison matrix and a corrected final version.
12. **New references.** Add these to the reference list and check each entry:
    - Gansner, E. R., & North, S. C. (2000). An open graph visualization system and its applications to software engineering. *Software: Practice and Experience, 30*(11), 1203–1233.
    - Hannun, A., Digani, J., Katharopoulos, A., & Collobert, R. (2023). *MLX: Efficient and flexible machine learning on Apple silicon* [Computer software]. Apple. https://github.com/ml-explore/mlx
    - ISO/IEC 25010:2023. *Systems and software engineering: Systems and software Quality Requirements and Evaluation (SQuaRE): Product quality model.*
    - ISO/IEC/IEEE 29148:2018. *Systems and software engineering: Life cycle processes: Requirements engineering.*
    - Su, J., Ahmed, M., Lu, Y., Pan, S., Bo, W., & Liu, Y. (2024). RoFormer: Enhanced transformer with rotary position embedding. *Neurocomputing, 568*, 127063.
    - van der Maaten, L., & Hinton, G. (2008). Visualizing data using t-SNE. *Journal of Machine Learning Research, 9*, 2579–2605.
    - Yang, A., et al. (2025). Qwen3 technical report. arXiv:2505.09388.
    - Zhang, Y., et al. (2025). Qwen3 Embedding: Advancing text embedding and reranking through foundation models. arXiv:2506.05176.

    APA 7 needs first-author initials wherever two first authors share a surname. Write (A. Yang et al., 2025) and (Z. Yang et al., 2018) in text. Chapter 3 §3.5.3 still cites "Yang A., 2024" for HotpotQA; it should be Z. Yang et al. (2018), as DESIGN_NOTES §F already notes.
13. **Internal sources.** The chapter cites DECISIONS.md (E-nn), FINDINGS.md (Fnn) and DESIGN_NOTES (DN). Decide how the report cites them, for example as appendices.
14. **Plan numbers are left out on purpose.** The plan page's figures (the 5 GB RAM budget, "29,000×", "75×", "21%") are not used as thresholds, because they appear only in the plan, not in DECISIONS, FINDINGS or the proposal.

## AI-assisted drafting log

| Date | Tool and model | Prompt | Inputs read | Output kept | Iterations and corrections | Verification still needed |
|---|---|---|---|---|---|---|
| 3 Nov 2026 | Claude Code (Anthropic), model Claude Opus 5.5 (`claude-opus-5-5`), run as a sub-agent | "Draft Chapter 4: System Analysis and Design … as Markdown plus Graphviz diagram sources", with the guide's Chapter 4 requirements, the one-system-two-versions decision, the style rules and the outputs listed. The full prompt is kept in the session transcript. | Guide pp. 65–78, 155, 161; Chapters 1–3; both READMEs; DECISIONS E-01–E-25; FINDINGS; DESIGN_NOTES; APP.md; v1 `store.py`, `logger.py`, `retrieval.py`, `make_diagrams.py`; v2 engine, app, agent, ruler and tests; the plan page | `chapter4.md`, `diagrams/*.dot` (10 files), this file | Two drafts. The first, of about 9,600 words, was cut to about 7,600. Fixes made in self-review: the 4B baseline uses a different reader; NFR-18 is a v1 requirement and was not failed; the cloud model's name was checked against the configs; an unsupported self-loop was removed from Figure 4.9. | Render and read every figure; check every number against its E or F source; check every citation; complete the manual use case exercise |
