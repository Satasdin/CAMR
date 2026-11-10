# Verified source pack for the Burrow report

Compiled and checked on 10 November 2026. Every entry below was confirmed today on the page named in its `Verified at:` line. Nothing here is taken from memory alone.

How each source was checked:

- **arXiv papers**: the arXiv record (title, authors, dates, comment field, abstract) was read through arXiv's own API for that identifier; the `Verified at:` link is the matching abstract page.
- **Published versions**: venue, volume, pages and DOI were read from the publisher's DOI record (Crossref for ACL Anthology, ACM, AAAI, MIT Press, NeurIPS and IEEE DOIs), from the PMLR or IOS Press page, or from the ACL Anthology page. Where only Semantic Scholar confirmed the venue (some ICLR and ICML papers have no DOI), the entry says so.
- **Findings** are restricted to what the abstract or the official page itself states. Numbers are the paper's own.
- **2026 sources**: instead of quoting the abstract, each one lists the arXiv submission date, version and comment field as evidence that it exists. (Abstract sentences are not copied verbatim into this file; every abstract is one click away at the link.)

Markers: **[NEW]** = not in `chapters2/7-references.md`; **[IN LIST]** = already there and re-verified; **[IN LIST, CORRECTED]** = already there, entry needs the change given in section 3.

---

## 1. Summary

### Counts

| Group | Verified | New | Already in list |
|---|---|---|---|
| 1. Small and on-device models, privacy | 11 | 9 | 2 |
| 2. Knowledge versus reasoning, long-tail knowledge | 5 | 4 | 1 |
| 3. Retrieval-augmented generation, hybrid retrieval, embeddings | 9 | 4 | 5 |
| 4. Adaptive retrieval and irrelevant context (most important) | 16 | 16 | 0 |
| 5. Context length, budgeting, compression | 6 | 6 | 0 |
| 6. Agent memory systems and their evaluation | 16 | 9 | 7 |
| 7. Graph retrieval and repository-level code retrieval | 7 | 6 | 1 |
| 8. Attribution, citation checking, groundedness | 6 | 6 | 0 |
| 9. Skills and procedural knowledge | 7 | 7 | 0 |
| 10. Protocols and local tooling | 6 | 2 | 4 |
| 11. Method, statistics, benchmarks, security | 9 | 4 | 5 |
| 12. Kenya and Africa | 5 | 4 | 1 |
| **Total** | **103** | **77** | **26** |

Of the 103, 73 are peer-reviewed (conference or journal), 21 are arXiv preprints or technical reports (one of them an industry report), and 9 are official documentation, law or policy.

### The 12 most important sources for this report

1. **Shi et al. (2023), ICML**: irrelevant sentences added to grade-school maths problems sharply lower accuracy. This is the direct precedent for the report's GSM8K finding.
2. **Mirzadeh et al. (2025), ICLR**: one extra clause that looks relevant but is not cuts accuracy by up to 65% on GSM8K-style problems. The strongest number for "irrelevant context hurts reasoning".
3. **Mallen et al. (2023), ACL**: retrieval helps on rare facts and can be skipped on popular ones; retrieving only when needed improves accuracy and lowers cost. The founding paper for gated retrieval.
4. **Yoran et al. (2024), ICLR**: retrieval can lower accuracy when the retrieved text is irrelevant, across five question-answering benchmarks. States the problem the gate solves.
5. **Cuconasu et al. (2024), SIGIR**: passages that score high in retrieval but do not contain the answer are the ones that hurt. Explains why a vector-database baseline degrades.
6. **Kandpal et al. (2023), ICML**: what a model knows tracks how often it saw it in training; closing the long tail by scale alone needs many orders of magnitude more parameters. Justifies external memory for small models.
7. **Jeong et al. (2024), NAACL**: Adaptive-RAG routes each question to no retrieval, one-step or multi-step retrieval. The closest published design to Burrow's router.
8. **Asai et al. (2024), ICLR**: Self-RAG retrieves on demand and criticises its own output, but needs a specially trained model. Burrow does the same job beside a frozen model.
9. **Joren et al. (2025), ICLR**: small models (Gemma 2, Mistral) err or abstain even when the context is sufficient; large models answer wrongly when it is not. Supports both the gate and the citation check.
10. **Gao et al. (2023), EMNLP**: even the best models lack full citation support half the time on one benchmark. Motivates checking that cited places were really shown.
11. **Narayan et al. (2025), ICML**: a small on-device model working with local data recovers 87% of a frontier cloud model's performance, 97.9% with task decomposition. The nearest published measure of "fraction of the gap closed".
12. **Hsieh et al. (2024), COLM** with **Hong et al. (2025)**: models degrade well before their stated context length, and distractors make it worse. Supports the token budget.

---

## 2. Sources by group

### Group 1. Small and on-device language models; privacy motivation

@ Lu, Z., Li, X., Cai, D., Yi, R., Liu, F., Zhang, X., Lane, N. D., & Xu, M. (2024). *Small language models: Survey, measurements, and insights*. arXiv. https://doi.org/10.48550/arXiv.2409.15790
Verified at: https://arxiv.org/abs/2409.15790 (v3, 26 Feb 2025; preprint) **[IN LIST]**
Finding: Surveys 70 open small models of 100 million to 5 billion parameters and measures their ability (commonsense, mathematics, in-context learning, long context) together with on-device latency and memory.
Use in report: 1.1 Background, 2.2 Current State. "Lu et al. (2024) measured 70 open models of up to five billion parameters and reported both what they can do and what they cost to run on a device."

@ Xu, J., Li, Z., Chen, W., Wang, Q., Gao, X., Cai, Q., & Ling, Z. (2024). *On-device language models: A comprehensive review*. arXiv. https://doi.org/10.48550/arXiv.2409.00088
Verified at: https://arxiv.org/abs/2409.00088 (v2; preprint) **[NEW]**
Finding: Reviews running language models on edge devices, giving reduced latency, data staying local and personalisation as the reasons, and covering compression, hardware acceleration and edge-cloud collaboration.
Use in report: 1.1 Background, 1.5 Justification. "Reviews of on-device models give three reasons for running a model locally: lower latency, data that stays on the device, and personalisation (Xu et al., 2024)."

@ Wang, F., Zhang, Z., Zhang, X., Wu, Z., Mo, T., Lu, Q., Wang, W., Li, R., Xu, J., Tang, X., He, Q., Ma, Y., Huang, M., & Wang, S. (2025). A comprehensive survey of small language models in the era of large language models: Techniques, enhancements, applications, collaboration with LLMs, and trustworthiness. *ACM Transactions on Intelligent Systems and Technology*, *16*(6), 1–87. https://doi.org/10.1145/3768165
Verified at: https://doi.org/10.1145/3768165 (Crossref record; preprint at https://arxiv.org/abs/2411.03350) **[NEW]**
Finding: A journal survey that defines small language models by their fit to resource-limited settings and reviews how they are built, improved and made trustworthy; it names privacy from local data handling, low latency and cost as the reasons they are preferred.
Use in report: 1.1 Background, 2.2 Current State. Replaces the weak IEEE conference surveys. "Wang et al. (2025) note that cloud models raise privacy concerns and cost, which is why small models that run locally are increasingly preferred."

@ Liu, Z., Zhao, C., Iandola, F., Lai, C., Tian, Y., Fedorov, I., Xiong, Y., Chang, E., Shi, Y., Krishnamoorthi, R., Lai, L., & Chandra, V. (2024). MobileLLM: Optimizing sub-billion parameter language models for on-device use cases. In *Proceedings of the 41st International Conference on Machine Learning* (pp. 32431–32454). PMLR. https://arxiv.org/abs/2402.14905
Verified at: https://arxiv.org/abs/2402.14905 (comment: "ICML 2024"); pages from https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.14905. The ordinal "41st" and the PMLR volume were not on a page I read; check the PMLR page before printing. **[NEW]**
Finding: Shows that architecture, not only size, decides quality below one billion parameters; the models gain 2.7 and 4.3 points over earlier 125M and 350M models and come close to a 7B model on API-calling tasks.
Use in report: 2.2 Current State. "Liu et al. (2024) showed that careful design lets models under one billion parameters approach a seven-billion-parameter model on a narrow task."

@ Gemma Team. (2025). *Gemma 3 technical report*. arXiv. https://doi.org/10.48550/arXiv.2503.19786
Verified at: https://arxiv.org/abs/2503.19786 (preprint; 216 listed authors beginning "Gemma Team") **[NEW]**
Finding: Gemma 3 spans 1 to 27 billion parameters with a context of at least 128K tokens; the 4B instruction-tuned model is reported as competitive with the previous generation's 27B model.
Use in report: 2.2 Current State (model families). "Each generation moves the same quality into a smaller model: the Gemma 3 report states that its 4B model is competitive with Gemma 2 at 27B (Gemma Team, 2025)."

@ Gemma Team. (2026). *Gemma 4 technical report*. arXiv. https://doi.org/10.48550/arXiv.2607.02770
Verified at: https://arxiv.org/abs/2607.02770 **[IN LIST]**
2026 evidence: submitted 2 July 2026, v2 dated 24 July 2026, comment "17 pages, 2 figures, technical report, updated", 323 listed authors.
Finding: Open-weight multimodal models from 2.3B to 31B parameters; the 12B model uses a unified encoder-free design, and a thinking mode produces reasoning before the answer.
Use in report: 2.2 Current State; Chapter 4/5 where Gemma 4 12B is named as the frozen model.

@ Yang, A., Li, A., Yang, B., Zhang, B., Hui, B., Zheng, B., Yu, B., Gao, C., Huang, C., Lv, C., Zheng, C., Liu, D., Zhou, F., Huang, F., Hu, F., Ge, H., Wei, H., Lin, H., Tang, J., . . . Qiu, Z. (2025). *Qwen3 technical report*. arXiv. https://doi.org/10.48550/arXiv.2505.09388
Verified at: https://arxiv.org/abs/2505.09388 (preprint; 60 authors) **[NEW]**
Finding: Qwen3 covers 0.6 to 235 billion parameters, unifies a thinking and a non-thinking mode with a thinking budget, and supports 119 languages and dialects.
Use in report: 2.2 Current State. The citable paper for the Qwen family, since Qwen3.5 has only a blog post (see section 4). "The Qwen3 report describes the family the 4B model belongs to (Yang et al., 2025); Qwen3.5 itself is documented only in a release post (Qwen Team, 2026)."

@ Belcak, P., Heinrich, G., Diao, S., Fu, Y., Dong, X., Muralidharan, S., Lin, Y. C., & Molchanov, P. (2025). *Small language models are the future of agentic AI*. arXiv. https://doi.org/10.48550/arXiv.2506.02153
Verified at: https://arxiv.org/abs/2506.02153 (v3, 22 Sep 2026; preprint, position paper) **[NEW]**
Finding: Argues that small models are powerful enough, better suited and cheaper for the repeated narrow tasks inside agent systems, and that mixed systems should call a large model only where general conversation is needed.
Use in report: 1.1 Background, 1.5 Justification. Cite as a position, not a result. "Belcak et al. (2025) argue that small models are sufficient for most calls an agent makes."

