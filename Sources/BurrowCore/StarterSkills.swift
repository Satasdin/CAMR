/// The skills a new vault starts with. Each is a short method a small model can follow. They are ordinary
/// Markdown files once installed: edit them, delete them, or add your own beside them.
enum StarterSkills {
    static let all: [String: String] = [
        "Answer from documents.md": """
        ---
        kind: skill
        when: Answering a question about what a document, law, regulation, policy, manual, release note or note says. Examples: what does the Act require, what is the deadline for, which version added, what is the penalty for.
        needs: vault
        fallback: documents
        ---
        # Answer from documents

        1. Find the sentence in the excerpts that answers the question. Read it twice.
        2. Copy the exact figure, date, name or condition from that sentence. Do not round it or reword it.
        3. If the sentence has an exception or a condition ("unless", "where", "except", "subject to"), include it.
        4. Give the answer in the first sentence. Then name the file and line it came from.
        5. If the question needs more than one fact, find each one separately first, then put them together in one line.
        6. If two excerpts disagree, say so and give both with their files.
        7. If no excerpt contains the answer, say that plainly. Do not fill the gap from memory.
        """,
        "Combine several facts.md": """
        ---
        kind: skill
        when: Answering a question that needs two or more separate facts found in different places and then put together, compared or chained. Examples: which of the two is longer, does X apply given Y, what do A and B have in common.
        needs: vault
        ---
        # Combine several facts

        1. Split the question into the separate facts it needs. Write each as a short sub-question.
        2. Answer each sub-question from the excerpts alone, with its file and line.
        3. If one fact is missing, stop and say which one. Do not guess it.
        4. Only then combine them: add, compare, or apply one to the other. Show that step in one line.
        5. State the final answer in one sentence, using the exact figures and names you found.
        """,
        "Work a calculation.md": """
        ---
        kind: skill
        when: Solving a word problem or sum with arithmetic: counting, totals, percentages, rates, money, time, how many are left. Examples: how many eggs are left, how much does she earn in a week, what is 17 times 23.
        ---
        # Work a calculation

        1. List the quantities given, each with its unit.
        2. Say what is being asked for, with its unit.
        3. Work in small steps, one operation per line. Write every intermediate number.
        4. Watch the usual traps: "each" and "per", totals against differences, what is left against what was used, percent of what.
        5. Check the result by a second route or by putting it back into the problem.
        6. End with one line: "Answer: " and the number alone.
        """,
        "Explain code.md": """
        ---
        kind: skill
        when: Explaining how some code works: what a function, class, module, command or feature does, how two parts work together, or where something is implemented. Examples: how does the chunker cut a file, how are the rankings merged, what does this function return.
        needs: vault
        fallback: code
        ---
        # Explain code

        1. Start from where the thing is defined, not where it is used. Name the file and line.
        2. Say in one sentence what it is for.
        3. Walk through what it does in the order it runs: inputs, the main steps, what it returns or changes.
        4. Name the other files it depends on only if the excerpts show them.
        5. Quote real names, constants and values from the excerpts. Never invent a name.
        6. A reason is only a reason if a note or comment gives it. Otherwise say the reason is not recorded.
        """,
        "Fix a bug.md": """
        ---
        kind: skill
        when: Finding the cause of a bug and fixing it, from a bug report, an error message, a crash, a failing test or wrong behaviour. Examples: the command crashes when the folder is missing, this test fails, the total is wrong.
        needs: vault
        ---
        # Fix a bug

        1. Restate the failure in one line: what was done, what happened, what should have happened.
        2. Find the code that produces the wrong result. Name the file, the function and the line.
        3. Check the notes for an earlier decision or a rejected fix about this code. If a fix was rejected, do not offer it again.
        4. Explain the cause in one or two sentences, pointing at the exact line.
        5. Give the smallest change that fixes it. Keep the existing style and names.
        6. Say which test would prove it, or what to run to see the fix work.
        """,
        "Review a change.md": """
        ---
        kind: skill
        when: Reviewing a diff, a pull request or a proposed change for mistakes and risks. Examples: review this change, is this patch safe, what does this diff break.
        ---
        # Review a change

        1. Say in one line what the change is trying to do.
        2. Check it against the recorded decisions and conventions in the notes. Name any it breaks.
        3. Look for what the change did not touch but should have: callers, tests, other files that use the same name.
        4. List problems most serious first. For each: the file and line, what goes wrong, and with what input.
        5. Separate what must be fixed from what is only a preference.
        6. If nothing is wrong, say so in one line. Do not invent problems.
        """,
        "Plan a change.md": """
        ---
        kind: skill
        when: Planning how to add a feature or make a change across several files before writing code. Examples: how should I add export, plan the steps to support a new file type.
        needs: vault
        ---
        # Plan a change

        1. State the goal in one sentence and what "done" looks like.
        2. List the files that must change, each with the function or section involved. Use only files the excerpts show.
        3. Note any recorded decision or convention the change must respect.
        4. Order the steps so that each one leaves the project working.
        5. Name the riskiest step and how to check it.
        6. Say what you could not see and would need to read first.
        """,
        "Summarise.md": """
        ---
        kind: skill
        when: Summarising a note, a document, a meeting, a thread or a set of files. Examples: summarise the README, give me the key points of this note, what was decided in this meeting.
        needs: vault
        ---
        # Summarise

        1. Open with the single most important point in one sentence.
        2. Follow with three to five points, each one sentence, in order of importance.
        3. Keep every number, date, name and decision exactly as written.
        4. Leave out background the reader already has and anything said twice.
        5. End with what is still open or undecided, if anything.
        """,
        "Compare options.md": """
        ---
        kind: skill
        when: Choosing between two or more options, tools, designs or approaches. Examples: which is better, SQLite or JSON, should I use A or B, what are the trade-offs.
        ---
        # Compare options

        1. Name the options and the one thing the choice has to achieve.
        2. Pick three or four things that matter for this choice. Use the same ones for every option.
        3. For each option, say how it does on each, using facts from the excerpts where they exist.
        4. Mark anything you are assuming and were not shown.
        5. Recommend one option in one sentence, with the main reason and the main cost.
        """,
    ]
}
