"""The Long Haul, hard set: 100 exam questions on new sentence templates, planted into an existing built history.

It is an exam, run only at milestones and never tuned on. No question, statement or wording here shares a 4-word
phrase with the original families' templates (``probes.py``), so a system tuned on those cannot pass it by pattern.
Families (count):

  three_hop (13)      A -> B -> C -> value, each link told at a different time in a different genre, with a parallel
                      decoy chain told in the same words (its end value is rejected)
  before_change (13)  the earlier value of a fact that changed 2 to 4 times: "before it became Y" or "back on <date>"
  count_changes (12)  how many times a fact changed; restatements and turned-down proposals are not changes
  far_lookalike (14)  near-identical people, repos, lorries and suppliers told months apart; ask about one
  conflict (12)       a group-chat rumour against a signed memo, or minutes against their correction: only the
                      confirmed value is right (the rumour or the corrected value grades as stale)
  reworded (12)       plain facts asked in words that share almost nothing with how they were told
  negated (12)        near-miss questions about things never said (the chain breaks, the attribute was never told)
  aggregate (12)      several facts combined: the dearest / cheapest branch, how many pay above a line, a sum or gap

How it is built: the base history's planted events are found again (by re-running its planner for its seed, which
never touches the tokenizer), and the new events go in at chosen depths between whole units (never inside a chat
turn or a planted unit). To keep every depth and the 2M cut where they were, about as many tokens of plain noise
(docs, meetings, decisions, logs; never a planted event) are taken out near each insertion. Tokens are recounted with
the haul's Qwen3 tokenizer and ``i`` / ``cum_tokens`` are renumbered.

Every hard grader is one of grade.py's own types (``exact`` with accept / stale / reject / others, or ``never`` with a
pool), so ``longhaul`` and ``python -m camr_engine.bench.haul grade`` grade the hard set with no change; ``grade``
below wraps grade.py for the hard families.

The output dir holds:

  script.jsonl       the new script
  probes.jsonl       the hard questions only (so ``longhaul`` and ``sample`` ask only these)
  probes-base.jsonl  the base's own probes, re-indexed to the new events (``load_base(dir)``), so the old families
                     still run on this script
  manifest.json      ``"hard": true``, the families, cuts and where it came from

    python -m camr_engine.bench.haul.hard build --from ../work/haul/s3 --seed 4 --out ../work/haul/s4-hard
    python -m camr_engine.bench.haul.hard show --dir ../work/haul/s4-hard
    python -m camr_engine.bench.haul.hard grade --dir ../work/haul/s4-hard --answers answers.jsonl --cut 2M
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import accumulate
from pathlib import Path
from typing import Callable

from camr_engine.bench.haul import tokens as tok
from camr_engine.bench.haul.grade import Grade, names
from camr_engine.bench.haul.grade import grade as base_grade
from camr_engine.bench.haul.noise import Noise
from camr_engine.bench.haul.probes import CONFIGS, NAME_POOL, Planner, exact
from camr_engine.bench.haul.sample import at_cut
from camr_engine.bench.haul.script import TARGET, _verify, budgets, calendar, load_events, load_probes
from camr_engine.bench.haul.words import BRANCHES, MONTHS, TOWNS, WEEKDAYS, cap, poss, say
from camr_engine.bench.haul.world import build_world

FAMILIES = {"three_hop": 13, "before_change": 13, "count_changes": 12, "far_lookalike": 14, "conflict": 12,
            "reworded": 12, "negated": 12, "aggregate": 12}
CUTS = {"64K": 64_000, "256K": 256_000, "1M": 1_000_000, "2M": 2_000_000}
LAST_DAY = 107  # nothing is planted after this day, so all of it sits inside the 2M cut
NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
TIMES_WORDS = {1: ["once"], 2: ["twice"], 3: ["thrice"]}

# -- the new world's words ----------------------------------------------------------------------------------------

NEW_FIRST = ["Akoth", "Wangari", "Chepkoech", "Kanini", "Mutheu", "Jelimo", "Nasimiyu", "Ayuma", "Waceke", "Kemunto",
             "Njambi", "Anyango", "Mwikali", "Nyokabi", "Awuor", "Nanjala", "Kagendo", "Ochola", "Kipruto", "Mwenda",
             "Omari", "Mugo", "Gakuru", "Odongo", "Kiplimo", "Wanyonyi", "Mbithi", "Nzau", "Lekishon", "Rashid",
             "Otiende", "Jabali", "Nyawira", "Kathambi", "Wawira", "Chelangat"]
NEW_LAST = ["Ayieko", "Obonyo", "Gathogo", "Kinyanjui", "Wahome", "Mugambi", "Kithinji", "Makau", "Mwendwa", "Ndungu",
            "Nzioka", "Ogola", "Owuor", "Omondi", "Kamotho", "Nyamu", "Kiragu", "Muasya", "Kasyoka", "Lelei",
            "Kosgei", "Jeptanui", "Sitienei", "Ekirapa", "Lokorio", "Ndirangu", "Gichuki", "Wanjohi", "Mbatia",
            "Kanyi"]
LOOK_SURNAMES = [("Odera", "Odero"), ("Wambua", "Wambugu"), ("Mutua", "Mutuku"), ("Kiprop", "Kiprotich"),
                 ("Chepkoech", "Chepkorir"), ("Nyaboke", "Nyabuto"), ("Achola", "Acholla")]
LOOK_FIRST = ["Achieng", "Wanjiku", "Jepkosgei", "Nekesa", "Mumbi", "Kwamboka"]
NEW_PLACES = ["Kitengela", "Juja", "Limuru", "Ruiru", "Athi River", "Kikuyu", "Kangundo", "Gatundu", "Mlolongo",
              "Kiserian", "Tigoni", "Githunguri", "Wangige", "Banana Hill", "Kamulu", "Utawala"]
NEW_TRADES = ["Provisions", "Larder", "Pantry Co", "Agro Hub", "Harvest House", "Food Stores", "Farm Shop",
              "Fine Foods", "Merchants"]
NEW_DISHES = [("coconut ndengu", "coconut cream"), ("smoked beef wet fry", "smoked paprika"),
              ("tilapia in tamarind", "tamarind paste"), ("pilau arancini", "arborio rice"),
              ("mukimo croquettes", "panko crumbs"), ("ginger goat ribs", "fresh ginger root"),
              ("sukuma pesto pasta", "fresh basil"), ("chapati tacos", "corn tortillas"),
              ("mango chicken skewers", "mango puree"), ("kienyeji chicken pie", "puff pastry"),
              ("masala omena bites", "chickpea flour"), ("matoke fritters", "green plantain"),
              ("chai creme brulee", "vanilla pods"), ("pumpkin gnocchi", "aged parmesan")]
PROJECTS = ["the loyalty card revamp", "the catering portal", "the rider app rewrite", "the stock scanner pilot",
            "the menu photo refresh", "the breakfast launch", "the kitchen display upgrade", "the gift voucher scheme",
            "the table booking widget", "the supplier invoice portal", "the staff rota app", "the waste tracker"]
BUILDINGS = ["Tumaini House", "Mvule Plaza", "Mugumo Court", "Jacaranda Towers", "Mukuyu House", "Acacia Point",
             "Kipepeo Centre", "Mbuyu Arcade", "Mwangaza Plaza", "Fahari Court"]
VANS = ["the Kifaru van", "the Twiga van", "the Nyati van", "the Duma van", "the Swara van", "the Pundamilia van",
        "the Ndovu van", "the Tausi van", "the Kanga van", "the Korongo van", "the Fisi van", "the Kongoni van",
        "the Paa van", "the Mbega van"]
ROUNDS = ["Kileleshwa", "Hurlingham", "Gigiri", "Runda", "Donholm", "Buruburu", "Ngara", "Pangani", "Kitisuru",
          "Muthaiga", "Loresho", "Riverside", "Madaraka", "South C", "Thome", "Ridgeways"]
ESTATES = ["Kayole", "Zimmerman", "Githurai 45", "Kahawa West", "Pipeline", "Mwiki", "Kawangware", "Dandora",
           "Huruma", "Kariobangi", "Tassia", "Fedha"]
SPECIAL_ANCHORS = [f"{d} {m} special" for d in WEEKDAYS[:5] for m in ("lunch", "dinner", "breakfast")]
CARS = ["silver Probox", "blue Vitz", "white Fielder", "red Demio", "green Axio", "black Premio", "grey Wish"]
STATIONS = ["grill", "pastry", "salad", "fryer", "sauce", "noodle"]
LANGUAGES = ["Kotlin", "Elixir", "Rust", "PHP", "Dart", "TypeScript", "Ruby", "Swift"]
HOSTS = ["vps-nbo-3", "box-ruaka-01", "droplet-fra-2", "pi-karen-1", "hetzner-hel-4", "lightsail-cpt-2"]
CARGO = ["bread flour", "cooking gas", "cold drinks", "fresh fish", "paper bags", "block ice"]
REPO_PAIRS = [("mnk-rider-app", "mnk-riders-app"), ("kitchen-rota", "kitchen-rotas"),
              ("njeri-loyalty", "njeri-loyalty-api"), ("mnk-tills", "mnk-till")]
SUPPLIER_PAIRS = [("Ngong Road Butchers", "Ngong Lane Butchers"), ("Kangemi Fresh Greens", "Kangemi Fresh Grains")]

# Facts that change, for before_change and count_changes: (noun phrase, how the value is written, values). No value
# holds a small whole number, so a count of changes is never found inside a value.
CHANGERS = [
    ("the Saturday opening hour at Karen", "{v}", ["07:00", "07:30", "08:00", "08:30", "09:00", "09:30", "10:00"]),
    ("the Sunday closing time at Kilimani", "{v}", ["19:00", "19:30", "20:00", "20:30", "21:00", "21:30", "22:00"]),
    ("the riders' daily fuel allowance", "KES {v}", [350, 400, 450, 500, 550, 600, 650]),
    ("the staff lunch budget per head", "KES {v}", [120, 150, 180, 200, 220, 250, 280]),
    ("the late-shift taxi allowance", "KES {v}", [600, 700, 800, 900, 1000, 1100, 1250]),
    ("the corkage fee for catering clients", "KES {v}", [500, 750, 1000, 1200, 1500, 1800, 2000]),
    ("the cash float in each till", "KES {v}", ["2,000", "2,500", "3,000", "3,500", "4,000", "4,500", "5,000"]),
    ("the delivery app commission", "{v}%", [18, 20, 22, 25, 28, 30, 32]),
    ("the house dessert", "{v}", ["malva pudding", "banana fritters", "mango sorbet", "chai panna cotta",
                                 "coconut tart", "tamarind sorbet", "baked mandazi pudding"]),
    ("the house coffee blend", "{v}", ["Kahawa Bora", "Kiambu Gold", "Nyeri Hill", "Gatomboya Estate",
                                      "Ruiru Roast", "Kirinyaga Peak", "Thika Valley"]),
    ("the cold-room cleaning contractor", "{v}", ["Usafi Pro", "Safi Kabisa", "Clean Sweep Kenya", "Ng'aa Services",
                                                  "Spotless Hygiene", "Usafi Bora", "Nadhifu Cleaners"]),
    ("the uniform tailor", "{v}", ["Mavazi Bora", "Cut and Stitch", "Kanzu House", "Uzi Works", "Pindo Tailors", "Kitenge Corner", "Shona Works"]),
    ("the bread supplier for Westlands", "{v}", ["Kamulu Bakers", "Mkate Moto", "Ngano Bakery", "Unga Fresh",
                                                 "Oven Door Bakers", "Mkate Bora", "Golden Crust Kenya"]),
    ("the grease-trap service interval", "every {v} days", [14, 21, 28, 35, 42, 49, 56]),
    ("the deep-fryer oil change interval", "every {v} hours", [36, 48, 60, 72, 84, 96, 120]),
    ("the cake order lead time", "{v} hours", [24, 36, 48, 60, 72, 96]),
    ("the weekly stocktake day", "{v}", WEEKDAYS[:6]),
    ("the induction day for new waiters", "{v}", WEEKDAYS[:5]),
    ("the guest Wi-Fi network name", "{v}", ["MNK-Guest", "NjeriFree", "Kitchen-Visitors", "MNK-Lounge",
                                             "Chakula-WiFi", "Njeri-Visitors", "MNK-Diners"]),
    ("the gas cylinder size we order", "{v} kg", [13, 22, 35, 45, 50]),
    ("the price of a half-litre of fresh juice", "KES {v}", [120, 150, 170, 200, 230, 250, 270]),
    ("the background music at Lavington", "{v}", ["benga classics", "lo-fi jazz", "Afro house", "rhumba", "taarab", "bongo flava", "Afro soul"]),
    ("the meeting point for the Friday team walk", "{v}", ["Uhuru Park gate", "Karura gate C", "the Arboretum car "
                                                           "park", "City Park entrance", "Ngong Road Forest gate"]),
    ("the minimum rating for riders to stay on the roster", "{v}", ["4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8"]),
    ("the reorder trigger for takeaway cups", "{v} sleeves", [12, 15, 20, 25, 30, 35, 40]),
    ("the staff discount on meals", "{v}%", [10, 15, 20, 25, 30, 35]),
    ("the Parklands night supervisor", "{p}", []),
]
CONFLICT_SUBJECTS = [
    ("the staff party venue", ["Tamambo terrace", "Kitisuru gardens", "Brew Bistro rooftop", "Ngong racecourse lawn",
                               "Kiambethu tea farm"]),
    ("the launch day of the breakfast menu", WEEKDAYS[:5]),
    ("the price of the new pizza oven", ["KES 180,000", "KES 215,000", "KES 240,000", "KES 265,000"]),
    ("the new Ruaka cashier", None),
    ("the colour of the new aprons", ["maroon", "teal", "mustard", "olive", "slate grey"]),
    ("the start time of the Westlands night stall", ["17:30", "18:00", "18:30", "19:00"]),
    ("the site of the new central kitchen", ["Mlolongo", "Ruiru", "Syokimau", "Kikuyu", "Athi River"]),
    ("the month the loyalty app goes live", ["March", "April", "June", "July", "August"]),
    ("the band booked for the year-end party", ["the Benga Brothers", "Rhumba Republic", "the Taarab Twins",
                                                "the Nairobi Horns"]),
    ("the chair count ordered for the Karen terrace", ["60", "72", "84", "96", "120"]),
    ("the new head of catering", None),
    ("the brand of the new dishwasher", ["Winterhalter", "Hobart", "Meiko", "Electrolux"]),
    ("the courier for catering invoices", ["Sendy", "Fargo", "G4S", "Wells Fargo Kenya"]),
]
AGG_TOPICS = [("lamb shoulder", "a kilo of"), ("avocado oil", "a litre of"), ("coconut briquettes", "a sack of"),
              ("macadamia nuts", "a kilo of"), ("sourdough loaves", "a dozen")]

# -- the templates ------------------------------------------------------------------------------------------------
# Statements (how a fact is told) and asks (how it is asked). The tests check none shares a 4-word phrase with any
# string in probes.py.

SAY = {
    "special_dish": ["Agreed: the {anchor} will be {dish} until further notice.",
                     "For the {anchor} we are running {dish}[ this term| from here on]."],
    "special_sup": ["{Dish} only tastes right with the {ing} that {sup} sends us.",
                    "The {ing} in our {dish} comes in from {sup}; nobody else stocks the good kind."],
    "special_town": ["{sup} run everything out of their depot in {town}.",
                     "{sups} warehouse sits up in {town}[, so allow time for the drive|]."],
    "proj_lead": ["{P} is heading {proj}.", "{Proj} is {P}'s baby now; they lead it."],
    "proj_boss": ["{P} reports to {Q} under the new org chart.", "On the org chart, {P} sits under {Q}."],
    "proj_bldg": ["{Q} has moved desks to {bldg}.", "You'll find {Q} on the second floor of {bldg} these days."],
    "van_round": ["{Van} has taken over the {area} round.", "Drops to {area} now go out on {van}."],
    "van_driver": ["{D} is the regular driver of {van}.", "{Van} is driven by {D} most days."],
    "van_estate": ["{D} lives out in {estate}, so they leave early.", "{D} has rented a place in {estate}."],
    "first": ["Starting point, for the file: {np} = {vu}.", "Mama Njeri has fixed {np} at {vu}.",
              "Going in with {vu} as {np}[ to begin with|]."],
    "next": ["Revision: {np} goes from {o} to {vu}.", "Mama Njeri signed off a new setting for {np}: {vu} "
             "(previously {o}).", "Effective this week {np} becomes {vu}; {o} is retired.",
             "{Np}: out with {o}, in with {vu}."],
    "again": ["Nothing has moved on {np}; it remains {vu}.", "Double-checked {np} with the office: still {vu}."],
    "refused": ["{n} floated switching {np} to {x}; Mama Njeri said no, so it remains {vu}.",
                "A proposal to make {np} {x} got voted down. It remains {vu}."],
    "rumour": ["Apparently {np} is going to be {v}; heard it from someone at {b}, nothing official yet.",
               "Word in the kitchen is {np} will be {v}. Don't quote me."],
    "rumour_late": ["Someone said {np} has been switched to {v}? Can't find anything written down.",
                    "Hearing {v} for {np} now, but that's just talk."],
    "confirmed": ["Confirmed: {np} is {v}.", "Signed and final: {np} will be {v}."],
    "minuted": ["Settled: {np} will be {v}.", "Agreed in the room: {np} is {v}."],
    "erratum": ["Correction to the minutes of {date}: {np} should read {v}, and {w} was wrong.",
                "Erratum for the {date} minutes: read {v} for {np}; {w} was a typo."],
    "look_nights": ["{P} is doing nights at {v} starting this week.", "Night cover at {v} belongs to {P} now."],
    "look_car": ["{P} drives a {v}; it's the one parked by the bins.", "That {v} by the gate belongs to {P}."],
    "look_station": ["{P} runs the {v} station on the line.", "Put {P} on {v} again tonight, that's their spot."],
    "look_lang": ["`{r}` is all {v}, no exceptions.", "Whoever touches `{r}` needs {v}; that's what it's in."],
    "look_host": ["`{r}` deploys to {v}.", "The box behind `{r}` is {v}."],
    "look_cargo": ["The lorry {r} brings our {v}.", "{r} turned up again, loaded with {v}."],
    "look_day": ["{r} drops off every {v}.", "Expect {r} every {v}; that is their run."],
    "rw_dayoff": ["Rota note: {P} never works on a {v}.", "{P} takes every {v} off."],
    "rw_origin": ["{P} was born and raised in {v}.", "{P}'s people are all in {v}; it is where they grew up."],
    "rw_allergy": ["{P} reacts badly to {v}; keep it off their plate.", "No {v} near {P}'s food, ever."],
    "rw_language": ["{P} grew up speaking {v} at home.", "Ask {P} to talk to that customer, they speak {v}."],
    "rw_nickname": ["Everyone on the line calls {P} \"{v}\".", "\"{v}\" is what the cooks shout when they want {P}."],
    "rw_keys": ["The spare key to the {b} storeroom stays with {v}.", "{v} holds the second key to {b}'s storeroom."],
    "rw_daughter": ["{P}'s little girl is called {v}.", "{P} brought their girl {v} to the staff day."],
    "rw_study": ["{P} did a diploma course at {v}.", "{P} trained at {v} before joining us."],
    "rw_team": ["{P} supports {v} and never misses a match.", "{P} was in a {v} shirt again on Monday."],
    "rw_chiller": ["{b}'s walk-in chiller is kept at {v} degrees.", "Walk-in chiller at {b}: {v} degrees, always."],
    "rw_sign": ["The new signboard over the {b} entrance was painted {v}.", "{b}'s sign got repainted {v}."],
    "rw_cycle": ["{P} cycles in from {v} every morning.", "{P} rides a bicycle to work all the way from {v}."],
    "agg": ["{b} currently pays {p} shillings for {unit} {item}.", "Invoice check: {unit} {item} sets {b} back KES {p}.",
            "{b} buys {unit} {item} for {p} shillings."],
    "agg_up": ["{b}'s {item} price has changed: KES {p} as of this week.",
               "New invoice at {b}: {item} now costs them KES {p}."],
    "hint_special": ["For the {anchor} we are running {dish}[ this term| from here on]."],
    "hint_van": ["{Van} has taken over the {area} round."],
}
ASK = {
    "special": ["Which town does the supplier behind the {anchor}'s key ingredient operate from?",
                "The {anchor}: where is the depot of the company that provides its star ingredient?"],
    "proj": ["Which building should I go to if I need the line manager of whoever leads {proj}?",
             "Where does the boss of {projs} lead have their desk?"],
    "van": ["Which estate is home to the driver of the van covering {area}?",
            "Whoever drives the {area} drops: in which estate do they live?"],
    "before_y": ["Before {np} became {y}, what had it been?", "What was {np} set to just ahead of the switch to {y}?"],
    "before_date": ["Back on {date}, where did {np} stand?", "As of {date}, what was in force for {np}?"],
    "count": ["Since it was first set, how often has {np} been altered?",
              "Count the revisions to {np} so far: how many have there been?",
              "How many separate times has {np} been moved to something new?"],
    "conflict": ["Officially, {wh} is {np}?", "What's the confirmed answer on {np}?",
                 "Going by the signed-off record, {wh} is {np}?"],
    "look_nights": ["Which branch has {P} working nights?"],
    "look_car": ["Which car does {P} drive to work?"],
    "look_station": ["Which station on the line does {P} run?"],
    "look_lang": ["Which programming language is {r} built in?"],
    "look_host": ["Where does {r} get deployed?"],
    "look_cargo": ["What does the lorry with plates {r} bring us?"],
    "look_day": ["Which weekday is the drop-off for {r}?"],
    "rw_dayoff": ["Which weekday won't {P} be in?"],
    "rw_origin": ["Where does {P} hail from?"],
    "rw_allergy": ["Which ingredient must the cooks avoid serving {P}?"],
    "rw_language": ["Apart from English, which tongue can {P} converse in?"],
    "rw_nickname": ["By what moniker is {P} known in the kitchen?"],
    "rw_keys": ["Who should I hunt down when the {b} stockroom is locked?"],
    "rw_daughter": ["What did {P} name their daughter?"],
    "rw_study": ["Which college trained {P}?"],
    "rw_team": ["Which side does {P} cheer for at weekends?"],
    "rw_chiller": ["To what temperature is the cold store at {b} held?"],
    "rw_sign": ["What shade is the board above the {b} door?"],
    "rw_cycle": ["Which neighbourhood does {P} set off from on the morning commute?"],
    "agg_max": ["Which branch pays the steepest price for {item}?"],
    "agg_min": ["Where among the branches does {item} cost least?"],
    "agg_count": ["How many branches pay more than {t} shillings for {unit} {item}?"],
    "agg_sum": ["Add what {b1} and {b2} pay for {unit} {item}: what's the total in shillings?"],
    "agg_diff": ["By how many shillings does {b1}'s {item} price exceed {b2}'s?"],
    "never_price": ["What does {b} pay for {unit} {item}?"],
    "never_boss": ["Who is the line manager of the person leading {proj}?"],
    "never_driver": ["Who is behind the wheel of the van on the {area} round?"],
}
REWORDED = {  # key -> values (the person, branch or value pool the fact is drawn from)
    "rw_dayoff": WEEKDAYS[:6],
    "rw_origin": ["Kakamega", "Nanyuki", "Kitui", "Bungoma", "Kilifi", "Iten", "Chuka", "Busia"],
    "rw_allergy": ["groundnuts", "prawns", "sesame", "mushrooms", "pineapple", "soya"],
    "rw_language": ["Kikamba", "Ekegusii", "Kalenjin", "Somali", "Luhya", "Kimeru", "Dholuo", "Maa"],
    "rw_nickname": ["Chef Pilipili", "Mzee Kijana", "Supersub", "Professor", "Bibi Mdogo", "Captain Sufuria"],
    "rw_keys": [],
    "rw_daughter": ["Zuri", "Nia", "Shiro", "Wema", "Tumaini", "Ayana"],
    "rw_study": ["Kenya Utalii College", "Boma Hospitality College", "Thika Technical Training Institute",
                 "Kenya Coast Polytechnic", "Eldoret National Polytechnic"],
    "rw_team": ["Gor Mahia", "AFC Leopards", "Tusker FC", "Arsenal", "Manchester United", "Liverpool", "Chelsea"],
    "rw_chiller": ["2", "3", "4", "5"],
    "rw_sign": ["maroon", "teal", "mustard yellow", "olive green", "burnt orange", "navy blue"],
    "rw_cycle": ESTATES,
}
GENRES = ["email", "minutes", "groupchat", "voicenote", "handover", "sms", "ticket"]


# -- planting ---------------------------------------------------------------------------------------------------

@dataclass
class HardPlant:
    ref: str
    day: int
    frac: float
    kind: str
    role: str
    text: str
    genre: str


@dataclass
class HardHaul:
    seed: int
    events: list[dict]
    probes: list[dict]
    base_probes: list[dict]
    manifest: dict
    removed: int = 0
    plants: list[HardPlant] = field(default_factory=list)


class HardPlanner:
    """Plants the hard families for one seed into a base whose script text is ``base_text`` (lowercased)."""

    def __init__(self, seed: int, base_world, dates: list, last_day: int, base_text: str):
        self.seed = seed
        self.rng = random.Random(f"hard:{seed}:plan")
        self.names_rng = random.Random(f"hard:{seed}:world")
        self.noise = Noise(random.Random(f"hard:{seed}:filler"), base_world, dates)
        self.dates = dates
        self.last_day = last_day
        self.base_text = base_text
        self.plants: list[HardPlant] = []
        self.probes: list[dict] = []
        self.people: list[str] = []
        self.suppliers: list[str] = []
        self.taken: set[str] = set()
        self.n = Counter()

    # -- names that are new to the base ------------------------------------------------------------------------
    def fresh(self, s: str) -> bool:
        k = s.casefold()
        if k in self.taken:
            return False
        return re.search(r"(?<![\w-])" + re.escape(k) + r"(?![\w-])", self.base_text) is None

    def claim(self, s: str) -> str:
        self.taken.add(s.casefold())
        return s

    def person(self) -> str:
        rng = self.names_rng
        for _ in range(2000):
            p = f"{rng.choice(NEW_FIRST)} {rng.choice(NEW_LAST)}"
            if self.fresh(p) and sum(q.split()[0] == p.split()[0] for q in self.people) < 2:
                self.people.append(p)
                return self.claim(p)
        raise RuntimeError("ran out of new people")

    def pick_fresh(self, pool: list[str], k: int = 1) -> list[str]:
        pool = [x for x in pool if self.fresh(x)]
        if len(pool) < k:
            raise RuntimeError(f"not enough fresh names in {pool[:3]}...")
        out = self.names_rng.sample(pool, k)
        for x in out:
            self.claim(x)
        return out

    def supplier(self) -> str:
        rng = self.names_rng
        for _ in range(500):
            s = f"{rng.choice(NEW_PLACES)} {rng.choice(NEW_TRADES)}"
            if self.fresh(s):
                self.suppliers.append(s)
                return self.claim(s)
        raise RuntimeError("ran out of supplier names")

    def date(self, day: int) -> str:
        d = self.dates[day - 1]
        return f"{d.day} {MONTHS[d.month - 1]}"

    # -- hosts: the new genres -----------------------------------------------------------------------------------
    def filler(self, day: int) -> str:
        """One line that tells nothing and names no weekday, branch or number (so it never blurs a planted fact)."""
        bad = re.compile(r"\d|" + "|".join(WEEKDAYS + BRANCHES))
        for _ in range(50):
            s = self.noise.sentence(day)
            if not bad.search(s):
                return s
        return "Busy day."

    def host(self, day: int, statement: str, genre: str) -> tuple[str, str, str]:
        rng, n = self.rng, self.noise
        f = lambda: self.filler(day)  # noqa: E731
        if genre == "email":
            who = n.name()
            subj = rng.choice(["quick update", "this week", "notes from the branches", "follow-up", "housekeeping",
                               "for your files", "odds and ends"])
            text = (f"From: {who}\nTo: kitchen-team\nSubject: {subj}\n\n"
                    f"{rng.choice(['Hi all', 'Team', 'Morning everyone', 'Hello both'])},\n\n{f()} {statement} {f()}"
                    f"\n\n{rng.choice(['Regards', 'Thanks', 'Asante', 'Cheers'])},\n{who.split()[0]}")
            return "doc", "user", text
        if genre == "minutes":
            items = [f() for _ in range(rng.randrange(2, 4))]
            items.insert(rng.randrange(len(items) + 1), statement)
            people = ", ".join(dict.fromkeys(n.name() for _ in range(rng.randrange(3, 6))))
            title = rng.choice(["ops review", "branch heads meeting", "kitchen committee", "menu council",
                                "admin huddle"])
            text = (f"Minutes of the {title}, {n.long_date(day)}\nIn attendance: {people}\n" +
                    "\n".join(f"{k}. {x}" for k, x in enumerate(items, 1)) + "\nNext sitting: in a week.")
            return "meeting", "user", text
        if genre == "groupchat":
            lines = [f"{n.name()}: {f()}" for _ in range(rng.randrange(2, 6))]
            lines.insert(rng.randrange(len(lines) + 1), f"{n.name()}: {statement}")
            h = rng.randrange(7, 21)
            stamped = [f"[{h:02d}:{(m * 3 + rng.randrange(3)) % 60:02d}] {x}" for m, x in enumerate(lines)]
            group = rng.choice(["Branch leads", "Kitchen crew", "Riders and dispatch", "Back office", "Line cooks"])
            return "chat", "user", f"Chat export ({group}):\n" + "\n".join(stamped)
        if genre == "voicenote":
            return "chat", "user", (f"Voice note from {n.name()}, typed out: \"{f()} {statement} {f()}\"")
        if genre == "handover":
            items = [f() for _ in range(rng.randrange(2, 4))]
            items.insert(rng.randrange(len(items) + 1), statement)
            return "doc", "user", (f"Shift handover, {n.long_date(day)}, night to morning:\n" +
                                   "\n".join(f"* {x}" for x in items))
        if genre == "sms":
            return "chat", "user", f"Text message from {n.name()}: {statement}"
        if genre == "ticket":
            status = rng.choice(["open", "closed", "waiting", "in progress"])
            return "doc", "user", (f"Ticket MNK-{rng.randrange(1000, 9999)} [{status}]\n> {n.name()}: {f()}\n"
                                   f"> {n.name()}: {statement}")
        if genre == "memo":
            return "doc", "user", (f"OFFICIAL MEMO {rng.randrange(100, 999)}/{self.dates[day - 1].year}, approved by "
                                   f"Mama Njeri ({n.long_date(day)}): {statement} This supersedes anything said "
                                   f"informally.")
        raise ValueError(genre)

    def tell(self, ref: str, day: int, statement: str, genre: str | None = None, frac: float | None = None) -> str:
        genre = genre or self.rng.choice(GENRES)
        kind, role, text = self.host(day, statement, genre)
        assert statement in text
        self.plants.append(HardPlant(ref, day, self.rng.random() if frac is None else frac, kind, role, text, genre))
        return ref

    def say(self, key: str, **slots) -> str:
        return say(self.rng, self.rng.choice(SAY[key]), **slots)

    def ask(self, key: str, **slots) -> str:
        return say(self.rng, self.rng.choice(ASK[key]), **slots)

    def day(self, lo: int, hi: int) -> int:
        lo, hi = max(2, lo), min(self.last_day, hi)
        return self.rng.randrange(lo, max(lo + 1, hi + 1))

    def days(self, k: int, lo: int = 2, hi: int | None = None, gap: int = 6) -> list[int]:
        """``k`` increasing days in [lo, hi], at least ``gap`` apart."""
        hi = hi or self.last_day
        for _ in range(1000):
            ds = sorted(self.rng.sample(range(lo, hi + 1), k))
            if all(b - a >= gap for a, b in zip(ds, ds[1:])):
                return ds
        raise RuntimeError("no room for the days")

    def genres(self, k: int) -> list[str]:
        g = GENRES[:]
        self.rng.shuffle(g)
        return (g * 2)[:k]

    def probe(self, family: str, ask: str, answer: str, grader: dict, refs: list[str], key: str | None,
              ready: str | None = None, evidence: list[tuple[str, str]] | None = None, **extra) -> dict:
        self.n[family] += 1
        p = {"id": f"hard-{family}-{self.n[family]:02d}", "family": family, "ask": ask, "answer": answer,
             "grader": grader, "refs": refs, "key": key, "ready_ref": ready, "evidence": evidence or [], "hard": True,
             **extra}
        self.probes.append(p)
        return p

    # -- the families ----------------------------------------------------------------------------------------
    def run(self) -> None:
        self.three_hops()
        self.timelines()
        self.lookalikes()
        self.conflicts()
        self.reworded()
        self.aggregates()
        self.negated()

    def three_hops(self) -> None:
        rng = self.rng
        anchors = self.pick_fresh(SPECIAL_ANCHORS, 10 + 2)
        dishes = [d for d in NEW_DISHES if self.fresh(d[0])]
        rng.shuffle(dishes)
        towns = TOWNS[:]
        rng.shuffle(towns)
        projects = self.pick_fresh(PROJECTS, 8 + 2)
        buildings = self.pick_fresh(BUILDINGS, 8)
        vans = self.pick_fresh(VANS, 8 + 2)
        rounds = [r.removesuffix(" round") for r in self.pick_fresh([f"{a} round" for a in ROUNDS], 8 + 2)]
        estates = ESTATES[:]
        rng.shuffle(estates)
        self.broken: dict[str, list] = {"special": [], "proj": [], "van": []}
        k = 0
        for shape, chains in (("special", 5), ("proj", 4), ("van", 4)):
            for c in range(chains):
                k += 1
                chain, decoy = [], []
                for side in (chain, decoy):
                    if shape == "special":
                        anchor = anchors.pop()
                        dish, ing = dishes.pop()
                        self.claim(dish), self.claim(ing)
                        sup, town = self.supplier(), towns.pop()
                        texts = [self.say("special_dish", anchor=anchor, dish=dish),
                                 self.say("special_sup", Dish=cap(dish), dish=dish, ing=ing, sup=sup),
                                 self.say("special_town", sup=sup, sups=poss(sup), town=town)]
                        side.extend([anchor, texts, town, TOWNS])
                    elif shape == "proj":
                        proj, lead, boss, bldg = projects.pop(), self.person(), self.person(), buildings.pop()
                        texts = [self.say("proj_lead", P=lead, proj=proj, Proj=cap(proj)),
                                 self.say("proj_boss", P=lead, Q=boss),
                                 self.say("proj_bldg", Q=boss, bldg=bldg)]
                        side.extend([proj, texts, bldg, BUILDINGS])
                    else:
                        van, area, driver, estate = vans.pop(), rounds.pop(), self.person(), estates.pop()
                        texts = [self.say("van_round", Van=cap(van), van=van, area=area),
                                 self.say("van_driver", D=driver, van=van, Van=cap(van)),
                                 self.say("van_estate", D=driver, estate=estate)]
                        side.extend([area, texts, estate, ESTATES])
                days = self.days(3, 2, self.last_day, gap=8)
                ddays = [min(self.last_day, d + rng.randrange(-5, 6)) for d in days]
                refs = []
                for side, ds, tag in ((chain, days, "a"), (decoy, ddays, "d")):
                    for j, (text, d, g) in enumerate(zip(side[1], ds, self.genres(3))):
                        r = self.tell(f"hard-hop-{k:02d}-{tag}{j}", max(2, d), text, g)
                        if tag == "a":
                            refs.append(r)
                anchor, _, value, pool = chain
                ask = self.ask(shape, anchor=anchor, proj=anchor, projs=poss(anchor), area=anchor)
                spec = exact([value], ask, reject=[decoy[2]], others=pool)
                self.probe("three_hop", ask, value, spec, refs, refs[-1], evidence=[(refs[-1], value)],
                           shape=shape, decoy=decoy[0])
        # chains that break after the first link, for the never-said near misses
        for shape in ("special", "proj", "van"):
            for _ in range(2):
                d = self.day(4, self.last_day - 4)
                if shape == "special":
                    anchor = anchors.pop()
                    dish, _ = dishes.pop()
                    self.claim(dish)
                    ref = self.tell(f"hard-break-{shape}-{len(self.broken[shape])}", d,
                                    self.say("hint_special", anchor=anchor, dish=dish))
                    self.broken[shape].append((anchor, dish, ref))
                elif shape == "proj":
                    proj, lead = projects.pop(), self.person()
                    ref = self.tell(f"hard-break-{shape}-{len(self.broken[shape])}", d,
                                    self.say("proj_lead", P=lead, proj=proj, Proj=cap(proj)))
                    self.broken[shape].append((proj, lead, ref))
                else:
                    van, area = vans.pop(), rounds.pop()
                    ref = self.tell(f"hard-break-{shape}-{len(self.broken[shape])}", d,
                                    self.say("hint_van", Van=cap(van), area=area))
                    self.broken[shape].append((area, van, ref))

    def _values(self, unit: str, pool: list, k: int) -> list[tuple[str, list[str]]]:
        if unit == "{p}":
            return [(p, [p]) for p in (self.person() for _ in range(k))]
        vals = self.rng.sample(pool, k)
        out = []
        for v in vals:
            v = f"{v:,}" if isinstance(v, int) else v
            text = unit.replace("{v}", v)
            out.append((text, [str(v)]))
        return out

    def timelines(self) -> None:
        rng = self.rng
        subjects = [s for s in CHANGERS if self.fresh(s[0])]
        rng.shuffle(subjects)
        if len(subjects) < 25:
            raise RuntimeError("not enough fresh changing subjects")
        counts = [1, 2, 2, 3, 3, 3, 4, 4, 5, 2, 4, 1]
        rng.shuffle(counts)
        tail = subjects[13:25]
        order = sorted(range(12), key=lambda j: (len(tail[j][2]) if tail[j][1] != "{p}" else 99, j))
        ranked = sorted(counts)
        counts = [0] * 12
        for j, c in zip(order, ranked):
            counts[j] = c
        for idx, (np_, unit, pool) in enumerate(subjects[:25]):
            self.claim(np_)
            counting = idx >= 13
            nvals = counts[idx - 13] + 1 if counting else rng.randrange(3, 6)
            if unit != "{p}":
                nvals = min(nvals, len(pool))
            extra = 1 if counting and unit != "{p}" and len(pool) > nvals else 0  # a value proposed, never adopted
            values = self._values(unit, pool, nvals + extra)
            spare = values.pop() if extra else None
            days = self.days(len(values), 2, self.last_day - 2, gap=6)
            refs, out = [], []
            cid = f"hard-tl-{idx:02d}"
            genres = self.genres(len(values))
            Np = cap(np_)
            for k, ((v, acc), d) in enumerate(zip(values, days)):
                text = (self.say("first", np=np_, vu=v) if k == 0 else
                        self.say("next", np=np_, Np=Np, vu=v, o=values[k - 1][0]))
                r = self.tell(f"{cid}-v{k}", d, text, genres[k])
                refs.append(r)
                out.append((v, acc, d, r))
            traps = []
            if counting:  # restatements and turned-down proposals that are not changes
                for t in range(rng.randrange(1, 3)):
                    k = rng.randrange(len(out))
                    hi = out[k + 1][2] - 1 if k + 1 < len(out) else self.last_day
                    if hi - out[k][2] < 2:
                        continue
                    d = self.day(out[k][2] + 1, hi)
                    if spare is not None and t == 0 and rng.random() < 0.7:
                        text = self.say("refused", n=self.noise.name(), np=np_, x=spare[0], vu=out[k][0])
                    else:
                        text = self.say("again", np=np_, vu=out[k][0])
                    traps.append(self.tell(f"{cid}-t{t}", d, text))
            if counting:
                n = len(values) - 1
                accept = ([str(n)] if n == 1 else [str(n), NUMBER_WORDS[n]]) + TIMES_WORDS.get(n, [])
                ask = self.ask("count", np=np_)
                last = max(refs + traps, key=lambda r: self._order(r))
                self.probe("count_changes", ask, str(n), {"type": "exact", "accept": accept}, refs + traps, refs[-1],
                           ready=last, evidence=[(r, v) for v, _, _, r in out], changes=n,
                           values=[v for v, _, _, _ in out], refused=spare[0] if spare else None)
                continue
            if rng.random() < 0.5:  # "before it became Y"
                k = rng.randrange(1, len(out))
                y = out[k][0]
                right = out[k - 1]
                ask = self.ask("before_y", np=np_, y=y)
                ready = out[k][3]
                form = "before"
            else:  # "back on <date>"
                gaps = [k for k in range(len(out) - 1) if out[k + 1][2] - out[k][2] >= 2]
                for _ in range(50):  # a date whose numbers do not name a value
                    k = rng.choice(gaps)
                    on = self.day(out[k][2] + 1, out[k + 1][2] - 1)
                    ask = self.ask("before_date", np=np_, date=self.date(on))
                    if not names(ask, [a for _, acc, _, _ in out for a in acc]):
                        break
                right = out[k]
                ready = out[k + 1][3]
                form = "date"
            stale = [a for v, acc, _, _ in out if v != right[0] for a in acc]
            stale = [s for s in stale if not names(ask, [s])]
            spec = {"type": "exact", "accept": right[1], "stale": stale}
            used = refs[:refs.index(ready) + 1]
            self.probe("before_change", ask, right[0], spec, used, right[3], ready=ready,
                       evidence=[(right[3], right[0])], form=form)

    def lookalikes(self) -> None:
        rng = self.rng
        firsts = LOOK_FIRST[:]
        rng.shuffle(firsts)
        surnames = LOOK_SURNAMES[:]
        rng.shuffle(surnames)
        kinds = ["look_nights", "look_car", "look_station"]
        rng.shuffle(kinds)
        pairs = []
        for kind in kinds:
            for _ in range(100):
                first, (s1, s2) = firsts.pop(), surnames.pop()
                a, b = f"{first} {s1}", f"{first} {s2}"
                if self.fresh(a) and self.fresh(b):
                    break
            else:
                raise RuntimeError("no fresh look-alike names")
            self.claim(a), self.claim(b)
            self.people += [a, b]
            pool = {"look_nights": BRANCHES, "look_car": CARS, "look_station": STATIONS}[kind]
            pairs.append((kind, a, b, pool, "P"))
        repo_pairs = [p for p in REPO_PAIRS if self.fresh(p[0]) and self.fresh(p[1])]
        for (r1, r2), kind in zip(rng.sample(repo_pairs, 2), rng.sample(["look_lang", "look_host"], 2)):
            self.claim(r1), self.claim(r2)
            pairs.append((kind, r1, r2, LANGUAGES if kind == "look_lang" else HOSTS, "r"))
        for _ in range(100):
            letters = rng.choice(["KDK", "KCZ", "KDA", "KBX"])
            d = rng.sample("123456789", 3)
            tail = rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")
            t1, t2 = f"{letters} {''.join(d)}{tail}", f"{letters} {d[0]}{d[2]}{d[1]}{tail}"
            if self.fresh(t1) and self.fresh(t2):
                break
        self.claim(t1), self.claim(t2)
        pairs.append(("look_cargo", t1, t2, CARGO, "r"))
        s1, s2 = rng.choice([p for p in SUPPLIER_PAIRS if self.fresh(p[0]) and self.fresh(p[1])])
        self.claim(s1), self.claim(s2)
        pairs.append(("look_day", s1, s2, WEEKDAYS[:6], "r"))
        self.look_people = [(kind, who) for kind, a, b, _, slot in pairs if slot == "P" for who in (a, b)]
        for kind, a, b, pool, slot in pairs:
            va, vb = rng.sample(pool, 2)
            d1 = self.day(3, 45)
            d2 = self.day(d1 + 40, min(d1 + 75, self.last_day))
            if rng.random() < 0.5:
                d1, d2 = d2, d1
            refs = {}
            for j, (who, v, d) in enumerate(((a, va, d1), (b, vb, d2))):
                refs[who] = self.tell(f"hard-look-{len(self.probes):03d}-{j}", d, self.say(kind, **{slot: who}, v=v))
            for who, v, other in ((a, va, vb), (b, vb, va)):
                ask = self.ask(kind, **{slot: who})
                acc = [v, v + "s"] if kind == "look_day" else [v]
                rej = [other, other + "s"] if kind == "look_day" else [other]
                spec = exact(acc, ask, reject=rej, others=pool + ([x + "s" for x in pool] if kind == "look_day" else []))
                mate = b if who == a else a
                self.probe("far_lookalike", ask, v, spec, [refs[who], refs[mate]], refs[who],
                           evidence=[(refs[who], v)], pair=[a, b])

    def conflicts(self) -> None:
        rng = self.rng
        subjects = [s for s in CONFLICT_SUBJECTS if self.fresh(s[0])]
        rng.shuffle(subjects)
        shapes = ["rumour_then_memo"] * 4 + ["memo_then_rumour"] * 4 + ["correction"] * 4
        rng.shuffle(shapes)
        for (np_, pool), shape in zip(subjects, shapes):
            self.claim(np_)
            if pool is None:
                right, wrong = self.person(), self.person()
            else:
                right, wrong = rng.sample(pool, 2)
            d1 = self.day(3, self.last_day - 30)
            d2 = self.day(d1 + 8, min(d1 + 50, self.last_day))
            cid = f"hard-cf-{len(self.probes):03d}"
            if shape == "rumour_then_memo":
                r1 = self.tell(f"{cid}-a", d1, self.say("rumour", np=np_, v=wrong, b=rng.choice(BRANCHES)),
                               "groupchat")
                r2 = self.tell(f"{cid}-b", d2, self.say("confirmed", np=np_, v=right), "memo")
                key, refs = r2, [r1, r2]
            elif shape == "memo_then_rumour":
                r1 = self.tell(f"{cid}-a", d1, self.say("confirmed", np=np_, v=right), "memo")
                r2 = self.tell(f"{cid}-b", d2, self.say("rumour_late", np=np_, v=wrong), "groupchat")
                key, refs = r1, [r1, r2]
            else:
                d2 = self.day(d1 + 1, d1 + 6)
                r1 = self.tell(f"{cid}-a", d1, self.say("minuted", np=np_, v=wrong), "minutes")
                r2 = self.tell(f"{cid}-b", d2, self.say("erratum", np=np_, v=right, w=wrong, date=self.date(d1)),
                               rng.choice(["email", "memo"]))
                key, refs = r2, [r1, r2]
            ask = self.ask("conflict", np=np_, wh="who" if pool is None else "what")
            acc = [right.removeprefix("KES ")] if right.startswith("KES ") else [right.removeprefix("the ")]
            st = [wrong.removeprefix("KES ")] if wrong.startswith("KES ") else [wrong.removeprefix("the ")]
            self.probe("conflict", ask, right, {"type": "exact", "accept": acc, "stale": st}, refs, key,
                       ready=refs[-1], evidence=[(key, right)], shape=shape, rumour=wrong)

    def reworded(self) -> None:
        rng = self.rng
        keys = list(REWORDED)
        rng.shuffle(keys)
        branches = BRANCHES[:]
        rng.shuffle(branches)
        self.rw_people: list[tuple[str, str]] = []
        for key in keys[:FAMILIES["reworded"]]:
            pool = REWORDED[key]
            d = self.day(2, self.last_day)
            slots: dict = {}
            if key in ("rw_chiller", "rw_sign", "rw_keys"):
                slots["b"] = branches.pop()
            if key == "rw_keys":
                v = self.person()
                accept, others = [v], []
            else:
                v = rng.choice(pool)
                accept = [v, v + "s"] if key == "rw_dayoff" else [v]
                others = pool
            if key not in ("rw_chiller", "rw_sign", "rw_keys"):
                slots["P"] = self.person()
                self.rw_people.append((key, slots["P"]))
            ref = self.tell(f"hard-rw-{key}", d, self.say(key, v=v, **slots))
            ask = self.ask(key, **slots)
            self.probe("reworded", ask, v, exact(accept, ask, others=others), [ref], ref,
                       evidence=[(ref, v)], slot=key)

    def aggregates(self) -> None:
        rng = self.rng
        topics = [t for t in AGG_TOPICS if self.fresh(t[0])]
        rng.shuffle(topics)
        self.agg_unused: list[tuple[str, str, str]] = []
        for ti, (item, unit) in enumerate(topics[:3]):
            self.claim(item)
            brs = rng.sample(BRANCHES, 5)
            self.agg_unused.append((rng.choice([b for b in BRANCHES if b not in brs]), item, unit))
            prices = rng.sample(range(250, 1200, 10), 5)
            days = self.days(5, 2, self.last_day - 10, gap=4)
            refs, ev, told = [], [], {}
            final = dict(zip(brs, prices))
            for k, (b, p, d) in enumerate(zip(brs, prices, days)):
                r = self.tell(f"hard-agg-{ti}-{k}", d, self.say("agg", b=b, p=p, unit=unit, item=item))
                refs.append(r)
                ev.append((r, str(p)))
                told[b] = r
            if ti == 0 or rng.random() < 0.5:  # one price moves later; the aggregate uses the latest
                b = rng.choice(brs)
                newp = rng.choice([x for x in range(250, 1200, 10) if x not in prices])
                d = self.day(days[brs.index(b)] + 4, self.last_day)
                r = self.tell(f"hard-agg-{ti}-up", d, self.say("agg_up", b=b, p=newp, unit=unit, item=item))
                refs.append(r)
                ev.append((r, str(newp)))
                final[b] = newp
                told[b] = r
            last = max(refs, key=self._order)
            vals = sorted(final.values())
            hi = max(final, key=final.get)
            lo = min(final, key=final.get)
            ask = self.ask("agg_max", item=item)
            self.probe("aggregate", ask, hi, exact([hi], ask, others=brs), refs, told[hi], ready=last, evidence=ev,
                       op="max", prices=final)
            ask = self.ask("agg_min", item=item)
            self.probe("aggregate", ask, lo, exact([lo], ask, others=brs), refs, told[lo], ready=last, evidence=ev,
                       op="min", prices=final)
            j = rng.randrange(1, 4)  # a line halfway between two prices: 1 to 3 branches pay above it
            t = (vals[-j - 1] + vals[-j]) // 2 // 5 * 5
            n = sum(1 for x in vals if x > t)
            ask = self.ask("agg_count", t=t, unit=unit, item=item)
            self.probe("aggregate", ask, str(n), {"type": "exact", "accept": [str(n), NUMBER_WORDS[n]]}, refs,
                       refs[0], ready=last, evidence=ev, op="count", threshold=t, prices=final)
            b1, b2 = rng.sample(brs, 2)
            if final[b1] < final[b2]:
                b1, b2 = b2, b1
            if rng.random() < 0.5:
                v = final[b1] + final[b2]
                ask = self.ask("agg_sum", b1=b1, b2=b2, unit=unit, item=item)
                op = "sum"
            else:
                v = final[b1] - final[b2]
                ask = self.ask("agg_diff", b1=b1, b2=b2, item=item)
                op = "diff"
            self.probe("aggregate", ask, f"KES {v:,}", {"type": "exact", "accept": [f"{v:,}"]}, refs, refs[0],
                       ready=last, evidence=ev, op=op, prices=final)

    def negated(self) -> None:
        """Near misses: the chain breaks after its first link, the attribute was told for someone else, the branch
        was never priced. Phrased exactly like the questions that do have answers."""
        rng = self.rng
        hard_people = sorted(set(self.people))
        out: list[tuple[str, list[str], list[str], list[str] | None]] = []  # (ask, pool, about, absent values)
        for anchor, dish, _ in self.broken["special"]:
            out.append((self.ask("special", anchor=anchor), TOWNS, [dish], list(self.suppliers)))
        for proj, lead, _ in self.broken["proj"]:
            out.append((self.ask("never_boss", proj=proj), NAME_POOL + hard_people, [lead],
                        [q for q in hard_people if q != lead]))
        for area, van, _ in self.broken["van"]:
            out.append((self.ask("never_driver", area=area), NAME_POOL + hard_people, [van], hard_people))
        looks = [rng.choice(self.look_people[k:k + 2]) for k in rng.sample(range(0, len(self.look_people), 2), 2)]
        for kind, who in looks:
            other = rng.choice([k for k in ("look_nights", "look_car", "look_station") if k != kind])
            pool = {"look_nights": BRANCHES, "look_car": CARS, "look_station": STATIONS}[other]
            out.append((self.ask(other, P=who), pool, [who], pool))
        rw = rng.sample(self.rw_people, 2)
        for key, who in rw:
            other = rng.choice([k for k in REWORDED if k not in ("rw_chiller", "rw_sign", "rw_keys", key)])
            pool = REWORDED[other] + ([v + "s" for v in REWORDED[other]] if other == "rw_dayoff" else [])
            out.append((self.ask(other, P=who), pool, [who], pool))
        for b, item, unit in self.agg_unused[:2]:
            out.append((self.ask("never_price", b=b, unit=unit, item=item), ["#number"], [b, item], None))
        if len(out) != FAMILIES["negated"]:
            raise RuntimeError(f"{len(out)} near misses, not {FAMILIES['negated']}")
        for ask, pool, about, absent in out:
            pool = [v for v in pool if not names(ask, [v])] if pool != ["#number"] else pool
            self.probe("negated", ask, "(never said)", {"type": "never", "pool": list(dict.fromkeys(pool))}, [], None,
                       absent={"about": about, "values": absent})

    def _order(self, ref: str) -> tuple:
        p = next(p for p in self.plants if p.ref == ref)
        return (p.day, p.frac, p.ref)


# -- the base ---------------------------------------------------------------------------------------------------

def _base_planner(seed: int, days: int):
    """The base's planner run again for its seed (no tokenizer): every planted event's text, and the configs."""
    dates = calendar(110)
    world = build_world(random.Random(f"{seed}:world"))
    noise = Noise(random.Random(f"{seed}:noise"), world, dates)
    per_day = budgets(random.Random(f"{seed}:days"), TARGET)
    ends = list(accumulate(per_day))

    def where(depth: float) -> tuple[int, float]:
        for d, end in enumerate(ends, start=1):
            if depth <= end:
                return d, (depth - (end - per_day[d - 1])) / per_day[d - 1]
        return 110, 1.0

    pl = Planner(seed, world, noise, dates, where, TARGET)
    pl.run()
    return pl, world


def _protected(events: list[dict], probes: list[dict], planner) -> set[int]:
    texts = {t for p in planner.plants for _, _, t in p.events}
    keep = {i for i, e in enumerate(events) if e["text"] in texts}
    missing = len(texts - {events[i]["text"] for i in keep})
    if missing:
        raise RuntimeError(f"{missing} planted texts of the base are not in its script: the base was built by "
                           f"another version of the generator")
    for p in probes:
        keep.update(_probe_events(p))
    return keep


def _probe_events(p: dict) -> list[int]:
    out = list(p.get("events") or [])
    if p.get("event") is not None:
        out.append(p["event"])
    g = p["grader"]
    if g["type"] == "timeline":
        out += [v["event"] for v in g["values"]]
    if g["type"] == "page":
        out += [v["event"] for v in g["timeline"]]
    return out


def _configs(events: list[dict], planner) -> list[tuple[str, list[str], int | None]]:
    by_text = {e["text"]: i for i, e in enumerate(events)}
    plants = {p.ref: p for p in planner.plants}
    out = []
    for np_, _, values in CONFIGS:
        ref = planner.configs.get(np_)
        told = None
        if ref:
            p = plants[ref]
            told = by_text[p.events[p.key % len(p.events)][2]]
        out.append((np_, [str(v) for v in values], told))
    return out


# -- putting it together ----------------------------------------------------------------------------------------

def harden(base_events: list[dict], base_probes: list[dict], base_manifest: dict, seed: int,
           count: Callable[[str], int] | None = None, base_dir: str | None = None) -> HardHaul:
    """The hard set for ``seed`` planted into a base history (its events, probes and manifest)."""
    count = count or tok.counter()
    E = base_events
    base_seed = base_manifest["seed"]
    planner, world = _base_planner(base_seed, max(e["day"] for e in E))
    protected = _protected(E, base_probes, planner)
    last_day = min(LAST_DAY, max(e["day"] for e in E) - 3)
    dates = calendar(max(e["day"] for e in E))
    text = "\n".join(e["text"] for e in E).casefold()
    hp = HardPlanner(seed, world, dates, last_day, text)
    hp.run()

    # where each plant goes: before base index k, on a boundary between whole units, nearest its place in the day
    by_day: dict[int, list[int]] = defaultdict(list)
    for k in range(1, len(E) + 1):
        nxt = E[k] if k < len(E) else None
        if nxt is not None and nxt["role"] == "assistant":
            continue
        if nxt is not None and (k - 1) in protected and k in protected:
            continue
        by_day[E[k - 1]["day"]].append(k)
    start = {}
    for e in E:
        start.setdefault(e["day"], e["cum_tokens"] - e["tokens"])
    end = {e["day"]: e["cum_tokens"] for e in E}
    slots: dict[int, list[tuple[float, str, HardPlant]]] = defaultdict(list)
    for p in hp.plants:
        want = start[p.day] + p.frac * (end[p.day] - start[p.day])
        k = min(by_day[p.day], key=lambda k: (abs(E[k - 1]["cum_tokens"] - want), k))
        slots[k].append((p.frac, p.ref, p))
    plant_tokens = {p.ref: count(p.text) for p in hp.plants}

    # noise taken out near each insertion, so the depths and the 2M cut stay where they were
    removable = [i for i, e in enumerate(E) if i not in protected and e["kind"] in ("doc", "meeting", "decision", "log")
                 and e["role"] in ("user", "tool") and not (i + 1 < len(E) and E[i + 1]["role"] == "assistant")]
    removable_set = set(removable)
    deleted: set[int] = set()
    debt = 0
    for k in sorted(slots):
        debt += sum(plant_tokens[r] for _, r, _ in slots[k])
        day = E[k - 1]["day"]
        while debt > 0:
            near = [i for i in range(max(0, k - 400), min(len(E), k + 400)) if i in removable_set and i not in deleted
                    and E[i]["day"] in (day, day + 1)]
            if not near:
                break
            i = min(near, key=lambda i: (abs(i - k), i))
            deleted.add(i)
            debt -= E[i]["tokens"]

    events: list[dict] = []
    old2new: dict[int, int] = {}
    where_ref: dict[str, int] = {}
    total = 0

    def emit(e: dict, tokens: int) -> None:
        nonlocal total
        total += tokens
        events.append({"i": len(events), "day": e["day"], "kind": e["kind"], "role": e["role"], "text": e["text"],
                       "tokens": tokens, "cum_tokens": total})

    for k in range(len(E) + 1):
        for _, ref, p in sorted(slots.get(k, []), key=lambda x: (x[0], x[1])):
            where_ref[ref] = len(events)
            emit({"day": E[k - 1]["day"], "kind": p.kind, "role": p.role, "text": p.text}, plant_tokens[ref])
        if k < len(E) and k not in deleted:
            old2new[k] = len(events)
            emit(E[k], E[k]["tokens"])

    day_end = {e["day"]: e["cum_tokens"] for e in events}
    base = [_reindex(p, old2new, events, day_end) for p in base_probes]
    probes = [_finish(p, events, where_ref) for p in hp.probes]
    configs = [(np_, vals, old2new[t] if t is not None else None) for np_, vals, t in _configs(E, planner)]
    _verify(events, base + probes, configs)
    check(events, probes, base_probes=base)
    manifest = _manifest(seed, base_manifest, events, probes, base, len(deleted), base_dir)
    return HardHaul(seed, events, probes, base, manifest, len(deleted), hp.plants)


def _reindex(p: dict, old2new: dict[int, int], events: list[dict], day_end: dict[int, int]) -> dict:
    """A base probe with its event indices and token depths moved to the new script."""
    p = copy.deepcopy(p)
    cum = lambda i: events[i]["cum_tokens"]  # noqa: E731
    p["events"] = [old2new[i] for i in p.get("events") or []]
    if p.get("event") is not None:
        p["event"] = old2new[p["event"]]
        p["planted_at"] = cum(p["event"])
        p["planted_day"] = events[p["event"]]["day"]
    g = p["grader"]
    if g["type"] == "timeline":
        for v in g["values"]:
            v["event"] = old2new[v["event"]]
            v["tokens"] = cum(v["event"])
        if g["on_day"] is not None:
            g["day_over_at"] = day_end[g["on_day"]]
            right = [v for v in g["values"] if v["day"] <= g["on_day"]][-1]
            p["ready_at"] = max(right["tokens"], g["day_over_at"])
        else:
            p["ready_at"] = g["values"][-1]["tokens"]
    elif g["type"] == "page":
        for v in g["timeline"]:
            v["event"] = old2new[v["event"]]
            v["tokens"] = cum(v["event"])
        p["ready_at"] = g["timeline"][0]["tokens"]
    else:
        p["ready_at"] = cum(max(p["events"])) if p["events"] else None
    return p


def _finish(p: dict, events: list[dict], where_ref: dict[str, int]) -> dict:
    p = dict(p)
    refs = p.pop("refs")
    key = p.pop("key")
    ready = p.pop("ready_ref")
    idx = sorted(where_ref[r] for r in refs)
    p["events"] = idx
    p["event"] = where_ref[key] if key else None
    p["planted_at"] = events[p["event"]]["cum_tokens"] if key else None
    p["planted_day"] = events[p["event"]]["day"] if key else None
    if refs:
        last = where_ref[ready] if ready else idx[-1]
        p["ready_at"] = events[last]["cum_tokens"]
    else:
        p["ready_at"] = None
    p["evidence"] = [{"event": where_ref[r], "text": t} for r, t in p["evidence"]]
    p.setdefault("sample", False)
    p.setdefault("ask_day", None)
    return p


def _manifest(seed: int, base: dict, events: list[dict], probes: list[dict], base_probes: list[dict], removed: int,
              base_dir: str | None) -> dict:
    cuts = {}
    for name, limit in CUTS.items():
        inside = [e for e in events if e["cum_tokens"] <= limit]
        cuts[name] = {"limit": limit, "tokens": inside[-1]["cum_tokens"], "events": len(inside),
                      "last_day": inside[-1]["day"],
                      "probes": dict(Counter(p["family"] for p in probes if at_cut(p, limit) is not None)),
                      "base_probes": dict(Counter(p["family"] for p in base_probes if at_cut(p, limit) is not None))}
    kinds: dict[str, dict] = defaultdict(lambda: {"events": 0, "tokens": 0})
    for e in events:
        kinds[e["kind"]]["events"] += 1
        kinds[e["kind"]]["tokens"] += e["tokens"]
    m = {k: v for k, v in base.items() if k not in ("cuts", "kinds", "families", "samples", "script_sha", "events",
                                                    "tokens")}
    m.update(name="The Long Haul, hard set", hard=True, hard_seed=seed, base_seed=base["seed"], seed=base["seed"],
             base={"dir": base_dir, "script_sha": base.get("script_sha"), "events": base.get("events"),
                   "tokens": base.get("tokens"), "families": base.get("families")},
             families=dict(Counter(p["family"] for p in probes)),
             base_families=dict(Counter(p["family"] for p in base_probes)),
             probes="probes.jsonl holds the hard set only; probes-base.jsonl holds the base's probes re-indexed",
             events=len(events), tokens=events[-1]["cum_tokens"], cuts=cuts, kinds=dict(kinds),
             removed_noise_events=removed, samples=[],
             script_sha=hashlib.sha256("".join(e["text"] for e in events).encode()).hexdigest()[:16])
    return m


# -- checks -------------------------------------------------------------------------------------------------------

def _words(s: str) -> list[str]:
    s = re.sub(r"\{[^}]*\}", " x ", s.casefold())
    s = s.replace("[", " ").replace("]", " ").replace("|", " ")
    return re.findall(r"[a-z0-9]+", s)


def grams(s: str, n: int = 4) -> set[tuple[str, ...]]:
    w = _words(s)
    return {g for g in zip(*(w[i:] for i in range(n))) if sum(t == "x" for t in g) < 3}


def probes_py_strings() -> list[str]:
    """Every string constant in probes.py (the original families' statements and questions)."""
    src = (Path(__file__).parent / "probes.py").read_text(encoding="utf-8")
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            out.append("".join(v.value if isinstance(v, ast.Constant) else "{x}" for v in node.values))
    return out


def phrase_clashes(templates: list[str], against: list[str], n: int = 4) -> list[str]:
    seen: dict[tuple, str] = {}
    for s in against:
        for g in grams(s, n):
            seen.setdefault(g, s)
    return [f"{t!r} shares {' '.join(g)!r} with {seen[g]!r}" for t in templates for g in sorted(grams(t, n))
            if g in seen]


def templates() -> dict[str, list[str]]:
    return {"ask": [t for ts in ASK.values() for t in ts], "say": [t for ts in SAY.values() for t in ts]}


def check(events: list[dict], probes: list[dict], base_probes: list[dict] | None = None) -> None:
    """The hard set's own fairness checks. Raises on any failure."""
    errors = []
    prev = 0
    for k, e in enumerate(events):
        if e["i"] != k or e["cum_tokens"] != prev + e["tokens"] or e["tokens"] <= 0:
            errors.append(f"event {k} is not numbered or counted in order")
            break
        prev = e["cum_tokens"]
    fams = Counter(p["family"] for p in probes)
    if fams != Counter(FAMILIES):
        errors.append(f"families {dict(fams)} are not {FAMILIES}")
    for p in probes:
        for v in p.get("evidence", []):
            if v["text"].casefold() not in events[v["event"]]["text"].casefold():
                errors.append(f"{p['id']}: event {v['event']} does not hold {v['text']!r}")
        if p["grader"]["type"] == "exact":
            if p["ready_at"] is None or p["ready_at"] > CUTS["2M"]:
                errors.append(f"{p['id']}: ready at {p['ready_at']}, past the 2M cut")
            if p["family"] not in ("count_changes", "aggregate") or p.get("op") in ("max", "min"):
                if not names(events[p["event"]]["text"], p["grader"]["accept"]):
                    errors.append(f"{p['id']}: its event does not name {p['answer']!r}")
            if p["family"] == "count_changes" and len(p["evidence"]) != p["changes"] + 1:
                errors.append(f"{p['id']}: {len(p['evidence'])} values for {p['changes']} changes")
        else:
            about, values = p["absent"]["about"], p["absent"]["values"]
            for e in events:
                low = e["text"].casefold()
                if all(a.casefold() in low for a in about):
                    if values is None or names(e["text"], values):
                        errors.append(f"{p['id']}: event {e['i']} says what was never to be said")
                        break
    clash = phrase_clashes(templates()["ask"] + templates()["say"], probes_py_strings())
    if base_probes is not None:
        clash += phrase_clashes([p["ask"] for p in probes], [p["ask"] for p in base_probes], n=5)
    errors += clash
    if errors:
        raise AssertionError("hard set unfair: " + "; ".join(errors[:8]))


# -- grading --------------------------------------------------------------------------------------------------------

def grade(probe: dict, answer: str) -> Grade:
    """grade.py's verdict on a hard probe. The hard graders are grade.py's own types (exact, never), so a runner that
    uses grade.py directly gets the same verdict; this wrapper refuses anything else. Counts accept their number
    words ("three", "twice") through the accept list."""
    kind = probe["grader"]["type"]
    if probe.get("hard") and kind not in ("exact", "never"):
        raise ValueError(f"{probe['id']}: a hard probe must use an exact or never grader, not {kind}")
    return base_grade(probe, answer or "")


# -- disk -----------------------------------------------------------------------------------------------------------

def build(base_dir: Path, seed: int, count: Callable[[str], int] | None = None) -> HardHaul:
    base_dir = Path(base_dir)
    if base_dir.name.startswith("s1"):
        raise SystemExit(f"{base_dir} is the locked exam history; the hard set is never built from it")
    manifest = json.loads((base_dir / "manifest.json").read_text())
    if manifest.get("hard"):
        raise SystemExit(f"{base_dir} is already a hard set")
    return harden(load_events(base_dir), load_probes(base_dir), manifest, seed, count, str(base_dir))


def write(h: HardHaul, out: Path) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("script.jsonl", h.events), ("probes.jsonl", h.probes), ("probes-base.jsonl", h.base_probes)):
        with open(out / name, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "manifest.json").write_text(json.dumps(h.manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_base(out: Path) -> list[dict]:
    """A hard dir's base probes (re-indexed to its script)."""
    return [json.loads(line) for line in open(Path(out) / "probes-base.jsonl", encoding="utf-8")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.haul.hard")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="plant the hard set into a built Long Haul")
    b.add_argument("--from", dest="base", type=Path, required=True)
    b.add_argument("--seed", type=int, default=4)
    b.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("show", help="the hard questions per family, with examples")
    s.add_argument("--dir", type=Path, required=True)
    s.add_argument("--examples", type=int, default=3)
    g = sub.add_parser("grade", help="grade answers given as JSON lines of {id, answer}")
    g.add_argument("--dir", type=Path, required=True)
    g.add_argument("--answers", type=Path, required=True)
    g.add_argument("--cut", default="2M")
    a = ap.parse_args(argv)

    if a.cmd == "build":
        h = build(a.base, a.seed)
        write(h, a.out)
        m = h.manifest
        print(f"{a.out}: {m['events']} events, {m['tokens']:,} tokens; {len(h.probes)} hard questions "
              f"{json.dumps(m['families'])}; {len(h.base_probes)} base probes re-indexed; "
              f"{len(h.plants)} events planted, {h.removed} noise events taken out")
        for name, c in m["cuts"].items():
            print(f"  {name:>4}: {c['tokens']:>9,} tokens, {sum(c['probes'].values())} hard questions askable")
        return 0

    probes = load_probes(a.dir)
    if a.cmd == "show":
        fams: dict[str, list] = defaultdict(list)
        for p in probes:
            fams[p["family"]].append(p)
        for fam, ps in fams.items():
            print(f"{fam} ({len(ps)})")
            for p in ps[:a.examples]:
                acc = p["grader"].get("accept") or "(declines)"
                print(f"  {p['ask']}  ->  {p['answer']}  accept {acc}")
        return 0

    by_id = {p["id"]: p for p in probes}
    cut = CUTS.get(a.cut) or int(a.cut)
    tally: Counter = Counter()
    for line in open(a.answers, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        p = by_id.get(row.get("id"))
        q = at_cut(p, cut) if p else None
        if q is None:
            print(json.dumps({"id": row.get("id"), "verdict": None, "reason": "unknown or not askable at this cut"}))
            continue
        v, reason = grade(q, str(row.get("answer", "")))
        tally[(q["family"], v)] += 1
        print(json.dumps({"id": q["id"], "family": q["family"], "verdict": v, "reason": reason}))
    for (fam, v), n in sorted(tally.items()):
        print(f"{fam:>14} {v:<12} {n}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
