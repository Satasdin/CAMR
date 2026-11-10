# Acknowledgements

The author acknowledges the guidance of the project supervisor, Tiberius Tabulu, of the School of Computing and Engineering Sciences at Strathmore University. The feedback given at the Sprint II review of 5 November 2026 changed the direction of this project and is recorded in Appendix 2. The author also acknowledges the maintainers of the open-source projects and the authors of the public dataset on which the evaluation depended.

# Abstract

Local language models let a developer use AI without uploading private code, but each session starts with no knowledge of the project, and the reasons behind code are rarely written in the code. This study aimed to develop and evaluate a private, on-device vault that gives local language models a lasting memory of notes and software projects. Burrow, a Mac application with a terminal version and a Model Context Protocol server, treats Markdown notes as a vault, links code folders, and gives a local Ollama model only the excerpts a question needs. Automated tests, simulated developer agents and real bug fixes compared no memory, plain search and link walking on a frozen version. All 186 automated tests passed; three defects remained open. On 101 real bug fixes in four Python repositories, walk mode, which reads one piece per file and follows links, reached a changed file 72 times against 59 for search (p = 0.002). A 3,833-file repository was indexed in under six minutes. On held-back synthetic projects, memory did not measurably help: the main model passed 5, 5 and 6 of 18 sessions under no memory, search and walk, and seven of nine sessions that depended on earlier decisions ended with code that crashed or no usable file. The study shows that walk mode retrieved more of the right code within the same limit, and that retrieval alone does not make a small model a dependable developer. Usability remains untested.

***Keywords: Local Language Models, On-Device Vault, Markdown Notes, Link Walking, Retrieval, Model Context Protocol, Simulated Developer Agents***

# Table of Contents

!toc TOC \o "1-3" \h \z \u

# List of Figures

!toc TOC \h \z \t "FigCaption,1"

# List of Tables

!toc TOC \h \z \t "TabCaption,1"

# List of Equations

!toc TOC \h \z \t "EqCaption,1"

# List of Abbreviations

AI - Artificial Intelligence
API - Application Programming Interface
BM25 - Best Matching 25 (a word-search ranking function)
DEF - Defect identifier
DR - Data requirement
FR - Functional requirement
FTS5 - Full-Text Search version 5 (SQLite)
HTTP - Hypertext Transfer Protocol
IEC - International Electrotechnical Commission
IEEE - Institute of Electrical and Electronics Engineers
IR - Interface and integration requirement
ISO - International Organization for Standardization
JSON-RPC - JavaScript Object Notation Remote Procedure Call
MCP - Model Context Protocol
NFR - Non-functional requirement
OOAD - Object-Oriented Analysis and Design
SWE-bench - Software Engineering benchmark
TC - Test case identifier
UML - Unified Modeling Language
UTF-8 - Unicode Transformation Format, 8-bit
XML - Extensible Markup Language
YAML - YAML Ain't Markup Language
