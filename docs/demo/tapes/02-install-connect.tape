Output "/Users/p3wrky/Developer/burrow/docs/demo/clips/02-install-and-connect.mp4"
Set Shell "bash"
Set FontSize 20
Set Width 1600
Set Height 900
Set Padding 30
Set Theme "Builtin Dark"
Set TypingSpeed 35ms
Hide
Type "cd ~/BurrowDemo/project && claude mcp remove burrow >/dev/null 2>&1; export PS1='$ ' PATH=$HOME/.local/bin:$PATH && cd ~/BurrowDemo/project && clear" Enter
Show
Sleep 1s
Type "# 1. Install Burrow: one command, checksum-verified, from the GitHub release" Enter
Sleep 1s
Type "curl -fsSL https://github.com/Satasdin/CAMR/releases/latest/download/install.sh | sh" Enter
Wait+Line@60s /\$$/
Type "# 2. Index the vault: a folder of your own notes, documents and code" Enter
Type "burrow index ~/BurrowDemo/Notes --vault" Enter
Wait+Line@300s /\$$/
Type "# 3. Connect it to your AI. Claude Code here; OpenCode, LM Studio and Ollama work the same way" Enter
Type "claude mcp add burrow -- burrow mcp ~/BurrowDemo/Notes" Enter
Wait+Line@30s /\$$/
Type "claude mcp get burrow" Enter
Wait+Line@60s /\$$/
Type "# Burrow is now a memory every Claude Code session in this folder can read" Enter
Sleep 4s
