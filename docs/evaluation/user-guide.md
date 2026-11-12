# User guide

How to install and use Burrow: the app, the terminal, and other programs through MCP.


**What is needed.** A Mac with Ollama. Pull the models with ollama pull gemma4:12b and ollama pull qwen3-embedding:0.6b. Section 5.2.3 gives the one-command install from a tagged release; to build from source, run swift build -c release in the project folder and app/build.sh for the app.

**Using the app.**

i) Choose a folder as the vault. An existing Obsidian vault works as it is.
ii) Write notes in the centre pane and link notes with [[. A note's properties are shown as fields above its text, and holding Command over a link previews the note.
iii) To add code, choose Add, then Link a Folder.
iv) Open the graph to see how notes link, and search from the sidebar.
v) Open Programs to connect a model or tool, such as Claude Code, LM Studio or Ollama, through the MCP server: press Connect, then Copy, or Add for Me to write the setting into the program. Its conversations then appear under Conversations as it works, and what it understood appears in the Ledger.

**Using the terminal.**

i) burrow index <vault> --vault builds the index.
ii) burrow fit <vault> --model gemma4:12b measures the model once.
iii) burrow ask <vault> "question" --mode engine --model gemma4:12b answers through the engine.
iv) burrow chat <vault> opens a chat, and burrow tui <vault> the full-screen terminal view.
v) burrow resume <vault> prints where the last session stopped, for any model to carry on.

**Using Burrow from another model or tool.** burrow brief <vault> "task" --json returns the prepared prompt for any model. For an MCP client, run burrow mcp <vault>; by default it offers burrow_find, burrow_read, burrow_resume and burrow_commit. A client that is a cloud service sends what it reads to that service.

**Known limitations.** Burrow runs on macOS only. The check with retry runs only on burrow ask --mode engine; the chat and MCP do not check. The app does not ask questions itself; the program connected to the vault does.

