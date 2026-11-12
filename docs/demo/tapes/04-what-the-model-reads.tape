Output "/Users/p3wrky/Developer/burrow/docs/demo/clips/04-what-the-model-reads.mp4"
Set Shell "bash"
Set FontSize 17
Set Width 1600
Set Height 1000
Set Padding 30
Set Theme "Builtin Dark"
Set TypingSpeed 30ms
Hide
Type "source ~/BurrowDemo/tapes/env.sh; cd ~/BurrowDemo; clear" Enter
Show
Sleep 1s
Type "# 1. Which parts of the vault answer the question: file, lines, and how each was found" Enter
Type "burrow find Notes 'breach notification deadline'" Enter
Wait+Line@30s /\$$/
Sleep 5s
Type "clear" Enter
Type "# 2. Exactly what the model is handed: short rules, then excerpts marked with file and line" Enter
Type "burrow brief Notes 'Within how many hours must a breach be reported?' --characters 2500 | head -28" Enter
Wait+Line@30s /\$$/
Sleep 8s
Type "clear" Enter
Type "# 3. A local model (Gemma 4 12B in Ollama) answers from it, citing the line, with time to first word and tokens read" Enter
Type "burrow ask Notes 'Within how many hours must a data controller report a breach to the Data Commissioner?' --model gemma4:12b" Enter
Wait+Line@180s /\$$/
Sleep 6s
