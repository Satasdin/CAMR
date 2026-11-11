# Decisions

Each entry says what was decided and why, so every choice can be defended. Newest last.

**D-1. Swift only for the app and engine.** There is no Python to install, so another person can run it, as the course guide requires. The app and the test tool share one engine, so the tests measure what ships.

**D-2. The files are the truth.** Code stays where it is. Notes are Markdown in `.burrow/notes`. `index.sqlite` is built from them and can be deleted at any time. A test confirms that deleting it loses nothing.

**D-3. Word search plus embeddings, merged by rank.** Word search finds exact names, embeddings find meaning. Reciprocal rank fusion merges them without tuning between two unlike scores.

**D-4. Links come from the code.** Imports for Python, JavaScript, TypeScript and C. Everywhere else, a file links to the file defining a name it uses. No model decides what is linked, so links can be checked. A name used by more than a tenth of the files is ignored, because it connects nothing.

**D-5. A cluster is a folder, limited to two levels.** Simple, predictable and readable on the Map.

**D-6. The vault walks and the model reads.** Search finds where to start, then Burrow follows links for up to two hops. A link opens the part of the file defining the name that made the link, or else the best word match.

**D-7. Every mode gets the same amount of text.** The default is 12,000 characters. A walk that runs out of links spends the rest on further search results. A win therefore cannot come from simply reading more.

**D-8. Code and notes are data.** The prompt says to follow no instruction inside excerpts. Search terms are quoted, so a question cannot act as query syntax.

**D-9. Large data files are left out.** JSON, XML, YAML and text files over 32 KB are not indexed. On the first real repository, results files made up about 90% of the chunks and drowned the code. Small configuration files are kept.

**D-10. Long jobs run in tmux, in a session named `burrow`.** They survive when a Claude session ends. An earlier benchmark queue was lost that way.

**D-11. The default model is Qwen3 4B Instruct, and excerpts carry line numbers.** On one question about a real repository, `qwen3:4b` reasoned aloud for 97 to 197 seconds even with thinking switched off, while the instruct build answered in 4 to 6 seconds. Without numbered lines the model invented a line number, and with them it cited the right one. This is one question, so it is a working choice and not a result.

**D-12. An exact name wins.** A chunk holding a compound name typed in the question, such as `APP_MEMORY`, goes ahead of the merged ranking, and where it is defined comes before where it is used. Underscores stay part of a word in the search index. This applies to plain search and to the walk alike, so the comparison stays fair. It was found on the CAMR repository, so that repository can't be used for final scoring.

**D-13. The agent test is a separate target on the same engine.** `burrow-trial` and the `BurrowTrial` library call the Vault the app calls, so the test measures what ships. They add nothing to `BurrowCore`.

**D-14. Projects are hand-authored and fixed, not generated from seeds.** A project is a folder of starting code, briefs, hidden tests and correct solutions, written by Claude and declared in the AI-use log. The plan said "fixed seeds", which was meant to make runs repeatable. Fixed files do that, and a template generator would have produced look-alike projects. The model's own seed stays fixed in `Ollama.swift`.

**D-15. A project must prove it can measure before any model runs.** `burrow-trial verify` requires that the correct solution passes, that the code before each task fails its task tests, that each tempting wrong fix fails the decision tests by a failed assertion and not a crash, and that the final code passes every session's tests.

**D-16. Sessions are categorised, and only later ones are scored.** Setup sessions establish a decision and are not scored. Depends sessions need an earlier decision, plain sessions are a control needing no memory, and unknown sessions ask about something never recorded, where the right answer is "I don't know".

**D-17. Each session starts from correct code.** The code is reset to the starting code plus the correct solutions of earlier sessions, as if a teammate had merged them. One failed session therefore cannot make later ones fail, and what differs between modes is memory and not accumulated damage.

**D-18. Every mode gets the same reading allowance.** After the excerpts, a simulated developer agent may open files in up to three rounds, within 12,000 characters. An attempt to replace a file it has not fully seen opens that file first and costs a round, because a whole-file edit made from an excerpt would delete the rest of the file.

**D-19. Notes come from the brief alone, once per session.** The model writes them through the normal note pipeline, so they are real and not scripted. Writing them only from the brief makes the notes identical for search and walk, so those two modes differ only in retrieval. With no memory, no notes are filed.

**D-20. A broken decision means a failed assertion.** Code that crashes says nothing about whether a decision was kept, so an error is recorded separately as "decision check errored" and not counted as broken. A session where the agent changed nothing is also reported, because it trivially keeps every decision.

