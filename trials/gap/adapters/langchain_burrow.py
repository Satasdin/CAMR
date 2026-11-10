"""Burrow as a LangChain retriever.

    from langchain_burrow import BurrowRetriever
    retriever = BurrowRetriever(vault="vault", store="work/store")
    documents = retriever.invoke("How deep is the borehole?")

Each Document is the lines Burrow chose from one file; metadata has path, start, end and reason.
"""
import json
import os
import subprocess
from typing import List

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

DEFAULT_BURROW = "/Users/p3wrky/Developer/burrow/.build/release/burrow"


class BurrowRetriever(BaseRetriever):
    vault: str
    store: str
    burrow_binary: str = DEFAULT_BURROW
    mode: str = "walk"
    timeout: int = 300

    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        done = subprocess.run(
            [self.burrow_binary, "find", self.vault, query, "--mode", self.mode, "--json", "--vault",
             "--store", self.store],
            capture_output=True, text=True, timeout=self.timeout)
        if done.returncode != 0:
            raise RuntimeError("burrow find failed: %s" % (done.stderr.strip() or done.stdout.strip())[-400:])
        reply = json.loads([line for line in done.stdout.splitlines() if line.strip().startswith("{")][-1])
        documents = []
        for excerpt in reply.get("excerpts", []):
            path = os.path.join(self.vault, excerpt["path"])
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    lines = handle.read().splitlines()
            except OSError:
                continue
            start, end = int(excerpt.get("start", 1)), int(excerpt.get("end", len(lines)))
            documents.append(Document(
                page_content="\n".join(lines[max(start - 1, 0):end]),
                metadata={"path": excerpt["path"], "start": start, "end": end, "reason": excerpt.get("reason"),
                          "note": excerpt.get("note")}))
        return documents
