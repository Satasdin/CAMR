CAMR Personal: your model, a memory that grows
==============================================

1. Install Ollama (https://ollama.com/download) and open it.
2. Pull a chat model in a terminal, for example:   ollama pull qwen2.5:1.5b
3. Start CAMR Personal:
     Windows:  double-click camr-personal.exe
               (if SmartScreen warns: More info -> Run anyway; the download is not code-signed yet)
     macOS:    double-click camr-personal; the first time, right-click -> Open
               (or run: xattr -d com.apple.quarantine camr-personal)
     Linux:    ./camr-personal
   Your browser opens at http://127.0.0.1:8502. On first run, click "Download memory model".
   Keep the window that opened while you use CAMR; close it (or press Ctrl+C) to quit.

Everything stays on your computer in the .camr folder in your home directory.
Guide and source: https://github.com/Satasdin/CAMR (docs/APP.md). MIT licence.
