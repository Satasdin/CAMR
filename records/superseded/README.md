# Superseded records

Kept, not deleted, because the guide asks for failed runs to be kept beside their retests.

- `221549-student-s1-errands-bare-27b.json` and `222527-student-s1-errands-camr-27b.json`: the 27B's first errands
  (3 November 2026). Every task scored as "no tool call", because the parser read only Qwen3's JSON tool calls
  and Qwen3.8 writes `<function=…><parameter=…>`. The parser was fixed and these were rerun (DECISIONS.md E-28).