@ Narayan, A., Biderman, D., Eyuboglu, S., May, A., Linderman, S., Zou, J., & Ré, C. (2025). *Minions: Cost-efficient collaboration between on-device and cloud language models* [Paper presentation]. International Conference on Machine Learning (ICML 2025). https://doi.org/10.48550/arXiv.2502.15964
Verified at: https://arxiv.org/abs/2502.15964; ICML venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2502.15964 **[NEW]**
Finding: A small on-device model that reads local documents and chats with a cloud model cuts cloud cost 30.4 times but recovers only 87% of the cloud model's performance; with the cloud model splitting the task into small local jobs, 97.9% is recovered at 5.7 times lower cost. The local model's two weaknesses were following multi-step instructions and reasoning over long contexts.
Use in report: 1.2 Problem, 2.3 Related Work, Chapter 5 discussion. "Narayan et al. (2025) measured the same gap this project targets and closed most of it, but by sending work to the cloud; Burrow keeps everything on the device."

@ Zhang, Z., Jia, M., Lee, H.-P., Yao, B., Das, S., Lerner, A., Wang, D., & Li, T. (2024). "It's a fair game", or is it? Examining how users navigate disclosure risks and benefits when using LLM-based conversational agents. In *Proceedings of the CHI Conference on Human Factors in Computing Systems* (pp. 1–26). ACM. https://doi.org/10.1145/3613904.3642385
Verified at: https://doi.org/10.1145/3613904.3642385 (Crossref record; abstract at https://arxiv.org/abs/2309.11653) **[NEW]**
Finding: From real ChatGPT conversations and interviews with 19 users, people constantly trade privacy against usefulness and convenience, and wrong mental models limit their grasp of the risk.
Use in report: 1.2 Problem, 1.5 Justification. "Users of cloud assistants disclose sensitive material while misunderstanding where it goes (Zhang et al., 2024)."

@ Mireshghallah, N., Antoniak, M., More, Y., Choi, Y., & Farnadi, G. (2024). *Trust no bot: Discovering personal disclosures in human-LLM conversations in the wild*. arXiv. https://doi.org/10.48550/arXiv.2407.11438
Verified at: https://arxiv.org/abs/2407.11438 (preprint) **[NEW]**
Finding: In real conversations with commercial chat models, personally identifiable information appears in unexpected tasks, in 48% of translation and 16% of code-editing conversations.
Use in report: 1.5 Justification. "Personal information turns up even in routine tasks such as code editing (Mireshghallah et al., 2024), which is exactly the material a notes-and-code vault holds."

### Group 2. Knowledge versus reasoning; long-tail knowledge

@ Mallen, A., Asai, A., Zhong, V., Das, R., Khashabi, D., & Hajishirzi, H. (2023). When not to trust language models: Investigating effectiveness of parametric and non-parametric memories. In *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 9802–9822). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.546
Verified at: https://doi.org/10.18653/v1/2023.acl-long.546 (Crossref) and https://arxiv.org/abs/2212.10511 **[IN LIST]**
Finding: On PopQA (14k questions, 10 models), models struggle with less popular facts and scaling barely helps in the long tail; retrieval-augmented models largely outperform models orders of magnitude larger, while unassisted models stay competitive on popular entities. Retrieving only when necessary improves performance and reduces cost.
Use in report: 1.2 Problem, 2.2.x Key Challenges, 2.3 Related Work. "Mallen et al. (2023) showed that retrieval should be switched on by need, not by default."

@ Kandpal, N., Deng, H., Roberts, A., Wallace, E., & Raffel, C. (2023). Large language models struggle to learn long-tail knowledge. In *Proceedings of the 40th International Conference on Machine Learning* (Vol. 202, pp. 15696–15707). PMLR. https://proceedings.mlr.press/v202/kandpal23a.html
Verified at: https://proceedings.mlr.press/v202/kandpal23a.html **[NEW]**
Finding: A model's accuracy on a factual question depends on how many training documents mention it; models would need to grow by many orders of magnitude to answer rarely-supported questions well, and retrieval reduces that dependence.
Use in report: 1.2 Problem, 2.2.x. "A person's own notes are the extreme long tail: no model saw them in training, and Kandpal et al. (2023) show that size alone does not fix that."

@ Sun, K., Xu, Y. E., Zha, H., Liu, Y., & Dong, X. L. (2024). Head-to-tail: How knowledgeable are large language models (LLMs)? A.K.A. will LLMs replace knowledge graphs? In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)* (pp. 311–325). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.naacl-long.18
Verified at: https://doi.org/10.18653/v1/2024.naacl-long.18 (Crossref) and https://arxiv.org/abs/2308.10168 **[NEW]**
Finding: On an 18K-question benchmark split into head, torso and tail facts, 16 public models were far from perfect, especially on torso-to-tail entities.
Use in report: 2.2.x Key Challenges. "Factual knowledge falls off from popular to rare entities in every model tested (Sun et al., 2024)."

@ Soudani, H., Kanoulas, E., & Hasibi, F. (2024). Fine tuning vs. retrieval augmented generation for less popular knowledge. In *Proceedings of the 2024 Annual International ACM SIGIR Conference on Research and Development in Information Retrieval in the Asia Pacific Region* (pp. 12–22). ACM. https://doi.org/10.1145/3673791.3698415
Verified at: https://doi.org/10.1145/3673791.3698415 (Crossref) and https://arxiv.org/abs/2403.01432 **[NEW]**
Finding: Across twelve language models of different sizes, retrieval beat fine-tuning by a large margin on the least popular facts; fine-tuning helps small models but needs extensive resources.
Use in report: 1.2 Problem, 2.4 Gaps, 3.x design choice. "This supports leaving the model frozen and adding memory beside it, as retrieval outperformed fine-tuning for rare knowledge (Soudani et al., 2024)."

@ Joren, H., Zhang, J., Ferng, C.-S., Juan, D.-C., Taly, A., & Rashtchian, C. (2025). *Sufficient context: A new lens on retrieval augmented generation systems* [Paper presentation]. International Conference on Learning Representations (ICLR 2025). https://doi.org/10.48550/arXiv.2411.06037
Verified at: https://arxiv.org/abs/2411.06037; ICLR venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2411.06037 **[NEW]**
Finding: Separates errors caused by missing context from errors in using it. Larger models answer well when context is sufficient but give wrong answers instead of abstaining when it is not; smaller models (Mistral, Gemma 2) hallucinate or abstain often even with sufficient context.
Use in report: 2.2.x, Chapter 5 discussion. "Joren et al. (2025) found that small models misuse even sufficient context, so retrieval alone cannot close the whole gap."

### Group 3. Retrieval-augmented generation, hybrid retrieval, embeddings

@ Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W.-t., Rocktäschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. In *Advances in Neural Information Processing Systems* (Vol. 33, pp. 9459–9474). Curran Associates. https://doi.org/10.48550/arXiv.2005.11401
Verified at: https://arxiv.org/abs/2005.11401 (title, authors); NeurIPS venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2005.11401. Volume and pages were not re-checked today. **[IN LIST]**
Finding: Introduced retrieval-augmented generation, pairing a generator with a retrieved document index.
Use in report: 2.2 Current State.

@ Gao, Y., Xiong, Y., Gao, X., Jia, K., Pan, J., Bi, Y., Dai, Y., Sun, J., Wang, M., & Wang, H. (2023). *Retrieval-augmented generation for large language models: A survey*. arXiv. https://arxiv.org/abs/2312.10997
Verified at: https://arxiv.org/abs/2312.10997 (v5, 27 Mar 2024; preprint; about 4,500 citations on Semantic Scholar) **[NEW]**
Finding: The standard survey of retrieval-augmented generation, tracing its progression and its retrieval, generation and augmentation parts, and how it addresses hallucination, outdated knowledge and untraceable reasoning.
Use in report: 2.2 Current State. "Gao et al. (2023) describe the progression of retrieval-augmented generation from fixed pipelines to modular ones."

@ Fan, W., Ding, Y., Ning, L., Wang, S., Li, H., Yin, D., Chua, T.-S., & Li, Q. (2024). A survey on RAG meeting LLMs: Towards retrieval-augmented large language models. In *Proceedings of the 30th ACM SIGKDD Conference on Knowledge Discovery and Data Mining* (pp. 6491–6501). ACM. https://doi.org/10.1145/3637528.3671470
Verified at: https://doi.org/10.1145/3637528.3671470 (Crossref); long version at https://arxiv.org/abs/2405.06211 **[NEW]**
Finding: A peer-reviewed survey of retrieval-augmented large language models covering architectures, training and applications.
Use in report: 2.2 Current State. The peer-reviewed survey to cite beside Gao et al.

@ Robertson, S., & Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond. *Foundations and Trends in Information Retrieval*, *3*(4), 333–389. https://doi.org/10.1561/1500000019
Verified at: https://api.semanticscholar.org/graph/v1/paper/DOI:10.1561/1500000019 (volume 3, pages 333–389). Note: the Crossref record for this DOI shows volume 4, pages 1–174, which is a metadata error; the existing entry is right. Issue number 4 was not shown on the page read. **[IN LIST]**
Use in report: 2.2 Current State (lexical retrieval behind SQLite FTS5).

@ Cormack, G. V., Clarke, C. L. A., & Buettcher, S. (2009). Reciprocal rank fusion outperforms Condorcet and individual rank learning methods. In *Proceedings of the 32nd International ACM SIGIR Conference on Research and Development in Information Retrieval* (pp. 758–759). ACM. https://doi.org/10.1145/1571941.1572114
Verified at: https://doi.org/10.1145/1571941.1572114 (Crossref) **[IN LIST]**
Use in report: 3.x/4.x where lexical and embedding results are fused.

@ Karpukhin, V., Oğuz, B., Min, S., Lewis, P., Wu, L., Edunov, S., Chen, D., & Yih, W.-t. (2020). Dense passage retrieval for open-domain question answering. In *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)* (pp. 6769–6781). Association for Computational Linguistics. https://doi.org/10.18653/v1/2020.emnlp-main.550
Verified at: https://doi.org/10.18653/v1/2020.emnlp-main.550 (Crossref) **[IN LIST]**

@ Bruch, S., Gai, S., & Ingber, A. (2023). An analysis of fusion functions for hybrid retrieval. *ACM Transactions on Information Systems*, *42*(1), 1–35. https://doi.org/10.1145/3596512
Verified at: https://doi.org/10.1145/3596512 (Crossref) and https://arxiv.org/abs/2210.11934 **[NEW]**
Finding: Studies fusing lexical and semantic search. Reciprocal rank fusion is sensitive to its parameters, and a tuned convex combination of scores outperforms it in and out of domain with only a small training set.
Use in report: 2.2 Current State, 5.x limitations. "Burrow uses reciprocal rank fusion because it needs no training data; Bruch et al. (2023) show a tuned weighted sum can do better, which is left as future work."

@ Thakur, N., Reimers, N., Rücklé, A., Srivastava, A., & Gurevych, I. (2021). *BEIR: A heterogenous benchmark for zero-shot evaluation of information retrieval models* [Paper presentation]. Conference on Neural Information Processing Systems (NeurIPS 2021), Datasets and Benchmarks Track. https://doi.org/10.48550/arXiv.2104.08663
Verified at: https://arxiv.org/abs/2104.08663 (comment: "Accepted at NeurIPS 2021 Dataset and Benchmark Track") **[NEW]**
Finding: Evaluates 10 retrieval systems (lexical, sparse, dense, late-interaction, re-ranking) on 18 datasets to test how they generalise outside their training domain.
Use in report: 2.2 Current State. "No single retriever generalises across domains (Thakur et al., 2021), which is the case for combining lexical and dense retrieval." Read the paper's results section before stating which retriever won.

