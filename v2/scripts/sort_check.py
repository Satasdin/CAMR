"""How well does "Auto" put a told fact on the right shelf? Hand-labelled statements, scored against the real embedder
and the real reader. Nothing here is a memory benchmark; it measures the shelf choice alone.

    .venv/bin/python scripts/sort_check.py             # the tuning set
    .venv/bin/python scripts/sort_check.py --held      # the held-back sets: scored once, after tuning is finished

The labels were written before any method was scored. TUNE may be looked at while changing the sorter; HELD and OWN
may not: a change made because of them would make their score meaningless.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from camr_engine import shelves
from camr_engine.models import Embedder, Reader

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"

SIX = (
    ("Writing", "How you write: your style, words you use and avoid, how you sign off, letters, drafts and emails."),
    ("Study", "Studying: courses, lectures, slides, exams, revision, topics you keep getting wrong."),
)
OWN_SHELVES = (
    ("Cafe", "The cafe I run: its menu, staff, suppliers and opening hours."),
    ("Garden", ""),  # a shelf made with a name and nothing else
    ("Car", "My car: servicing, fuel, repairs and insurance."),
)

TUNE = [
    # the demo life, as told in scripts/demo_life.py
    ("My sister Amina moved to Nakuru last week, and her birthday is on 14 March.", "personal"),
    ("Mama Wanjiru's birthday is on 13 November. Her old kikoy is worn out and she wants a blue one for church.", "personal"),
    ("My friend Otieno works at the county office and prefers calls after 6 pm.", "personal"),
    ("Kevin handles payroll at work and his extension is 209.", "projects"),
    ("Ms Achieng is the hiring manager for the data team. She signs her emails 'Ms', with no full stop.", "projects"),
    ("My rent is KSh 25,000 a month, paid on the 28th.", "personal"),
    ("The matatu fare to Kitengela is KSh 100.", "personal"),
    ("The water bill is due on the 10th of each month.", "personal"),
    ("I go to the gym on Mondays and Wednesdays.", "personal"),
    ("I pass the fabric shops on Moi Avenue on Tuesday evenings.", "personal"),
    ("The shop site's cart total must always round to whole shillings: never show cents.", "coding"),
    ("The shop site runs on port 8010 in production.", "coding"),
    ("I promised Kevin the payroll sheet by Friday.", "projects"),
    ("My final-year project is CAMR, a memory engine for small models on a Mac.", "projects"),
    ("CAMR's deadline for the thesis draft is the end of November.", "projects"),
    ("I write short sentences and use British spelling.", "writing"),
    ("I never use the word 'utilise' in my letters.", "writing"),
    ("I sign my letters 'Kind regards, Ibrahim'.", "writing"),
    ("My letter to the bank in June told the M-Pesa till story and got me an interview.", "writing"),
    ("In algorithms, I keep forgetting that counting sort is O(n) when the keys are small.", "study"),
    ("My statistics exam is on 21 November.", "study"),
    ("Slide 14 of my algorithms lecture explains counting sort.", "study"),
    ("I'm planning a trip to Mount Kenya in late January with Otieno.", "personal"),
    ("We want to stay in Laikipia, under KSh 8,000 a night.", "personal"),
    ("I'm free from 24 to 26 January.", "personal"),
    ("Update: my rent went up to KSh 28,000 from March.", "personal"),
    ("The matatu fare to Kitengela went up to KSh 120.", "personal"),
    ("Kevin's extension changed to 214 on the new phones.", "projects"),
    ("The water bill is now due on the 15th.", "personal"),
    ("I moved my gym days to Tuesday, Thursday and Saturday.", "personal"),
    ("The shop site moved to port 8200 in production; the staging box took 8010.", "coding"),
    # and a few more of each
    ("Fixed the crash in the login form; the session cookie was never set.", "coding"),
    ("The build fails on Python 3.13 because of a missing wheel.", "coding"),
    ("We use pytest and run it with -x in CI.", "coding"),
    ("The client wants the logo changed before launch.", "projects"),
    ("Njeri approved the budget for the new branch.", "projects"),
    ("Our standup moved to 9:30.", "projects"),
    ("Met the landlord of the Westlands branch about the lease.", "projects"),
    ("The paper claims dropout helps small models more.", "research"),
    ("I read that sleep consolidates memories in the hippocampus.", "research"),
    ("The benchmark showed 12% better recall with a reranker.", "research"),
    ("The source for the inflation figure is the KNBS 2024 report.", "research"),
    ("My dad's knee surgery is on the 3rd.", "personal"),
    ("I need to buy a new phone charger.", "personal"),
    ("Electricity tokens ran out again.", "personal"),
    ("Dinner at Wanjiku's on Sunday.", "personal"),
    ("Always start emails with the person's first name.", "writing"),
    ("My cover letter opens with the story of the till.", "writing"),
    ("The report's introduction should be two paragraphs in my draft.", "writing"),
    ("Organic chemistry quiz on Thursday covers alkenes.", "study"),
    ("I keep mixing up mitosis and meiosis.", "study"),
    ("Lecture 7 on recursion was confusing, rewatch it.", "study"),
]

HELD = [
    ("The payment webhook returns a 500 when the amount is zero.", "coding"),
    ("Use ripgrep instead of grep in the deploy script.", "coding"),
    ("I renamed getUser to fetchUser across the frontend.", "coding"),
    ("The Docker image is 2 GB because node_modules got copied in.", "coding"),
    ("Our API rate limit is 60 requests a minute per key.", "coding"),
    ("The migration dropped the email index by mistake.", "coding"),
    ("Swift's macro plugin is missing, so the build fails without Xcode.", "coding"),
    ("The date parser breaks on leap years.", "coding"),
    ("The staging database password rotates every 30 days.", "coding"),
    ("git bisect pointed at the commit that changed the cache key.", "coding"),
    ("The printer wants half the money upfront for the flyers.", "projects"),
    ("Achieng is taking over the Mombasa account from January.", "projects"),
    ("We agreed to close the Thika branch on Sundays.", "projects"),
    ("The caterer quoted KSh 900 a head for the launch.", "projects"),
    ("Head office wants the stock count by month end.", "projects"),
    ("Brian resigned from the sales team yesterday.", "projects"),
    ("The client signed off on phase two at Tuesday's meeting.", "projects"),
    ("Delivery of the new tills slipped to the 12th.", "projects"),
    ("My manager wants the quarterly numbers in a spreadsheet, not slides.", "projects"),
    ("We're switching suppliers for packaging because of the price rise.", "projects"),
    ("A 2023 study found that spaced retrieval beats rereading by 20%.", "research"),
    ("The survey had 412 respondents across three counties.", "research"),
    ("Our second experiment failed to replicate the effect.", "research"),
    ("Smith et al. use a contrastive loss on the embeddings.", "research"),
    ("The control group scored higher on the delayed test.", "research"),
    ("According to the WHO report, malaria cases fell by 8%.", "research"),
    ("The dataset has a labelling bias towards urban households.", "research"),
    ("I should cite the original attention paper in related work.", "research"),
    ("Larger context windows slowed inference by 30% in our runs.", "research"),
    ("The findings suggest fertiliser subsidies raised yields only in wet years.", "research"),
    ("My cousin is getting married in Kisumu in April.", "personal"),
    ("I'm allergic to penicillin.", "personal"),
    ("The plumber is coming on Saturday morning.", "personal"),
    ("Car insurance renews on 3 June.", "personal"),
    ("My daughter starts nursery in January.", "personal"),
    ("Spent KSh 4,500 on groceries this week.", "personal"),
    ("Flight to Dubai leaves at 6:40 from JKIA.", "personal"),
    ("I need to renew my passport before August.", "personal"),
    ("Grandma likes her tea without sugar.", "personal"),
    ("The landlord is fixing the kitchen tap next week.", "personal"),
    ("I prefer 'start' to 'commence' in everything I write.", "writing"),
    ("My emails end with 'Thanks, Ibrahim'.", "writing"),
    ("Keep my blog posts under 600 words.", "writing"),
    ("I don't use exclamation marks in formal letters.", "writing"),
    ("The opening line of my personal statement needs more punch.", "writing"),
    ("Use the Oxford comma in my essays.", "writing"),
    ("My tone with clients should be warm but brief.", "writing"),
    ("The second draft of my op-ed cut the anecdote about the bus.", "writing"),
    ("Never start a paragraph of mine with 'However'.", "writing"),
    ("The reference letter for Njoki should mention her leadership.", "writing"),
    ("My calculus midterm covers integrals and series.", "study"),
    ("I always forget the quadratic formula's sign.", "study"),
    ("Chapter 9 of the economics textbook is on the exam.", "study"),
    ("Flashcards for French verbs are due for revision on Sunday.", "study"),
    ("The professor said question 4 on the past paper is a trap.", "study"),
    ("I got a C on the linear algebra assignment because of eigenvectors.", "study"),
    ("My tutorial group meets on Wednesdays in room 12.", "study"),
    ("I need to revise the Krebs cycle before Friday.", "study"),
    ("Office hours for thermodynamics are on Thursdays at 2.", "study"),
    ("Binary trees came up in last year's data structures final.", "study"),
]

OWN = [  # shelves the user made; nothing about them may be tuned for
    ("We're adding a chai latte to the menu.", "cafe"),
    ("The espresso machine needs descaling every month.", "cafe"),
    ("Wambui opens up on weekends now, and the milk comes on Fridays.", "cafe"),
    ("The tomatoes need staking this week.", "garden"),
    ("Prune the roses in July.", "garden"),
    ("The compost heap is ready to spread on the beds.", "garden"),
    ("Oil change due at 90,000 km.", "car"),
    ("The left front tyre has a slow puncture.", "car"),
    ("A full tank costs about KSh 7,000.", "car"),
    ("The login page throws a 404 after the redirect.", "coding"),
    ("My mum is visiting next weekend.", "personal"),
    ("The board wants the quarterly report before the AGM.", "projects"),
]


def use(root: Path, extra) -> None:
    shelves._set(shelves.DEFAULTS)
    for label, about in extra:
        shelves.add(root, label, about)


def score(sorter, cases, show: bool, reader=None) -> dict:
    right, wrong, slow, asked = 0, Counter(), [], 0
    for text, want in cases:
        t = time.perf_counter()
        got = sorter.sort(text, reader).name
        slow.append(time.perf_counter() - t)
        asked += int(sorter.asked)
        if got == want:
            right += 1
        else:
            wrong[f"{want}->{got}"] += 1
            if show:
                print(f"  want {want:9} got {got:9} {text[:80]}")
    slow.sort()
    return {"right": right, "of": len(cases), "share": round(right / len(cases), 3), "wrong": dict(wrong.most_common()),
            "asked_reader": asked, "median_s": round(slow[len(slow) // 2], 4), "slowest_s": round(slow[-1], 3)}


def main() -> int:
    import tempfile

    ap = argparse.ArgumentParser()
    ap.add_argument("--held", action="store_true", help="the held-back sets: run once, when tuning is over")
    ap.add_argument("--model", default=MODEL)
    a = ap.parse_args()
    embedder, reader = Embedder(), Reader(a.model)
    out = {"model": a.model, "held": a.held, "methods": {}}
    plan = [("own", OWN_SHELVES, OWN), ("six", SIX, HELD)] if a.held else [("six", SIX, TUNE)]
    with tempfile.TemporaryDirectory() as tmp:
        for name, extra, cases in plan:
            use(Path(tmp) / name, extra)
            sorter = shelves.Sorter(embedder)
            for method, by in (("embedder alone (before)", None), ("reader (now)", reader)):
                print(f"\n{name}: {method}")
                got = score(sorter, cases, by is reader, by)
                print(json.dumps(got))
                out["methods"][f"{name}: {method}"] = got
    shelves._set(shelves.DEFAULTS)
    if a.held:
        dest = Path(__file__).resolve().parents[1] / "records" / "sorting" / time.strftime("%Y-%m-%d-%H%M%S-held.json")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=1))
        print(f"\nkept in {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