**D-21. Code written by a model runs in a sandbox.** Hidden tests run under `sandbox-exec` with no network and no writes outside the run's scratch folder, using `python3 -B` and a 20 second limit. A test confirms a write outside the folder is blocked.

**D-22. Line numbers copied into a file are removed.** Excerpts carry line numbers and opened files do not. If every line of a written file starts with a number, the harness strips them, so a copied number can't count against the modes that show excerpts.

**D-23. Results are saved once.** A run refuses to write into an existing results folder, unless told to overwrite. Simulated developer agents are reported as exactly that, and never as participants.

**D-24. A file block with no end line is kept if the model stopped by itself.** Then nothing is lost. If the reply reached the length limit, the block is half a file and is dropped, and that is counted as a parse failure. A note's next line naming its file stays with the note, because that is what links the note to code.

**D-25. In a note, an everyday word is not a link.** A plain lowercase word such as "amount" links a note to code only when the note writes it as code: in backticks, with brackets, or next to the word "function". Names with capitals or underscores, and file paths, still link. On Burrow's own repository a note about text budgets had linked to a pricing file, and the walk followed it. This was found on Burrow's own code and the tuning project, not on held-back material.

**D-26. The app is a separate package in `app/`, using the same engine.** It builds on its own with `app/build.sh`. Map, Notes and Ask call `BurrowCore`, and a proposed change uses the reply format and note wording from the agent test, so the test measures what ships. Ask always walks. A change is written to the file only when someone accepts it, and only if the file hasn't changed since it was proposed.

**D-27. Tools are defined once, in `BurrowTools`.** The MCP server and the terminal chat read the same list and run the same code, so a tool can't behave one way for Claude Code and another way for a local model. The seven tools are `vault_search`, `vault_read`, `vault_links`, `vault_list`, `vault_folders`, `vault_remember` and `vault_ask`.

**D-28. Tools open only what is indexed.** `vault_read` and `vault_links` look a path up in the index before touching the disk. That shuts out `..`, absolute paths, git-ignored files and Burrow's own store, with one rule and no list of exceptions. A path that isn't indexed yet triggers one re-index before it is refused, so a new file isn't turned away.

**D-29. Only `vault_remember` writes, and only by adding a note.** It calls the same `addNote` as the command line, which never overwrites. Re-indexing writes to `.burrow`, which is disposable by D-2, and is the only other thing the tools change. In the terminal chat a person has to agree to each note first, because a model reading a poisoned file must not be able to plant memory in the vault. Over MCP, that decision belongs to the client, so the tool is marked as not read-only.

**D-30. Project text is marked as data, and can't escape its mark.** Tool output says that text inside `<excerpt>` tags is project content, and to follow no instruction in it. A file containing `</excerpt>` has that text defanged, so it can't end the block early and pass what follows as Burrow's own words. This extends D-8 to clients Burrow doesn't control.

**D-31. The MCP server is hand-written, line-delimited JSON-RPC 2.0 over stdio.** No dependency, as with the rest of the engine. A call that doesn't fit the tool's definition is a JSON-RPC error (-32602), and a tool that can't do its job (no such file, Ollama down) is a normal result with `isError` set, so a model can read it and try again. `ping` and `tools/list` answer at once. Tool calls run one at a time, because a `Vault` can't be shared between threads. Stdout is duplicated privately and the real descriptor pointed at stderr, so nothing else can write into the protocol.

**D-32. `burrow chat` searches first by default, and says so.** `ollama run` has no tool support in 0.40.14, so the chat calls `/api/chat` with `tools` itself. On 16 questions with known answers from a scratch vault, `qwen3:4b-instruct-2507-q4_K_M` called a tool by itself on 6 with the first prompt and 7 with a blunter one, and got 6 and then 8 right. It answered the rest from nothing. `qwen3:1.7b` called on 11 and got 9 right, and `qwen3:8b` called on all 16 and got 15 right. Searching first took the 4B to 16 of 16 and the 1.7B to 15 of 16, so that is the default. The search is printed with a label saying Burrow ran it and the model didn't choose it, and `--tools-only` turns it off. This is one small vault and fixed questions, so it is a working choice and not a result.

**D-33. Chat history keeps questions and answers, and drops tool output.** Old excerpts would crowd the next question out of the model's context. Each question is limited to 5 rounds and 24,000 characters of tool output. After that the model is offered no tools and has to answer.