@ Zhang, Y., Li, M., Long, D., Zhang, X., Lin, H., Yang, B., Xie, P., Yang, A., Liu, D., Lin, J., Huang, F., & Zhou, J. (2025). *Qwen3 Embedding: Advancing text embedding and reranking through foundation models*. arXiv. https://doi.org/10.48550/arXiv.2506.05176
Verified at: https://arxiv.org/abs/2506.05176 (v3; preprint) **[IN LIST]**
Finding: Embedding and reranking models in 0.6B, 4B and 8B sizes built on Qwen3, reported as state of the art on multilingual, code and cross-lingual retrieval benchmarks.
Use in report: 4.x (embedding model used).

### Group 4. Adaptive or gated retrieval and robustness to irrelevant context

@ Shi, F., Chen, X., Misra, K., Scales, N., Dohan, D., Chi, E. H., Schärli, N., & Zhou, D. (2023). Large language models can be easily distracted by irrelevant context. In *Proceedings of the 40th International Conference on Machine Learning* (Vol. 202, pp. 31210–31227). PMLR. https://proceedings.mlr.press/v202/shi23a.html
Verified at: https://proceedings.mlr.press/v202/shi23a.html and https://arxiv.org/abs/2302.00093 **[NEW]**
Finding: Introduces GSM-IC, grade-school maths problems with irrelevant information added. Model performance falls dramatically when irrelevant information is included; self-consistency decoding and an instruction to ignore irrelevant information reduce the damage.
Use in report: 1.2 Problem, 2.2.x Key Challenges, Chapter 5 discussion. "The drop Burrow's ungated baseline showed on GSM8K repeats what Shi et al. (2023) observed when irrelevant sentences were added to the same kind of problem."

@ Mirzadeh, I., Alizadeh, K., Shahrokhi, H., Tuzel, O., Bengio, S., & Farajtabar, M. (2025). *GSM-Symbolic: Understanding the limitations of mathematical reasoning in large language models* [Paper presentation]. International Conference on Learning Representations (ICLR 2025). https://arxiv.org/abs/2410.05229
Verified at: https://arxiv.org/abs/2410.05229 (comment: "ICLR camera ready") **[NEW]**
Finding: On templated variants of GSM8K, all models lose accuracy when only the numbers change, and adding a single clause that seems relevant but does not affect the answer causes drops of up to 65% across state-of-the-art models.
Use in report: 2.2.x, Chapter 5. "Mirzadeh et al. (2025) report losses of up to 65% from one irrelevant clause, so retrieved text that is merely on-topic is a real hazard for a reasoning task."

@ Yang, M., Huang, E., Zhang, L., Surdeanu, M., Wang, W., & Pan, L. (2025). *How is LLM reasoning distracted by irrelevant context? An analysis using a controlled benchmark*. arXiv. https://doi.org/10.48550/arXiv.2505.18761
Verified at: https://arxiv.org/abs/2505.18761 (v2, 22 Sep 2025; preprint. Semantic Scholar lists EMNLP 2025, pp. 13329–13347; confirm on the ACL Anthology before citing the venue) **[NEW]**
Finding: GSM-DC injects controlled distractors into maths problems; models are significantly sensitive to irrelevant context, which affects both the reasoning path chosen and the arithmetic.
Use in report: Chapter 5 discussion. "Irrelevant context changes which reasoning path a model follows, not only its arithmetic (Yang et al., 2025)."

@ Yoran, O., Wolfson, T., Ram, O., & Berant, J. (2024). *Making retrieval-augmented language models robust to irrelevant context* [Paper presentation]. International Conference on Learning Representations (ICLR 2024). https://doi.org/10.48550/arXiv.2310.01558
Verified at: https://arxiv.org/abs/2310.01558; ICLR venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2310.01558 **[NEW]**
Finding: Across five open-domain question-answering benchmarks, retrieval sometimes lowers accuracy. Filtering passages with an entailment model prevents the loss but discards useful passages; fine-tuning on a mix of relevant and irrelevant contexts (1,000 examples suffice) gives robustness.
Use in report: 1.2 Problem, 2.3 Related Work, 2.4 Gaps. "Yoran et al. (2024) fix the problem by fine-tuning the model; Burrow leaves the model frozen and decides before retrieval."

@ Cuconasu, F., Trappolini, G., Siciliano, F., Filice, S., Campagnano, C., Maarek, Y., Tonellotto, N., & Silvestri, F. (2024). The power of noise: Redefining retrieval for RAG systems. In *Proceedings of the 47th International ACM SIGIR Conference on Research and Development in Information Retrieval* (pp. 719–729). ACM. https://doi.org/10.1145/3626772.3657834
Verified at: https://doi.org/10.1145/3626772.3657834 (Crossref) and https://arxiv.org/abs/2401.14887 **[NEW]**
Finding: The retriever's highest-scoring passages that do not contain the answer reduce the model's effectiveness; surprisingly, adding random documents improved accuracy by up to 35%.
Use in report: 2.2.x, Chapter 5 (why the Chroma baseline hurts). "The most harmful passages are the ones a vector search ranks highly without their holding the answer (Cuconasu et al., 2024)."

@ Wu, S., Xie, J., Chen, J., Zhu, T., Zhang, K., & Xiao, Y. (2024). *How easily do irrelevant inputs skew the responses of large language models?* [Paper presentation]. Conference on Language Modeling (COLM 2024). https://doi.org/10.48550/arXiv.2404.03302
Verified at: https://arxiv.org/abs/2404.03302 (comment: "COLM 2024") **[NEW]**
Finding: Models are most easily misled by irrelevant information that is semantically related to the question, and existing remedies have limited effect.
Use in report: 2.2.x. "Related-but-irrelevant text distracts more than unrelated text (Wu et al., 2024)."

@ Chen, J., Lin, H., Han, X., & Sun, L. (2024). Benchmarking large language models in retrieval-augmented generation. *Proceedings of the AAAI Conference on Artificial Intelligence*, *38*(16), 17754–17762. https://doi.org/10.1609/aaai.v38i16.29728
Verified at: https://doi.org/10.1609/aaai.v38i16.29728 (Crossref) and https://arxiv.org/abs/2309.01431 **[NEW]**
Finding: Tests six models on four abilities needed for retrieval-augmented generation: noise robustness, negative rejection, information integration and counterfactual robustness. Models show some noise robustness but struggle with rejecting, integrating and false information.
Use in report: 2.2.x, 3.x evaluation design. "Chen et al. (2024) name negative rejection, declining to answer when the retrieved text does not hold the answer, as a weak point; Burrow's citation check targets it."

@ Jin, B., Yoon, J., Han, J., & Arik, S. O. (2025). *Long-context LLMs meet RAG: Overcoming challenges for long inputs in RAG* [Paper presentation]. International Conference on Learning Representations (ICLR 2025). https://doi.org/10.48550/arXiv.2410.05983
Verified at: https://arxiv.org/abs/2410.05983; ICLR venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2410.05983 **[NEW]**
Finding: As the number of retrieved passages rises, output quality first improves and then declines; retrieved "hard negatives" are a key cause.
Use in report: 2.2.x, 3.x token budget. "More retrieved passages is not better: quality rises and then falls (Jin et al., 2025)."

@ Asai, A., Wu, Z., Wang, Y., Sil, A., & Hajishirzi, H. (2024). *Self-RAG: Learning to retrieve, generate, and critique through self-reflection* [Paper presentation]. International Conference on Learning Representations (ICLR 2024). https://arxiv.org/abs/2310.11511
Verified at: https://arxiv.org/abs/2310.11511; ICLR venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2310.11511 **[NEW]**
Finding: Trains one model (7B and 13B) to retrieve on demand and to judge retrieved passages and its own output with special reflection tokens; it outperforms ChatGPT and retrieval-augmented Llama2-chat on question answering, reasoning and fact verification, and improves citation accuracy.
Use in report: 2.3 Related Work (named), 2.4 Gaps. "Self-RAG needs a model trained to emit reflection tokens (Asai et al., 2024); Burrow obtains the same behaviours around an unmodified model."

@ Jeong, S., Baek, J., Cho, S., Hwang, S. J., & Park, J. C. (2024). Adaptive-RAG: Learning to adapt retrieval-augmented large language models through question complexity. In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)* (pp. 7036–7050). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.naacl-long.389
Verified at: https://doi.org/10.18653/v1/2024.naacl-long.389 (Crossref) and https://arxiv.org/abs/2403.14403 **[NEW]**
Finding: A small classifier predicts each question's complexity and routes it to no retrieval, single-step retrieval or multi-step retrieval, improving both efficiency and accuracy over fixed strategies.
Use in report: 2.3 Related Work (named). "Adaptive-RAG (Jeong et al., 2024) routes by a trained classifier; Burrow routes by rules over the question and the vault, and adds link-following as a third path."

@ Yan, S.-Q., Gu, J.-C., Zhu, Y., & Ling, Z.-H. (2024). *Corrective retrieval augmented generation*. arXiv. https://doi.org/10.48550/arXiv.2401.15884
Verified at: https://arxiv.org/abs/2401.15884 (v3, 7 Oct 2024; preprint) **[NEW]**
Finding: A lightweight evaluator scores retrieved documents and triggers different actions, including falling back to web search and filtering documents down to key information; it improves several retrieval-augmented methods on four datasets.
Use in report: 2.3 Related Work. "CRAG checks retrieved documents after retrieval (Yan et al., 2024); its fallback is web search, which a private local system cannot use."

@ Jiang, Z., Xu, F. F., Gao, L., Sun, Z., Liu, Q., Dwivedi-Yu, J., Yang, Y., Callan, J., & Neubig, G. (2023). Active retrieval augmented generation. In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing* (pp. 7969–7992). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.emnlp-main.495
Verified at: https://doi.org/10.18653/v1/2023.emnlp-main.495 (Crossref) and https://arxiv.org/abs/2305.06983 **[NEW]**
Finding: FLARE predicts the next sentence and retrieves only when that sentence contains low-confidence tokens, deciding when and what to retrieve during generation.
Use in report: 2.3 Related Work. "FLARE triggers retrieval from token confidence (Jiang et al., 2023), which Ollama does not expose for every model."

@ Wang, Y., Li, P., Sun, M., & Liu, Y. (2023). Self-knowledge guided retrieval augmentation for large language models. In *Findings of the Association for Computational Linguistics: EMNLP 2023* (pp. 10303–10315). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.findings-emnlp.691
Verified at: https://doi.org/10.18653/v1/2023.findings-emnlp.691 (Crossref) and https://arxiv.org/abs/2310.05002 **[NEW]**
Finding: Retrieved knowledge does not always help and sometimes harms the original answer; letting the model recognise what it knows and call retrieval only for new questions beats always retrieving.
Use in report: 2.2.x, 2.3. "Wang et al. (2023) reached the same conclusion for question answering: always retrieving is worse than retrieving when the model does not know."

@ Yu, W., Zhang, H., Pan, X., Cao, P., Ma, K., Li, J., Wang, H., & Yu, D. (2024). Chain-of-note: Enhancing robustness in retrieval-augmented language models. In *Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing* (pp. 14672–14685). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.emnlp-main.813
Verified at: https://doi.org/10.18653/v1/2024.emnlp-main.813 (Crossref; eight authors in the published version, six on arXiv 2311.09210) **[NEW]**
Finding: Having the model write a reading note on each retrieved document before answering gave +7.9 exact match with entirely noisy documents and +10.5 in rejection rate for out-of-scope questions.
Use in report: 2.3 Related Work. "Chain-of-Note spends extra generated tokens on judging each passage (Yu et al., 2024), a cost a laptop model can ill afford."

