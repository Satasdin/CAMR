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