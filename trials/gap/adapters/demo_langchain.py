#!/usr/bin/env python3
"""A small LangChain chain with Burrow as its memory: retriever -> prompt -> local model.

    python adapters/demo_langchain.py "How deep is the Tumaini borehole?" \
        --vault fixture/vault --store fixture/store
"""
import argparse
import json
import os
import sys
import urllib.request

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from langchain_burrow import DEFAULT_BURROW, BurrowRetriever  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--vault", required=True)
    parser.add_argument("--store", required=True)
    parser.add_argument("--burrow", default=DEFAULT_BURROW)
    parser.add_argument("--mode", default="walk")
    parser.add_argument("--model", default="qwen3:4b-instruct-2507-q4_K_M")
    args = parser.parse_args()

    retriever = BurrowRetriever(vault=os.path.abspath(args.vault), store=os.path.abspath(args.store),
                                burrow_binary=args.burrow, mode=args.mode)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer from the excerpts below. If they do not contain the answer, say you don't know."),
        ("human", "{excerpts}\n\nQuestion: {question}"),
    ])

    def paste(documents):
        return "\n\n".join("[%s lines %s-%s]\n%s" % (d.metadata["path"], d.metadata["start"], d.metadata["end"],
                                                     d.page_content) for d in documents)

    def ollama(prompt_value):
        roles = {"system": "system", "human": "user", "ai": "assistant"}
        messages = [{"role": roles[m.type], "content": m.content} for m in prompt_value.to_messages()]
        if "qwen3" in args.model.lower():
            messages[-1]["content"] += "\n\n/no_think"
        body = json.dumps({"model": args.model, "stream": False, "messages": messages,
                           "options": {"num_ctx": 8192, "temperature": 0}}).encode("utf-8")
        request = urllib.request.Request("http://localhost:11434/api/chat", data=body,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read())["message"]["content"]

    used = []

    def remember(documents):
        used.extend(documents)
        return documents

    chain = ({"excerpts": retriever | RunnableLambda(remember) | RunnableLambda(paste),
              "question": RunnablePassthrough()}
             | prompt | RunnableLambda(ollama) | StrOutputParser())
    print(chain.invoke(args.question).strip())
    print("\nFiles used:")
    for document in used:
        print("  %s lines %s-%s (%s)" % (document.metadata["path"], document.metadata["start"],
                                         document.metadata["end"], document.metadata["reason"]))


if __name__ == "__main__":
    main()