@ Moskvoretskii, V., Marina, M., Salnikov, M., Ivanov, N., Pletenev, S., Galimzianova, D., Krayko, N., Konovalov, V., Nikishina, I., & Panchenko, A. (2025). Adaptive retrieval without self-knowledge? Bringing uncertainty back home. In *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 6355–6384). Association for Computational Linguistics. https://doi.org/10.18653/v1/2025.acl-long.319
Verified at: https://doi.org/10.18653/v1/2025.acl-long.319 (Crossref) and https://arxiv.org/abs/2501.12835 (second author appears as "Lysyuk" on arXiv and "Marina" in the published record; use the published form) **[NEW]**
Finding: Compares 35 adaptive retrieval methods on 6 datasets with 10 metrics. Simple uncertainty estimates often beat complex adaptive pipelines on efficiency and self-knowledge with comparable answer quality.
Use in report: 2.3, 2.4 Gaps, 3.x. "A simple gate can match elaborate ones (Moskvoretskii et al., 2025), which supports Burrow's lightweight router."

@ Wang, F., Wan, X., Sun, R., Chen, J., & Arik, S. O. (2025). Astute RAG: Overcoming imperfect retrieval augmentation and knowledge conflicts for large language models. In *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 30553–30571). Association for Computational Linguistics. https://doi.org/10.18653/v1/2025.acl-long.1476
Verified at: https://doi.org/10.18653/v1/2025.acl-long.1476 (Crossref) and https://arxiv.org/abs/2410.07176 **[NEW]**
Finding: Controlled analysis under realistic conditions finds imperfect retrieval to be inevitable, common and harmful, with conflicts between what the model knows and what was retrieved as the bottleneck.
Use in report: 2.2.x. "Imperfect retrieval is the normal case, not the exception (Wang et al., 2025)."

### Group 5. Context length, budgeting, compression

@ Liu, N. F., Lin, K., Hewitt, J., Paranjape, A., Bevilacqua, M., Petroni, F., & Liang, P. (2024). Lost in the middle: How language models use long contexts. *Transactions of the Association for Computational Linguistics*, *12*, 157–173. https://doi.org/10.1162/tacl_a_00638
Verified at: https://doi.org/10.1162/tacl_a_00638 (Crossref) and https://arxiv.org/abs/2307.03172 **[NEW]**
Finding: Performance is highest when the relevant information sits at the start or end of the input and drops significantly when it is in the middle, even for models built for long context.
Use in report: 2.2.x, 3.x (ordering of what is shown). "Where a passage sits in the prompt changes whether the model uses it (Liu et al., 2024)."

@ Levy, M., Jacoby, A., & Goldberg, Y. (2024). Same task, more tokens: The impact of input length on the reasoning performance of large language models. In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 15339–15353). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.acl-long.818
Verified at: https://doi.org/10.18653/v1/2024.acl-long.818 (Crossref) and https://arxiv.org/abs/2402.14848 **[NEW]**
Finding: Padding the same reasoning question to different lengths shows a notable drop in reasoning performance at input lengths far shorter than the model's technical maximum.
Use in report: 1.2 Problem, 2.2.x, Chapter 5. "Reasoning degrades with input length alone, well inside the context limit (Levy et al., 2024), which is why Burrow fits the amount shown to a budget."

@ Hsieh, C.-P., Sun, S., Kriman, S., Acharya, S., Rekesh, D., Jia, F., Zhang, Y., & Ginsburg, B. (2024). *RULER: What's the real context size of your long-context language models?* [Paper presentation]. Conference on Language Modeling (COLM 2024). https://doi.org/10.48550/arXiv.2404.06654
Verified at: https://arxiv.org/abs/2404.06654 (comment: "COLM 2024") **[NEW]**
Finding: Of 17 long-context models tested on 13 tasks, almost all show large drops as context grows; all claim 32K tokens or more, but only half keep satisfactory performance at 32K.
Use in report: 2.2.x. "A model's advertised context length overstates what it can use: only half of 17 models held up at 32K tokens (Hsieh et al., 2024)."

@ Hong, K., Troynikov, A., & Huber, J. (2025, July 14). *Context rot: How increasing input tokens impacts LLM performance*. Chroma. https://www.trychroma.com/research/context-rot
Verified at: https://www.trychroma.com/research/context-rot (the old address research.trychroma.com/context-rot redirects here; industry technical report, not peer-reviewed) **[NEW]**
Finding: Across 18 models, reliability falls as input grows even on simple tasks; one related distractor lowers accuracy and four lower it further, with the effect growing with length.
Use in report: 2.2.x. Use as a supporting industry source beside Levy and Hsieh, and note that it comes from the vendor of the baseline database. "Chroma's own study reports the same decline and names it context rot (Hong et al., 2025)."

@ Li, Z., Li, C., Zhang, M., Mei, Q., & Bendersky, M. (2024). Retrieval augmented generation or long-context LLMs? A comprehensive study and hybrid approach. In *Proceedings of the 2024 Conference on Empirical Methods in Natural Language Processing: Industry Track* (pp. 881–893). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.emnlp-industry.66
Verified at: https://doi.org/10.18653/v1/2024.emnlp-industry.66 (Crossref) and https://arxiv.org/abs/2407.16833 **[NEW]**
Finding: With enough resources, feeding the whole long context beats retrieval on average, but retrieval is far cheaper; routing each query by the model's own judgement keeps comparable quality at much lower cost.
Use in report: 2.4 Gaps, Chapter 5. "On frontier models long context can beat retrieval (Li et al., 2024); a 4B or 12B local model has neither the window nor the speed, so selection is forced."

@ Xu, F., Shi, W., & Choi, E. (2024). *RECOMP: Improving retrieval-augmented LMs with compression and selective augmentation* [Paper presentation]. International Conference on Learning Representations (ICLR 2024). https://doi.org/10.48550/arXiv.2310.04408
Verified at: https://arxiv.org/abs/2310.04408; ICLR venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2310.04408 **[NEW]**
Finding: Compresses retrieved documents into short summaries before they reach the model, down to 6% of the original length with minimal loss; the compressor returns an empty string when the documents are irrelevant, which is selective augmentation.
Use in report: 2.3 Related Work, 3.x token budget. "RECOMP shows that showing nothing is sometimes the right output of the retrieval step (Xu et al., 2024)."

Also relevant and already in the list (DOI records re-verified on Crossref today): Jiang et al. (2023) LLMLingua, EMNLP, pp. 13358–13376; Chevalier et al. (2023), EMNLP, pp. 3829–3846.

### Group 6. Memory systems for LLM agents and their evaluation

@ Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). *MemGPT: Towards LLMs as operating systems*. arXiv. https://doi.org/10.48550/arXiv.2310.08560
Verified at: https://arxiv.org/abs/2310.08560 (v2, 12 Feb 2024; preprint) **[IN LIST]**
Finding: Manages memory tiers the way an operating system pages memory, moving data in and out of the model's limited context for document analysis and multi-session chat.
Use in report: 2.3 Related Work (named).

@ Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative agents: Interactive simulacra of human behavior. In *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology* (pp. 1–22). ACM. https://doi.org/10.1145/3586183.3606763
Verified at: https://doi.org/10.1145/3586183.3606763 (Crossref) **[IN LIST]**

@ Zhong, W., Guo, L., Gao, Q., Ye, H., & Wang, Y. (2024). MemoryBank: Enhancing large language models with long-term memory. *Proceedings of the AAAI Conference on Artificial Intelligence*, *38*(17), 19724–19731. https://doi.org/10.1609/aaai.v38i17.29946
Verified at: https://doi.org/10.1609/aaai.v38i17.29946 (Crossref) **[IN LIST]**

@ Chhikara, P., Khant, D., Aryan, S., Singh, T., & Yadav, D. (2025). Mem0: Building production-ready AI agents with scalable long-term memory. In *ECAI 2025* (Frontiers in Artificial Intelligence and Applications, Vol. 413, pp. 2993–3000). IOS Press. https://doi.org/10.3233/FAIA251160
Verified at: https://ebooks.iospress.nl/doi/10.3233/FAIA251160 **[IN LIST, CORRECTED]** (was cited as an arXiv preprint; it is now a peer-reviewed ECAI 2025 paper)
Finding: Extracts, consolidates and retrieves salient facts from conversations; on LoCoMo it reports a 26% relative improvement over OpenAI's memory on an LLM-as-judge metric, with a graph variant about 2% higher.
Use in report: 2.3 Related Work (named). "Mem0 writes memories automatically from the conversation (Chhikara et al., 2025); Burrow proposes a note and waits for consent."

@ Xu, W., Liang, Z., Mei, K., Gao, H., Tan, J., & Zhang, Y. (2025). A-Mem: Agentic memory for LLM agents. In *Advances in Neural Information Processing Systems* (Vol. 38, pp. 20004–20031). Neural Information Processing Systems Foundation. https://doi.org/10.52202/085713-0593
Verified at: https://doi.org/10.52202/085713-0593 (Crossref) and https://arxiv.org/abs/2502.12110 **[NEW]**
Finding: Organises memories as interlinked notes on Zettelkasten principles: each new memory becomes a structured note with keywords and tags, is linked to related notes, and can update older notes.
Use in report: 2.3 Related Work (named), 2.4 Gaps. "A-Mem has the model build a linked note network (Xu et al., 2025); Burrow starts from the links a person already wrote in their own vault."

@ Rasmussen, P., Paliychuk, P., Beauvais, T., Ryan, J., & Chalef, D. (2025). *Zep: A temporal knowledge graph architecture for agent memory*. arXiv. https://doi.org/10.48550/arXiv.2501.13956
Verified at: https://arxiv.org/abs/2501.13956 (preprint, written by the vendor) **[NEW]**
Finding: A time-aware knowledge-graph memory (Graphiti); reports 94.8% against MemGPT's 93.4% on Deep Memory Retrieval and up to 18.5% higher accuracy with 90% lower latency on LongMemEval.
Use in report: 2.3 Related Work. Treat the numbers as vendor-reported.

@ Gutiérrez, B. J., Shu, Y., Gu, Y., Yasunaga, M., & Su, Y. (2024). HippoRAG: Neurobiologically inspired long-term memory for large language models. In *Advances in Neural Information Processing Systems* (Vol. 37, pp. 59532–59569). Neural Information Processing Systems Foundation. https://doi.org/10.52202/079017-1902
Verified at: https://doi.org/10.52202/079017-1902 (Crossref) and https://arxiv.org/abs/2405.14831 **[IN LIST]** (pages and DOI can now be added)
Finding: Builds a knowledge graph and runs Personalized PageRank over it; up to 20% better than prior methods on multi-hop question answering, and 10 to 30 times cheaper and 6 to 13 times faster than iterative retrieval.
Use in report: 2.3 Related Work (named).

@ Gutiérrez, B. J., Shu, Y., Qi, W., Zhou, S., & Su, Y. (2025). *From RAG to memory: Non-parametric continual learning for large language models* [Paper presentation]. International Conference on Machine Learning (ICML 2025). https://doi.org/10.48550/arXiv.2502.14802
Verified at: https://arxiv.org/abs/2502.14802 (comment: "ICML 2025") **[NEW]**
Finding: HippoRAG 2. Notes that graph-augmented retrieval methods fall considerably below standard retrieval on basic factual memory, and fixes this; it gains 7% over the best embedding model on associative memory tasks.
Use in report: 2.3, 2.4 Gaps. "Structure-heavy memory can lose to plain retrieval on simple facts (Gutiérrez et al., 2025), a reason Burrow keeps full-text search as the first path."

