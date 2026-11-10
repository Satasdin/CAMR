#!/usr/bin/env python3
"""The developer's own labelled questions used to set the skill thresholds (floor 0.55, margin 0.10).
None of these is a scored task. Run from the repository root with Ollama up: prints each question's closest skill."""
import glob, json, math, re, urllib.request

def embed(texts):
    call = urllib.request.Request("http://127.0.0.1:11434/api/embed", data=json.dumps({"model": "qwen3-embedding:0.6b", "input": texts}).encode(),
                                  headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(call))["embeddings"]

def cosine(a, b):
    return sum(x * y for x, y in zip(a, b)) / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))

skills = {}
for path in sorted(glob.glob("trials/gap/vault/Skills/*.md")):
    text = open(path).read()
    skills[re.search(r"^# (.*)$", text, re.M).group(1)] = re.search(r"^when: (.*)$", text, re.M).group(1)
names = list(skills)
skill_vectors = embed([f"{name}. {skills[name]}" for name in names])

QUESTIONS = [
    ("In the Burrow project, what is the default number of hops the walk follows?", None),
    ("What is the default value of the hops setting?", None),
    ("Which file defines the Budget struct?", None),
    ("Under the Kenya Data Protection Act, who appoints the Data Commissioner?", "Answer from documents"),
    ("Within how many hours must a breach be reported to the Data Commissioner?", "Answer from documents"),
    ("What does SQLite 3.54.0 change about the default page size?", "Answer from documents"),
    ("Which Python 3.15 feature replaces the old import hook?", "Answer from documents"),
    ("Why did Burrow choose reciprocal rank fusion?", None),
    ("How does Burrow merge the word ranking and the meaning ranking?", "Explain code"),
    ("Explain how the chunker cuts a file into pieces", "Explain code"),
    ("What does the function bestChunk return when no symbol is given?", "Explain code"),
    ("The index command crashes with a missing folder, find the cause and fix it", "Fix a bug"),
    ("test_login fails with KeyError 'user', what is wrong?", "Fix a bug"),
    ("Review this diff: it removes the lock around the cache", "Review a change"),
    ("Plan the steps to add PDF support to the scanner", "Plan a change"),
    ("Summarise the README", "Summarise"),
    ("Give me the key points of the Data Protection Act part 4", "Summarise"),
    ("Which is better for the index, SQLite or a JSON file?", "Compare options"),
    ("Should I use Chroma or Burrow for my notes?", "Compare options"),
    ("A farmer has 12 crates with 30 eggs each and sells two thirds. How many eggs are left?", "Work a calculation"),
    ("Janet earns 18 dollars an hour and works 35 hours. She pays 20 percent tax. What does she take home?", "Work a calculation"),
    ("What is 17 times 23 plus 9?", "Work a calculation"),
    ("What is the capital of France?", None),
    ("Write a haiku about rain", None),
    ("Does the registration fee for a small data processor differ from that of a large one, and by how much?", "Combine several facts"),
    ("Is the notification deadline in the Act the same as the one in the General Regulations?", "Combine several facts"),
]
INSTRUCTION = "Instruct: Given a request, find the description of the kind of task it is\nQuery: "
FLOOR, MARGIN = 0.55, 0.10
vectors = embed([INSTRUCTION + question for question, _ in QUESTIONS])
accepted = wrong = 0
for (question, wanted), vector in zip(QUESTIONS, vectors):
    ranked = sorted(((cosine(vector, other), name) for other, name in zip(skill_vectors, names)), reverse=True)
    taken = ranked[0][0] >= FLOOR and ranked[0][0] - ranked[1][0] >= MARGIN
    accepted += taken
    wrong += taken and wanted is None
    print(f"{ranked[0][0]:.2f} {ranked[0][0] - ranked[1][0]:+.2f} {'TAKEN' if taken else '     '} {ranked[0][1]:22} wanted {wanted or '-':22} | {question[:60]}")
print(f"{accepted} matched, {wrong} of them on a question that wanted no skill")
