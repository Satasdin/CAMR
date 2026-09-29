"""Write policies (FR-01): turn source text into candidate notes.

* ``VerbatimWritePolicy`` - overlapping token-window chunks (the control).
* ``StructuredNoteWritePolicy`` - the local model distils each passage into one
  short declarative note (the treatment), trading ingestion-time compute for
  denser notes at read time.

Both prefix the passage title, because in the benchmarks the title *is* the
entity the passage is about and is often absent from the passage body.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from camr.memory.note import CandidateNote, Document
from camr.models.prompt import DISTIL
from camr.models.runner import GenerationError, ModelRunner
from camr.models.tokenizer import RegexTokenizer, Tokenizer


class WritePolicy(ABC):
    name: str

    def __init__(self, note_type: str):
        self.note_type = note_type

    @abstractmethod
    def distil(self, doc: Document) -> list[CandidateNote]: ...


class VerbatimWritePolicy(WritePolicy):
    name = "verbatim"

    def __init__(self, tokenizer: Tokenizer, note_type: str = "verbatim", chunk_tokens: int = 96, overlap: int = 16):
        super().__init__(note_type)
        self.tokenizer = tokenizer
        self.chunk_tokens = chunk_tokens
        self.overlap = overlap
        self._spanner = tokenizer if isinstance(tokenizer, RegexTokenizer) else RegexTokenizer()

    def distil(self, doc: Document) -> list[CandidateNote]:
        text = doc.text.strip()
        prefix = f"{doc.title}: " if doc.title else ""
        if not text:
            return [CandidateNote("", self.note_type)]
        spans = self._spanner.spans(text)
        if len(spans) <= self.chunk_tokens:
            return [CandidateNote(prefix + text, self.note_type)]
        out: list[CandidateNote] = []
        step = self.chunk_tokens - self.overlap
        for start in range(0, len(spans), step):
            end = min(start + self.chunk_tokens, len(spans))
            chunk = text[spans[start][0] : spans[end - 1][1]]
            out.append(CandidateNote(prefix + chunk, self.note_type))
            if end == len(spans):
                break
        return out


_LEADS = re.compile(r"^(note|summary|fact)\s*:\s*", re.IGNORECASE)


class StructuredNoteWritePolicy(WritePolicy):
    name = "structured"

    def __init__(self, runner: ModelRunner, note_type: str = "structured", max_words: int = 60):
        super().__init__(note_type)
        self.runner = runner
        self.max_words = max_words

    def distil(self, doc: Document) -> list[CandidateNote]:
        if not doc.text.strip():
            return [CandidateNote("", self.note_type)]
        prompt = DISTIL.fill(max_words=self.max_words, title=doc.title or "(untitled)", passage=doc.text.strip())
        try:
            out = self.runner.generate(prompt).text
        except GenerationError as exc:
            # Returned as a failed candidate so the rejection is logged with provenance.
            return [CandidateNote("", self.note_type, error=str(exc))]
        note = " ".join(line.strip() for line in out.strip().splitlines() if line.strip())
        note = _LEADS.sub("", note).strip().strip('"').strip()
        if note and doc.title and doc.title.casefold() not in note.casefold():
            note = f"{doc.title}: {note}"
        return [CandidateNote(note, self.note_type)]
