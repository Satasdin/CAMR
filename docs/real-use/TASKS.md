# Real-use tasks and pass marks

Frozen on Saturday 7 November 2026, before any curated shelf note was written. Notes must not be written from these
tasks, and these tasks must not change after seeing a result. If one has to change, the change is recorded here with
its reason and every run before it is reported as run on the old version. The supervisor's own cold task on Monday is
the check on all of this.

The model is Qwen3 4B (`mlx-community/Qwen3-4B-4bit`). Each task runs with shelves on and with shelves off. "Thinking"
says whether the model may reason before it answers. Every run is done in the app. Results are kept with the build's
commit.

## T1. How long can it build alone?

Brief, told once: a café called Kahawa Corner on Argwings Kodhek Road in Kilimani, open 7am to 9pm Monday to Saturday,
closed on Sunday; filter coffee KES 180, masala chai KES 120, mandazi KES 40, chicken wrap KES 450, avocado toast
KES 380; colours deep green #1F4D3A and cream #F5EBDD. Request: "Build Kahawa Corner a small website where a customer
can add items to an order and see the total."

Thinking on. Count: steps and minutes before it needs the person; files written.

Pass:
- Every told fact is on the page, and nothing checkable is invented.
- Opens in the built-in browser with no script errors and no dead links.
- Adding two items shows the right total (filter coffee + mandazi = KES 220).
- Runs at least 5 steps without being asked to continue.

## T2. Does it ask the right questions?

The same brief with the hours and the colours left out and no phone number. Request: "Build the Kahawa Corner website."

Thinking on. Count: right questions (about what is missing), needless questions (about what it was told), missed gaps.

Pass: asks about at least 2 of the 3 gaps, asks nothing needless, and invents none of the three.

## T3. Does it stop making things up?

Eight questions on the T1 brief: four it was told, four it was not (owner's name, phone number, year founded, wifi
password). Thinking off.

Pass: at least 3 of 4 told answers right, at least 3 of 4 untold declined, and the fact check flags any invented fact.

## T4. Can it reason? (thinking off, as he asked)

Group A, a method shown before. Told once with a worked example: "Delivery is 5% of the order, rounded up to the next
KES 10, at least KES 50." Asked: orders of KES 820, KES 1,500 and KES 640 (50, 80, 50). And: "Tax is added first, then
the 10% member discount." Asked: KES 1,000 with 16% tax, for a member (KES 1,044).

Group B, no precedent. Three problems with no method told: a schedule with one constraint to satisfy, a two-step
stock calculation, and an ordering puzzle, fixed by the grader before any run and not seen by whoever writes the notes.

Pass for "reuses reasoning": at least 3 of 4 in Group A with shelves on, and more than with shelves off.
"Produces new reasoning" is claimed only if Group B with shelves on beats Group B with shelves off. Report both.

## T5. Can it help decide?

Told, with reasons: "We take M-Pesa only, because card fees cost more than our margin on chai." "No delivery past
Westlands, because the rider cannot make it back in the lunch rush." "Prices never change mid-month, because regulars
complained." Then a later change: "We now also take Airtel Money, as requested by customers."

Asked: "A customer wants to pay by card, should we add it?" "A customer in Karen wants delivery, can we?" "Sugar went
up today, should we raise prices now?" "Which payments do we take?"

Pass: at least 3 of 4 follow the record and give its reason, and the last names both M-Pesa and Airtel Money.

## T6. Does it outlast its context window?

One project in one conversation: 30 change requests to the T1 site, read from `change-requests.txt` beside this file,
with decisions in the early ones that later ones depend on. The model's window is limited to 4,096 tokens for this
task, so the conversation cannot simply be re-read.

Pass: at least 8 of the 10 decision checks written in that file hold at the end, and the tokens read per step do not
grow with the length of the conversation.

## T7. Side by side with Claude

The T1 brief given to Claude Sonnet 5.5 through the API, with the same tools. Same counts and same checks, and
screenshots of both pages side by side. No pass mark: this is reported as it comes.

## The grader

A separate agent, given the lecturer's own words, this file and the app, and nothing of the builder's reasoning. It
uses the app as a person would and scores each task. It may add what it finds lacking; it may not lower a pass mark.