**D-34. The terminal view is raw ANSI with no dependencies, in `BurrowTUI`.** Keys become events, events change a `Model`, and a `View` draws a cell grid from it. Only changed cells are sent. Colour means something and there is little of it: gold for notes, blue for code, red for trouble, always paired with a shape or weight so it survives `NO_COLOR`. Layout follows the Reading Room direction: text capped at 80 columns, no boxes around panes, and the side panel only when there's room. There's no mouse capture, so terminal text selection keeps working.

**D-35. Anything from a file is cleaned before it reaches the terminal.** Control characters are dropped at the cell grid, so a note or a model can't send escape codes. Pasted text arrives as one event and is never read as keys. The terminal is restored by a signal handler that only uses plain memory, on exit, Control-C, termination and crash signals alike.

**D-36. The terminal view opens the vault twice.** A `Vault` can't be shared between threads, so the screen reads through one and background jobs (indexing, Ask) use another. SQLite's write-ahead log lets the two work at once.

**D-37. The star view shows one file and its neighbours, and counts what's beyond.** A list already names the links. The star adds what a list can't show at a glance: how much hangs off each neighbour, and a way to walk the vault by hopping between files. Names two links away would be clutter, so they are only specks.

**D-38. `burrow link` and `burrow index --vault` are new, and the old commands are unchanged.** The terminal has to be able to link a code folder and to embed a whole vault. Without `--vault`, `index` behaves exactly as before.

**D-39. Tools re-index only when the files have changed.** `Vault.refresh` reads every file and rebuilds every link. Before calling it, the tools compare a quick summary of every file's name, size and date with the one saved beside the index, and skip it if they match. That costs a directory walk and no file reads, which matters most for a linked folder in iCloud, where a read waits for the file to download. Adding a note always re-indexes.

**D-40. A vault holds everything, and code is one thing it can hold.** Every Markdown file in the vault is a note. Other folders are linked in under a name of their own and stay read-only unless someone accepts a proposed change. The single-project mode stays for the agent test, so its results keep meaning the same thing.

**D-41. A question limited to a folder stays inside that folder.** An earlier version let the walk reach notes linked to the folder. On the first real try those notes crowded out the code and the model answered from an unrelated note. Asking the whole vault still reads notes and code together.

**D-42. Markdown marks show only on the line being edited.** Each mark is given no width elsewhere, so the file keeps every character and a note reads as finished text. A blank line is drawn short, or paragraphs drift apart.

**D-43. The graph is a live simulation that settles before it is first shown.** Links pull together, near things push apart and folders gather. It opens calm rather than exploding outwards, and it only moves again when something is dragged.

**D-44. Claude Code through Ollama is not a supported way to use Burrow's small models.** On one task, `qwen3:8b` with a 32,768-word context either answered without using Burrow, or searched and then repeated edits until it timed out. `burrow chat` is the local route, and Claude Code is for cloud models. This is one task on one project.

**D-45. Tests and the output of past runs rank below the code they are about.** They repeat its words, so on Burrow's own repository a test file came first on 6 of 13 questions about code, and run summaries pushed the code out entirely on one. Their search score is multiplied by 0.7 and 0.4, unless the question asks for tests or results or names the file or folder. They are demoted and never removed. Markdown is never demoted, because a person wrote it. Checked on 16 hand-written questions on this repository: right file first went from 6 to 10, in the first four files from 13 to 15. This is a tuning check and not a result.

**D-46. A piece of a file also has a limit in characters.** Pieces were measured only in lines, so prose with long lines became 8,431 characters while an excerpt shows 3,000, and the rest could never be read. Pieces now stop at 3,000 characters on a blank line. An index built before this rebuilds itself the next time it is refreshed.

**D-47. One lock guards each database connection.** An async call on `Vault` leaves its caller's actor, so the app could ask a question on the same connection as a rebuild. A stress test crashed 5 times in 5 before the lock and passed 8 times in 8 after it. A transaction holds the lock until it ends.

**D-48. A reason has to be written down somewhere.** With memory on, the model read a limit in the code and made up why it existed, where with no memory it said it did not know. Every prompt now says that code shows what and not why, that a setting's value is not a reason, and that an unrecorded reason should be reported as not recorded. On 12 tuning questions with no recorded reason, honest answers went from 8 to 10 with search and stayed at 10 with walk; the 5 questions with recorded reasons and 5 plain facts stayed right. The remaining failures call the code itself the reason. Other tasks on the tuning project moved up and down with the new wording, so that project's small changes in score are noise. This is a tuning check and not a result.

