"""Planting the probes: what is told, when, in whose words, and the question that later checks it.

A ``Plant`` is one or more events placed on a day at a position within it (0 = first, 1 = last). A probe names the
plants it needs by ``ref``; the builder turns those into event indices and token depths once the script is laid
out. Families: fact, changed, two_hop, maths, page, code, lookalike, never.
"""

from __future__ import annotations

import random
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from camr_engine.bench.haul import codefit, maths, page
from camr_engine.bench.haul.grade import names
from camr_engine.bench.haul.noise import Noise
from camr_engine.bench.haul.words import (BRANCHES, DISHES, FIRST, LAPTOPS, MONTHS, ROLES, ROUTES, SUPPLY_ITEMS, SURNAMES,
                                     TOWNS, VENUES, WEEKDAYS, cap, ordinal, plural, poss, say)
from camr_engine.bench.haul.world import Person, World

COUNTS = {"fact": 400, "changed": 80, "two_hop": 40, "maths": 40, "page": 3, "code": 20, "lookalike": 30,
          "never": 60}
DECOYS = 400


@dataclass
class Plant:
    ref: str
    day: int
    pos: float
    events: list[tuple[str, str, str]]
    key: int = -1  # which of the events carries what is planted (the probe's "event")


def weekday(rng: random.Random) -> tuple[str, list[str]]:
    d = rng.choice(WEEKDAYS)
    return d, [d, d + "s"]


def hhmm(h: int, m: int) -> tuple[str, list[str]]:
    """'21:30' and the usual ways of writing it. The grader reads times as minutes since midnight, so these are only
    for writing the statement; any of them names the time."""
    v = f"{h:02d}:{m:02d}"
    h12 = h % 12 or 12
    ap = "am" if h < 12 else "pm"
    out = [v, f"{h12}:{m:02d} {ap}", f"{h12}:{m:02d}{ap}", f"{h12}.{m:02d} {ap}", f"{h12}.{m:02d}{ap}"]
    if h < 10:
        out.append(f"{h}:{m:02d}")
    return v, out


def person_accept(p: Person, world: World) -> list[str]:
    everyone = world.staff + world.contacts + world.managers
    firsts = [q.first for q in everyone]
    out = [p.full]
    if firsts.count(p.first) == 1 and p.first not in world.hop_people:
        out.append(p.first)
    return out


# -- the fact catalog: per kind, attribute -> (value maker, ways to say it, ways to ask it) ----------------------
# A value maker takes (rng, planner) and returns (value as written, values that count as naming it).

def _num(lo: int, hi: int, step: int = 1, unit: str = "") -> Callable:
    def make(rng: random.Random, pl: "Planner") -> tuple[str, list[str]]:
        n = rng.randrange(lo, hi + 1, step)
        return (f"{n:,}{unit}", [f"{n:,}"])
    return make


def _uniq(key: str, make: Callable) -> Callable:
    def made(rng: random.Random, pl: "Planner") -> tuple[str, list[str]]:
        for _ in range(500):
            v = make(rng, pl)
            if v[0] not in pl.used[key]:
                pl.used[key].add(v[0])
                return v
        raise RuntimeError(f"ran out of values for {key}")
    return made


def _choice(seq: list[str]) -> Callable:
    return lambda rng, pl: (lambda v: (v, [v]))(rng.choice(seq))


def _person(rng: random.Random, pl: "Planner") -> tuple[str, list[str]]:
    p = pl.take_contact()
    return p.full, person_accept(p, pl.world)


def _staff_person(rng: random.Random, pl: "Planner") -> tuple[str, list[str]]:
    p = rng.choice(pl.world.staff)
    return p.full, person_accept(p, pl.world)


def _plate(rng: random.Random, pl: "Planner") -> tuple[str, list[str]]:
    v = f"K{rng.choice('ABCD')}{rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')} {rng.randrange(100, 1000)}" \
        f"{rng.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}"
    return v, [v, v.replace(" ", "")]


