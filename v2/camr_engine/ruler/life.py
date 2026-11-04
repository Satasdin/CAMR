"""Scripted lives: twelve weeks of one person's notes, with planted facts and a fixed quiz of 100 questions.

A life is fixed by its persona and seed. Notes are dated "[YYYY-MM-DD] ..." (the form the old CAMR engine reads).
Every question knows its right answer on every day: nothing until the fact is first told (and never, for facts that
never are), then the told value, then the new value once an update is told.

The lives are messy on purpose: typos, lowercase, Swahili asides, changed minds, "yesterday", a gap of several days,
facts split across two notes, and the same names and values turning up in unrelated notes.
"""

from __future__ import annotations

import datetime as dt
import random
import re
from dataclasses import dataclass

START = dt.date(2026, 1, 5)  # a Monday
WEEKS = 12
DAYS = WEEKS * 7
COUNTS = {"single": 45, "update": 15, "multi": 10, "time": 15, "abstain": 15}  # 100 questions

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def date_aliases(d: dt.date) -> tuple[str, ...]:
    m, m3 = MONTHS[d.month - 1].lower(), MONTHS[d.month - 1][:3].lower()
    return (f"{d.day} {m}", f"{m} {d.day}", f"{d.day} {m3}", f"{m3} {d.day}", d.isoformat(),
            f"{d.day:02d}/{d.month:02d}/{d.year}", f"{d.day}/{d.month}/{d.year}")


def birthday_aliases(day: int, month: int) -> tuple[str, ...]:
    m, m3 = MONTHS[month - 1].lower(), MONTHS[month - 1][:3].lower()
    return f"{day} {m}", f"{m} {day}", f"{day} {m3}", f"{m3} {day}"


