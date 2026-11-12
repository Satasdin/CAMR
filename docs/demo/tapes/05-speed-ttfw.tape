Output "/Users/p3wrky/Developer/burrow/docs/demo/clips/05-speed-time-to-first-word.mp4"
Set Shell "bash"
Set FontSize 17
Set Width 1600
Set Height 1000
Set Padding 30
Set Theme "Builtin Dark"
Set TypingSpeed 30ms
Hide
Type "source ~/BurrowDemo/tapes/env.sh; cd ~/BurrowDemo; Q='Within how many hours must a data controller notify the Data Commissioner of a breach?'; clear" Enter
Show
Sleep 1s
Type "# Every new chat makes a local model re-read the same documents before its first word." Enter
Type "# Burrow keeps that reading, the model's working memory, on the SSD: the shelf." Enter
Type "burrow kv Notes list" Enter
Wait+Line@30s /\$$/
Sleep 5s
Type "clear" Enter
Type "# Cold: Qwen3 4B in llama.cpp reads the Act from the start" Enter
Type 'kvq --cold' Enter
Wait+Line@120s /\$$/
Sleep 4s
Type "# Warm: Burrow loads the saved working memory from disk; the model reads only the question" Enter
Type 'kvq' Enter
Wait+Line@120s /\$$/
Sleep 6s
