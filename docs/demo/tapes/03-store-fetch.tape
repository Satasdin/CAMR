Output "/Users/p3wrky/Developer/burrow/docs/demo/clips/03-memory-stored-and-fetched.mp4"
Set Shell "bash"
Set FontSize 18
Set Width 1600
Set Height 1000
Set Padding 30
Set Theme "Builtin Dark"
Set TypingSpeed 30ms
Hide
Type "rm -rf ~/BurrowDemo/Notes/.burrow/ledger ~/BurrowDemo/Notes/.burrow/sessions/*; source ~/BurrowDemo/tapes/env.sh; clear" Enter
Show
Sleep 1s
Type "# Session 1: ask Claude Code. Burrow fetches from the vault, and the decision is kept in its Ledger" Enter
Sleep 1s
Type "c 'From my Burrow vault: within how many hours must a data controller in Kenya report a breach to the Data Commissioner? Name the file. Then keep this decision in the Ledger, citing it: Our runbook targets 48 hours, inside the 72-hour legal limit.'" Enter
Wait+Line@180s /\$$/
Sleep 2s
Type "# What was stored: a Ledger commit that cites the file it rests on" Enter
Type "burrow log ~/BurrowDemo/Notes --limit 1" Enter
Wait+Line@30s /\$$/
Sleep 3s
Type "# Session 2: a brand-new Claude Code session. No chat history; the memory is Burrow" Enter
Sleep 1s
Type "c 'New session. What did we decide about our breach notification target, and why? It is saved in Burrow.'" Enter
Wait+Line@180s /\$$/
Sleep 5s
