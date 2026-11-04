# Chapter 6: CAMR v2 additions (insertion blocks)

> **How to use this file.** Each block is headed with the section of `Chapter6_CAMR.docx` it goes into. The v1 text stays as it is. Tables are numbered "Table 6.v2-N" for renumbering, and section references such as "5.v2" point to the CAMR v2 blocks of Chapter 5. No result appears here that is not already in Chapter 5. The 27B comparison is still running, so nothing is concluded from it.

---

## Insert into 6.1 Introduction

*Placement: after the v1 introduction's first paragraph.*

CAMR was built in two versions. CAMR v2 is the deployed memory on an Apple-silicon Mac. It keeps the notes that a frozen 1.7B model writes while reading each moment, stores them on the SSD in rooms of related moments, and lays one room in front of the model for each question. It was evaluated on three scripted twelve-week lives held out from development, against CAMR v1 and three other baselines on the same Mac. Pass marks were written before the runs. The conclusions below add CAMR v2's evidence to each objective. They hold only for scripted lives, one machine and a 1.7B reader.

---

## Insert into 6.2 Conclusions

**Objective i (techniques and their limits).** CAMR v2 adds one limit to those found by CAMR v1. Saved key–value notes that were written separately do not combine for a 1.7B reader. With 30 unrelated moments beside the right one, such notes found 2 of 46 facts, against 32 from the words. The training-free fixes tried did not close the difference (Chapter 5, objective ii; E-15). Reusing a model's own notes works only where they were written together.

**Objective ii (design).** The design met its accuracy mark. Within one room, the saved notes answered as the words did: 164 against 163 facts and 25 against 24 false memories at week 12, with identical answers on 3,483 of 3,600 questions. The event log also identified what each answer used: the most-attended moment held the answer in 47 of 47 right single-fact answers. The design has one structural limit. A question sees one room, so facts told across two notes were almost never joined (2 of 30).

**Objective iii (on the device).** CAMR v2 ran on an Apple-silicon laptop. Over twelve weeks its notes grew from 82 to 963 MB, while the wait for the first word stayed at 0.064–0.072 s and peak RAM stayed between 1.65 and 1.83 GB. Two of the three speed and accuracy marks were met: 0.233 s at 2,000 words, and notes matching words. The third failed: notes were 4.6 times sooner than words, against a mark of 10. That mark came from the slower MacBook Air, and the Air was not used for the proof. CAMR v2 was installed from a fresh clone and passed its health check, and only its own page can use its server. The objective's embedded database was replaced by files on the SSD (Table 4.9). The memory therefore grows on the SSD, at about 1 GB per 84-day life, instead of in RAM or the wait.

**Objective iv (evaluation).** CAMR v2 has no cloud ceiling, so the gap closed was not computed. Against local references it gave a mixed result:
- On the quiz it was level with CAMR v1 on the same reader: 164 against 166 facts, at half the wait and 0.4 GB less RAM, and without v1's hand-written rules.
- On errands it did three times as well: 122 against 40.
- It stayed well below CAMR v1 on a 4B reader (208).
- It was strong on single facts and weak on facts that must be combined, which repeats CAMR v1's finding on real benchmarks that memory recovers knowledge, not reasoning.
- It was not honest about what it had never been told. It made up 25 of 45 such quiz answers and 42 of 45 such errands, and never asked.

<!-- 27B: add one sentence here when the runs finish, from Tables 5.v2-19 only. -->

**Objective v (token budget).** For a 1.7B reader the best desk was small and fixed: rooms of at most 512 tokens (about 210 on average) plus four moments re-read. Larger rooms knew fewer facts at every setting tried. The context stayed at 336–420 tokens at week 12 however large memory grew. This agrees with CAMR v1, where more text distracted a small reader.

**Contribution and boundaries.** CAMR v2 contributes three things:
1. A working memory of a frozen model's own notes, stored in rooms on the SSD, whose wait and RAM stayed flat as memory grew.
2. A ruler of scripted lives with pre-written pass marks and test records that name the machine and the code behind every number.
3. A local app whose every answer can be replayed against the moments it used.

The conclusions hold for three synthetic personas on one MacBook Pro, run once per contender with a 1.7B reader. They do not establish performance for real users, on other Macs, or with several rooms read together.

Table 6.v2-1: Alignment of CAMR v2 from objectives to evidence and conclusions

| Objective | Evidence (Chapter 5) | Conclusion | Status |
|---|---|---|---|
| i. Techniques and limits | Table 5.v2-12; E-15, E-16 | Separately written notes do not combine for a 1.7B reader | Answered for v2's case |
| ii. Design | T-v2-19, T-v2-22, T-v2-23; Table 5.v2-11 | Notes are faithful within one room; the log identifies what was used | Met (mark 2; NFR-05, NFR-19) |
| iii. On the device | T-v2-18, T-v2-20, T-v2-21, T-v2-14; Table 5.v2-15 | Flat wait and nearly flat RAM as memory grows; SSD cost about 1 GB per life | Partly met (mark 1 met, mark 3 not met; files replace the database) |
| iv. Evaluation | Tables 5.v2-16 to 5.v2-18 | Level with CAMR v1 on facts, ahead on errands, below the 4B, not honest when untold | Carried out; no pass mark, so no success claimed |
| v. Token budget | Table 5.v2-20 | A small, fixed desk is best for 1.7B | Determined on development lives only |