@ Maharana, A., Lee, D.-H., Tulyakov, S., Bansal, M., Barbieri, F., & Fang, Y. (2024). Evaluating very long-term conversational memory of LLM agents. In *Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 13851–13870). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.acl-long.747
Verified at: https://doi.org/10.18653/v1/2024.acl-long.747 (Crossref) **[IN LIST]**
Finding: LoCoMo: conversations of about 300 turns and 9K tokens over up to 35 sessions; long-context models and retrieval help but stay well behind humans.

@ Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W., & Yu, D. (2025). *LongMemEval: Benchmarking chat assistants on long-term interactive memory* [Paper presentation]. International Conference on Learning Representations (ICLR 2025). https://doi.org/10.48550/arXiv.2410.10813
Verified at: https://arxiv.org/abs/2410.10813 (comment: "ICLR 2025") **[IN LIST]**
Finding: 500 questions testing five memory abilities, including knowledge updates and abstention; commercial assistants and long-context models drop 30% in accuracy across sustained interactions.

@ Hu, Y., Wang, Y., & McAuley, J. (2025). *Evaluating memory in LLM agents via incremental multi-turn interactions*. arXiv. https://doi.org/10.48550/arXiv.2507.05257
Verified at: https://arxiv.org/abs/2507.05257 (v4, 28 June 2026; Semantic Scholar lists ICLR as the venue, the arXiv record does not; cite as a preprint unless OpenReview confirms) **[NEW]**
Finding: MemoryAgentBench names four competencies for memory agents: accurate retrieval, test-time learning, long-range understanding and selective forgetting, and feeds information in incrementally across turns.
Use in report: 2.2 Current State (evaluation), 5.x limitations. "Burrow is evaluated on retrieval and attribution; test-time learning and forgetting, as defined by Hu et al. (2025), are not measured."

@ Sumers, T. R., Yao, S., Narasimhan, K., & Griffiths, T. L. (2024). Cognitive architectures for language agents. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2309.02427
Verified at: https://arxiv.org/abs/2309.02427 (comment: "v3 is TMLR camera ready version") **[NEW]**
Finding: The CoALA framework describes a language agent as modular memory (working, episodic, semantic, procedural), a structured action space and a decision loop.
Use in report: 2.2 Current State, 3.x design. "In the terms of Sumers et al. (2024), Burrow's vault is semantic memory, its decision notes episodic memory and its skills procedural memory."

@ Zhang, Z., Dai, Q., Bo, X., Ma, C., Li, R., Chen, X., Zhu, J., Dong, Z., & Wen, J.-R. (2025). A survey on the memory mechanism of large language model-based agents. *ACM Transactions on Information Systems*, *43*(6), 1–47. https://doi.org/10.1145/3748302
Verified at: https://doi.org/10.1145/3748302 (Crossref; preprint at https://arxiv.org/abs/2404.13501 with a different author order) **[NEW]**
Finding: A journal survey of what agent memory is, why it is needed, and how memory modules are designed and evaluated.
Use in report: 2.2 Current State.

@ Hu, Y., Liu, S., Yue, Y., Zhang, G., Liu, B., Zhu, F., Lin, J., Guo, H., Dou, S., Xi, Z., Jin, S., Tan, J., Yin, Y., Liu, J., Zhang, Z., Sun, Z., Zhu, Y., Sun, H., Peng, B., . . . Yan, S. (2025). *Memory in the age of AI agents*. arXiv. https://doi.org/10.48550/arXiv.2512.13564
Verified at: https://arxiv.org/abs/2512.13564 (submitted 15 Dec 2025, v2 13 Jan 2026; preprint; 47 authors) **[NEW]**
Finding: Separates agent memory from retrieval-augmented generation and context engineering, and classifies it by form (token-level, parametric, latent), function (factual, experiential, working) and dynamics (formation, evolution, retrieval).
Use in report: 2.2 Current State. "By the taxonomy of Hu et al. (2025), Burrow is token-level memory serving factual and experiential functions."

@ Huang, W.-C., Zhang, W., Liang, Y., Bei, Y., Chen, Y., Feng, T., Pan, X., Tan, Z., Wang, Y., Wei, T., Wu, S., Xu, R., Yang, L., Yang, R., Yang, W., Yeh, C.-Y., Zhang, H., Zhang, H., Zhu, S., . . . Shu, K. (2026). A survey of agent memory in the second half: Towards self-evolving and long-horizon agents. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2602.06052
Verified at: https://arxiv.org/abs/2602.06052 **[NEW]**
2026 evidence: submitted 14 January 2026, v4 dated 4 August 2026, comment "Accepted at Transactions on Machine Learning Research (TMLR) with Survey Certification", 60 authors.
Finding: Organises agent memory by substrate (inside the model or external stores), cognitive mechanism (sensory, working, episodic, semantic, procedural) and subject (user or agent), and treats portable agent skills as part of memory.
Use in report: 2.2 Current State, 2.4 Gaps. "The most recent survey treats skills as procedural memory (Huang et al., 2026), the same position Burrow takes."

@ Luo, J., Tian, Y., Cao, C., Luo, Z., Lin, H., Li, K., Kong, C., Yang, R., & Ma, J. (2026). From storage to experience: A survey on the evolution of LLM agent memory mechanisms. In *Findings of the Association for Computational Linguistics: ACL 2026* (pp. 41622–41652). Association for Computational Linguistics. https://doi.org/10.18653/v1/2026.findings-acl.2069
Verified at: https://doi.org/10.18653/v1/2026.findings-acl.2069 (Crossref) and https://arxiv.org/abs/2605.06716 **[NEW]**
2026 evidence: arXiv submission 7 May 2026, comment "Accepted by ACL 2026 Findings"; Crossref lists the Findings of ACL 2026 record with nine authors.
Finding: Describes three stages of agent memory: storage (keeping trajectories), reflection (refining them) and experience (abstracting across them).
Use in report: 2.2 Current State. "On the scale of Luo et al. (2026), Burrow sits at storage with a first step into experience through its decision notes and skills."

### Group 7. Graph and structure-aware retrieval; repository-level code retrieval

@ Edge, D., Trinh, H., Cheng, N., Bradley, J., Chao, A., Mody, A., Truitt, S., Metropolitansky, D., Ness, R. O., & Larson, J. (2024). *From local to global: A graph RAG approach to query-focused summarization*. arXiv. https://arxiv.org/abs/2404.16130
Verified at: https://arxiv.org/abs/2404.16130 (v2, 19 Feb 2025; preprint) **[NEW]**
Finding: An LLM builds an entity graph and pre-writes community summaries; for global sense-making questions over about a million tokens this beats conventional retrieval on comprehensiveness and diversity.
Use in report: 2.3 Related Work (named), 2.4 Gaps. "GraphRAG pays for its graph with many model calls at indexing time (Edge et al., 2024); Burrow reads the graph from links and imports that already exist."

@ Peng, B., Zhu, Y., Liu, Y., Bo, X., Shi, H., Hong, C., Zhang, Y., & Tang, S. (2025). Graph retrieval-augmented generation: A survey. *ACM Transactions on Information Systems*, *44*(2), 1–52. https://doi.org/10.1145/3777378
Verified at: https://doi.org/10.1145/3777378 (Crossref; online 23 Dec 2025; preprint at https://arxiv.org/abs/2408.08921) **[NEW]**
Finding: Formalises graph-based retrieval as graph indexing, graph-guided retrieval and graph-enhanced generation.
Use in report: 2.2 Current State.

@ Zhang, F., Chen, B., Zhang, Y., Keung, J., Liu, J., Zan, D., Mao, Y., Lou, J.-G., & Chen, W. (2023). RepoCoder: Repository-level code completion through iterative retrieval and generation. In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing* (pp. 2471–2484). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.emnlp-main.151
Verified at: https://doi.org/10.18653/v1/2023.emnlp-main.151 (Crossref) and https://arxiv.org/abs/2303.12570 **[NEW]**
Finding: Retrieving from the rest of the repository, then generating, then retrieving again improves on in-file completion by over 10% in all settings.
Use in report: 2.3 Related Work. "Code questions need context from other files, as RepoCoder showed (Zhang et al., 2023)."

@ Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2024). *SWE-bench: Can language models resolve real-world GitHub issues?* [Paper presentation]. International Conference on Learning Representations (ICLR 2024). https://doi.org/10.48550/arXiv.2310.06770
Verified at: https://arxiv.org/abs/2310.06770 (comment gives ICLR 2024 and the OpenReview link) **[IN LIST]**
Finding: 2,294 problems from 12 Python repositories; at publication the best model solved 1.96%.

@ Wang, Z. Z., Asai, A., Yu, X. V., Xu, F. F., Xie, Y., Neubig, G., & Fried, D. (2025). CodeRAG-Bench: Can retrieval augment code generation? In *Findings of the Association for Computational Linguistics: NAACL 2025* (pp. 3199–3214). Association for Computational Linguistics. https://doi.org/10.18653/v1/2025.findings-naacl.176
Verified at: https://doi.org/10.18653/v1/2025.findings-naacl.176 (Crossref) and https://arxiv.org/abs/2406.14497 **[NEW]**
Finding: Retrieval gives notable gains for code generation when the context is high quality, but retrievers struggle when there is little word overlap and generators fail to improve with limited context length.
Use in report: 2.2.x, Chapter 5. "For code, retrieval helps only when the right context is found and fits (Wang et al., 2025)."

@ Ouyang, S., Yu, W., Ma, K., Xiao, Z., Zhang, Z., Jia, M., Han, J., Zhang, H., & Yu, D. (2025). *RepoGraph: Enhancing AI software engineering with repository-level code graph* [Paper presentation]. International Conference on Learning Representations (ICLR 2025). https://doi.org/10.48550/arXiv.2410.14684
Verified at: https://arxiv.org/abs/2410.14684 (comment: "ICLR 2025") **[NEW]**
Finding: A plug-in repository-level code graph that raised the performance of four different systems on SWE-bench.
Use in report: 2.3 Related Work. "Following code structure, not only text similarity, improves repository tasks (Ouyang et al., 2025)."

@ Liu, X., Lan, B., Hu, Z., Liu, Y., Zhang, Z., Wang, F., Shieh, M. Q., & Zhou, W. (2025). CodexGraph: Bridging large language models and code repositories via code graph databases. In *Proceedings of the 2025 Conference of the Nations of the Americas Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)* (pp. 142–160). Association for Computational Linguistics. https://doi.org/10.18653/v1/2025.naacl-long.7
Verified at: https://doi.org/10.18653/v1/2025.naacl-long.7 (Crossref) and https://arxiv.org/abs/2408.03910 **[NEW]**
Finding: Similarity-based retrieval often has low recall on complex code tasks; letting the agent query a code graph database gives structure-aware retrieval.
Use in report: 2.3, 2.4. "CodexGraph needs a separate graph database (Liu et al., 2025); Burrow keeps links in the same SQLite file as the text index."

### Group 8. Attribution, citation checking, groundedness

@ Gao, T., Yen, H., Yu, J., & Chen, D. (2023). Enabling large language models to generate text with citations. In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing* (pp. 6465–6488). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.emnlp-main.398
Verified at: https://doi.org/10.18653/v1/2023.emnlp-main.398 (Crossref) and https://arxiv.org/abs/2305.14627 **[NEW]**
Finding: ALCE, the first benchmark for automatic citation evaluation, measuring fluency, correctness and citation quality. On ELI5 even the best models lack complete citation support 50% of the time.
Use in report: 1.2 Problem, 2.2.x, 2.3. "Gao et al. (2023) found that half of the best models' answers lacked full citation support, which is why Burrow checks every cited place."

