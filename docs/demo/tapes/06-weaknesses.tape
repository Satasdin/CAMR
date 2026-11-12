Output "/Users/p3wrky/Developer/burrow/docs/demo/clips/06-weaknesses-burrow-covers.mp4"
Set Shell "bash"
Set FontSize 17
Set Width 1600
Set Height 1000
Set Padding 30
Set Theme "Builtin Dark"
Set TypingSpeed 30ms
Hide
Type "cp ~/BurrowDemo/Notes/Law/act-part-04b-obligations-and-breach.md /tmp/act04b.bak; source ~/BurrowDemo/tapes/env.sh; cd ~/BurrowDemo; clear" Enter
Show
Sleep 1s
Type "# Weakness 1: documents pasted in front of every question can wreck a model's reasoning" Enter
Type "echo $MATH" Enter
Type "# Plain retrieval, what most memory tools do: excerpts first, then the question" Enter
Type 'burrow ask Notes "$MATH" --mode search --model gemma4:12b | head -3' Enter
Wait+Line@180s /\$$/
Sleep 3s
Type "# Burrow's engine first decides whether the vault is needed at all" Enter
Type 'burrow ask Notes "$MATH" --mode engine --model gemma4:12b' Enter
Wait+Line@180s /\$$/
Sleep 6s
Type "clear" Enter
Type "# Weakness 2: making an answer up when the facts are not there. The vault holds Kenyan law, not Ugandan" Enter
Type 'burrow ask Notes "$UGANDA" --mode engine --model gemma4:12b' Enter
Wait+Line@180s /\$$/
Sleep 6s
Type "clear" Enter
Type "# Weakness 3: memory that goes stale without anyone noticing. Someone edits the Act the decision rests on" Enter
Type "echo 'Amended: the notice period is now 24 hours.' >> Notes/Law/act-part-04b-obligations-and-breach.md" Enter
Type "burrow log Notes --limit 1" Enter
Wait+Line@30s /\$$/
Sleep 6s
Hide
Type "cp /tmp/act04b.bak ~/BurrowDemo/Notes/Law/act-part-04b-obligations-and-breach.md" Enter