def says(d: dt.date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


NAMES = ["Amina", "Otieno", "Wanjiru", "Kamau", "Njeri", "Mwangi", "Achieng", "Baraka", "Zawadi", "Imani", "Juma",
         "Akinyi", "Kiprono", "Chebet", "Mutua", "Nduta", "Wekesa", "Halima", "Omondi", "Atieno", "Wairimu", "Nafula",
         "Cherono", "Makena", "Kibet", "Rotich", "Auma", "Musa", "Fatuma", "Kerubo", "Njoroge", "Moraa", "Ouma",
         "Wambui", "Kiptoo", "Jeptoo", "Mumbua", "Onyango", "Sanaipei", "Lemayian", "Gathoni", "Barasa", "Wafula",
         "Nyambura", "Koech", "Adhiambo", "Kipkemboi", "Muthoni"]
PLACES = ["Nakuru", "Kisumu", "Eldoret", "Thika", "Nyeri", "Malindi", "Naivasha", "Kericho", "Mombasa", "Machakos",
          "Kitale", "Embu", "Meru", "Kakamega", "Nanyuki", "Kilifi", "Narok", "Bungoma", "Voi", "Garissa", "Lamu",
          "Kitui", "Homa Bay", "Isiolo"]
# (value as written, extra words that also count as naming it)
JOBS = [("nurse", ()), ("matatu driver", ("matatu",)), ("accountant", ()), ("teacher", ()), ("mechanic", ()),
        ("pharmacist", ()), ("electrician", ()), ("tailor", ()), ("police officer", ("policeman", "policewoman")),
        ("bank teller", ("teller",)), ("chef", ("cook",)), ("carpenter", ("fundi",)), ("journalist", ("reporter",)),
        ("lab technician", ()), ("surveyor", ()), ("plumber", ()), ("radio presenter", ()), ("veterinary officer", ("vet",))]
PHONES = [("Tecno", ()), ("Samsung", ()), ("Infinix", ()), ("iPhone", ()), ("Nokia", ()), ("Oppo", ()),
          ("Xiaomi", ("redmi",)), ("Itel", ()), ("Huawei", ()), ("Google Pixel", ("pixel",))]
FOODS = [("pilau", ()), ("githeri", ()), ("nyama choma", ()), ("chapati", ("chapo",)), ("ugali and sukuma", ("ugali",)),
         ("mandazi", ("mandazis",)), ("matoke", ()), ("biryani", ()), ("samaki wa kupaka", ("samaki",)), ("mukimo", ()),
         ("chips mayai", ()), ("bhajia", ())]
TEAMS = [("Gor Mahia", ("gor",)), ("AFC Leopards", ("leopards", "ingwe")), ("Arsenal", ()), ("Manchester United", ("man u", "man united")),
         ("Chelsea", ()), ("Liverpool", ()), ("Tusker FC", ("tusker",)), ("Bandari", ()), ("Real Madrid", ())]
CARS = [("Toyota Probox", ("probox",)), ("Nissan Note", ()), ("Subaru Forester", ("forester",)), ("Toyota Vitz", ("vitz",)),
        ("Mazda Demio", ("demio",)), ("Honda Fit", ()), ("Isuzu D-Max", ("d-max", "dmax")), ("Toyota Fielder", ("fielder",)),
        ("Mitsubishi Pajero", ("pajero",)), ("Suzuki Swift", ("swift",))]
DOGS = [(n, ()) for n in ["Simba", "Bosco", "Kahawa", "Duma", "Zuri", "Shiro", "Jasiri", "Pendo", "Tiny", "Rex", "Chui", "Moto"]]
ASIDES = ["aki", "sawa", "lol", "sigh", "anyway", "si mbaya", "eish", "haha", "kwani"]
KEEP = {"today", "yesterday", "morning"}  # never misspelt: they decide which date a note is about

# Facts about the people in a life. "say" tells it; "update" tells a new value replacing the old (updatable only).
ATTRS = {
    "lives": dict(q="Where does my {rel} live?", pool="PLACES", say=[
        "My {rel} {name} has moved to {v}.", "Called my {rel} {name}, still settling in {v}.",
        "{name} (my {rel}) says life in {v} is expensive but quiet."],
        update=["Big news: my {rel} {name} moved from {old} to {v}.", "My {rel} {name} left {old} for good, now living in {v}."]),
    "job": dict(q="What does my {rel} do for work?", pool="JOBS", say=[
        "My {rel} {name} got a job as a {v}.", "{name}, my {rel}, works as a {v} these days.",
        "My {rel} {name} is a {v} and complains about the night shifts."],
        update=["My {rel} {name} quit being a {old} and now works as a {v}.", "{name} (my {rel}) changed careers, no longer a {old}, now a {v}."]),
    "phone": dict(q="What phone brand does my {rel} use?", pool="PHONES", say=[
        "My {rel} {name} finally bought a {v} phone.", "{name} (my {rel}) keeps showing off the new {v}."],
        update=["My {rel} {name} dropped the {old} and switched to a {v}.", "{name}, my {rel}, sold the {old} phone, using a {v} now."]),
    "car": dict(q="What car does my {rel} drive?", pool="CARS", say=[
        "My {rel} {name} drives a {v}.", "Got a lift from my {rel} {name} in the {v}."],
        update=["My {rel} {name} sold the {old} and now drives a {v}.", "{name} (my {rel}) traded the {old} for a {v}."]),
    "food": dict(q="What is my {rel}'s favourite food?", pool="FOODS", say=[
        "My {rel} {name} would eat {v} every single day if allowed.", "Cooked {v} because it's my {rel} {name}'s favourite."]),
    "team": dict(q="Which football team does my {rel} support?", pool="TEAMS", say=[
        "My {rel} {name} supports {v}, no matter how badly they play.", "{name}, my {rel}, was shouting at the TV for {v} again."]),
    "birthday": dict(q="When is my {rel}'s birthday?", pool="BIRTHDAYS", say=[
        "Reminder to self: my {rel} {name}'s birthday is on {v}.", "Must not forget my {rel} {name}'s birthday, {v}."]),
    "dog": dict(q="What is the name of my {rel}'s dog?", pool="DOGS", say=[
        "My {rel} {name} has a dog called {v}.", "{v}, my {rel} {name}'s dog, chewed my shoe."]),
}
UPDATABLE = ("lives", "job", "phone", "car")

# Second-degree people: told in two notes, one naming the relation and one about the person by name only.
HOPS = {
    "job": ("What does my {rel}'s {rel2} do for work?", "JOBS", ["{b} works as a {v} now.", "{b} says being a {v} pays the bills."]),
    "lives": ("Where does my {rel}'s {rel2} live?", "PLACES", ["{b} has been living in {v} since December.", "{b} rents a place in {v}."]),
    "car": ("What car does my {rel}'s {rel2} drive?", "CARS", ["{b} came round in a {v}.", "{b} drives a {v}, always clean."]),
}
HOP_RELATION = ["My {rel} {a}'s {rel2} is {b}.", "Met {b}, my {rel} {a}'s {rel2}, at the wedding.",
                "Turns out {b} is my {rel} {a}'s {rel2}."]
RELS2 = ["husband", "wife", "boss", "son", "daughter", "fiancé", "roommate"]
NEVER = ["What does my grandfather do for work?", "Where does my godmother live?", "What car does my uncle drive?",
         "What is my nephew's favourite food?"]

PERSONAS = {
    "student": dict(
        people=["mum", "sister", "brother", "cousin", "best friend", "roommate", "lecturer", "classmate", "landlord",
                "neighbour"],
        events=["submitted my final-year project proposal", "sat the statistics CAT", "paid the semester fees",
                "moved into the new hostel room", "had my first internship interview", "joined the drama club",
                "registered for the hackathon", "bought a second-hand bicycle", "got my HELB loan",
                "presented at the research seminar", "went to the career fair", "started the library job",
                "lost my student ID", "had my wisdom tooth removed", "planted sukuma wiki on the balcony",
                "renewed my library card", "fixed my laptop charger"],
        filler=["Lecture on {topic} ran over again.", "Water cut in the hostel, bathed with a jerrican.",
                "Matatu fare to town went up to KES {n}.", "Group work with {name} on {topic}, nobody read anything.",
                "Bought data bundles, KES {n} gone just like that.", "Rain the whole afternoon in {place}.",
                "{team} lost again, the common room was loud.", "Made {food} for supper, not bad.",
                "{name} borrowed my notes on {topic}.", "Stayed up till 2am on the {topic} assignment.",
                "Saw a {car} parked outside the library, wondered whose it is.", "Church choir practice, {name} sang solo.",
                "My {phone} battery is dying by noon now.", "Power went out during the {topic} test prep."],
        topics=["linear algebra", "databases", "operating systems", "statistics", "networks", "research methods"]),
    "farmer": dict(
        people=["mum", "sister", "brother", "cousin", "best friend", "neighbour", "vet", "chairman", "driver",
                "deputy"],
        events=["bought a new milk cooler", "vaccinated the herd against foot-and-mouth",
                "signed the contract with the Brookside depot", "planted napier grass on the lower plot",
                "held the cooperative AGM", "fixed the borehole pump", "paid the members' bonuses",
                "registered three new members", "bought a second-hand pickup", "hosted the county extension officer",
                "repaired the cattle dip", "started using the record-keeping app", "sold the old chaff cutter",
                "inseminated the Friesian cow", "opened the cooperative's savings account", "fenced the east paddock"],
        filler=["Collected {n} litres this morning, {name} was late again.", "Milk price at the depot is KES {n} a litre now.",
                "Rain in {place}, the road to the depot is mud.", "{name} wants a loan from the cooperative for school fees.",
                "One cow off feed, watching her.", "Market day, bought {food} for the workers.",
                "{team} won, the boys at the dairy were happy.", "Diesel for the generator cost KES {n}.",
                "The {car} from the feed company came late.", "Meeting with {name} about the {topic}.",
                "My {phone} fell in the trough, still works.", "Long day at the collection centre."],
        topics=["milk quality tests", "feed prices", "the dip schedule", "the new bylaws", "member arrears"]),
    "developer": dict(
        people=["mum", "sister", "brother", "cousin", "best friend", "teammate", "manager", "client", "landlord",
                "neighbour"],
        events=["deployed version 2 of the payments service", "had the outage on the M-Pesa callback",
                "signed the contract with the logistics client", "passed my AWS certification", "bought a new laptop",
                "started learning Rust", "gave a talk at the Python meetup", "moved to the new co-working space",
                "fixed the memory leak in the queue worker", "upgraded the database to Postgres 16",
                "hired the new intern", "renewed the domain for the clinic site", "set up the backup server",
                "shipped the mobile app to the Play Store", "switched the team to trunk-based development"],
        filler=["Standup ran long, {name} blocked on {topic}.", "Power cut, worked from the {place} cafe.",
                "Internet down for 3 hours, Safaricom again.", "Traffic on Mombasa Road was insane.",
                "{team} game at the pub with {name}.", "Lunch was {food}, too much of it.",
                "Code review on the {topic} module, {n} comments.", "Saw a {car} with a broken tail light at the office.",
                "My {phone} keeps disconnecting from the hotspot.", "Coffee bill this week: KES {n}.",
                "{name} asked for help with {topic}.", "Spent the evening reading about {topic}."],
        topics=["auth", "billing", "the queue worker", "caching", "the dashboard", "SMS gateway"]),
}


@dataclass
class Question:
    qid: str
    kind: str  # single | update | multi | time | abstain
    text: str
    # (first day it is known, value as written, words that count as naming it), earliest first; empty = never told
    timeline: tuple[tuple[int, str, tuple[str, ...]], ...]

    def answer_on(self, day: int) -> tuple[str, tuple[str, ...]] | None:
        """The right answer at the end of ``day``: (value, aliases), or None if it should not be known."""
        known = [(v, a) for d, v, a in self.timeline if d <= day]
        return known[-1] if known else None

    def superseded_on(self, day: int) -> tuple[str, ...]:
        """Aliases of values that an update had replaced by ``day`` (saying one of them is a stale answer)."""
        known = [a for d, _, a in self.timeline if d <= day]
        return tuple(x for a in known[:-1] for x in a)


@dataclass
class Day:
    index: int
    date: dt.date
    notes: list[str]

    def dated(self) -> list[str]:
        return [f"[{self.date.isoformat()}] {n}" for n in self.notes]


@dataclass
class Life:
    persona: str
    seed: int
    days: list[Day]
    questions: list[Question]

    @property
    def quiz_days(self) -> list[int]:
        return [d.index for d in self.days if d.index % 7 == 6]

    def told_on(self, day: int) -> int:
        return sum(q.answer_on(day) is not None for q in self.questions)


def _aliases(value: str, extra: tuple[str, ...]) -> tuple[str, ...]:
    return (value.lower(), *extra)


def _mess(template: str, rng: random.Random) -> str:
    """Typos, lowercase, missing full stops and asides, applied to a template's own words (never its slots)."""
    if rng.random() < 0.3:
        words = template.split(" ")
        ok = [i for i, w in enumerate(words) if "{" not in w and len(w) >= 5 and w.isalpha()
              and w.lower() not in KEEP]
        for i in rng.sample(ok, min(len(ok), rng.choice([1, 2]))):
            w, j = words[i], rng.randrange(1, len(words[i]) - 2)
            words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
        template = " ".join(words)
    if rng.random() < 0.2:
        template = re.sub(r"(^|\})([^{]*)", lambda m: m.group(1) + m.group(2).lower(), template)
    if rng.random() < 0.15:
        template = template.rstrip(".")
    if rng.random() < 0.12:
        template = template.rstrip(".") + ", " + rng.choice(ASIDES)
    return template


def build(persona: str, seed: int) -> Life:
    """The life of ``persona`` for ``seed``: 84 days of notes and the 100-question quiz."""
    spec = PERSONAS[persona]
    rng = random.Random(f"{persona}:{seed}")
    pools = {"PLACES": [(p, ()) for p in PLACES], "JOBS": JOBS, "PHONES": PHONES, "FOODS": FOODS, "TEAMS": TEAMS,
             "CARS": CARS, "DOGS": DOGS}
    names = NAMES[:]
    rng.shuffle(names)
    people = {rel: names.pop() for rel in spec["people"]}
    hop_names = [names.pop() for _ in range(COUNTS["multi"])]
    filler_names = names + list(people.values())  # the people also turn up in notes about nothing in the quiz

    gap_start = rng.randrange(42, 49)
    empty = set(range(gap_start, gap_start + 4)) | set(rng.sample([d for d in range(1, DAYS) if d < 42 or d > 52], 6))
    active = [d for d in range(DAYS) if d not in empty]
    notes: dict[int, list[str]] = {d: [] for d in range(DAYS)}

    def value(pool: str) -> tuple[str, tuple[str, ...]]:
        if pool == "BIRTHDAYS":
            day, month = rng.randrange(1, 29), rng.randrange(1, 13)
            return f"{day} {MONTHS[month - 1]}", birthday_aliases(day, month)
        v, extra = rng.choice(pools[pool])
        return v, _aliases(v, extra)

    def tell(day: int, template: str, **slots) -> None:
        notes[day].append(_mess(template, rng).format(**slots))

    pairs = [(rel, attr) for rel in spec["people"] for attr in ATTRS]
    rng.shuffle(pairs)
    updates = [p for p in pairs if p[1] in UPDATABLE][:COUNTS["update"]]
    rest = [p for p in pairs if p not in updates]
    singles, never = rest[:COUNTS["single"]], rest[COUNTS["single"]:COUNTS["single"] + COUNTS["abstain"] - len(NEVER)]

    questions: list[tuple[str, str, tuple]] = []
    for rel, attr in singles:
        a = ATTRS[attr]
        v, al = value(a["pool"])
        d = rng.choice(active)
        tell(d, rng.choice(a["say"]), rel=rel, name=people[rel], v=v)
        questions.append(("single", a["q"].format(rel=rel), ((d, v, al),)))
    for rel, attr in updates:
        a = ATTRS[attr]
        (v1, al1), (v2, al2) = value(a["pool"]), value(a["pool"])
        while v2 == v1:
            v2, al2 = value(a["pool"])
        d1 = rng.choice([d for d in active if d <= 55])
        d2 = rng.choice([d for d in active if d >= d1 + 7])
        tell(d1, rng.choice(a["say"]), rel=rel, name=people[rel], v=v1)
        tell(d2, rng.choice(a["update"]), rel=rel, name=people[rel], old=v1, v=v2)
        questions.append(("update", a["q"].format(rel=rel), ((d1, v1, al1), (d2, v2, al2))))
    hop_rels = rng.sample(spec["people"], COUNTS["multi"])
    for b, rel in zip(hop_names, hop_rels):
        attr = rng.choice(list(HOPS))
        q, pool, says_b = HOPS[attr]
        rel2 = rng.choice(RELS2)
        v, al = value(pool)
        d1, d2 = rng.choice(active), rng.choice(active)
        tell(d1, rng.choice(HOP_RELATION), rel=rel, a=people[rel], rel2=rel2, b=b)
        tell(d2, rng.choice(says_b), b=b, v=v)
        questions.append(("multi", q.format(rel=rel, rel2=rel2), ((max(d1, d2), v, al),)))
    for event in rng.sample(spec["events"], COUNTS["time"]):
        d = rng.choice([x for x in active if x >= 1])
        if rng.random() < 0.3:
            tell(d, rng.choice(["Yesterday I {e}.", "Forgot to write it down: yesterday I {e}."]), e=event)
            when = START + dt.timedelta(days=d - 1)
        else:
            tell(d, rng.choice(["Today I {e}.", "Finally {e} today.", "This morning I {e}."]), e=event)
            when = START + dt.timedelta(days=d)
        questions.append(("time", f"What date was it when I {event}?", ((d, says(when), date_aliases(when)),)))
    for rel, attr in never:
        questions.append(("abstain", ATTRS[attr]["q"].format(rel=rel), ()))
    for text in NEVER:
        questions.append(("abstain", text, ()))

    for d in active:
        for _ in range(rng.randint(2, 4)):
            slots = dict(name=rng.choice(filler_names), place=rng.choice(PLACES), food=rng.choice(FOODS)[0],
                         team=rng.choice(TEAMS)[0], car=rng.choice(CARS)[0], phone=rng.choice(PHONES)[0],
                         topic=rng.choice(spec["topics"]), n=rng.choice([45, 60, 80, 120, 150, 250, 500, 1000, 1200]))
            tell(d, rng.choice(spec["filler"]), **slots)
        rng.shuffle(notes[d])

    rng.shuffle(questions)
    qs = [Question(f"q{i + 1:03d}", kind, text, timeline) for i, (kind, text, timeline) in enumerate(questions)]
    days = [Day(d, START + dt.timedelta(days=d), notes[d]) for d in range(DAYS)]
    return Life(persona, seed, days, qs)
