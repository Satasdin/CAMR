# Real runs of the lead (7 November 2026)

Qwen3 4B (mlx-community/Qwen3-4B-4bit) in the CAMR app, on a MacBook Pro M5 Pro, driven by a script through the app's
own chat (CAMR_SCRIPT), in scratch memory and project folders. Each brief was new to the agent: none is one of the
frozen tasks in TASKS.md, and nothing in the skills or shelves names them. Every number below comes from the run's
own REPORT.md, written by rules from its records.

| Run | Brief | Worked for | Stops for the person | What it showed | What changed after it |
|---|---|---|---|---|---|
| 1 | Bookshop site with a reading-list total | 6 min 24 s | 0 (all facts told) | Brief exact. app.js began with `require('mcp')` (a tool name leaked into code); onclick attributes | Static page check (browser-only code, inline handlers, missing ids); behaviour skill names the mistakes |
| 2 | The same | 4 min 16 s | 0 | Brand colours used, ids matched, no onclick. One logic bug: the first `.btn` also cleared the list | Architecture lists class names; design uses only the brief's colours |
| 3 | Physio clinic: prices, a cost calculator, contact; hours and phone not told | 2 min 9 s | 0 (should have been 2) | The questions before the build were refused: the researcher's tools left out ask_user | The researcher can ask; answers reach every model, with or without memory; the report says when a question never reached the person |
| 4 | The same, agent tests running scripts | 4 min 3 s | 2 | Both answers in the brief word for word. Tests pressed every button: none worked, and every error read "Script error." | The shut-in preview has an origin of its own, so real errors show; a const that is changed is found statically; the lead plans a fix when the last test fails |
| 5 | The same | 5 min 33 s | 2 | Real error ("Attempted to assign to readonly property") and the static check's cause reached the model; the lead planned the fix twice; the 4B had the right fix but its edit failed 5 times on indentation | Edits match line for line ignoring indentation when exactly one place matches |
| 6 | The same, Playwright connected | stopped at 32 min | 2 | Chrome's own error reached the report ("Assignment to constant variable"); the lead's fix made the change (const to let) but the edit then crashed on finding its line; the reviewer called Playwright itself and waited at the gate | Edits matched ignoring indentation find their line; the reviewer gets browser tools only from a plugin that runs without asking |
| D1 | "Make a PDF price list for Riverbank Physio that we can print" | 33 s | 0 | The writer invented a US price list ($150, (123) 456-7890): the researcher never got what was told. The fact check caught all 8; edits could not take them out. WebKit's print loop wrote a 15.7 GB PDF (deleted) | Every plan's brief gets what was told; 3+ made-up facts mean a rewrite; the PDF is drawn onto A4 pages, bounded |
| D3 | The same | 19 s | 0 | Every fact exact, nothing invented; one A4 page; the 4B still wrote the brand colours in as a section | Colour codes and empty headings are taken out by rule |
| O1 | Clinic site, built by qwen3:4b in Ollama (same lead, prompts, tools, told facts; no CAMR notes) | stopped at 40 min | 2 | That build (Qwen3-4B Thinking 2507) wrote its reasoning into every answer until the 3,000-token limit | Its reasoning is kept apart; only the answer is read |
| O2 | The same | 27 min 30 s to the review (stopped at 40 min) | 2 | All five parts right first time; no const bug; every fact on the page. About 7 times as long as the 4B in MLX with CAMR, which is fast but needs its fix loop | (thinking costs time and buys cleaner first drafts) |

Before run 1 the app recorded a frame every quarter second for these records; that alone cost the app 117 to 210% CPU
during a build. With it off (from run 6), the app uses 15 to 30% while the model works, and most of that is SwiftUI
waiting.

## What is decided by rule and what by the model

Rules: the order of the parts, which role makes which file, retrying a part once, planning a fix when the last page
test fails, which file a change goes to, the checks (facts, static page check, browser tests), and the report.
The model: the brief, the list of files, every file's content, and whether the page does each thing the brief asks.
