"""Fixed prompt templates, one per (condition family, task family) (section 3.5.6).

Templates are data, not code paths: they are exported verbatim with every run
(DR-09) and identified by a content hash that is logged with each query, so a
template edit can never silently change a reported number.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

EMPTY_CONTEXT = "(none)\n"


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    body: str

    @property
    def template_id(self) -> str:
        return f"{self.name}@{hashlib.sha256(self.body.encode()).hexdigest()[:10]}"

    @property
    def uses_memory(self) -> bool:
        return "{context}" in self.body

    def render(self, question: str, context: str | None = None) -> str:
        if self.uses_memory:
            return self.body.format(question=question.strip(), context=context or EMPTY_CONTEXT)
        return self.body.format(question=question.strip())

    def fill(self, **fields: object) -> str:
        return self.body.format(**fields)


QA_BARE = PromptTemplate(
    "qa_bare",
    "Answer the question with a short phrase only. Do not explain.\n\n"
    "Question: {question}\n"
    "Answer:",
)

QA_MEMORY = PromptTemplate(
    "qa_memory",
    "Use the notes below if they are relevant. "
    "Answer the question with a short phrase only. Do not explain.\n\n"
    "Notes:\n{context}\n"
    "Question: {question}\n"
    "Answer:",
)

MATH_BARE = PromptTemplate(
    "math_bare",
    "Solve the problem. Show brief working, then give the final numeric answer "
    "on the last line in the form '#### <number>'.\n\n"
    "Problem: {question}\n",
)

MATH_MEMORY = PromptTemplate(
    "math_memory",
    "Use the notes below if they are relevant. Solve the problem. Show brief working, "
    "then give the final numeric answer on the last line in the form '#### <number>'.\n\n"
    "Notes:\n{context}\n"
    "Problem: {question}\n",
)

# Write-path templates (structured write policy and model-rated importance).
DISTIL = PromptTemplate(
    "distil",
    "Rewrite the passage below as one short factual note of at most {max_words} words. "
    "Keep every name, date and number exactly as written. Do not add facts that are not "
    "in the passage. Output only the note.\n\n"
    "Title: {title}\n"
    "Passage: {passage}\n"
    "Note:",
)

RATE_IMPORTANCE = PromptTemplate(
    "rate_importance",
    "On a scale of 1 to 10, how much specific factual information (names, dates, numbers, "
    "relations) does this note contain? Reply with a single integer.\n\n"
    "Note: {note}\n"
    "Rating:",
)

ALL_TEMPLATES = [QA_BARE, QA_MEMORY, MATH_BARE, MATH_MEMORY, DISTIL, RATE_IMPORTANCE]


def answer_template(task_type: str, with_memory: bool) -> PromptTemplate:
    if task_type == "reasoning":
        return MATH_MEMORY if with_memory else MATH_BARE
    return QA_MEMORY if with_memory else QA_BARE