@ Liu, N. F., Zhang, T., & Liang, P. (2023). Evaluating verifiability in generative search engines. In *Findings of the Association for Computational Linguistics: EMNLP 2023* (pp. 7001–7025). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.findings-emnlp.467
Verified at: https://doi.org/10.18653/v1/2023.findings-emnlp.467 (Crossref) and https://arxiv.org/abs/2304.09848 **[NEW]**
Finding: In four commercial generative search engines, only 51.5% of generated sentences were fully supported by their citations and only 74.5% of citations supported their sentence.
Use in report: 1.2 Problem, 1.5 Justification. "Citations in deployed systems look trustworthy and often are not: a quarter did not support the sentence they were attached to (Liu et al., 2023)."

@ Rashkin, H., Nikolaev, V., Lamm, M., Aroyo, L., Collins, M., Das, D., Petrov, S., Tomar, G. S., Turc, I., & Reitter, D. (2023). Measuring attribution in natural language generation models. *Computational Linguistics*, *49*(4), 777–840. https://doi.org/10.1162/coli_a_00486
Verified at: https://doi.org/10.1162/coli_a_00486 (Crossref) and https://arxiv.org/abs/2112.12870 **[NEW]**
Finding: Defines "Attributable to Identified Sources" (AIS), a framework for judging whether generated statements are supported by named sources.
Use in report: 2.2.x, 3.x. "Burrow's check is a narrow, mechanical form of the AIS idea (Rashkin et al., 2023): it confirms the cited place was shown, not that the claim follows from it." State this limit plainly in Chapter 5.

@ Es, S., James, J., Espinosa Anke, L., & Schockaert, S. (2024). RAGAs: Automated evaluation of retrieval augmented generation. In *Proceedings of the 18th Conference of the European Chapter of the Association for Computational Linguistics: System Demonstrations* (pp. 150–158). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.eacl-demo.16
Verified at: https://doi.org/10.18653/v1/2024.eacl-demo.16 (Crossref) and https://arxiv.org/abs/2309.15217 **[NEW]**
Finding: Reference-free metrics for retrieval pipelines covering context relevance, faithful use of context and answer quality, without human-annotated ground truth.
Use in report: 2.2 Current State (evaluation), 3.x. "RAGAs scores faithfulness with another model call (Es et al., 2024); Burrow's check is deterministic and costs no extra call."

@ Huang, L., Yu, W., Ma, W., Zhong, W., Feng, Z., Wang, H., Chen, Q., Peng, W., Feng, X., Qin, B., & Liu, T. (2025). A survey on hallucination in large language models: Principles, taxonomy, challenges, and open questions. *ACM Transactions on Information Systems*, *43*(2), 1–55. https://doi.org/10.1145/3703155
Verified at: https://doi.org/10.1145/3703155 (Crossref) and https://arxiv.org/abs/2311.05232 **[NEW]**
Finding: Taxonomy of hallucination, its causes, detection and mitigation, including the limits of retrieval-augmented models in fighting it.
Use in report: 1.1 Background, 2.2.x.

@ Ji, Z., Lee, N., Frieske, R., Yu, T., Su, D., Xu, Y., Ishii, E., Bang, Y. J., Madotto, A., & Fung, P. (2023). Survey of hallucination in natural language generation. *ACM Computing Surveys*, *55*(12), 1–38. https://doi.org/10.1145/3571730
Verified at: https://doi.org/10.1145/3571730 (Crossref; ten authors in the published record) **[NEW]**
Finding: The earlier general survey of hallucination across generation tasks, with metrics and mitigation methods.
Use in report: 1.1 Background.

### Group 9. Skills and procedural knowledge

@ Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., Chi, E. H., Le, Q. V., & Zhou, D. (2022). *Chain-of-thought prompting elicits reasoning in large language models* [Paper presentation]. Conference on Neural Information Processing Systems (NeurIPS 2022). https://doi.org/10.48550/arXiv.2201.11903
Verified at: https://arxiv.org/abs/2201.11903; NeurIPS venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2201.11903 **[NEW]**
Finding: Showing a few worked examples with intermediate steps improves arithmetic, commonsense and symbolic reasoning; with eight examples a 540B model set the state of the art on GSM8K. The abstract says the ability emerges in sufficiently large models.
Use in report: 2.3, 3.x (calculation skill), Chapter 5. "The calculation skill hands the model a written step-by-step method, following Wei et al. (2022); they note the effect is strongest in large models, so the gain on a 4B model has to be measured, not assumed."

@ Wang, G., Xie, Y., Jiang, Y., Mandlekar, A., Xiao, C., Zhu, Y., Fan, L., & Anandkumar, A. (2023). *Voyager: An open-ended embodied agent with large language models*. arXiv. https://doi.org/10.48550/arXiv.2305.16291
Verified at: https://arxiv.org/abs/2305.16291 (v2; preprint. Semantic Scholar lists Transactions on Machine Learning Research; the arXiv record does not say so) **[NEW]**
Finding: Keeps an ever-growing skill library of executable code that is stored and retrieved, without changing model weights; obtains 3.3 times more unique items than prior methods in Minecraft.
Use in report: 2.3 Related Work (named). "Voyager's skills are code the agent wrote (Wang et al., 2023); Burrow's are short written methods a person can read and edit."

@ Zhao, A., Huang, D., Xu, Q., Lin, M., Liu, Y.-J., & Huang, G. (2024). ExpeL: LLM agents are experiential learners. *Proceedings of the AAAI Conference on Artificial Intelligence*, *38*(17), 19632–19642. https://doi.org/10.1609/aaai.v38i17.29936
Verified at: https://doi.org/10.1609/aaai.v38i17.29936 (Crossref) and https://arxiv.org/abs/2308.10144 **[NEW]**
Finding: An agent gathers experience, extracts insights in natural language and recalls them at inference, improving as experience accumulates without any parameter updates.
Use in report: 2.3 Related Work. "ExpeL shows that written insights recalled at the right moment improve a frozen model (Zhao et al., 2024)."

@ Wang, Z. Z., Mao, J., Fried, D., & Neubig, G. (2025). *Agent workflow memory* [Paper presentation]. International Conference on Machine Learning (ICML 2025). https://doi.org/10.48550/arXiv.2409.07429
Verified at: https://arxiv.org/abs/2409.07429; ICML venue from https://api.semanticscholar.org/graph/v1/paper/arXiv:2409.07429 **[NEW]**
Finding: Induces reusable workflows from past tasks and supplies them selectively; relative success rises 24.6% on Mind2Web and 51.1% on WebArena.
Use in report: 2.3 Related Work. "Supplying a workflow only for the matching task type is what made the difference (Wang et al., 2025)."

@ Anthropic. (2026). *Agent Skills*. Claude Docs. Retrieved November 10, 2026, from https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
Verified at: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview (official documentation; page carries no publication date) **[NEW]**
Finding: A Skill is a folder with a `SKILL.md` file. Loading is staged ("progressive disclosure"): only the name and description are always in context (about 100 tokens per skill), the instructions load when the skill is triggered (under 5k tokens), and bundled files load only when read.
Use in report: 2.3 Related Work (named), 3.x design. "Burrow's skills follow the same staged loading so that an unused skill costs a small model almost no context (Anthropic, 2026)."

@ Li, X., Liu, Y., Chen, W., You, B., Di, Z., He, Y., Zheng, S., Choe, K. W., Sun, J., Wang, S., Tao, C., Li, B., Zhao, X., Geng, H., Wu, X., Zhou, J., Chen, X., Xing, H., Li, Y., . . . Song, D. (2026). *SkillsBench: Benchmarking how well agent skills work across diverse tasks*. arXiv. https://doi.org/10.48550/arXiv.2602.12670
Verified at: https://arxiv.org/abs/2602.12670 (preprint) **[NEW]**
2026 evidence: submitted 13 February 2026, v4 dated 14 June 2026, 78 authors, about 360 citations on Semantic Scholar.
Finding: On 87 tasks in 8 domains, curated skills raise the average pass rate from 33.9% to 50.5% across 18 model and harness configurations; focused skills of at most three modules beat larger bundles, and smaller models with skills can match larger models without them.
Use in report: 1.2 Problem, 2.3, Chapter 5. "SkillsBench reports that smaller models given skills can match larger models without them (Li et al., 2026), the same lever Burrow pulls on reasoning-bound tasks."

@ Xu, R., & Yan, Y. (2026). *Agent skills for large language models: Architecture, acquisition, security, and the path forward*. arXiv. https://doi.org/10.48550/arXiv.2602.12430
Verified at: https://arxiv.org/abs/2602.12430 (preprint) **[NEW]**
2026 evidence: submitted 12 February 2026, v4 dated 2 June 2026, comment "Accepted by Agent Skills '26 Workshop at ACM Conference on AI and Agentic Systems 2026".
Finding: Surveys agent skills (the SKILL.md format, progressive loading, their relation to MCP) and cites analyses finding that 26.1% of community-contributed skills contain vulnerabilities.
Use in report: 2.2 Current State, 5.x security limits. "Skills are instructions the model obeys, so skills from strangers are a risk: about a quarter of community skills were found vulnerable (Xu & Yan, 2026)."

### Group 10. Protocols and local tooling

@ Model Context Protocol. (2026). *Specification*. Retrieved November 10, 2026, from https://modelcontextprotocol.io/specification/latest
Verified at: https://modelcontextprotocol.io/specification/latest (official; the page points to schema revision 2026-07-28) **[NEW]** (the list has only the introductory page)
Finding: An open protocol over JSON-RPC 2.0 between hosts, clients and servers. Servers offer resources, prompts and tools. The specification requires explicit user consent before user data is exposed to a server or a tool is invoked.
Use in report: 2.2 Current State, 3.x/4.x. "Burrow exposes its memory as MCP tools; the specification requires user consent for data access (Model Context Protocol, 2026), which matches Burrow's consent step for memory writing."

@ Hou, X., Zhao, Y., Wang, S., & Wang, H. (2026). Model Context Protocol (MCP): Landscape, security threats, and future research directions. *ACM Transactions on Software Engineering and Methodology*, *35*(10), 1–37. https://doi.org/10.1145/3796519
Verified at: https://doi.org/10.1145/3796519 (Crossref; issue dated 16 Sep 2026; preprint at https://arxiv.org/abs/2503.23278) **[NEW]**
2026 evidence: Crossref lists the article in volume 35, issue 10 of the journal; the arXiv preprint dates from 30 March 2025 (v3, 7 Oct 2025).
Finding: Defines the life cycle of an MCP server in four phases and 16 activities, and a threat taxonomy of 16 scenarios across four attacker types, with case studies.
Use in report: 2.2 Current State, 5.x security. The peer-reviewed source for MCP. "Hou et al. (2026) catalogue 16 threat scenarios for MCP servers."

@ Ollama. (2026). *Ollama* [Computer software]. https://ollama.com
Verified at: https://docs.ollama.com/ (official documentation live; page title "Ollama documentation") **[IN LIST]**

@ Chroma. (2026). *Architecture overview*. Chroma Docs. https://docs.trychroma.com/docs/overview/architecture
Verified at: https://docs.trychroma.com/docs/overview/introduction (documentation site live; the architecture page itself was not opened today) **[IN LIST]**