STAFF_ATTRS = {
    "ext": (_uniq("ext", _num(200, 899)), [
        "[Put|Note] {e} down as extension {v}[ on the new switchboard|].", "{e} is on extension {v} now that the phones "
        "are in.", "If you need {e}, dial extension {v}[, not the main line|].", "{es} desk phone is extension {v}.",
        "{e} asked me to share their extension: {v}."],
        ["What is {es} phone extension?", "Which extension do I dial to reach {e}?"]),
    "locker": (_uniq("locker", _num(1, 160)), [
        "{e} [has|got] locker {v} in the staff room.", "Locker {v} [is|now belongs to] {e}[, the one by the window|].",
        "Gave {e} the key to locker {v}."], ["Which locker number is {es}?", "What locker number does {e} have?"]),
    "route": (_choice(ROUTES), [
        "{e} comes in on the route {v} matatu[ every morning|].", "{e} takes matatu route {v} to work[, which is why "
        "they're late when it rains|].", "{e} says the {v} matatu is the only one that works for them."],
        ["Which matatu route does {e} take to work?"]),
    "hometown": (_choice(TOWNS), [
        "{e} is from {v} originally.", "{e} grew up in {v}.", "{e} [is going|went] home to {v} for the weekend, "
        "that's where [the family is|they grew up]."], ["Which town is {e} from?", "Where did {e} grow up?"]),
    "dayoff": (lambda rng, pl: weekday(rng), [
        "{es} day off is {v}.", "{e} is off every {v}[, plan the rota around it|].", "Don't schedule {e} on {v}s, "
        "that's their day off."], ["What is {es} day off?", "Which day of the week is {e} off?"]),
    "laptop": (_choice(LAPTOPS), [
        "{e} is working off a {v}[ the office bought|].", "The {v} on the shelf is {es}.", "{e} got issued a {v}[ for "
        "the back office work|]."], ["Which laptop does {e} use?"]),
    "badge": (_uniq("badge", lambda rng, pl: (lambda v: (v, [v]))(f"MNK-{rng.randrange(1000, 10000)}")), [
        "{es} staff badge number is {v}.", "Badge {v} goes to {e}.", "Printed {es} badge: {v}."],
        ["What is {es} staff badge number?"]),
    "role": (_choice(ROLES), [
        "{e} [started|is working] as our {v}[ this week|].", "{e} is the {v} now.", "Meet {e}, our new {v}."],
        ["What is {es} job at the kitchen?", "What does {e} do at Mama Njeri's Kitchen?"]),
    "branch": (_choice(BRANCHES), [
        "{e} works out of the {v} branch.", "{e} is based at {v}[ from this week|].", "{e} will cover the {v} branch"
        "[ for good|]."], ["Which branch does {e} work at?"]),
}
SUPPLIER_ATTRS = {
    "supplies": (None, ["Our {v} {comes} from {e}.", "{e} supplies [all|] our {v}.", "We buy {v} from {e}[ now|]."],
                 ["What does {e} supply us with?"]),
    "delivery_day": (lambda rng, pl: weekday(rng), [
        "{e} delivers on {v}s.", "{es} truck comes every {v}.", "Delivery day for {e} is {v}."],
        ["On which day of the week does {e} deliver?"]),
    "account": (_uniq("account", lambda rng, pl: (lambda v: (v, [v]))(f"AC-{rng.randrange(10000, 100000)}")), [
        "Our account number with {e} is {v}.", "Quote account {v} when you call {e}.", "The {e} invoice says account "
        "{v}."], ["What is our account number with {e}?"]),
    "contact": (_person, ["Our contact at {e} is {v}.", "Call {v} at {e} for orders.", "{v} handles our account at "
                          "{e}."], ["Who is our contact person at {e}?"]),
    "plate": (_uniq("plate", _plate), [
        "{es} delivery truck is {v}.", "The {e} truck, plate {v}, [was early|came late|blocked the gate] today.",
        "Security should let in {v}, that's {es} truck."], ["What is the number plate of {es} delivery truck?"]),
    "lead_time": (_num(1, 10), ["{e} needs {v} days' notice for an order.", "Order from {e} at least {v} days ahead."],
                  ["How many days' notice does {e} need for an order?"]),
    "min_order": (_num(2000, 50000, 500), ["{es} minimum order is KES {v}.", "{e} won't deliver below KES {v}."],
                  ["What is {es} minimum order, in shillings?"]),
}
BRANCH_ATTRS = {
    "seats": (_num(24, 180), ["{b} seats {v} people[ after the refit|].", "The {b} branch has {v} seats.",
                              "We counted {v} seats at {b}."], ["How many seats does the {b} branch have?"]),
    "parking": (_num(3, 40), ["{b} has {v} parking slots.", "There are {v} parking spots at the {b} branch."],
                ["How many parking slots does the {b} branch have?"]),
    "ovens": (_num(2, 9), ["The {b} kitchen runs {v} ovens.", "{b} has {v} ovens[ now|]."],
              ["How many ovens does the {b} kitchen have?"]),
    "landlord": (_person, ["The landlord at {b} is {v}.", "{v} owns the {b} building[, rent goes to them|]."],
                 ["Who is the landlord of the {b} branch?"]),
    "rent_day": (lambda rng, pl: (lambda n: (ordinal(n), [str(n)]))(rng.randrange(1, 29)), [
        "Rent for {b} is due on the {v} of every month.", "{b} rent: due the {v}[, don't be late|]."],
        ["On which day of the month is the {b} rent due?"]),
    "radius": (_num(3, 15, 1, " km"), ["{b} delivers within {v}.", "The delivery radius from {b} is {v}."],
               ["What is the delivery radius of the {b} branch, in km?"]),
    "generator": (_choice(["10", "15", "20", "30", "40", "60"]), [
        "{b} has a {v} kVA backup generator.", "The generator at {b} is {v} kVA."],
        ["What size is the {b} backup generator, in kVA?"]),
    "extinguishers": (_num(2, 12), ["{b} has {v} fire extinguishers[ on the walls|].", "We now keep {v} fire "
                                                                                   "extinguishers at {b}."],
                      ["How many fire extinguishers does the {b} branch have?"]),
}
DISH_ATTRS = {
    "portion": (_num(150, 600, 10, " g"), ["A portion of {e} is {v}.", "{E} goes out at {v} a plate."],
                ["How many grams is a portion of {e}?"]),
    "prep": (_num(5, 90), ["{E} takes {v} minutes from order to plate.", "Prep time for {e} is {v} minutes."],
             ["How many minutes does {e} take to prepare?"]),
    "creator": (_staff_person, ["The {e} recipe is {v}'s.", "{v} came up with our {e}."],
                ["Who came up with the {e} recipe?"]),
    "price": (_num(80, 900, 10), ["{E} is KES {v} on the menu.", "We're charging KES {v} for {e}."],
              ["How much is {e} on the menu?"]),
    "branch_only": (_choice(BRANCHES), ["{E} is only served at the {v} branch.", "Only {v} makes {e}[, the others "
                                                                                 "don't have the oven for it|]."],
                    ["Which branch is the only one that serves {e}?"]),
}
CLIENT_ATTRS = {
    "guests": (_num(20, 400), ["The {e} event is for {v} guests.", "{e} confirmed {v} people."],
               ["How many guests is the {e} event for?"]),
    "venue": (None, ["The {e} do is at {v}.", "{e} booked {v} for their event."],
              ["Where is the {e} event being held?"]),
    "contact": (_person, ["Our contact at {e} is {v}.", "{v} is organising the {e} event[ on their side|]."],
                ["Who is our contact at {e}?"]),
    "main": (_choice(DISHES), ["{e} chose {v} as the main dish.", "{e} want {v} for the main."],
             ["Which main dish did {e} choose?"]),
    "deposit": (_num(5000, 80000, 500), ["{e} paid a deposit of KES {v}.", "Deposit from {e} came in: KES {v}."],
                ["How much deposit did {e} pay?"]),
}
# Settings that are told once: (noun phrase, how the value is written, values).
CONFIGS = [
    ("the Redis TTL for the menu cache", "{v} seconds", [45, 75, 150, 210, 270, 330, 420, 540]),
    ("the maximum photo upload size", "{v} MB", [3, 6, 7, 9, 11, 14, 18]),
    ("the Postgres database name", "{v}", ["mnk_prod", "kitchen_main", "njeri_db", "mnk_core", "mamanjeri_live"]),
    ("the S3 bucket for menu photos", "{v}", ["mnk-menu-photos", "njeri-img-store", "mnk-media-ke", "kitchen-pics-nbo"]),
    ("the Sentry project name", "{v}", ["mnk-frontend", "njeri-backend", "kitchen-site-prod", "mnk-api-errors"]),
    ("the SMS sender ID", "{v}", ["MAMANJERI", "NJERIKITCH", "MNKITCHEN", "NJERIFOOD"]),
    ("the thumbnail width for menu photos", "{v} px", [320, 360, 400, 480, 540]),
    ("the page size for the orders list", "{v}", [15, 20, 25, 30, 40]),
    ("the run time for the stock report", "{v}", ["05:15", "05:45", "06:10", "04:50"]),
    ("the Python version on the servers", "{v}", ["3.11.9", "3.12.4", "3.12.7", "3.13.1"]),
    ("the gunicorn worker count", "{v}", [3, 5, 7, 9]),
    ("the nginx upload limit", "{v} MB", [16, 20, 24, 32]),
    ("the CDN hostname", "{v}", ["img.mnk-cdn.example", "static.njeri.example", "cdn.mnk-static.example"]),
    ("the CI runner label", "{v}", ["mnk-runner-1", "self-hosted-nbo", "kitchen-ci"]),
    ("the release branch name", "{v}", ["release-main", "prod-live", "stable"]),
    ("the Docker base image", "{v}", ["python:3.12-slim", "python:3.12-bookworm", "python:3.11-alpine"]),
    ("the admin URL path", "{v}", ["/back-office/", "/mnk-admin/", "/staff-only/"]),
    ("the WebP quality setting", "{v}", [72, 78, 82, 85]),
    ("the login link lifetime", "{v} minutes", [20, 30, 45]),
    ("the M-Pesa callback path", "{v}", ["/payments/mpesa/hook", "/mpesa/confirm", "/pay/callback/v2"]),
    ("the prefix for online order numbers", "{v}", ["ON-", "WEB-", "OL-"]),
    ("the Celery queue for SMS", "{v}", ["sms-high", "sms_queue", "notify-sms"]),
    ("the health check path", "{v}", ["/healthz", "/status/ping", "/up"]),
    ("the web analytics tool", "{v}", ["Plausible", "Umami", "Matomo"]),
    ("the uptime check interval", "{v} seconds", [30, 45, 60, 90]),
    ("the low-stock alert level for eggs", "{v} trays", [4, 6, 8, 10]),
    ("the low-stock alert level for cooking oil", "{v} litres", [5, 10, 15, 20]),
    ("the maximum items per cart", "{v}", [20, 25, 30, 40]),
    ("the receipt printer model", "{v}", ["Epson TM-T20III", "Xprinter XP-58", "Star TSP143"]),
    ("the POS tablet model", "{v}", ["Samsung Tab A9", "Lenovo Tab M10", "Huawei MatePad T10"]),
    ("the backup retention", "{v} days", [14, 21, 28, 45]),
    ("the receipt font size", "{v} pt", [8, 9, 10, 11]),
    ("the menu JSON schema version", "{v}", ["v3", "v4", "v5"]),
    ("the SMS cost per message", "KES {v}", ["0.80", "0.85", "0.90"]),
    ("the staging server's RAM", "{v} GB", [2, 4, 8]),
    ("the production server's disk", "{v} GB", [40, 80, 160]),
    ("the minimum version of the riders' app", "{v}", ["2.3.0", "2.4.1", "2.5.0"]),
    ("the map tile provider", "{v}", ["OpenStreetMap", "Mapbox", "Carto"]),
    ("the delivery slot length", "{v} minutes", [20, 30, 45]),
    ("the kitchen display refresh interval", "{v} seconds", [5, 10, 15]),
    ("the loyalty points per 100 shillings", "{v}", [1, 2, 3]),
    ("the server region", "{v}", ["Johannesburg", "Cape Town", "Frankfurt"]),
]
CONFIG_SAY = ["{Np} is {vu}.", "Set {np} to {vu}[ in the settings|].", "We agreed {np} stays at {vu}.",
              "[FYI|For the record|Note]: {np} is {vu}."]

