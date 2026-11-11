# Chapter 6:  Conclusions, Recommendations and Future Works

## 6.1 Introduction

This chapter closes the chain from the problem stated in Chapter 1 to the evidence of Chapter 5. Section 6.2 states what the study established for each specific objective, Section 6.3 recommends what should be done on the strength of those findings, and Section 6.4 names the work that remains open. No new experiment, result or source is introduced; each statement rests on a section of Chapter 5.

## 6.2 Conclusions

The study began from a choice that a person who wants a private assistant is forced to make: a small model on their own laptop keeps their material private but lacks the facts they need, and a large cloud model has the capability but takes the material off the device. The purpose was to measure how much of that gap an external memory engine beside a frozen small model can close, by task type, and at what cost. The completed solution is Burrow, a memory engine in Swift with an embedded SQLite index that keeps a vault of the person's own files, decides for each question whether the vault is needed, fits what it shows to the model's reading speed, and checks the places an answer cites. It is reached through a command-line tool, a desktop application, a terminal chat and a Model Context Protocol server.

**Objective i.** The review established that the gap between small and large models is concentrated in long-tail and private knowledge, that retrieval can stand in for scale on such knowledge but can lower accuracy when the text it supplies is irrelevant, and that no reviewed work measured what a memory engine beside a frozen small model closes on a consumer device, by task type (Section 5.9.1). This gap framed the remaining objectives.

**Objective ii.** A write policy, a retrieval policy and a token budgeting mechanism were designed and built as the engine's Learn, Decide and Fit steps (Section 5.9.2). The objective was partly met: the write policy proposes notes for the person to approve rather than distilling every interaction, and neither its effect on later answers nor the recency and importance signals added after the freeze were measured.

**Objective iii.** The engine was developed on one consumer laptop with no discrete graphics card and an embedded database. All 212 automated tests and all 23 test cases passed, and a lookup that followed links took a median of 0.18 seconds on an index of 11,710 pieces (Section 5.9.3). The objective was met on the one laptop tested.

**Objective iv.** On 120 knowledge questions about material the models could not have memorised, Gemma 4 12B answered 9 alone and 102 with the engine, which is 93% of the gap to the cloud model given the same vault (109). On 50 reasoning problems, where plain retrieval cut the model from 47 to 7 correct answers, the engine left the vault out of every problem and the model solved 48. The engine's own work took under a tenth of a second per answer (Sections 5.5.3 and 5.9.4). The objective was partly met: the reasoning gap was too small to express as a fraction, and on knowledge the engine's gain over plain retrieval came mainly from showing the model more text, while on the 4 billion parameter model the engine answered fewer knowledge questions than plain retrieval (91 against 97).

**Objective v.** Gain per token was highest at the smallest budget that delivered excerpts and fell as more was shown, while accuracy kept rising up to the largest budget tested (Section 5.9.5). The objective was partly met: the study found that the budget is a choice between speed and accuracy, not a single best value.

The contribution of the study is a measured answer to the question it set: on private and recent material, an on-device model given a well-prepared memory of the person's own files came within 7 of 120 questions of a cloud model given the same memory, at a median of about nine seconds an answer, and a memory that first decides whether it is needed avoids the harm that retrieval does to reasoning. The study also contributes an evaluation method, the fraction of the gap closed against a cloud model given the same memory, with token and latency accounting on the device. These conclusions hold for one laptop, two on-device models, English text, three curated subjects with questions written by language-model agents, and one run of each question. They do not show that the engine's decisions, as distinct from its larger budget, improve on plain retrieval for knowledge, and they make no claim about usability, since no person other than the developer used the application.

## 6.3 Recommendations

The recommendations below follow from the results and limitations of Chapter 5. The first two are essential for anyone who adopts the approach; the others are improvements.

i) **Developers of on-device assistants should decide whether to retrieve before supplying memory to a question.** Pasting excerpts in front of every question cut the main model from 47 to 7 of 50 reasoning problems, while an engine that decided first kept 48 (Section 5.5.3). Where an assistant handles both kinds of question, this step protects the answers that need no memory.

ii) **Developers should give a local model enough of the vault to answer, and set the budget from what the model can read in an acceptable time.** Accuracy on knowledge rose from 56 to 112 of 120 as the amount shown grew from 4,000 to 32,000 characters, while the time per answer grew from 2.1 to 15.6 seconds (Section 5.5.5). The right budget depends on how long the person will wait, which the engine's Fit step measures for each model.

iii) **People who keep private notes and documents should consider an on-device model with a memory of those files before sending them to a cloud service.** On such material the cloud model alone answered 40 of 120 questions and the on-device model with the vault answered 102 (Section 5.5.3), so the private choice was the more capable one here. This holds within the conditions above: a laptop with enough memory for a 12 billion parameter model, and material of the kind tested.

iv) **Researchers measuring memory for small models should compare against a cloud model given the same memory, not against the cloud model alone.** Against the cloud model alone the fraction closed passed 100% and stopped being informative, because the ceiling had no access to the material (Section 5.5.3).

v) **Maintainers of Burrow should close the three known gaps in the frozen code before relying on its citation check outside the command line:** the check with retry runs only on one command, the Model Context Protocol server and the terminal chat use a fixed budget, and the engine's prompt does not stop an excerpt from closing its block (Section 5.9.6).

## 6.4 Future Works

The following directions arise from the limitations of Section 5.9.6. Each extends the research rather than completing promised work.

i) **Separating the engine's decisions from its budget.** The scored runs gave the engine a larger budget than the baselines, so its gain could not be credited to Decide or Fit. Running the engine and plain retrieval at equal budgets, and switching Decide and Fit off in turn, would show what each step adds on knowledge questions, and whether the result on the 4 billion parameter model reflects the model or the steps.

ii) **Measuring the write policy over time.** Learn was tested only by automated tests. A study that lets the engine propose notes across many sessions, and measures later answers with and without the kept notes, would test the write policy that objective ii describes, together with the recency and importance signals on a vault whose notes go out of date.

iii) **Questions written by people, and questions that mix knowledge and reasoning.** The knowledge questions were written by agents from the same family as the cloud model, and knowledge and reasoning were tested apart. Questions written by the people who own a vault, including problems that need a fact and a calculation together, would test whether the results transfer to real use and whether the decision to retrieve holds when a question needs both.

iv) **A study with real users.** No person other than the developer used the application. A usability study with people working in their own vaults would show whether the decisions the engine displays help them trust or correct an answer.

v) **Other devices, models and languages.** Every result came from one laptop, two models and English text. Repeating the evaluation on lower-memory laptops, on phones, and in other languages, including Kiswahili, would show how far the conclusions generalise, with each question run several times so that variation between runs can be measured.
