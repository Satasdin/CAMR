# Evaluation plan, fixed before scoring

Written on 10 November 2026, before any held-back project or real-repository instance had been run.

## Freeze

The engine is frozen at the git tag `evaluation-1`. No file under `Sources/` or `app/` changes until every run below has finished. Anything found to be wrong during scoring is reported, not fixed in place.

## Held-back agent test (RQ2)

Three projects written after the freeze, `split: held`, by agents that are told not to read the engine. Each must pass `burrow-trial verify` with no wrong checks. Each has 2 setup, 1 plain, 3 depends and 2 unknown sessions, so 6 scored sessions.

Each project runs once per model and condition (none, search, walk). The primary model is `qwen3:4b-instruct-2507-q4_K_M`. `qwen3:1.7b` and `qwen3:8b` are secondary. Primary measures: scored sessions passed, decisions broken among depends sessions, unknown sessions answered honestly.

## Real-repository test (RQ3)

Source: the SWE-bench test split (Jimenez et al., 2024), which pairs real GitHub issues with the commit before their fix. Repositories, chosen by size before any result: `psf/requests`, `pallets/flask`, `pytest-dev/pytest`, `django/django`. For each, the latest 30 instances by date (all of them if fewer). `mwaskom/seaborn` is used only to check the harness and is not scored.

For each instance the repository is checked out at the commit before the fix and indexed. The issue text is the question. Retrieval only, no model. The gold set is the existing source files the fix changed (SWE-bench keeps test changes apart).

Measures for search and walk, each held to 12,000 characters: right file first; any changed file reached; every changed file reached; mean recall. Walk and search are compared with an exact two-sided sign test on the instances where they disagree.

## Growth test (RQ4)

From the same four repositories: files, pieces, links, index size, time of the first full index, median and longest retrieval time over all instances, and mean time for a full answer on the first five instances.
