"""Scenario data: the support desk of an invented company (Helio Solar), so no model can know any of it.

A knowledge base (product sheets, policies, error codes), then eight days of customer tickets. Each ticket is one
of four kinds, which is what a deployed assistant meets:

  kb        answerable from the knowledge base as it stands
  learned   not in the knowledge base: the first time, a human agent answers it and the resolution is taught; later
            tickets ask the same thing in other words
  update    a policy changed on a given day (the old document is replaced); later tickets must get the new value
  unknown   nothing anywhere answers it (a product that does not exist, information the company never published):
            the only right move is to hand it to a human

Gold answers are short strings matched in the reply; `stale` strings are the superseded values (an answer that
gives one is wrong).

    python scripts/agentic/helio_data.py   # writes data/agentic/helio.json
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

KB = [
    ("HS-400 solar panel", "The HS-400 is Helio Solar's standard monocrystalline panel. It is rated at 400 watts. "
     "The HS-400 has a 25-year product warranty. The HS-400 costs $420 per panel."),
    ("HS-520 bifacial panel", "The HS-520 is a bifacial panel rated at 520 watts. The HS-520 has a 30-year product "
     "warranty. The HS-520 costs $610 per panel."),
    ("Volta-2 inverter", "The Volta-2 is a 7.6 kW hybrid inverter. The Volta-2 inverter has a 10-year warranty. "
     "The Volta-2 supports one Lumen battery."),
    ("Volta-X inverter", "The Volta-X is an 11.4 kW three-phase inverter. The Volta-X inverter has a 10-year "
     "warranty. The Volta-X supports up to three Lumen batteries."),
    ("Lumen LB-13 battery", "The Lumen LB-13 is a 13.5 kWh home battery. The Lumen LB-13 has a 10-year warranty. "
     "The Lumen LB-13 costs $8,900."),
    ("Installation fee policy", "The Helio installation fee is $180 per job plus $35 for each panel installed."),
    ("Rush shipping policy", "Rush shipping adds a surcharge of 7% of the order value."),
    ("Returns policy", "Unused equipment can be returned within 45 days. Every return needs an RMA number, which "
     "starts with HLX-."),
    ("Support hours", "The Helio support desk is open from 07:00 to 19:00, Monday to Saturday."),
    ("Service area", "Helio Solar installs in Nairobi, Mombasa and Kisumu."),
    ("Volta-2 error E21", "Error E21 on a Volta-2 means the grid voltage is out of range: check the AC isolator."),
    ("Volta-2 error E34", "Error E34 on a Volta-2 means battery communication was lost: reseat the CAN cable."),
    ("Monitoring app", "Customers monitor their system in the Helio Pulse app."),
    ("Escalation", "Technical cases the first line cannot solve go to the tier-2 desk at extension 4410."),
]

# resolutions a human agent gives the first time; taught afterwards
RESOLUTIONS = {
    "e57": ("Volta-X error E57", "Error E57 on a Volta-X means a fan fault: clear the intake grille and restart "
            "the inverter."),
    "clean": ("Panel cleaning", "Helio recommends cleaning the panels every 6 months."),
    "mesh": ("Bird mesh kit", "The Helio bird mesh kit costs $95."),
    "maxpanels": ("Volta-2 panel limit", "A Volta-2 inverter takes at most 18 panels."),
    "firmware": ("Volta-2 firmware", "The latest Volta-2 firmware is version 4.2.1."),
    "cable": ("Battery cable", "The Lumen LB-13 connects with the Helio CB-3 cable."),
}

# policy changes: on `day` the document `replaces` is withdrawn and this one published
UPDATES = [
    {"day": 4, "id": "warranty2", "replaces": "Volta-2 inverter",
     "title": "Volta-2 inverter", "text": "The Volta-2 is a 7.6 kW hybrid inverter. From November 2026 the Volta-2 "
     "inverter has a 12-year warranty. The Volta-2 supports one Lumen battery."},
    {"day": 5, "id": "area2", "replaces": "Service area",
     "title": "Service area", "text": "Helio Solar installs in Nairobi, Mombasa, Kisumu and Nakuru."},
    {"day": 6, "id": "fee2", "replaces": "Installation fee policy",
     "title": "Installation fee policy", "text": "The Helio installation fee is $200 per job plus $35 for each panel "
     "installed."},
]


def t(day, text, kind, gold, stale=(), teaches=None, ref=None):
    return {"day": day, "text": text, "kind": kind, "gold": list(gold), "stale": list(stale),
            "teaches": teaches, "ref": ref}


TICKETS = [
    # day 1
    t(1, "Hi, how long is the warranty on the HS-400 panel?", "kb", ["25"]),
    t(1, "What is the price of one HS-520 panel?", "kb", ["610"]),
    t(1, "My Volta-2 shows error E21. What does it mean?", "kb", ["AC isolator", "grid voltage"]),
    t(1, "What app do I use to monitor my panels?", "kb", ["Helio Pulse", "Pulse"]),
    t(1, "My Volta-X is showing error E57, what should I do?", "learned", ["intake grille", "fan"], teaches="e57"),
    t(1, "What is the delivery time for a Lumen battery?", "unknown", []),
    t(1, "How often should solar panels be cleaned?", "learned", ["6 months", "six months"], teaches="clean"),
    t(1, "What is the warranty on the Volta-2 inverter?", "kb", ["10"]),
    t(1, "What is the warranty on the HS-700 panel?", "unknown", []),
    # day 2
    t(2, "Volta-X error code E57 again on my unit. Fix?", "learned", ["intake grille", "fan"], ref="e57"),
    t(2, "How many kWh does the Lumen LB-13 store?", "kb", ["13.5"]),
    t(2, "What hours is the support desk open?", "kb", ["07:00", "7:00", "7 am", "7am", "7 a.m."]),
    t(2, "How much is the bird mesh kit?", "learned", ["95"], teaches="mesh"),
    t(2, "Where do RMA numbers start?", "kb", ["HLX"]),
    t(2, "What is the phone number of your CEO?", "unknown", []),
    t(2, "How many days do I have to return unused equipment?", "kb", ["45"]),
    t(2, "What is the maximum number of panels on one Volta-2?", "learned", ["18"], teaches="maxpanels"),
    t(2, "Which cities do you install in?", "kb", ["Kisumu"]),
    # day 3
    t(3, "Recommended cleaning interval for my panels?", "learned", ["6 months", "six months"], ref="clean"),
    t(3, "Price of the Helio bird mesh kit please", "learned", ["95"], ref="mesh"),
    t(3, "What does E34 mean on the Volta-2?", "kb", ["CAN cable", "battery communication"]),
    t(3, "What is the latest firmware for the Volta-2?", "learned", ["4.2.1"], teaches="firmware"),
    t(3, "How many Lumen batteries can a Volta-X take?", "kb", ["three", "3"]),
    t(3, "What is the delivery time to Kampala?", "unknown", []),
    t(3, "What is the rated power of the HS-400?", "kb", ["400"]),
    t(3, "Which cable connects the Lumen LB-13 battery?", "learned", ["CB-3"], teaches="cable"),
    t(3, "How long is the Lumen LB-13 warranty?", "kb", ["10"]),
    # day 4 (Volta-2 warranty becomes 12 years)
    t(4, "How many panels can I connect to a single Volta-2 inverter?", "learned", ["18"], ref="maxpanels"),
    t(4, "What warranty does the Volta-2 inverter come with?", "update", ["12"], stale=["10-year", "10 years"],
      ref="warranty2"),
    t(4, "What is the newest Volta-2 firmware version?", "learned", ["4.2.1"], ref="firmware"),
    t(4, "What is the extension for the tier-2 desk?", "kb", ["4410"]),
    t(4, "Does Helio offer financing plans?", "unknown", []),
    t(4, "What is the rush shipping surcharge?", "kb", ["7%", "7 percent", "7 per cent"]),
    t(4, "How much does the Lumen LB-13 cost?", "kb", ["8,900", "8900"]),
    # day 5 (Nakuru added to the service area)
    t(5, "Which cities does Helio install in now?", "update", ["Nakuru"], ref="area2"),
    t(5, "My Volta-X shows E57. Any idea?", "learned", ["intake grille", "fan"], ref="e57"),
    t(5, "Which cable do I need for the LB-13 battery?", "learned", ["CB-3"], ref="cable"),
    t(5, "What is the warranty on the HS-520?", "kb", ["30"]),
    t(5, "How long is the warranty on a Volta-2?", "update", ["12"], stale=["10-year", "10 years"], ref="warranty2"),
    t(5, "What is the warranty on the Volta Max inverter?", "unknown", []),
    t(5, "What is the base installation fee per job?", "kb", ["180"]),
    # day 6 (installation base fee becomes $200)
    t(6, "What is the base installation fee per job now?", "update", ["200"], stale=["180"], ref="fee2"),
    t(6, "How often do you recommend cleaning panels?", "learned", ["6 months", "six months"], ref="clean"),
    t(6, "What is the per-panel installation charge?", "kb", ["35"]),
    t(6, "List the cities in Helio's service area.", "update", ["Nakuru"], ref="area2"),
    t(6, "Is there a discount for schools?", "unknown", []),
    t(6, "What does Volta-2 error E21 mean?", "kb", ["AC isolator", "grid voltage"]),
    # day 7
    t(7, "Bird mesh kit price?", "learned", ["95"], ref="mesh"),
    t(7, "What's the Volta-2 firmware version I should install?", "learned", ["4.2.1"], ref="firmware"),
    t(7, "Volta-2 warranty length?", "update", ["12"], stale=["10-year", "10 years"], ref="warranty2"),
    t(7, "What is the battery capacity of the Lumen LB-13?", "kb", ["13.5"]),
    t(7, "What is the price of the HS-400?", "kb", ["420"]),
    t(7, "How do I reach the tier-2 desk?", "kb", ["4410"]),
    t(7, "What is the warranty on your EV charger?", "unknown", []),
    # day 8
    t(8, "Max panels per Volta-2 inverter?", "learned", ["18"], ref="maxpanels"),
    t(8, "What is the installation fee per job?", "update", ["200"], stale=["180"], ref="fee2"),
    t(8, "Cable for connecting an LB-13?", "learned", ["CB-3"], ref="cable"),
    t(8, "What does error E34 on a Volta-2 mean?", "kb", ["CAN cable", "battery communication"]),
    t(8, "Who manufactures your panels' glass?", "unknown", []),
    t(8, "Which app shows my system's production?", "kb", ["Helio Pulse", "Pulse"]),
]


def build() -> dict:
    tickets = [{"id": f"T{n + 1:03d}", **x} for n, x in enumerate(TICKETS)]
    return {"company": "Helio Solar (invented)", "kb": [{"title": a, "text": b} for a, b in KB],
            "resolutions": {k: {"title": a, "text": b} for k, (a, b) in RESOLUTIONS.items()},
            "updates": UPDATES, "tickets": tickets,
            "counts": {k: sum(x["kind"] == k for x in tickets) for k in ("kb", "learned", "update", "unknown")}}


if __name__ == "__main__":
    d = build()
    out = ROOT / "data/agentic/helio.json"
    out.write_text(json.dumps(d, indent=1))
    print(out, d["counts"], len(d["tickets"]), "tickets")