# Settings and things that change 2 to 4 times: (noun phrase, how the value is written, values).
CHANGING = [
    ("the production app port", "{v}", [8000, 8001, 8010, 8100, 8200]),
    ("the API request timeout", "{v} seconds", [10, 15, 20, 30, 45]),
    ("the Celery worker concurrency", "{v}", [2, 4, 6, 8, 12]),
    ("the Postgres version", "{v}", ["14.11", "15.6", "16.2", "16.4", "17.0"]),
    ("the Node version for the front end", "{v}", ["18.19", "20.11", "20.15", "22.3"]),
    ("the nightly backup time", "{v}", ["01:30", "02:00", "02:45", "03:15", "03:40"]),
    ("the session timeout", "{v} minutes", [30, 45, 60, 90, 120]),
    ("the API rate limit per minute", "{v}", [60, 90, 120, 180, 240]),
    ("the CDN cache TTL", "{v} seconds", [300, 600, 1200, 1800, 3600]),
    ("the log retention", "{v} days", [7, 14, 30, 60, 90]),
    ("the maximum receipt upload size", "{v} MB", [2, 4, 5, 8, 10]),
    ("the SMS retry count", "{v}", [2, 3, 4, 5, 6]),
    ("the M-Pesa STK push retry count", "{v}", [1, 2, 3, 4]),
    ("the web container memory limit", "{v} MB", [512, 768, 1024, 1536, 2048]),
    ("the deploy branch", "{v}", ["deploy-main", "release-candidate", "ship", "go-live"]),
    ("the free delivery threshold", "KES {v}", ["1,500", "2,000", "2,500", "3,000", "3,500"]),
    ("the catering deposit percentage", "{v}%", [20, 25, 30, 40, 50]),
    ("the staging database host", "{v}", ["db-staging-1", "db-stg-02", "pg-staging-3", "stg-db-04"]),
    ("the lunch rush start time", "{v}", ["11:30", "11:45", "12:00", "12:15"]),
    ("the WhatsApp orders cut-off time", "{v}", ["20:00", "20:30", "21:00", "21:30"]),
    ("the image CDN quality", "{v}", [60, 65, 70, 75, 80]),
    ("the order history page size", "{v}", [10, 12, 24, 36, 48]),
    ("the stock alert email time", "{v}", ["06:30", "07:00", "07:15", "07:45"]),
    ("the kitchen display font size", "{v} px", [18, 20, 22, 24, 28]),
    ("the number of riders on Saturdays", "{v}", [4, 5, 6, 7, 8]),
    ("the tip suggested at checkout", "{v}%", [5, 8, 10, 12]),
    ("the loyalty discount", "{v}%", [3, 5, 7, 10]),
    ("the staging certificate provider", "{v}", ["Let's Encrypt", "ZeroSSL", "Buypass"]),
    ("the Redis memory limit", "{v} MB", [128, 256, 384, 512, 768]),
    ("the number of gunicorn threads", "{v}", [2, 3, 4, 6, 8]),
    ("the reorder level for charcoal", "{v} sacks", [6, 8, 10, 12, 15]),
    ("the minimum catering order", "{v} guests", [15, 20, 25, 30]),
    ("the Sunday opening time", "{v}", ["08:00", "08:30", "09:00", "09:30", "10:00"]),
]
NEVER_ENTITY = [  # (question, words that must never appear in the script)
    ("What is Otieno's surname?", []),
    ("Who supplies our honey?", ["honey"]),
    ("Which bank holds the kitchen's savings account?", ["savings account"]),
    ("What is the Wi-Fi password at the Westlands branch?", ["password"]),
    ("What is the name of Mama Njeri's dog?", ["dog", "dogs"]),
    ("Which radio station did we advertise on?", ["radio station"]),
    ("How many followers does the kitchen's Instagram page have?", ["followers"]),
    ("Who designed the kitchen's logo?", ["logo"]),
    ("In what year was Mama Njeri's Kitchen founded?", ["founded"]),
    ("Which school do Mama Njeri's grandchildren attend?", ["grandchild", "grandchildren"]),
    ("What brand is the espresso machine at Westlands?", ["espresso"]),
    ("Who is the kitchen's insurance broker?", ["broker"]),
    ("Who is the head chef at the Rongai branch?", ["head chef"]),
    ("When is Otieno's birthday?", ["birthday"]),
    ("What score did the county inspector give the Karen branch?", ["inspector"]),
    ("What is the name of the Mombasa office's manager?", ["Mombasa office manager", "manager of the Mombasa"]),
    ("Which accountancy firm audits the kitchen's books?", ["accountancy", "auditor"]),
    ("What did the kitchen pay for its delivery motorbikes?", ["motorbike"]),
    ("What is the kitchen's KRA PIN?", ["KRA PIN"]),
    ("Which hospital is Mama Njeri's husband treated at?", ["hospital"]),
]
NEVER_SLOTS = COUNTS["never"] - len(NEVER_ENTITY)

# Values that would be a guess, by question: a decline that then names one of these is a false memory. "#number"
# stands for any number the question does not name itself.
WEEKDAY_FORMS = WEEKDAYS + [d + "s" for d in WEEKDAYS]
NAME_POOL = sorted(set(FIRST + SURNAMES + ["Kamau", "Njoroge"]) - {"Joy", "Grace", "Faith", "Mercy", "Purity", "Sang"})
BANKS = ["KCB", "Equity", "Equity Bank", "Co-op Bank", "Co-operative Bank", "Cooperative Bank", "NCBA", "Absa",
         "Stanbic", "Standard Chartered", "I&M", "DTB", "Diamond Trust", "Family Bank", "Sidian", "Kingdom Bank",
         "Barclays", "Postbank", "Bank of Africa", "Prime Bank", "Ecobank", "Gulf African Bank"]
