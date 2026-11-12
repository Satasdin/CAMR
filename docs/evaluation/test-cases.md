# Test cases and results

The full test record behind Section 5.6 of the report. Each case names the requirement it verifies; [traceability.md](traceability.md) traces each requirement to its component.


**Table T1: Test cases and results**

| Test ID | Requirement | Scenario and test data | Expected result | Actual result and evidence | Verdict |
|---|---|---|---|---|---|
| TC-01 | FR-01 | A vault indexed twice, then with one file changed and one removed | Nothing rebuilt the second time; old words gone the third time | As expected; test log | Pass |
| TC-02 | FR-02 | A question whose words are absent from the right file | The file is found by meaning | As expected; test log | Pass |
| TC-03 | FR-03 | A question naming only the first of three linked files | The third file is reached by following links | As expected; test log | Pass |
| TC-04 | FR-04 | A question the vault knows nothing about | The vault is left out | Left out; the model received only the question; test log | Pass |
| TC-05 | FR-04 | The 50 reasoning problems of Section 5.5, on the frozen program | The vault is left out | Left out on 50 of 50; saved results | Pass |
| TC-06 | FR-05 | A sum, with a calculation skill and a documents skill in the vault | The calculation skill and no excerpts | As expected; test log | Pass |
| TC-07 | FR-06 | A fast small model, a fast large model and a slow large model | 8,000, 24,000 and 6,400 characters | As expected; test log | Pass |
| TC-08 | FR-07, IR-01 | A question on the command line; a question about a regulation asked by Gemma 4 12B in OpenCode through MCP | An answer naming file and line, with the decision line; in the app, each lookup and the files read | As in Figures 5.3 and 5.6 | Pass |
| TC-09 | FR-08 | An answer citing a file it was not shown, with a scripted model | One retry; the better grounded answer kept | As expected; test log | Pass |
| TC-10 | FR-09, DR-03 | Three proposed notes, one quoting words the person never typed; a note kept with and without agreement | Only the two backed by the person's words offered; nothing written without agreement | As expected; test log | Pass |
| TC-11 | FR-10, IR-03 | vault_prepare called through MCP; a tool called before initialising | The decision and excerpts, no chat model called; the early call refused | As in Figure 5.10; test log | Pass |
| TC-12 | NFR-02 | The index deleted and rebuilt | No note lost; same pieces and links | As expected; test log | Pass |
| TC-13 | NFR-01 | Inspection of the model client's source | Local model calls go to 127.0.0.1 | Default address 127.0.0.1:11434 in the source | Pass |
| TC-14 | NFR-03 | Excerpts returned by the search tool | Marked as material to read, with the notice | As expected on the tools path; test log | Pass on the tools path |
| TC-15 | NFR-04 | The 2,520 saved answer records checked by script | Tokens read and written and seconds on every record | Present on all; retrieval time absent only on the 170 cloud-alone records, which retrieve nothing | Pass |
| TC-16 | NFR-05 | Inspection of the storage code | One database file, a vector copy and two settings files; no server process | As expected | Pass |
| TC-17 | NFR-06 | swift test on the frozen source; the package file inspected | 212 tests pass; no third-party package | As expected; test log | Pass on one machine |
| TC-18 | DR-01 | A change attempted on a linked folder | The folder can be read and is not changed | As expected; test log | Pass |
| TC-19 | DR-02 | Inspection of the index tables against Figure 4.8 | File, lines, text and at most one vector per piece | As expected | Pass |
| TC-20 | DR-04 | The key-checking scripts; the location of the questions | Keys found in the source text and absent from their questions; questions outside the vault | As expected; key-checking script | Pass |
| TC-21 | IR-02 | Ollama unreachable during a search and during an answer | Search continues on words; the failure is reported | As expected; test log | Pass |
| TC-22 | IR-04 | A vault with links in double square brackets and Obsidian's own settings folder | The links join the notes; the settings are left out | As expected; test log. Not opened in Obsidian itself | Pass on format |
| TC-23 | IR-05 | The published install command run into an empty folder with the application option; the landing page and its download link fetched | Program and application installed, checksums pass, the program indexes a vault; page and link return successfully | As expected. The browser download on a second computer was not tried | Pass on one machine |
