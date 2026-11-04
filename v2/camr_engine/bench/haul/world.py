"""The people, places and things of Mama Njeri's Kitchen, drawn once from the seed and split so that no two probes
can ever be about the same thing.

Every planted fact belongs to exactly one (thing, attribute) slot. Slots are split between probes, decoys (told but
never asked, so a planted fact does not stand out) and never-said questions (asked but never told). The noise only
ever names people and things; it never states one of their attributes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from camr_engine.bench.haul.words import (BRANCHES, COMPANIES, DISHES, FIRST, SUPPLIER_WORDS, SUPPLY_ITEMS, SURNAMES, TOWNS,
                                     AREAS, VENUES)

# Dishes whose prices live in the code helpers (mnk/kitchen.py); no planted fact may give them another price.
CODE_DISHES = ["pilau", "biryani", "chapati", "mandazi", "beef samosa", "nyama choma", "githeri", "mukimo",
               "sukuma wiki", "ugali", "fried tilapia", "kuku kienyeji", "kachumbari"]


@dataclass(frozen=True)
class Person:
    first: str
    last: str

    @property
    def full(self) -> str:
        return f"{self.first} {self.last}"


@dataclass
class World:
    staff: list[Person]
    contacts: list[Person]
    hop_people: list[str]  # first names only; Otieno first. None of them ever gets a surname.
    suppliers: list[str]
    hop_suppliers: list[str]
    clients: list[str]
    hop_clients: list[str]
    fact_venues: list[str]
    hop_venues: list[str]
    fact_dishes: list[str]
    changed_dishes: list[str]
    look_dishes: list[str]
    supply_items: list[str]
    hop_items: list[str]
    managers: list[Person]
    extra: dict = field(default_factory=dict)

    def noise_names(self) -> list[str]:
        """Names the noise may drop in passing: staff (first names and full), the hop people, both Wanjirus."""
        return ([p.first for p in self.staff] + [p.full for p in self.staff[:20]] + self.hop_people +
                ["Wanjiru", "Wanjiru", "Mama Njeri", "Mama Njeri"])


def _people(rng: random.Random, firsts: list[str], n: int, taken: set[str], unique_last: bool = True) -> list[Person]:
    out: list[Person] = []
    surnames = SURNAMES[:]
    rng.shuffle(surnames)
    while len(out) < n:
        for first in firsts:
            if len(out) == n:
                break
            rng.shuffle(surnames)
            for last in surnames:
                full = f"{first} {last}"
                if last != first and full not in taken and not (unique_last and last in {p.last for p in out}):
                    out.append(Person(first, last))
                    taken.add(full)
                    break
        if not unique_last and len(out) < n and not firsts:
            break
        if unique_last:
            break
    return out


def build_world(rng: random.Random) -> World:
    firsts = FIRST[:]
    rng.shuffle(firsts)
    staff_firsts, hop_firsts, rest = firsts[:56], firsts[56:69], firsts[69:]
    taken: set[str] = set()
    staff = _people(rng, staff_firsts, 56, taken)
    pool = rest + staff_firsts  # contacts may share a first name with staff, never the full name
    rng.shuffle(pool)
    contacts = _people(rng, pool, 110, taken, unique_last=False)
    managers = _people(rng, [f for f in pool if f not in {c.first for c in contacts[:40]}], 30, taken)

    places = TOWNS + AREAS
    suppliers: list[str] = []
    items = SUPPLY_ITEMS[:]
    rng.shuffle(items)
    while len(suppliers) < 46:
        word = rng.choice(items).split()[0]
        word = word if word.isupper() else word.title()
        name = f"{rng.choice(places)} {rng.choice(['', '', word + ' '])}{rng.choice(SUPPLIER_WORDS)}".replace("  ", " ")
        if name not in suppliers:
            suppliers.append(name)
    companies = COMPANIES[:]
    rng.shuffle(companies)
    venues = VENUES[:]
    rng.shuffle(venues)
    dishes = [d for d in DISHES if d not in CODE_DISHES]
    rng.shuffle(dishes)
    return World(
        staff=staff, contacts=contacts, hop_people=["Otieno"] + hop_firsts, suppliers=suppliers[:32],
        hop_suppliers=suppliers[32:46], clients=companies[:24], hop_clients=companies[24:38],
        fact_venues=venues[:7], hop_venues=venues[7:20], fact_dishes=dishes[:20], changed_dishes=dishes[20:26],
        look_dishes=dishes[26:31], supply_items=items[:26], hop_items=items[26:40], managers=managers,
        extra={"branches": BRANCHES[:]})