RADIO = ["Classic 105", "Kiss 100", "Kiss FM", "Capital FM", "Radio Citizen", "Radio Jambo", "Radio Maisha",
         "Homeboyz", "Kameme", "Inooro", "NRG", "Hot 96", "Ghetto Radio", "Milele FM", "KBC", "Radio Africa",
         "Ramogi", "Chamgei", "Mbaitu", "Muuga", "Egesa", "Coro FM", "Bahari FM", "Pwani FM"]
SCHOOLS = ["Brookhouse", "Hillcrest", "Braeburn", "Peponi", "Banda", "Rusinga", "Makini", "St Mary's", "Strathmore",
           "Alliance", "Kenton", "Riara", "Light Academy", "Greensteds", "Pembroke", "Nairobi Academy",
           "Moi Educational", "Kenya High", "Loreto", "Starehe", "Lenana", "Aga Khan Academy", "Hospital Hill",
           "Kilimani Primary"]
ESPRESSO = ["La Marzocco", "Breville", "De'Longhi", "DeLonghi", "Gaggia", "Rancilio", "Nespresso", "Jura", "Siemens",
            "Philips", "Saeco", "Nuova Simonelli", "Victoria Arduino", "Krups", "Faema", "Lavazza", "Bezzera",
            "Expobar", "Astoria", "Wega", "Kenwood", "Smeg", "Melitta", "Bosch"]
BROKERS = ["Minet", "Marsh", "Aon", "Kenbright", "Liaison", "Howden", "Zamara", "Britam", "Jubilee", "CIC", "Madison",
           "APA", "Old Mutual", "UAP", "Sanlam", "AAR", "Heritage", "GA Insurance", "ICEA", "First Assurance"]
AUDITORS = ["KPMG", "Deloitte", "PwC", "PricewaterhouseCoopers", "EY", "Ernst & Young", "Grant Thornton", "BDO",
            "Baker Tilly", "RSM", "Mazars", "Forvis Mazars", "Crowe", "PKF", "Moore", "Nexia"]
HOSPITALS = ["Aga Khan", "Nairobi Hospital", "Kenyatta", "KNH", "MP Shah", "M.P. Shah", "Karen Hospital", "Gertrude's",
             "Mater", "Avenue Hospital", "Nairobi West Hospital", "Coptic", "Mbagathi", "Nairobi Women's",
             "Metropolitan", "Mama Lucy", "Guru Nanak", "Kikuyu Hospital", "Matter Hospital"]
DOGS = ["Simba", "Rex", "Bosco", "Bingo", "Jack", "Bella", "Lucky", "Rocky", "Snoopy", "Tommy", "Shaggy", "Chui"]
NEVER_POOLS = {
    "What is Otieno's surname?": SURNAMES + ["Kamau", "Njoroge"],
    "Which bank holds the kitchen's savings account?": BANKS,
    "What is the Wi-Fi password at the Westlands branch?": ["#number"],
    "What is the name of Mama Njeri's dog?": DOGS + NAME_POOL,
    "Which radio station did we advertise on?": RADIO + ["#number"],
    "How many followers does the kitchen's Instagram page have?": ["#number"],
    "Who designed the kitchen's logo?": NAME_POOL,
    "In what year was Mama Njeri's Kitchen founded?": ["#number"],
    "Which school do Mama Njeri's grandchildren attend?": SCHOOLS,
    "What brand is the espresso machine at Westlands?": ESPRESSO,
    "Who is the kitchen's insurance broker?": NAME_POOL + BROKERS,
    "Who is the head chef at the Rongai branch?": NAME_POOL,
    "When is Otieno's birthday?": MONTHS + ["#number"],
    "What score did the county inspector give the Karen branch?": ["#number"],
    "What is the name of the Mombasa office's manager?": NAME_POOL,
    "Which accountancy firm audits the kitchen's books?": AUDITORS,
    "What did the kitchen pay for its delivery motorbikes?": ["#number"],
    "What is the kitchen's KRA PIN?": ["#number"],
    "Which hospital is Mama Njeri's husband treated at?": HOSPITALS,
}

DUTIES = [  # what the person does, and how "whoever ..." refers to it
    ("handles our payments", "handles payments"), ("does the weekly stock-take", "does the stock-take"),
    ("runs our Instagram page", "runs the Instagram page"), ("keeps the keys to the cold room", "keeps the cold room "
                                                                                                "keys"),
    ("books the delivery riders", "books the riders"), ("signs off the payroll", "signs off payroll"),
    ("manages the catering bookings", "manages catering bookings"), ("does the bank runs", "does the bank runs"),
    ("trains the new waiters", "trains new waiters"), ("fixes the POS tablets", "fixes the POS tablets"),
    ("looks after the CCTV", "looks after the CCTV"), ("handles customer complaints", "handles complaints"),
    ("plans the weekly menu", "plans the weekly menu"), ("answers the WhatsApp orders line", "answers the WhatsApp "
                                                                                            "line"),
]
OFFICE_CITIES = ["Kisumu", "Nakuru", "Eldoret", "Thika", "Nyeri", "Malindi", "Machakos", "Kericho"]


