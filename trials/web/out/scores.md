# Website trial: checks passed, 10 November 2026

Fixed checks in a real browser (`check.js`), the same for every page. Gemma 4 12B ran locally through Ollama; Claude is `claude-sonnet-5-5`.

| Brief | Checks | Gemma alone | Gemma, engine's brief | Gemma, skill + failure notes | Claude alone | Claude, engine's brief | Claude, skill + failure notes |
|---|---|---|---|---|---|---|---|
| Matatu fare splitter | 13 | 12 | 13 | 12 | 13 | 13 | 13 |
| Clinic queue board | 14 | 14 | 14 | 14 | 14 | 14 | 14 |
| Soma Vault landing page | 15 | 15 | 12 | 15 | 15 | 15 | 15 |
| Total | 42 | 41 | 39 | 41 | 42 | 42 | 42 |

Misses: Gemma alone and with skill + notes left the old result on screen after an invalid input (fare). With the engine's brief, Gemma's landing page had a JavaScript syntax error, so the pricing toggle and the phone menu did not work.
For every brief the engine handed over the "Build a web page" skill and left the vault out, so the note of known failures was not retrieved.
