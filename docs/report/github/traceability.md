
Table T2 traces each requirement to the part that implements it and the test that verifies it.

!tab Table T2: Traceability from requirement to component and test
!widths 1.05,0.8,2.1,1.2,1.15
| Requirement | Objective | Component | Test case | Result |
| FR-01 | iii | Vault, Scanner, Chunker | TC-01 | Pass |
| FR-02 | ii, iii | Retrieval, Index | TC-02 | Pass |
| FR-03 | ii, iii | Retrieval | TC-03 | Pass |
| FR-04 | ii | Engine.brief | TC-04, TC-05 | Pass |
| FR-05 | ii | Skills, Engine.brief | TC-06 | Pass |
| FR-06 | ii, v | Fit | TC-07 | Pass |
| FR-07 | iii | Engine.engage | TC-08 | Pass |
| FR-08 | ii | Engine.engage | TC-09 | Pass on the command line only |
| FR-09 | ii | Engine.lessons, keep | TC-10 | Pass in the terminal chat |
| FR-10 | iii | Engine.brief, BurrowMCP | TC-11 | Pass |
| NFR-01 | iii | Ollama | Inspection | Pass |
| NFR-02 | iii | Rebuildable index | TC-12 | Pass |
| NFR-03 | iii | Asking, ProjectContent | Automated tests | Pass on the tools path |
| NFR-04 | iv | Harness | Table 5.7 | Pass |
| NFR-05 | iii | Database | Inspection | Pass |
| NFR-06 | iii | Swift package | 212 automated tests | Pass on one machine |
| DR-01 | iii | Vault, linked folders | TC-18 | Pass |
| DR-02 | iii | Database, Index | TC-19 | Pass |
| DR-03 | ii | keep | TC-10 | Pass |
| DR-04 | iv | Harness | TC-20 | Pass |
| IR-01 | iii | Mac app, conversation page | TC-08 | Pass |
| IR-02 | iii | Ollama, VaultTools | TC-21 | Pass |
| IR-03 | iii | BurrowMCP | TC-11 | Pass |
| IR-04 | iii | Vault | TC-22 | Pass |