---

## Insert into 6.3 Recommendations

*Placement: after Table 6.3, as CAMR v2 recommendations.*

Each recommendation follows from a result or limitation in the CAMR v2 blocks of Chapter 5. Essential safeguards come first.

Table 6.v2-2: Recommendations from CAMR v2

| Priority | Audience | Recommended action | Evidence and condition |
|---|---|---|---|
| 1. Essential | Maintainers of CAMR v2 (the student) | Commit the crash-window fix and its test, and the server security test; re-run the suite before any release | D-v2-04, T-v2-06, T-v2-12. A memory can be corrupted if the app is killed between an append and a save |
| 2. Essential | Anyone letting CAMR v2 act on errands | Confirm every tool call before it is carried out, and treat any argument as unverified | T-v2-25: 42 of 45 never-told errands made up and none asked. This holds until asking when unsure is built and measured |
| 3. High | Developers of on-device assistants on Apple silicon | Keep a growing memory as the model's notes in rooms on the SSD, and read one small room per question | Tables 5.v2-15 and 5.v2-20: flat wait and RAM for twelve weeks. Tested on one M5 Pro and synthetic lives only |
| 4. High | Builders of memory for agents | Test memories on tasks worded as requests, not only as questions | Table 5.v2-18: errands 122 against 40 while the quiz was level |
| 5. Medium | Users and maintainers | Allow about 1 GB of SSD per three months of use, and show the size in the app | Table 5.v2-1. This holds until sleep shrinks old notes |
| 6. Medium | Researchers evaluating memory | Write pass marks before the runs, count false memories apart from facts known, and set speed marks on the machine that will be measured | E-19; T-v2-20 failed only because the mark came from a slower machine |
| 7. Lower | The student and supervisor | Obtain ethics approval before any user session, and audit the page's accessibility before a release | T-v2-28: neither was done |

---

## Insert into 6.4 Future Works

*Placement: after Table 6.4, as CAMR v2 directions.*

Each direction extends CAMR v2 from a limitation in Chapter 5. Steps 3 to 6 of the plan were designed but not built (E-22; `docs/plan/camr-plan.html`).

Table 6.v2-3: Prioritised future works for CAMR v2

| Priority | Direction and rationale | What would change; resources | How to evaluate |
|---|---|---|---|
| 1 | **Honesty: asking when unsure.** The agent never asked, and it made up 42 of 45 never-told errands. The plan settles an unsure fact when it is needed: it resolves the doubt from evidence, or asks one line. The top moment's attention share was lower for answers given without knowledge (Table 5.v2-13), so it is one candidate signal | A rule or a small learned check before answering or calling a tool; development lives only | Made-up answers out of the 45 never-told quiz questions and errands, with asks counted, on the held-out lives. Facts known must not fall; the pass mark is written first |
| 2 | **Several rooms read together.** One room per question joined 2 of 30 two-note facts. Three rooms of separate notes knew 96 of 255 against 144 as words, and re-reading the start of each room recovered facts only in proportion to its cost (E-16) | A way to combine rooms without re-reading them: re-encoding where rooms meet, or the trained translation layer below | The 30 two-note questions, and facts known out of 255, at a wait no higher than one room's |
| 3 | **The trained translation layer and shorthand** (plan step 3). Notes cost about 1 GB per life | A small network, trained once on the charger, that turns compact vectors back into notes the frozen model can read; the model itself stays frozen | As the plan sets out: time to the first word flat from 1,000 to 1,000,000 facts, and shorthand accuracy measured against notes and words; SSD per life |
| 4 | **Sleep** (plan step 4). Memory only grows; changed facts stay as two moments (6 stale answers), and nothing is ever distilled | Replay, distilling checked by a quiz built from the original moments, shrinking, fading without destroying, re-packing rooms, and settling unsure facts | As the plan sets out: a two-week scripted life with quiz scores rising and RAM and speed flat. In addition, week-1 facts asked again in week 12, and false memories that do not rise |
| 5 | **Other hardware.** The proof ran on one M5 Pro; the 10× mark was set on a slower Air, and M1 to M3 and 8 GB Macs were never tested | The proof lives re-run on the 16 GB Air and at least one older or smaller Mac | NFR-01 to NFR-03 per machine, from records that name each machine; repeated runs to give variation |
| 6 | **Real data and real users.** The results come from synthetic lives only. A LongMemEval loader exists but was never run | A LongMemEval run; then, with ethics approval and consent, a study of the app with real users; an accessibility audit of the page | LongMemEval accuracy by question type, with false memories counted. For users: answers judged right from memory, made-up answers, and task completion in each tab |

<!-- 27B: if the 27B runs change the ranking of memories, add a future-work row that follows from them; otherwise leave this table as it is. -->