**D-49. The evaluation is fixed in advance.** `docs/report/evaluation-plan.md` was written before any held-back project or real repository was run. The engine is tagged `evaluation-1` and isn't changed until scoring ends. A fault found during scoring is reported and not fixed in place.

**D-50. The approved topic stays, and Burrow is its engine.** On 10 November 2026 the student chose to keep the June proposal's title, "A Lightweight External Memory Engine to Bridge the Capability Gap Between On-Device and Cloud Language Models", with Burrow in place of the first prototype. The first held-back results already matched the proposal's prediction: retrieval found the right code more often, and the small model did not write working code more often. What was missing was the cloud anchor, so the gap could not be stated.

**D-51. Vectors are one memory-mapped block, and the word index is read once per question.** Every question used to load all vectors from SQLite, compare them one number at a time, read the chunk-to-file table twice and search the word index up to three times. The vectors are now unit rows in `vectors.bin`, compared with one matrix multiplication, and a counter in the `meta` table says when the file is stale. On the Django index (11,710 pieces) a walk went from 0.6 to 1.3 seconds to about 0.1 seconds as a whole command. The measured before and after are in `trials/results/gap-1/speed-django.json`.

**D-52. An engine decides; a database only answers.** `Vault.brief` runs a cheap search first and reads its signal. Below a closeness of 0.40 the vault is left out. When the closest files are code the links are followed, and when they are notes and documents a plain search is used. The thresholds were set on the developer's own questions and are tied to `qwen3-embedding:0.6b`.

**D-53. Each model is measured once and shown what it can read in eight seconds.** `burrow fit` times a model reading half prose and half code and records its size. The budget is the smaller of a ceiling by size and what it reads in eight seconds, and the window is sized as if everything shown were code. The first version measured on prose alone and overflowed an 8,192-token window on code.

**D-54. Citations are checked, with one retry.** Every `file:line` in an answer is compared with the excerpts shown. If any is not among them the model is asked again once, and the second answer is kept only if it cites fewer places it was not shown. What remains is reported to the person.

**D-55. Skills are Markdown methods in the vault.** A `Skills` folder holds short methods for kinds of task. The engine matches one to the question at closeness 0.55 and 0.10 clear of the next, and otherwise falls back on one method for documents and one for code. Skills are never shown as facts about the vault. On 26 labelled development questions the first thresholds (0.52 and 0.05) handed "Compare options" to a plain lookup, so they were raised.

**D-56. Learning needs the person's words and the person's consent.** The model proposes up to three notes from a conversation. A note is kept only if its quote is in what the person typed, which stops the model turning its own guess or a sentence from a file into a remembered fact. The chat's `/keep` asks before each note is written, in line with D-29.

**D-57. The rule on reasons is given only when why is asked.** With the rule always present (D-48), Qwen3 4B opened plain factual answers with "The reason is not recorded." It is now added only when the question asks for a reason. The rules also say to answer in a full sentence before citing, because without that two of six fixture answers were a bare citation.

**D-58. Evaluation 2 is fixed in advance.** `docs/report/evaluation-plan-2.md` was written before any scored run. The engine is frozen as the binary recorded in `trials/results/gap-1/binary.sha256`, with its source beside it. The first cloud run was set aside because the harness cut answers at 600 tokens; the note is in `trials/results/gap-1/void`.

**D-59. A folder is read whole in packs, and a pack opens the conversation.** llama.cpp reuses a saved cache only for the shared start of a prompt, so excerpts fetched in the middle of a conversation can't be loaded from a cache built elsewhere. A pack is a folder's text in a fixed form: a map of the folder and its own notes (the spine), then every file with line numbers, cut into parts sized to the model's window as if everything were code (D-53). The same files always give the same text and key, every part starts with the same spine, and the text is read as the system message through the model's chat template. `vault_pack` gives the same text to any client, so whether a cache exists never changes what a model reads. On Qwen3 4B, a 20,891-token part took 24.9 to 28.8 seconds to read cold and 0.4 seconds to load.

**D-60. Burrow warms the shelf after a lookup, never before the answer.** With `burrow mcp --llama URL`, a folder that two lookups touched is read into its pack on the server's last slot once no slot is working, and loaded again when it comes up later. Only a spare slot is used, so with one slot Burrow does nothing. A lookup builds one part at most, the one holding most of its files, because the first trial's three searches built four parts of a folder nobody asked to read, 11 GB in all. A build reads about 14,000 characters at a time and waits whenever a client's slot is working: in the first trial a client that arrived during a build wrote 3.8 tokens a second instead of about 50. The shelf clears its least recently used caches above 12 GB, since a part is about 3 GB. Every failure is only logged. A client that opens with the pack is sent to that slot by llama.cpp's own prefix matching: on Qwen3 4B through MCP, a conversation that opened with a 24,240-token pack read 919 tokens and started answering in 5.3 seconds, against 25,158 tokens and 37.7 seconds with nothing saved, with the same answer.