@ LangChain. (2026). *LangChain* [Computer software]. https://github.com/langchain-ai/langchain
Verified at: https://docs.langchain.com/oss/python/langchain/overview (official documentation live) **[IN LIST]**

@ SQLite. (2026, October 9). *SQLite FTS5 extension*. https://www.sqlite.org/fts5.html
Verified at: https://www.sqlite.org/fts5.html (page title "SQLite FTS5 Extension"; the date in the entry was not re-checked) **[IN LIST]**

### Group 11. Method, statistics, benchmarks, security

@ Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design science in information systems research. *MIS Quarterly*, *28*(1), 75–105. https://doi.org/10.2307/25148625
Verified at: https://doi.org/10.2307/25148625 (Crossref lists pages 75–106; 75–105 is the range normally cited, so the entry is left as it is) **[IN LIST]**
Use in report: 3.2 Research Paradigm.

@ Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S. (2007). A design science research methodology for information systems research. *Journal of Management Information Systems*, *24*(3), 45–77. https://doi.org/10.2753/MIS0742-1222240302
Verified at: https://doi.org/10.2753/MIS0742-1222240302 (Crossref) **[IN LIST]**
Use in report: 3.2 Research Paradigm.

@ Dror, R., Baumer, G., Shlomov, S., & Reichart, R. (2018). The hitchhiker's guide to testing statistical significance in natural language processing. In *Proceedings of the 56th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 1383–1392). Association for Computational Linguistics. https://doi.org/10.18653/v1/P18-1128
Verified at: https://aclanthology.org/P18-1128/ **[NEW]**
Finding: Explains which significance test fits which NLP task and metric, proposes a simple selection protocol, and reports from a survey of 2017 ACL and TACL papers that testing is often ignored or misused.
Use in report: 3.x data analysis. "The choice of significance test for paired accuracy on the same questions follows Dror et al. (2018)."

@ Cobbe, K., Kosaraju, V., Bavarian, M., Chen, M., Jun, H., Kaiser, L., Plappert, M., Tworek, J., Hilton, J., Nakano, R., Hesse, C., & Schulman, J. (2021). *Training verifiers to solve math word problems*. arXiv. https://doi.org/10.48550/arXiv.2110.14168
Verified at: https://arxiv.org/abs/2110.14168 (preprint) **[IN LIST]**
Finding: Introduces GSM8K, 8.5K grade-school maths word problems needing multi-step reasoning.

@ Zhang, H., Da, J., Lee, D., Robinson, V., Wu, C., Song, W., Zhao, T., Raja, P., Zhuang, C., Slack, D., Lyu, Q., Hendryx, S., Kaplan, R., Lunati, M., & Yue, S. (2024). *A careful examination of large language model performance on grade school arithmetic* [Paper presentation]. Conference on Neural Information Processing Systems (NeurIPS 2024), Datasets and Benchmarks Track. https://doi.org/10.48550/arXiv.2405.00332
Verified at: https://arxiv.org/abs/2405.00332 (comment: "2024 NeurIPS Camera Ready (Datasets and Benchmarks Track)") **[NEW]**
Finding: On GSM1k, a fresh test built to mirror GSM8K, accuracy falls by up to 8% for some model families, evidence that some models have partly memorised GSM8K; frontier models show little overfitting.
Use in report: 3.x threats to validity, 5.x limitations. "GSM8K may be partly memorised by some models (Zhang et al., 2024), so absolute scores are read with caution and the comparison between conditions on the same model carries the argument."

@ Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection. In *Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security* (pp. 79–90). ACM. https://doi.org/10.1145/3605764.3623985
Verified at: https://doi.org/10.1145/3605764.3623985 (Crossref) and https://arxiv.org/abs/2302.12173 **[NEW]**
Finding: Shows that instructions hidden in data a model is likely to retrieve can take over the application remotely, blurring the line between data and instructions.
Use in report: 2.2.x, 5.x security. "Anything Burrow retrieves, including a note or a web clipping in the vault, can carry instructions (Greshake et al., 2023)."

@ Zou, W., Geng, R., Wang, B., & Jia, J. (2025). PoisonedRAG: Knowledge corruption attacks to retrieval-augmented generation of large language models. In *Proceedings of the USENIX Security Symposium 2025* (pp. 3827–3844). USENIX Association. https://arxiv.org/abs/2402.07867
Verified at: https://arxiv.org/abs/2402.07867 (comment: "To appear in USENIX Security Symposium 2025"); pages from https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.07867. Take the exact proceedings title from the USENIX page before printing. **[NEW]**
Finding: Injecting five malicious texts per target question into a knowledge base of millions of texts achieves a 90% attack success rate.
Use in report: 5.x security. "A handful of planted passages is enough to steer answers (Zou et al., 2025)."

@ Chen, Z., Xiang, Z., Xiao, C., Song, D., & Li, B. (2024). AgentPoison: Red-teaming LLM agents via poisoning memory or knowledge bases. In *Advances in Neural Information Processing Systems* (Vol. 37, pp. 130185–130213). Neural Information Processing Systems Foundation. https://doi.org/10.52202/079017-4136
Verified at: https://doi.org/10.52202/079017-4136 (Crossref) **[IN LIST]** (pages and DOI can now be added)

@ Dong, S., Xu, S., He, P., Li, Y., Tang, J., Liu, T., Liu, H., & Xiang, Z. (2025). Memory injection attacks on LLM agents via query-only interaction. In *Advances in Neural Information Processing Systems* (Vol. 38, pp. 52119–52153). Neural Information Processing Systems Foundation. https://doi.org/10.52202/085713-1554
Verified at: https://doi.org/10.52202/085713-1554 (Crossref) **[IN LIST, CORRECTED]** (was cited as a preprint; now NeurIPS 2025)
Finding: An attacker who can only send queries can plant malicious records in an agent's memory that later steer other users' queries.
Use in report: 2.4, 5.x. "Memory that writes itself can be poisoned through ordinary use (Dong et al., 2025), the reason Burrow writes a note only with the person's consent."

### Group 12. Kenya and Africa

@ Data Protection Act, No. 24 of 2019, Laws of Kenya. (2019). https://www.odpc.go.ke/wp-content/uploads/2024/02/TheDataProtectionAct__No24of2019.pdf
Verified at: https://www.odpc.go.ke/wp-content/uploads/2024/02/TheDataProtectionAct__No24of2019.pdf (Office of the Data Protection Commissioner; the file is the Kenya Gazette scan). A second copy titled "Kenya Data Protection Act, 2019" (51 pages) is at https://ictpolicyafrica.org/en/document/n7xolcf4vk8, hosted by Strathmore's CIPIT. **[IN LIST, CORRECTED]** (the entry had a pending URL)
Finding: Kenya's data protection statute. The scan is not machine-readable, so section text could not be read today. Search results describe Part VI, section 48, as "Conditions for transfer out of Kenya". Read sections 25 and 48 to 50 in the PDF and cite the exact section before relying on any wording.
Use in report: 1.5 Justification. "Sending personal notes to a cloud model is a transfer of personal data out of Kenya, which the Data Protection Act (2019) makes conditional; a model that runs on the laptop avoids the transfer."

@ Ministry of Information, Communications and the Digital Economy. (2025). *Kenya artificial intelligence strategy 2025–2030*. Republic of Kenya. https://ict.go.ke/sites/default/files/2025-03/Kenya%20AI%20Strategy%202025%20-%202030.pdf
Verified at: https://ict.go.ke/sites/default/files/2025-03/Kenya%20AI%20Strategy%202025%20-%202030.pdf (the ministry's own site serves the PDF, 23.9 MB; its text was not machine-read today). Title, ministry and the March 2025 launch come from search results for the copy at data4sdgs.org, which is headed "Kenya Artificial Intelligence Strategy 2025-2030, March 2025"; that page itself refused a direct fetch. **[NEW]**
Finding: Kenya's national AI strategy. For its content rely on the CIPIT analysis below or read the PDF; do not quote from it on the strength of this entry.
Use in report: 1.5 Justification. "Kenya's AI strategy lists data governance and local AI infrastructure among its pillars (Ministry of Information, Communications and the Digital Economy, 2025; Ogonjo, 2025)."

@ Ogonjo, F. A. (2025, April 22). *The Kenya National AI Strategy 2025-2030: Regional and global positioning*. Centre for Intellectual Property and Information Technology Law, Strathmore University. https://cipit.strathmore.edu/?p=4885
Verified at: https://cipit.strathmore.edu/?p=4885 **[NEW]**
Finding: Analysis from Strathmore's own research centre. Reports that the strategy's data pillar calls for a data governance structure and secure data sharing, that its infrastructure pillar aims for affordable AI infrastructure and more local data centres, and that data and AI sovereignty are reflected in it.
Use in report: 1.5 Justification. "Ogonjo (2025) notes that data and AI sovereignty run through the strategy; a memory engine that keeps personal data on the device is one small instance of that aim."

@ Adelani, D. I., Ojo, J., Azime, I. A., Zhuang, J. Y., Alabi, J. O., He, X., Ochieng, M., Hooker, S., Bukula, A., Lee, E.-S. A., Chukwuneke, C., Buzaaba, H., Sibanda, B., Kalipe, G., Mukiibi, J., Kabongo, S., Yuehgoh, F., Setaka, M., Ndolela, L., . . . Stenetorp, P. (2025). IrokoBench: A new benchmark for African languages in the age of large language models. In *Proceedings of the 2025 Conference of the Nations of the Americas Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)* (pp. 2732–2757). Association for Computational Linguistics. https://doi.org/10.18653/v1/2025.naacl-long.139
Verified at: https://doi.org/10.18653/v1/2025.naacl-long.139 (Crossref) and https://arxiv.org/abs/2406.03368 (27 authors) **[NEW]**
Finding: A human-translated benchmark for 17 African languages covering inference, mathematical reasoning and knowledge questions. The best open model (Gemma 2 27B) reached only 63% of the best proprietary model's (GPT-4o) performance.
Use in report: 1.2 Problem, 1.5 Justification. "For African languages the gap between open and proprietary models is wide: the best open model reached 63% of GPT-4o (Adelani et al., 2025). This project measures the gap in English only." Check the paper's language list before saying which Kenyan languages it covers.

@ Ojo, J., Ogundepo, O., Oladipo, A., Ogueji, K., Lin, J., Stenetorp, P., & Adelani, D. I. (2025). AfroBench: How good are large language models on African languages? In *Findings of the Association for Computational Linguistics: ACL 2025* (pp. 19048–19095). Association for Computational Linguistics. https://doi.org/10.18653/v1/2025.findings-acl.976
Verified at: https://doi.org/10.18653/v1/2025.findings-acl.976 (Crossref) and https://arxiv.org/abs/2311.07978 **[NEW]**
Finding: Across 64 African languages, 15 tasks and 22 datasets, large gaps remain between English and African languages on most tasks.
Use in report: 1.5 Justification, 5.x limitations (English-only evaluation).

---

## 3. Corrections to existing entries

Each correction was read from the DOI record or the publisher's page today.