class Planner:
    """Plants every probe family for one seed. ``where(depth)`` maps a token depth to (day, position in day)."""

    def __init__(self, seed: int, world: World, noise: Noise, dates: list, where: Callable[[float], tuple[int, float]],
                 target: int):
        self.rng = random.Random(f"{seed}:probes")
        self.world = world
        self.noise = noise
        self.dates = dates
        self.where = where
        self.target = target
        self.plants: list[Plant] = []
        self.probes: list[dict] = []
        self.used: dict[str, set] = defaultdict(set)
        self.contacts = list(world.contacts)
        self.decoys = 0
        self.configs: dict[str, str | None] = {}  # config noun phrase -> the ref that tells it (None: never told)

    def take_contact(self) -> Person:
        return self.contacts.pop()

    def plant(self, ref: str, day: int, pos: float, events: list[tuple[str, str, str]], key: int = -1) -> str:
        self.plants.append(Plant(ref, day, pos, events, key))
        return ref

    def tell(self, ref: str, day: int, statement: str, pos: float | None = None, genre: str | None = None) -> str:
        pos = self.rng.random() if pos is None else pos
        events = self.noise.host(day, statement, genre)
        key = next(i for i, (_, _, text) in enumerate(events) if statement in text)
        return self.plant(ref, day, pos, events, key)

    def probe(self, pid: str, family: str, ask: str, answer: str, grader: dict, refs: list[str], **extra) -> dict:
        p = {"id": pid, "family": family, "ask": ask, "answer": answer, "grader": grader, "refs": refs, **extra}
        self.probes.append(p)
        return p

    def day_between(self, lo: int, hi: int) -> int:
        return self.rng.randrange(max(1, lo), max(lo + 1, hi))

    def random_depth(self) -> tuple[int, float]:
        return self.where(self.rng.random() * self.target * 0.99)

    # -- everything ----------------------------------------------------------------------------------------------
    def run(self) -> None:
        self.samples()
        self.lookalikes()
        self.two_hops()
        self.changed()
        self.slot_facts()
        self.maths()
        self.pages()
        self.code()
        self.never_entities()

    def samples(self) -> None:
        """The doc's own examples, word for word (the maths and page samples are planted with their families)."""
        self.tell("hop-01-a", 9, "Otieno handles our payments.", genre="chat")
        self.tell("hop-01-b", 74, "Whoever handles payments moves to the Mombasa office in March.", genre="meeting")
        self.probe("hop-01", "two_hop", "Which city will Otieno work in from March?", "Mombasa",
                   {"type": "exact", "accept": ["Mombasa"]}, ["hop-01-a", "hop-01-b"], sample=True, ask_day=115,
                   note="The doc asks on day 115, after the 110 working days; it is asked after the script.")
        self.used["duty"].add("handles our payments")
        port = [("8080", 12, "Staging is up on port 8080[, same box as the database for now|]."),
                ("8443", 40, "Moved staging to port 8443 so it can run behind TLS."),
                ("9443", 88, "Staging now listens on 9443; 8443 clashed with the new proxy.")]
        values = []
        for k, (v, day, text) in enumerate(port):
            ref = self.tell(f"changed-staging-v{k}", day, say(self.rng, text), genre="chat")
            values.append({"value": v, "accept": [v], "day": day, "ref": ref})
            nxt = port[k + 1][1] if k + 1 < len(port) else 106
            for j in range(3 - k):
                d = self.day_between(day + 1, nxt)
                self.plant(f"echo-staging-{k}-{j}", d, self.rng.random(), [(
                    "log", "tool", say(self.rng, "staging | [INFO] [Uvicorn running on|Listening at] https://0.0.0.0:{v}"
                                                 "[ (Press CTRL+C to quit)|]\nstaging | [INFO] Application startup "
                                                 "complete.", v=v))])
        self.probe("changed-01-past", "changed", "What port did staging use on day 50?", "8443",
                   {"type": "timeline", "values": values, "on_day": 50}, [v["ref"] for v in values], sample=True)
        self.probe("changed-01-now", "changed", "And now? What port does staging use?", "9443",
                   {"type": "timeline", "values": values, "on_day": None}, [v["ref"] for v in values], sample=True)
        self.probe("never-01", "never", "What is Otieno's surname?", "(never said)",
                   {"type": "never", "pool": NEVER_POOLS["What is Otieno's surname?"]}, [], sample=True)

    # -- look-alikes ---------------------------------------------------------------------------------------------
    def lookalikes(self) -> None:
        rng = self.rng
        n = 0
        a, b = Person("Wanjiru", "Kamau"), Person("Wanjiru", "Njoroge")
        pairs = {"role": ("pastry chef", "bookkeeper"), "branch": ("Westlands", "Kilimani"), "ext": ("314", "341"),
                 "locker": ("17", "71"), "dayoff": ("Tuesday", "Thursday")}
        self.used["ext"].update({"314", "341"})
        self.used["locker"].update({"17", "71"})
        for attr, (va, vb) in pairs.items():
            _, says, asks = STAFF_ATTRS[attr]
            for who, v, other in ((a, va, vb), (b, vb, va)):
                n += 1
                ref = self.tell(f"look-{n:02d}", self.day_between(3, 100),
                                say(rng, rng.choice(says), e=who.full, es=poss(who.full), v=v))
                accept = [v, v + "s"] if attr == "dayoff" else [v]
                reject = [other, other + "s"] if attr == "dayoff" else [other]
                ask = say(rng, rng.choice(asks), e=who.full, es=poss(who.full))
                pool = {"role": ROLES, "branch": BRANCHES, "dayoff": WEEKDAY_FORMS}.get(attr, [])
                self.probe(f"lookalike-{n:02d}", "lookalike", ask, v,
                           exact(accept, ask, reject=reject, others=[x for x in pool if x not in reject]),
                           [ref, f"look-{n + (1 if who is a else -1):02d}"], pair="wanjiru")
        repos = [("mnk-site", "mnk-sites", "the live customer site", "the old experiment with several landing pages"),
                 ("mnk-backoffice", "mnk-back-office", "the back office app", "the abandoned back office prototype"),
                 ("kitchen-api", "kitchen_api", "the orders API service", "the Python client library for the "
                                                                          "orders API"),
                 ("njeri-menu-data", "njeri-menus-data", "the menu data we publish from",
                  "the photo shoot manifests"),
                 ("mnk-infra", "mnk-infra2", "the production Terraform", "the staging infrastructure experiments")]
        says = ["{w} lives in the `{r}` repo.", "`{r}` is {w}[, don't mix it up|].", "For {w}, use the `{r}` repo.",
                "Reminder: {w} is `{r}`."]
        for r1, r2, w1, w2 in repos:
            for r, w, other in ((r1, w1, r2), (r2, w2, r1)):
                n += 1
                ref = self.tell(f"look-{n:02d}", self.day_between(4, 100), cap(say(rng, rng.choice(says), r=r, w=w)))
                self.probe(f"lookalike-{n:02d}", "lookalike", f"Which repo holds {w}?", r,
                           {"type": "exact", "accept": [r], "reject": [other]},
                           [ref, f"look-{n + (1 if r == r1 else -1):02d}"], pair="repos")
        branch_pairs = [("Westlands", "Kilimani"), ("Karen", "Lavington"), ("Parklands", "Ruaka"),
                        ("South B", "Kasarani"), ("Upper Hill", "Langata")]
        for dish, (b1, b2) in zip(self.world.look_dishes, branch_pairs):
            p1 = rng.randrange(15, 60) * 10 - 1
            for br, price, other in ((b1, p1, p1 + 1), (b2, p1 + 1, p1)):
                n += 1
                text = say(rng, rng.choice(["At {b}, {d} is KES {p}.", "{b} charges KES {p} for {d}.",
                                            "{D} at the {b} branch: KES {p}."]), b=br, d=dish, D=cap(dish), p=price)
                ref = self.tell(f"look-{n:02d}", self.day_between(5, 100), text)
                self.probe(f"lookalike-{n:02d}", "lookalike", f"How much is {dish} at the {br} branch?", f"KES {price}",
                           {"type": "exact", "accept": [str(price)], "reject": [str(other)]},
                           [ref, f"look-{n + (1 if br == b1 else -1):02d}"], pair="prices")

    # -- two hops ------------------------------------------------------------------------------------------------
    def two_hops(self) -> None:
        rng = self.rng
        n = 1  # hop-01 is the Otieno sample
        duties = DUTIES[1:]
        people = self.world.hop_people[1:]
        for (duty, whoever), person in zip(duties, people):
            n += 1
            d1 = self.day_between(2, 70)
            d2 = self.day_between(d1 + 12, min(d1 + 50, 105))
            kind = rng.choice(["city", "laptop", "dayoff", "ext", "course"])
            month = MONTHS[(self.dates[min(d2 + 25, len(self.dates)) - 1].month) % 12]
            a = say(rng, "[{p} {d}.|From this week {p} {d}.|Just so everyone knows, {p} {d}.|{p} is the one who {d} "
                         "now.]", p=person, d=duty)
            w = say(rng, "[Whoever|The person who] {w}", w=whoever)
            if kind == "city":
                v = rng.choice(OFFICE_CITIES)
                b, q, acc = f"{w} moves to the {v} office in {month}.", f"Which city will {person} work in from " \
                                                                        f"{month}?", [v]
            elif kind == "laptop":
                v = rng.choice(LAPTOPS)
                b, q, acc = f"{w} is getting a new {v} next week.", f"Which laptop is {person} getting?", [v]
            elif kind == "dayoff":
                v, acc = weekday(rng)
                b, q = f"{w} will have {v}s off from next month.", f"Which day will {person} have off from next month?"
            elif kind == "ext":
                v = str(rng.randrange(900, 1000))
                b, q, acc = f"{w} gets extension {v} on the new phones.", f"Which extension will {person} get on " \
                                                                          f"the new phones?", [v]
            else:
                v = rng.choice(TOWNS)
                b, q, acc = f"{w} is off to a training course in {v} in {month}.", f"Where is {poss(person)} " \
                                                                                  f"training course?", [v]
            pool = {"city": OFFICE_CITIES, "laptop": LAPTOPS, "dayoff": WEEKDAY_FORMS, "course": TOWNS}.get(kind, [])
            r1 = self.tell(f"hop-{n:02d}-a", d1, a)
            r2 = self.tell(f"hop-{n:02d}-b", d2, b)
            self.probe(f"hop-{n:02d}", "two_hop", q, v, exact(acc, q, others=pool), [r1, r2], shape="duty")
        for item, supplier in zip(self.world.hop_items[:13], self.world.hop_suppliers):
            n += 1
            d1 = self.day_between(2, 70)
            d2 = self.day_between(d1 + 12, min(d1 + 50, 105))
            a = say(rng, "[From next week|Starting this month|Going forward] our {i} [{c}|will come] from {s}.",
                    i=item, s=supplier, c="come" if plural(item) else "comes")
            kind = rng.choice(["day", "plate", "contact", "notice"])
            if kind == "day":
                v, acc = weekday(rng)
                b, q = f"{supplier} only delivers on {v}s.", f"On which day of the week does our {item} arrive?"
            elif kind == "plate":
                v, acc = _uniq("plate", _plate)(rng, self)
                b, q = f"{supplier} sends its truck, {v}.", f"What is the number plate of the truck that brings our " \
                                                            f"{item}?"
            elif kind == "contact":
                p = self.take_contact()
                v, acc = p.full, person_accept(p, self.world)
                b, q = f"{supplier} has a new contact person, {v}.", f"Who should I call about our {item} order?"
            else:
                v = str(rng.randrange(2, 9))
                acc = [v]
                b, q = f"{supplier} now needs {v} days' notice for any order.", f"How many days' notice do we " \
                                                                                f"have to give for {item}?"
            r1 = self.tell(f"hop-{n:02d}-a", d1, a)
            r2 = self.tell(f"hop-{n:02d}-b", d2, b)
            self.probe(f"hop-{n:02d}", "two_hop", q, v, exact(acc, q, others=WEEKDAY_FORMS if kind == "day" else []),
                       [r1, r2], shape="supplier")
        for client, venue in zip(self.world.hop_clients[:13], self.world.hop_venues):
            n += 1
            d1 = self.day_between(2, 70)
            d2 = self.day_between(d1 + 12, min(d1 + 50, 105))
            a = say(rng, "The {c} [party|launch|retreat|end-of-year do|staff lunch] is at {v}.", c=client, v=venue)
            kind = rng.choice(["sockets", "gate", "parking"])
            if kind == "sockets":
                v = str(rng.randrange(2, 10))
                acc = [v]
                b, q = f"{cap(venue)} only has {v} power sockets.", f"How many power sockets will we have at the " \
                                                                    f"{client} event?"
            elif kind == "gate":
                v, acc = hhmm(rng.choice([17, 18, 19, 20, 21, 22]), rng.choice([0, 30]))
                b, q = f"{cap(venue)} closes its gate at {v}.", f"What time does the gate close at the venue of the " \
                                                               f"{client} event?"
            else:
                v = str(rng.randrange(6, 41))
                acc = [v]
                b, q = f"{cap(venue)} has parking for {v} cars.", f"How many cars can park at the venue of the " \
                                                                  f"{client} event?"
            r1 = self.tell(f"hop-{n:02d}-a", d1, a)
            r2 = self.tell(f"hop-{n:02d}-b", d2, b)
            self.probe(f"hop-{n:02d}", "two_hop", q, v, exact(acc, q), [r1, r2], shape="venue")

    # -- changed facts -------------------------------------------------------------------------------------------
    def timeline(self, cid: str, values: list[tuple[str, list[str]]], first: Callable, change: Callable,
                 echo: Callable, ask_now: str, ask_past: str) -> None:
        rng = self.rng
        days = [self.day_between(2, 50)]
        for _ in values[1:]:
            days.append(days[-1] + rng.randrange(6, 26))
        if days[-1] > 104:
            span = 104 - days[0]
            days = [days[0] + round((d - days[0]) * span / (days[-1] - days[0])) for d in days]
        out = []
        for k, ((v, acc), day) in enumerate(zip(values, days)):
            text = first(v) if k == 0 else change(v, values[k - 1][0])
            ref = self.tell(f"{cid}-v{k}", day, text)
            out.append({"value": v, "accept": acc, "day": day, "ref": ref})
            nxt = days[k + 1] if k + 1 < len(days) else 106
            for j in range(max(0, 3 - k)):
                if nxt - day > 1:
                    self.tell(f"echo-{cid}-{k}-{j}", self.day_between(day + 1, nxt), echo(v),
                              genre=rng.choice(["chat", "meeting", "whatsapp"]))
        k = rng.randrange(len(days) - 1)
        on_day = self.day_between(days[k] + 1, days[k + 1])
        refs = [v["ref"] for v in out]
        self.probe(f"{cid}-now", "changed", ask_now, out[-1]["value"],
                   {"type": "timeline", "values": out, "on_day": None}, refs)
        self.probe(f"{cid}-past", "changed", ask_past.replace("{D}", str(on_day)), out[k]["value"],
                   {"type": "timeline", "values": out, "on_day": on_day}, refs)

    def changed(self) -> None:
        rng = self.rng
        n = 1  # changed-01 is the staging port sample
        for np_, unit, pool in CHANGING:
            n += 1
            vals = rng.sample(pool, rng.randrange(3, min(5, len(pool)) + 1))
            values = [self._value(unit, v) for v in vals]
            Np = cap(np_)
            self.timeline(
                f"changed-{n:02d}", values,
                first=lambda v, np_=np_, Np=Np: say(rng, rng.choice(CONFIG_SAY), np=np_, Np=Np, vu=v),
                change=lambda v, old, np_=np_: say(rng, rng.choice([
                    "[From today|Starting today|As of this morning|Heads up:] {np} is {v}[, not {o}| (was {o})| instead "
                    "of {o}|].", "Changed {np} to {v}[ on Mama Njeri's request| after this week's numbers| for "
                    "now|]."]), np=np_, v=v, o=old),
                echo=lambda v, np_=np_: say(rng, rng.choice(["[Checked: |Still |]{np} [is|=] {v}[ on the dashboard| in "
                                                             "the config|].", "Reminder that {np} is {v} for now."]),
                                            np=np_, v=v),
                ask_now=f"What is {np_} now?", ask_past=f"What was {np_} on day {{D}}?")
        branches = rng.sample(BRANCHES, 6)
        managers = list(self.world.managers)
        for b in branches:
            n += 1
            people = [managers.pop() for _ in range(rng.randrange(3, 6))]
            self.timeline(
                f"changed-{n:02d}", [(p.full, person_accept(p, self.world)) for p in people],
                first=lambda v, b=b: say(rng, "[{v} manages the {b} branch.|The {b} branch manager is {v}.]", v=v, b=b),
                change=lambda v, old, b=b: say(rng, "[{v} takes over as manager at {b}[ from {o}|].|New manager at "
                                                    "{b}: {v}.]", v=v, o=old, b=b),
                echo=lambda v, b=b: say(rng, "[Spoke to {v} at {b}.|{v} ({b} manager) says the rush was fine.]", v=v,
                                        b=b),
                ask_now=f"Who manages the {b} branch now?", ask_past=f"Who was managing the {b} branch on day {{D}}?")
        staff = rng.sample(self.world.staff, 10)
        for p in staff:
            n += 1
            times = rng.sample([(6, 0), (6, 30), (7, 0), (7, 30), (8, 0), (9, 0), (10, 0), (11, 0), (14, 0)],
                               rng.randrange(3, 6))
            self.timeline(
                f"changed-{n:02d}", [hhmm(h, m) for h, m in times],
                first=lambda v, p=p: say(rng, "[{es} shift starts at {v}.|{e} starts at {v} every day.]", e=p.full,
                                         es=poss(p.full), v=v),
                change=lambda v, old, p=p: say(rng, "{es} shift now starts at {v}[ instead of {o}|].", es=poss(p.full),
                                               v=v, o=old),
                echo=lambda v, p=p: say(rng, "{e} was in at {v} as usual.", e=p.full, v=v),
                ask_now=f"What time does {poss(p.full)} shift start now?",
                ask_past=f"What time did {poss(p.full)} shift start on day {{D}}?")
        for s in rng.sample(self.world.suppliers, 12):
            n += 1
            vals = rng.sample([150, 200, 250, 300, 350, 400, 450, 500, 600], rng.randrange(3, 6))
            self.timeline(
                f"changed-{n:02d}", [(f"KES {v}", [str(v)]) for v in vals],
                first=lambda v, s=s: say(rng, "{s} charges {v} for delivery.", s=s, v=v),
                change=lambda v, old, s=s: say(rng, "{s} [raised|changed] their delivery charge to {v}[ (was {o})|].",
                                               s=s, v=v, o=old),
                echo=lambda v, s=s: say(rng, "Paid {s} the usual {v} delivery charge.", s=s, v=v),
                ask_now=f"What is {poss(s)} delivery charge now?", ask_past=f"What was {poss(s)} delivery charge on day {{D}}?")
        for d in self.world.changed_dishes:
            n += 1
            vals = rng.sample(range(150, 700, 10), rng.randrange(3, 6))
            self.timeline(
                f"changed-{n:02d}", [(f"KES {v}", [str(v)]) for v in vals],
                first=lambda v, d=d: say(rng, "{D} is {v} on the menu.", D=cap(d), v=v),
                change=lambda v, old, d=d: say(rng, "[New price|Price change]: {d} is now {v}[, up from {o}| (was {o})|].",
                                               d=d, v=v, o=old),
                echo=lambda v, d=d: say(rng, "Sold out of {d} at {v} a plate by two o'clock.", d=d, v=v),
                ask_now=f"How much is {d} now?", ask_past=f"How much was {d} on day {{D}}?")
        for c in self.world.clients[:12]:
            n += 1
            vals = rng.sample(range(30, 400, 5), rng.randrange(3, 6))
            self.timeline(
                f"changed-{n:02d}", [(str(v), [str(v)]) for v in vals],
                first=lambda v, c=c: say(rng, "The {c} event is for {v} guests.", c=c, v=v),
                change=lambda v, old, c=c: say(rng, "{c} [changed|updated] the numbers: {v} guests now[ instead of {o}|].",
                                               c=c, v=v, o=old),
                echo=lambda v, c=c: say(rng, "Planning the {c} menu for {v} people.", c=c, v=v),
                ask_now=f"How many guests is the {c} event for now?",
                ask_past=f"How many guests was the {c} event for on day {{D}}?")
        self.used["client_guests"].update(self.world.clients[:12])

    @staticmethod
    def _value(unit: str, v) -> tuple[str, list[str]]:
        text = unit.replace("{v}", str(v))
        if isinstance(v, str) and len(v) == 5 and v[2] == ":":
            return hhmm(int(v[:2]), int(v[3:]))
        return text, [str(v)]

    # -- facts told once, decoys and never-said slots ------------------------------------------------------------
    def slots(self) -> list[tuple[str, str, str]]:
        """Every (kind, thing, attribute) that may carry a fact."""
        w = self.world
        out = [("staff", p.full, a) for p in w.staff for a in STAFF_ATTRS]
        out += [("supplier", s, a) for s in w.suppliers for a in SUPPLIER_ATTRS
                if a != "supplies" or w.suppliers.index(s) < len(w.supply_items)]
        out += [("branch", b, a) for b in BRANCHES for a in BRANCH_ATTRS]
        out += [("dish", d, a) for d in w.fact_dishes for a in DISH_ATTRS]
        out += [("client", c, a) for c in w.clients for a in CLIENT_ATTRS
                if not (a == "guests" and c in self.used["client_guests"])]
        out += [("config", np_, "value") for np_, _, _ in CONFIGS]
        return out

    def pool(self, kind: str, thing: str, attr: str) -> list[str]:
        """The values a slot's fact could have had, as the grader names them ("#number": any number)."""
        if kind == "config":
            np_, unit, values = next(c for c in CONFIGS if c[0] == thing)
            written = [self._value(unit, v)[1][0] for v in values]
            return ["#number"] if all(re.fullmatch(r"[\d.,]+", w) for w in written) else written
        table = {("staff", "hometown"): TOWNS, ("staff", "dayoff"): WEEKDAY_FORMS, ("staff", "laptop"): LAPTOPS,
                 ("staff", "role"): ROLES, ("staff", "branch"): BRANCHES, ("supplier", "supplies"): SUPPLY_ITEMS,
                 ("supplier", "delivery_day"): WEEKDAY_FORMS, ("supplier", "contact"): NAME_POOL,
                 ("branch", "landlord"): NAME_POOL, ("dish", "creator"): NAME_POOL, ("dish", "branch_only"): BRANCHES,
                 ("client", "venue"): [v.removeprefix("the ") for v in VENUES], ("client", "contact"): NAME_POOL,
                 ("client", "main"): DISHES}
        if (kind, attr) in table:
            return list(table[(kind, attr)])
        return ["#number"]

    def fact_text(self, kind: str, thing: str, attr: str, told: bool = True) -> tuple[str, list[str], str, str]:
        """(value, accept, statement, question) for one slot. ``told=False`` gives only the question."""
        rng = self.rng
        if not told:
            if kind == "config":
                return "", [], "", f"What is {thing}?"
            table = {"staff": STAFF_ATTRS, "supplier": SUPPLIER_ATTRS, "branch": BRANCH_ATTRS, "dish": DISH_ATTRS,
                     "client": CLIENT_ATTRS}[kind]
            return "", [], "", say(rng, rng.choice(table[attr][2]), e=thing, E=cap(thing), es=poss(thing), b=thing)
        if kind == "config":
            np_, unit, pool = next(c for c in CONFIGS if c[0] == thing)
            v = rng.choice(pool)
            value, accept = self._value(unit, v)
            return value, accept, say(rng, rng.choice(CONFIG_SAY), np=np_, Np=cap(np_), vu=value), f"What is {np_}?"
        table = {"staff": STAFF_ATTRS, "supplier": SUPPLIER_ATTRS, "branch": BRANCH_ATTRS, "dish": DISH_ATTRS,
                 "client": CLIENT_ATTRS}[kind]
        make, says, asks = table[attr]
        if kind == "supplier" and attr == "supplies":
            v = self.world.supply_items[self.world.suppliers.index(thing)]
            value, accept = v, [v]
        elif kind == "client" and attr == "venue":
            v = rng.choice(self.world.fact_venues)
            value, accept = v, [v.removeprefix("the ")]
        else:
            value, accept = make(rng, self)
        slots = dict(e=thing, E=cap(thing), es=poss(thing), b=thing, v=value,
                     comes="come" if plural(value) else "comes")
        return value, accept, cap(say(rng, rng.choice(says), **slots)), say(rng, rng.choice(asks), **slots)

    def slot_facts(self) -> None:
        rng = self.rng
        slots = self.slots()
        rng.shuffle(slots)
        never, probes, decoys = slots[:NEVER_SLOTS], slots[NEVER_SLOTS:NEVER_SLOTS + COUNTS["fact"]], \
            slots[NEVER_SLOTS + COUNTS["fact"]:NEVER_SLOTS + COUNTS["fact"] + DECOYS]
        if len(decoys) < DECOYS or len(probes) < COUNTS["fact"]:
            raise RuntimeError("not enough fact slots")
        for i, (kind, thing, attr) in enumerate(probes, start=1):
            value, accept, statement, question = self.fact_text(kind, thing, attr)
            day, pos = self.random_depth()
            ref = self.tell(f"fact-{i:03d}", day, statement, pos)
            pool = [v for v in self.pool(kind, thing, attr) if v != "#number"]
            self.probe(f"fact-{i:03d}", "fact", question, value, exact(accept, question, others=pool), [ref],
                       slot=f"{kind}:{attr}")
            if kind == "config":
                self.configs[thing] = ref
        for i, (kind, thing, attr) in enumerate(decoys, start=1):
            _, _, statement, _ = self.fact_text(kind, thing, attr)
            day, pos = self.random_depth()
            ref = self.tell(f"decoy-{i:03d}", day, statement, pos)
            self.decoys += 1
            if kind == "config":
                self.configs[thing] = ref
        for i, (kind, thing, attr) in enumerate(never, start=len(NEVER_ENTITY) + 1):
            _, _, _, question = self.fact_text(kind, thing, attr, told=False)
            self.probe(f"never-{i:02d}", "never", question, "(never said)",
                       {"type": "never", "pool": self.pool(kind, thing, attr)}, [], slot=f"{kind}:{attr}")
            if kind == "config":
                self.configs[thing] = None

    def never_entities(self) -> None:
        for i, (q, absent) in enumerate(NEVER_ENTITY[1:], start=2):
            pool = NEVER_POOLS.get(q) or NAME_POOL + self.world.suppliers + self.world.hop_suppliers  # honey
            self.probe(f"never-{i:02d}", "never", q, "(never said)", {"type": "never", "pool": list(pool)}, [],
                       absent=absent)

    # -- maths, the page and code --------------------------------------------------------------------------------
    def maths(self) -> None:
        samples = {("maths-01", "new"), ("maths-01", "rule"), ("maths-02", "new")}
        for prob in maths.problems(self.rng, len(self.dates)):
            pos = 0.3 if prob.sample else self.rng.random()
            self.plant(prob.pid, prob.day, pos, [("maths", "user", prob.ask), ("maths", "assistant", prob.reply),
                                                 ("maths", "user", prob.correction)])
            for a in prob.asks:
                extra = {"sample": True} if (prob.pid, a.way) in samples else {}
                if a.way in prob.ask_days:
                    extra["ask_day"] = prob.ask_days[a.way]
                self.probe(f"{prob.pid}-{a.way}", "maths", a.text, str(a.answer),
                           {"type": "number", "value": str(a.answer), "stale": [_num_text(t) for t in a.trap]},
                           [prob.pid], way=a.way, method=prob.family, params=_jsonable(a.params), **extra)

    def pages(self) -> None:
        self.plant("page-design", page.DESIGN_DAY, 0.2, [("decision", "user", page.DESIGN_SYSTEM),
                                                         ("code", "assistant", page.DESIGN_TOKENS)], key=0)
        self.plant("page-colour", page.CHANGE_DAY, 0.4, [("decision", "user", page.COLOUR_CHANGE),
                                                         ("code", "assistant", page.COLOUR_CHANGE_REPLY)], key=0)
        for pid, ask, h1, sample in page.PAGES:
            spec = page.spec(page.NEW_COLOUR, [page.OLD_COLOUR], h1)
            spec["timeline"] = [{"value": page.OLD_COLOUR, "ref": "page-design"},
                                {"value": page.NEW_COLOUR, "ref": "page-colour"}]
            extra = {"sample": True, "ask_day": 110} if sample else {}
            self.probe(pid, "page", ask, f"an HTML page in the design system, main colour {page.NEW_COLOUR}", spec,
                       ["page-design"], **extra)

    def code(self) -> None:
        for name, day in codefit.PLANT_DAYS.items():
            self.plant(f"code-{name}", day, self.rng.random(), [("chat", "user", codefit.REQUESTS[name]),
                                                                ("code", "assistant", codefit.plant_text(name))])
        for ask in codefit.code_asks():
            spec = {"type": "code", "entry": ask.entry, "cases": ask.cases, "needs": ask.needs,
                    "modules": {m: codefit.MODULES[m] for m in ask.needs}, "timeout": 10}
            self.probe(ask.pid, "code", ask.ask, f"a function {ask.entry} that passes {len(ask.cases)} tests", spec,
                       [f"code-{m}" for m in ask.needs], reference=ask.reference)


def exact(accept: list[str], ask: str, reject: list[str] | None = None, others: list[str] | None = None) -> dict:
    """An exact grader spec. ``others`` are the rest of the value's pool: naming one of them as well makes a list of
    candidates, not an answer. Values the question itself names are left out of ``others``."""
    spec: dict = {"type": "exact", "accept": accept}
    if reject:
        spec["reject"] = reject
    rest = [v for v in (others or []) if v not in accept and v not in (reject or []) and not names(ask, [v])
            and not names(v, accept) and not names(accept[0], [v])]
    if rest:
        spec["others"] = rest
    return spec


def _num_text(x) -> str:
    from fractions import Fraction
    if isinstance(x, Fraction) and x.denominator != 1:
        return f"{x.numerator}/{x.denominator}"
    return str(int(x))


def _jsonable(p: dict) -> dict:
    from fractions import Fraction
    return {k: (str(v) if isinstance(v, Fraction) else v) for k, v in p.items()}
