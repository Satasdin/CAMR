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