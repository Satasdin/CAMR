# Usability check (to run before the defence)

The guide's Sprint III asks for each module to be reviewed "with someone representative of the intended users", who
completes the task "without coaching", with task success, confusion and time recorded, and the important issues
corrected and retested. No one other than the developer has used Burrow yet (Section 5.9.6), so this is the one
evaluation the report still lacks. Nothing here may be filled in except from real sessions.

## Who

Three to five people who use an AI assistant for study or work and keep notes or code on a laptop: classmates are fine.
Record only a first name or a code (P1, P2…), their course, and whether they have used a local model before. Ask
their permission to note what they do; record no screen unless they agree.

## Set-up

- The Mac with Burrow 1.x installed, Ollama running with gemma4:12b, and OpenCode set up with the `burrow` agent.
- A copy of the evaluation vault (Law, Project, Skills, Software), opened in the app.
- A timer. This sheet.

Say only: "This is Burrow, a private memory for AI on your own laptop. I'll give you some tasks. Think aloud; I can't
help, and anything that goes wrong is the app's fault, not yours."

## Tasks

| # | Task given to the person | Success means | Requirement |
|---|---|---|---|
| T1 | "Find the note about how long a company has to report a data breach in Kenya, and open it." | The note open in the editor | FR-01, IR-01 |
| T2 | "Write a new note saying the defence is on 23 November, link it to the Project folder's plan, and tag it #deadline." | Note saved with a working [[link]] and the tag | FR-02 |
| T3 | "Connect OpenCode to this vault." (Programs page) | OpenCode shows Connected, or the setup line copied into its settings | IR-02 |
| T4 | "In OpenCode, ask: within how many hours must a breach be reported? Then go back to Burrow and find which files the model read." | The conversation page open, the breach-notification file identified | IR-01, FR-07 |
| T5 | "Keep the answer as a decision so the next model knows it." | A Ledger commit of kind decision citing the file | DR-03 |
| T6 | "Something changed in the breach note. Find out which kept decision may now be out of date." | The stale commit identified on the Ledger page | DR-03 |

## Record per person and task

| Person | Task | Done without help? (yes / with a hint / no) | Time (s) | Errors or confusion observed, in their words where possible |
|---|---|---|---|---|
| P1 | T1 | | | |

After all tasks, the ten System Usability Scale statements (Brooke, 1996), each scored 1 (strongly disagree) to 5
(strongly agree), and two open questions: "What was hardest?" and "What would make you use this?"

## After the sessions

1. Count task success per task, median time, and the SUS score per person (standard scoring: odd items score − 1,
   even items 5 − score, sum × 2.5) with the mean and range. With five people this is indicative only; say so.
2. List each usability problem seen by more than one person, fix the important ones, and run that task again with one
   person. Record the fix and the retest.
3. Add the results to Section 5.6 as Table 5.x "Usability check with N people", remove "no person other than the
   developer used the application" from 5.9.6 and 6.2, and add a row to the feedback matrix and the AI-use log.