1. **Chhikara et al. (2025), Mem0**
   As it is: `*Mem0: ...*. arXiv. https://doi.org/10.48550/arXiv.2504.19413`
   Wrong: it is no longer only a preprint; it was published at ECAI 2025.
   Corrected: see Group 6 (IOS Press, Frontiers in Artificial Intelligence and Applications, Vol. 413, pp. 2993–3000, https://doi.org/10.3233/FAIA251160).
   Verified at: https://ebooks.iospress.nl/doi/10.3233/FAIA251160

2. **Dong et al. (2025), memory injection attacks**
   As it is: arXiv preprint.
   Wrong: published at NeurIPS 2025.
   Corrected: see Group 11 (Advances in Neural Information Processing Systems, Vol. 38, pp. 52119–52153, https://doi.org/10.52202/085713-1554).
   Verified at: https://doi.org/10.52202/085713-1554

3. **Wang, H., et al. (2026), IEEE Transactions on Services Computing**
   As it is: `Advance online publication.`
   Wrong: it now has a volume, issue and pages.
   Corrected: `@ Wang, H., Huang, Y., Hu, Z., Li, Q., Fan, P., Huang, Y., Wang, S., & Qi, T. (2026). Efficient and effective personalized in-context learning for on-device large model services. *IEEE Transactions on Services Computing*, *19*(4), 2788–2800. https://doi.org/10.1109/TSC.2026.3697569`
   Verified at: https://doi.org/10.1109/TSC.2026.3697569 (Crossref)

4. **Anusha et al. (2026), ICICT**
   As it is: `Anusha, M., Bhavani, S., Likitha, M., & Jahnavi, A.`
   Wrong: author order (Jahnavi comes before Likitha) and the first author's initials (the record gives "M. Baby Anusha").
   Corrected author list: `Anusha, M. B., Bhavani, S., Jahnavi, A., & Likitha, M. (2026).` Rest of the entry (title, pp. 845–851, DOI) is confirmed.
   Verified at: https://doi.org/10.1109/ICICT68280.2026.11510906 (Crossref)

5. **Renuka et al. (2025), ICIIET**
   As it is: `Renuka, K., Albert, P., Anusuya, R., Ranjith, R., Naveen, V., & Shyam Surya, S.`
   Wrong: author order. The record lists: Karthika Renuka; R. Anusuya; Naveen V; Prince Albert R; Ranjith R; Shyam Surya S G.
   Corrected author list: `Renuka, K., Anusuya, R., Naveen, V., Prince Albert, R., Ranjith, R., & Shyam Surya, S. G. (2025).` Title, pp. 1–5 and DOI are confirmed. The split of these names into surname and initials is my reading of the record; check the IEEE Xplore page.
   Verified at: https://doi.org/10.1109/ICIIET65921.2025.11377539 (Crossref)

6. **Shafin et al. (2026), ICISCoIS**
   As it is: `Shafin, J., Lankesh, M., & Vargheese, A.`
   Wrong: names are shortened incorrectly. The record lists "Jersho Shafin D J", "Lankesh M" and "Allin Geo Vargheese".
   Corrected author list: `Jersho Shafin, D. J., Lankesh, M., & Geo Vargheese, A. (2026).` Same caution on name order as above.
   Verified at: https://doi.org/10.1109/ICISCoIS62701.2026.11447893 (Crossref)

7. **Patra et al. (2026), IEMENTech**
   As it is: last author `Bishnu, S.`
   Wrong: missing initial; the record gives "Soham Kanti Bishnu".
   Corrected: `... Karmakar, S., & Bishnu, S. K. (2026).`
   Verified at: https://doi.org/10.1109/IEMENTech202669403.2026.11434122 (Crossref)

8. **Ho et al. (2020), 2WikiMultihopQA**
   As it is: second author `Nguyen, A.-K. D.`
   Wrong: the DOI record gives the surname as "Duong Nguyen".
   Corrected: `Ho, X., Duong Nguyen, A.-K., Sugawara, S., & Aizawa, A. (2020).` Rest confirmed (pp. 6609–6625).
   Verified at: https://doi.org/10.18653/v1/2020.coling-main.580 (Crossref)

9. **Borgeaud et al. (2022), ICML**
   As it is: a PMLR proceedings entry ending in the arXiv DOI.
   Wrong: the link does not match the cited version. Pages 2206–2240 are confirmed.
   Corrected ending: `In *Proceedings of the 39th International Conference on Machine Learning* (Vol. 162, pp. 2206–2240). PMLR. https://proceedings.mlr.press/v162/borgeaud22a.html`
   Verified at: https://proceedings.mlr.press/v162/borgeaud22a.html

10. **Gutiérrez et al. (2024), HippoRAG** and **Chen et al. (2024), AgentPoison**
    As they are: `[Paper presentation]. Conference on Neural Information Processing Systems (NeurIPS 2024)` with arXiv DOIs.
    Not wrong, but the proceedings records now exist and are stronger. Corrected entries are in Groups 6 and 11 (Vol. 37, pp. 59532–59569, https://doi.org/10.52202/079017-1902; Vol. 37, pp. 130185–130213, https://doi.org/10.52202/079017-4136).
    Verified at: the two DOI records (Crossref).

11. **Data Protection Act, No. 24 of 2019**
    As it is: `[PENDING: confirm URL of the official text on Kenya Law]`
    Wrong: no URL. Kenya Law's pages returned errors or empty pages today (403 on kenyalaw.org, empty response on new.kenyalaw.org), so the regulator's copy is used.
    Corrected: `@ Data Protection Act, No. 24 of 2019, Laws of Kenya. (2019). https://www.odpc.go.ke/wp-content/uploads/2024/02/TheDataProtectionAct__No24of2019.pdf`
    Verified at: that URL (PDF served by the Office of the Data Protection Commissioner).

12. **Qwen Team (2026), Qwen3.5 blog post**
    As it is: `(2026, February). ... https://qwen.ai/blog?id=qwen3.5`
    Issue: the qwen.ai page loads only with JavaScript and returned no text. The post exists: Alibaba Cloud mirrors it under the same title at https://www.alibabacloud.com/blog/qwen3-5-towards-native-multimodal-agents_602894, and most secondary reports date the release 16 February 2026 (one says 15 February).
    Suggested: keep the entry, give the date as `(2026, February 16)` once checked in a browser, and add the Qwen3 technical report (Group 1) as the citable paper for the family. No general Qwen3.5 technical report is on arXiv; only "Qwen3.5-Omni Technical Report" (arXiv:2604.15804) was found.
    Verified at: web search results for the post title (10 Nov 2026); arXiv title search for "Qwen3.5".

Entries re-verified and found correct (no change needed): Chevalier et al. (2023); Chopra et al. (2025); Collins & Loftus (1975); Cormack et al. (2009); Gemma Team (2026); Hevner et al. (2004); Izacard et al. (2023, JMLR 24, article 251, pp. 1–43, per Semantic Scholar); Jiang et al. (2023); Karpukhin et al. (2020); Lu et al. (2024); Maharana et al. (2024); Mallen et al. (2023); Park et al. (2023); Peffers et al. (2007); Robertson & Zaragoza (2009); Teyler & DiScenna (1986); Xiao et al. (2024); Yang et al. (2018); Zhang et al. (2025, Qwen3 Embedding); Zhong et al. (2024). Titles and arXiv identifiers of the remaining arXiv entries (Abdin, Ge, Gemma 2, Grattafiori, Gunter, Kaplan, Packer, Yang Qwen2.5) resolve correctly on Semantic Scholar.

**Weak entries to replace or demote.** These exist and are correctly identified, but they are low-tier conference papers that add little authority, and their use as the main support for the on-device background is what makes the list look thin:

- Anusha et al. (2026), Patra et al. (2026), Shafin et al. (2026), Renuka et al. (2025): replace as the main citations with Lu et al. (2024), Xu et al. (2024), Wang, F., et al. (2025, ACM TIST) and Liu et al. (2024, ICML). Keep at most one as an example of recent applied work.
- Chopra et al. (2025): keep only if the report uses its specific finding.
- Chroma, LangChain and Ollama entries: fine as software citations, but each claim about what retrieval does should now rest on a paper from Groups 3 to 5.

Not re-verified today (not relied on in this pack): Anthropic (2026a, 2026b) Claude Code pages; Obsidian (2025a, 2025b).

---

## 4. Not found or rejected

- **A general Qwen3.5 technical report.** Not on arXiv as of today. Only the release blog post and "Qwen3.5-Omni Technical Report" (arXiv:2604.15804) exist. Cite the blog post plus the Qwen3 report.
- **Kenya Law's own page for the Data Protection Act.** kenyalaw.org returned 403 and new.kenyalaw.org returned an empty response. The ODPC copy is used instead. The Act's section wording could not be read by machine (scanned PDF); section numbers must be checked by hand.
- **The text of the Kenya AI Strategy.** The ministry PDF downloads but was not machine-read; the data4sdgs.org page returned 403. Content claims rest on Ogonjo (2025).
- **Peer-reviewed work on LLM use in Kenya specifically that bears on local inference or privacy.** None found that I could verify. The pack offers the Act, the strategy, the CIPIT analysis and two African-language benchmarks instead. Nothing was invented to fill this gap.
- **A peer-reviewed study measuring "fraction of the small-versus-cloud gap closed by retrieval" on a laptop.** Not found. Narayan et al. (2025) is the nearest (they report the share of cloud performance recovered, with cloud help). This is a real gap the report can claim in 2.4.
- **A published study that tests retrieval on GSM8K itself with a small local model.** Not found. The supporting evidence is indirect: irrelevant context on GSM-style problems (Shi et al., 2023; Mirzadeh et al., 2025; Yang et al., 2025) and retrieval lowering accuracy in question answering (Yoran et al., 2024; Wang et al., 2023). The report's GSM8K result should be presented as extending these, not as replicating one.
- **DBLP lookups.** DBLP's API returned empty responses today, so no entry relies on it. Venues come from arXiv comment fields, Crossref DOI records, publisher pages, the ACL Anthology and Semantic Scholar.
- **Left out for lack of a second confirmation:** the PMLR volume number for Liu et al. (2024, MobileLLM); publication venues that only Semantic Scholar reports for Voyager (TMLR), MemoryAgentBench (ICLR) and GSM-DC (EMNLP 2025). These are cited as preprints with a note.
- **Considered and dropped as lower value:** MTEB (Muennighoff et al., 2023, EACL, verified, pp. 2014–2037, https://doi.org/10.18653/v1/2023.eacl-main.148); Reflexion (Shinn et al., 2023, NeurIPS 36, verified, https://doi.org/10.52202/075280-0377); Attributed QA (Bohnet et al., 2022, arXiv:2212.08037, verified preprint); "A survey of small language models" (Van Nguyen et al., 2024, arXiv:2410.20011, verified preprint); "Long context RAG performance of large language models" (Leng et al., 2024, arXiv:2411.03538, workshop paper); "When to retrieve" (Labruna et al., 2024, arXiv:2404.19705); MiniRAG (Fan et al., 2025, arXiv:2501.06713, preprint about retrieval for small models, usable in 2.3 if a small-model retrieval system is wanted). All exist and can be added if a section needs them.


## Added on 10 November 2026 for the Word report

@ Larman, C., & Basili, V. R. (2003). Iterative and incremental development: A brief history. *Computer*, *36*(6), 47–56. https://doi.org/10.1109/MC.2003.1204375
Verified at: https://doi.org/10.1109/MC.2003.1204375 (Crossref record read on 10 November 2026: authors C. Larman and V. R. Basili, Computer, volume 36, issue 6, pages 47 to 56, June 2003, IEEE).
Use in report: 3.3.1, as the source for iterative and incremental development.

Removed from the cited list: Anthropic (n.d.), Agent Skills, because the course guide asks that undated sources be avoided. The sentence that cited it was cut.