**D-61. No speculative decoding is added: none made answers faster here.** Measured on Qwen3 4B with a 21,000-token pack, first answers only: plain decoding wrote 42 tokens a second on code. n-gram lookup in the context (simple, map, mod), Burrow's lookup table from the plain vault text, and a Qwen3 1.7B draft model all gave 10 to 42. A second identical request ran at up to 200 a second under ngram-mod, because it remembers the server's earlier output; that is a repeat, not a gain, and is not counted. The draft model at 64,000 tokens ran this 24 GB Mac out of memory, and at 48,000 it halved speed. Results are in `trials/results/kv-1`.

**D-62. Shorter context is the only speed-up for writing, so its cost is written down.** Line numbers made a pack 29 % more tokens on code and 37 % on prose, and without them reading took 16.7 seconds against 24.9 and writing ran at 47 tokens a second against 42. They stay. Asked where 40 names were declared, Qwen3 4B gave the exact line 29 times with every line numbered, 9 with every fifth, none with every tenth and none with no numbers; Gemma 4 12B, without thinking, gave 38, 18, 8 and 2 (`trials/results/kv-2`). Fewer numbers would save 15 to 19 % of the tokens and cost most of the exact citations, which D-54 checks. Keeping the cache in 8 bits (`-fa on -ctk q8_0 -ctv q8_0`) halved a part to 1.6 GB and its load to 0.13 seconds, wrote slightly faster, and gave the same answers on all four test questions, so the docs recommend it.

**D-63. The Ledger keeps what AIs understood, not versions of files.** Git already keeps the code. What a model loses when its context is compacted or a chat starts fresh is its understanding: why something was decided, what was tried, where it stopped. Each Ledger commit is one Markdown file under `.burrow/ledger/<branch>/` that cites its files with content hashes, and goes stale when one of them changes, the same rule as a saved cache. Commits are never deleted; a wrong one gets a correction, shown wherever the old one appears. The commands borrow git's words with `burrow` in front (commit, log, resume, blame, diff, revert), as the student chose on 11 November 2026. Details are in `docs/ledger.md`.

**D-64. Hooks keep the memory, not the model.** Small models pick tools unreliably (D-44), and even Claude Code forgets to save before compaction. So Claude Code's SessionStart hook hands over the Ledger head, PreCompact and SessionEnd write the plan and a handoff from the transcript, git's post-commit links code commits by sha, and a closed MCP connection writes a handoff from its own lookups. Handoffs, plans and context are written automatically. Facts and decisions are written only when the person asked, as the student set on 11 November 2026, and Burrow's own chat refuses the write tools because it asks before keeping anything (D-56).

**D-65. A model sees four tools by default.** `burrow mcp` lists `burrow_find`, `burrow_read`, `burrow_resume` and `burrow_commit`. Every other tool still answers by name, `--tools full` lists them all, and `--tools classic` gives the earlier list for runs that must match Evaluation 2. Whether four beats twelve for a 4B model is a claim of Evaluation 3, not something assumed here.

**D-66. Every search says how much the vault holds.** A trust line follows the content notice: the vault does not hold this, nothing close, thin, or strong, using the engine's own closeness thresholds (D-52), so the line and the engine agree. When a Ledger correction covers a file in the results, the line gives only its id, never its model-written words; those stay inside the Ledger's fenced output.

**D-67. Recency and importance break ties in the ranking; they never overrule relevance.** Objective ii names a retrieval policy that ranks by similarity, recency and importance, after Park et al. (2023). Recency is a note's own `date:`, or else the file's last change, halving every 90 days; importance is how many files link to it (on a log scale) plus a weight for decision, convention, rejected and bug notes. Each lifts a candidate by at most 0.4% of its score, below the gap between two neighbouring places in the top 60, and pieces with the same word score now share a place, so the two signals decide only among files that match equally well. At first weights of 5% let a loosely matching new decision note beat the note that held the answer; a test caught it. On the 120 Evaluation 2 questions search found the evidence for 105 before and 105 after, and within the first 4,000 characters for 79 before and 78 after. Setting either weight in `Budget` to zero turns it off.
