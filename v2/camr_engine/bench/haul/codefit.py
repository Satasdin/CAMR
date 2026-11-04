"""Code that must fit: five helper modules planted with exact names, units and quirks, then 20 asks for new code
that calls them.

The modules are planted word for word as the assistant's code on days 5, 18, 33, 47 and 58. An answer is graded by
running unit tests on it in a sandboxed subprocess, in a temporary folder holding the same modules as the package
``mnk``. Calling a helper by a wrong name, in the wrong unit or in the wrong module fails the tests. The expected
values are computed here by running the reference solution against the same modules, and they never leave this
process: the child only reports what the answer returned.
"""

from __future__ import annotations

import ctypes
import functools
import json
import os
import re
import secrets
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

MONEY = '''"""Money helpers. Every amount inside the system is integer cents; shillings only at the edges."""

from decimal import ROUND_HALF_UP, Decimal

VAT_PERCENT = 16


def kes_to_cents(kes) -> int:
    """Shillings (int, float or str) to cents. Half a cent rounds up: 12.345 -> 1235."""
    return int((Decimal(str(kes)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_to_kes(cents: int) -> str:
    """Cents to a price label: 123450 -> "KES 1,234.50". A negative amount gets a leading minus."""
    sign = "-" if cents < 0 else ""
    c = abs(cents)
    return f"{sign}KES {c // 100:,}.{c % 100:02d}"


def add_vat(net_cents: int) -> int:
    """Net cents to gross with 16% VAT. The VAT part rounds DOWN to the cent (agreed with the accountant)."""
    return net_cents + net_cents * VAT_PERCENT // 100


def split_bill(total_cents: int, people: int) -> list[int]:
    """Equal shares that add up exactly. The leftover cents go to the FIRST shares, one each."""
    base, extra = divmod(total_cents, people)
    return [base + 1 if i < extra else base for i in range(people)]
'''

KITCHEN = '''"""Menu codes, prices and portions. A menu code is three capital letters, like "PIL" for pilau."""

PRICE_CENTS = {"PIL": 45000, "BIR": 52000, "CHP": 3000, "MND": 2000, "SAM": 6000, "NYC": 95000, "GTH": 35000,
               "MKM": 38000, "SKW": 15000, "UGL": 10000, "TLP": 85000, "KKN": 120000, "KCH": 5000}
GRAMS_PER_GUEST = {"PIL": 350, "BIR": 380, "CHP": 120, "MND": 90, "SAM": 100, "NYC": 300, "GTH": 320, "MKM": 330,
                   "SKW": 150, "UGL": 250, "TLP": 400, "KKN": 450, "KCH": 80}
BATCH_MINUTES = {"PIL": 55, "BIR": 70, "CHP": 25, "MND": 30, "SAM": 35, "NYC": 90, "GTH": 60, "MKM": 45,
                 "SKW": 15, "UGL": 20, "TLP": 40, "KKN": 120, "KCH": 10}
PACK_GRAMS = 500
BATCH_PORTIONS = 12


def price_cents(code: str) -> int:
    """Price of one portion in cents. An unknown code raises KeyError: there is no default price."""
    return PRICE_CENTS[code]


def portion_grams(code: str, guests: int) -> int:
    """Raw grams to buy for a party, rounded UP to whole 500 g packs (the market sells packs)."""
    need = GRAMS_PER_GUEST[code] * guests
    return -(-need // PACK_GRAMS) * PACK_GRAMS


def prep_minutes(code: str, portions: int) -> int:
    """Kitchen time in minutes: a dish cooks in batches of 12 portions, one batch after another."""
    batches = -(-portions // BATCH_PORTIONS)
    return batches * BATCH_MINUTES[code]
'''

DELIVERY = '''"""Delivery fees and zones. Distances are in METRES, because the maps API gives metres."""

BASE_FEE_KES = 150
BASE_METRES = 2000
PER_KM_KES = 40
ZONES = {"Westlands": "A", "Kilimani": "A", "Parklands": "A", "Lavington": "B", "Kileleshwa": "B",
         "South B": "B", "Karen": "C", "Rongai": "C", "Ruaka": "C"}


def delivery_fee_kes(distance_m: int) -> int:
    """Whole shillings, not cents: 150 up to 2 km, then 40 more for every started km after that."""
    if distance_m <= BASE_METRES:
        return BASE_FEE_KES
    extra_km = -(-(distance_m - BASE_METRES) // 1000)
    return BASE_FEE_KES + PER_KM_KES * extra_km


def zone_of(area: str) -> str:
    """ "A", "B" or "C". An area we don't serve gives "X", never an error."""
    return ZONES.get(area, "X")


def rider_minutes(distance_m: int, rush_hour: bool = False) -> int:
    """A rider's minutes: 3 per started km plus 10 to hand over; all of it doubles in rush hour."""
    minutes = 3 * -(-distance_m // 1000) + 10
    return minutes * 2 if rush_hour else minutes
'''

STAFF = '''"""Staff helpers. Shifts are in MINUTES, pay rates are cents per hour, and day numbers start at 1."""

SHIFT_MINUTES = {"early": 390, "late": 480, "split": 435}
RATE_CENTS = {"cook": 31250, "waiter": 25000, "rider": 27500, "cashier": 26000, "cleaner": 22500}


def shift_minutes(shift: str) -> int:
    """Length of a shift in minutes: early 390, late 480, split 435."""
    return SHIFT_MINUTES[shift]


def hourly_rate_cents(role: str) -> int:
    """Pay per hour in cents for a role."""
    return RATE_CENTS[role]


def normalise_phone(raw: str) -> str:
    """Any Kenyan mobile form to 12 digits with NO plus: "0700 000 001" -> "254700000001"."""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("254"):
        digits = digits[3:]
    if digits.startswith("0"):
        digits = digits[1:]
    return "254" + digits


def week_of(day: int) -> int:
    """Project week of a working day: days 1 to 5 are week 1, days 6 to 10 week 2, and so on."""
    return (day - 1) // 5 + 1
'''

ORDERS = '''"""Order references and kitchen hours. Times are HHMM integers: 930 means 09:30."""

BRANCH_CODES = {"Westlands": "WL", "Kilimani": "KL", "Karen": "KR", "Lavington": "LV", "Parklands": "PK"}
KITCHEN_HOURS = {"Westlands": (700, 2200), "Kilimani": (730, 2130), "Karen": (800, 2100),
                 "Lavington": (730, 2200), "Parklands": (630, 2030)}


def order_ref(branch: str, n: int) -> str:
    """ "WL-000123": the branch code, a dash and the number padded to six digits."""
    return f"{BRANCH_CODES[branch]}-{n:06d}"


def is_open(branch: str, hhmm: int) -> bool:
    """Whether the kitchen takes orders at hhmm: from opening time up to, but not including, closing time."""
    start, end = KITCHEN_HOURS[branch]
    return start <= hhmm < end
'''

MODULES = {"money": MONEY, "kitchen": KITCHEN, "delivery": DELIVERY, "staff": STAFF, "orders": ORDERS}
PLANT_DAYS = {"money": 5, "kitchen": 18, "delivery": 33, "staff": 47, "orders": 58}
REQUESTS = {
    "money": "Can you write the money helpers for the back office? Cents everywhere inside, a label for prices, VAT "
             "at 16% (the accountant says the VAT part rounds down), and a way to split a bill exactly.",
    "kitchen": "Next, the kitchen helpers: price per portion from the menu code, how much to buy for a party (the "
               "market sells 500 g packs) and how long the kitchen needs, since we cook in batches of 12.",
    "delivery": "Delivery helpers please. Careful: the maps API gives distances in metres, so the helpers take "
                "metres. Fee is 150 up to 2 km and 40 per started km after; zones A, B, C, and X for areas we "
                "don't serve.",
    "staff": "Staff helpers for the rota and payroll: shift lengths in minutes, hourly rates in cents, phone numbers "
             "in the form the SMS gateway wants (254..., no plus), and the project week of a working day.",
    "orders": "Last ones: order references like WL-000123 per branch, and whether a branch kitchen takes orders at "
              "a given time. We store times as HHMM integers, so 930 is half past nine.",
}


@dataclass
class CodeAsk:
    pid: str
    entry: str
    ask: str
    reference: str
    cases: list[list]
    needs: list[str]


ASKS = [
    ("catering_total_cents", ["money", "kitchen", "delivery"],
     "Write `catering_total_cents(order: dict[str, int], distance_km: float) -> int` for catering quotes. `order` "
     "maps menu codes to portions and `distance_km` is how far the venue is, in kilometres. It returns the total in "
     "cents: the food at menu prices with VAT added, plus our delivery fee for that distance. Use our existing "
     "helpers.",
     "def catering_total_cents(order, distance_km):\n    food = sum(price_cents(c) * q for c, q in order.items())\n"
     "    return add_vat(food) + kes_to_cents(delivery_fee_kes(round(distance_km * 1000)))\n",
     [[{"PIL": 10, "CHP": 30}, 3.2], [{"NYC": 4, "KCH": 4}, 1.5], [{"BIR": 25}, 12.0], [{"SAM": 7, "MND": 13}, 2.0],
      [{"GTH": 3}, 7.25]]),
    ("food_label", ["money", "kitchen"],
     "Write `food_label(order: dict[str, int]) -> str`: the price label for the food in an order (menu code -> "
     "portions), VAT included, in our usual label format. Use our helpers.",
     "def food_label(order):\n    return cents_to_kes(add_vat(sum(price_cents(c) * q for c, q in order.items())))\n",
     [[{"PIL": 3}], [{"CHP": 7, "SKW": 2}], [{"KKN": 11, "TLP": 1}], [{"MND": 1}]]),
    ("shopping_grams", ["kitchen"],
     "Write `shopping_grams(menu: list[str], guests: int) -> dict[str, int]`: for each menu code, the raw grams the "
     "market run must buy for that many guests. Use our kitchen helpers.",
     "def shopping_grams(menu, guests):\n    return {c: portion_grams(c, guests) for c in menu}\n",
     [[["PIL", "SKW"], 37], [["NYC"], 12], [["MKM", "CHP", "KCH"], 101], [["UGL"], 3]]),
    ("kitchen_minutes", ["kitchen"],
     "Write `kitchen_minutes(order: dict[str, int]) -> int`: how many minutes the kitchen needs for an order of "
     "menu code -> portions, one dish after another. Use our helpers.",
     "def kitchen_minutes(order):\n    return sum(prep_minutes(c, q) for c, q in order.items())\n",
     [[{"PIL": 12}], [{"PIL": 13, "CHP": 40}], [{"KKN": 1, "UGL": 25, "SAM": 24}], [{"BIR": 100}]]),
    ("shift_pay_cents", ["staff"],
     "Write `shift_pay_cents(role: str, shifts: list[str]) -> int`: the pay in cents for one person in that role "
     "working those shifts (\"early\", \"late\", \"split\"). Each shift's pay rounds down to the cent. Use our staff "
     "helpers.",
     "def shift_pay_cents(role, shifts):\n    return sum(hourly_rate_cents(role) * shift_minutes(s) // 60 "
     "for s in shifts)\n",
     [["cook", ["early", "late"]], ["waiter", ["split", "split", "early"]], ["cleaner", ["late"]],
      ["rider", ["early"] * 5]]),
    ("sms_list", ["staff"],
     "Write `sms_list(raw: list[str]) -> list[str]`: clean phone numbers typed in by staff into the form our SMS "
     "helper uses, drop duplicates, and return them sorted. Use our helpers.",
     "def sms_list(raw):\n    return sorted(set(normalise_phone(r) for r in raw))\n",
     [[["0700 000 001", "+254 700 000 001", "0700000002"]], [["254711000003", "0711-000-003", "0722 000 004"]],
      [["0733 000 005"]]]),
    ("orders_in_week", ["staff"],
     "Write `orders_in_week(orders: list[tuple[int, str]], week: int) -> list[str]`: from (working day number, "
     "order reference) pairs, the references whose day falls in that project week, in their original order. Use "
     "our helpers.",
     "def orders_in_week(orders, week):\n    return [ref for day, ref in orders if week_of(day) == week]\n",
     [[[[1, "WL-1"], [5, "WL-2"], [6, "KL-3"], [10, "KR-4"], [11, "KR-5"]], 2],
      [[[1, "WL-1"], [5, "WL-2"], [6, "KL-3"]], 1], [[[44, "A"], [45, "B"], [46, "C"], [50, "D"]], 9]]),
    ("next_refs", ["orders"],
     "Write `next_refs(branch: str, last: int, count: int) -> list[str]`: the next `count` order references for "
     "a branch after order number `last`. Use our order helpers.",
     "def next_refs(branch, last, count):\n    return [order_ref(branch, last + i) for i in range(1, count + 1)]\n",
     [["Westlands", 122, 3], ["Karen", 0, 2], ["Parklands", 999999, 1], ["Kilimani", 4517, 4]]),
    ("open_kitchens", ["orders"],
     "Write `open_kitchens(hhmm: int) -> list[str]`: the branches (by name, sorted) whose kitchens take orders at "
     "that time, written the way our order helpers write times. Use our helpers.",
     "def open_kitchens(hhmm):\n    return sorted(b for b in BRANCH_CODES if is_open(b, hhmm))\n",
     [[700], [2130], [2029], [630], [2200], [745]]),
    ("share_per_guest", ["money", "kitchen", "delivery"],
     "Write `share_per_guest(order: dict[str, int], distance_km: float, guests: int) -> list[int]`: each guest's "
     "share in cents of a catering order (food with VAT plus delivery for `distance_km` kilometres), split so the "
     "shares add up exactly, the way our bill splitting does it. Use our helpers.",
     "def share_per_guest(order, distance_km, guests):\n    food = sum(price_cents(c) * q for c, q in order.items())\n"
     "    total = add_vat(food) + kes_to_cents(delivery_fee_kes(round(distance_km * 1000)))\n"
     "    return split_bill(total, guests)\n",
     [[{"PIL": 3, "CHP": 6}, 2.5, 4], [{"SAM": 9}, 0.8, 7], [{"BIR": 2, "KCH": 2}, 4.1, 3]]),
    ("zone_fees", ["delivery"],
     "Write `zone_fees(areas_km: dict[str, float]) -> dict[str, int]`: for each area and its distance in "
     "kilometres, our delivery fee in shillings, or -1 for an area we don't deliver to. Use our helpers.",
     "def zone_fees(areas_km):\n    return {a: (delivery_fee_kes(round(km * 1000)) if zone_of(a) != 'X' else -1) "
     "for a, km in areas_km.items()}\n",
     [[{"Westlands": 1.2, "Karen": 14.6}], [{"Lavington": 2.01, "Gigiri": 5.0}], [{"Rongai": 21.0}]]),
    ("rider_plan", ["delivery"],
     "Write `rider_plan(stops_km: list[float], rush_hour: bool) -> int`: the rider minutes for a run of drops, each "
     "stop given in kilometres from the kitchen. Use our delivery helpers.",
     "def rider_plan(stops_km, rush_hour):\n    return sum(rider_minutes(round(km * 1000), rush_hour) "
     "for km in stops_km)\n",
     [[[1.0, 2.5, 0.4], False], [[7.2], True], [[3.0, 3.001], False]]),
    ("cheapest_dish", ["kitchen"],
     "Write `cheapest_dish(codes: list[str]) -> str`: the code of the cheapest dish among those codes. Ignore "
     "codes that are not on our menu; on a tie, the code that comes first alphabetically wins. Use our helpers.",
     "def cheapest_dish(codes):\n    known = []\n    for c in codes:\n        try:\n"
     "            known.append((price_cents(c), c))\n        except KeyError:\n            pass\n"
     "    return min(known)[1]\n",
     [[["PIL", "BIR", "CHP"]], [["XYZ", "SKW", "UGL"]], [["NYC", "QQQ", "KKN", "TLP"]], [["MND", "KCH"]]]),
    ("vat_part_cents", ["money"],
     "Write `vat_part_cents(net_items: list[int]) -> int`: the total VAT in cents on a receipt whose lines have "
     "these net amounts in cents. VAT is worked out line by line, the way our money helpers do it.",
     "def vat_part_cents(net_items):\n    return sum(add_vat(n) - n for n in net_items)\n",
     [[[1999, 1999, 1999]], [[5, 5, 5, 5]], [[100000]], [[12345, 6789]]]),
    ("week_counts", ["staff"],
     "Write `week_counts(days: list[int]) -> dict[int, int]`: how many of these working day numbers fall in each "
     "project week, keyed by week number. Use our helpers.",
     "def week_counts(days):\n    out = {}\n    for d in days:\n        w = week_of(d)\n"
     "        out[w] = out.get(w, 0) + 1\n    return dict(sorted(out.items()))\n",
     [[[1, 2, 5, 6, 10, 11]], [[25, 26, 30, 31]], [[100]]]),
    ("party_packs", ["kitchen"],
     "Write `party_packs(menu: list[str], guests: int) -> int`: how many market packs to buy in all for a party "
     "with these menu codes. Use our helpers.",
     "def party_packs(menu, guests):\n    return sum(portion_grams(c, guests) // 500 for c in menu)\n",
     [[["PIL", "CHP"], 40], [["NYC", "SKW", "MND"], 15], [["KCH"], 1]]),
    ("fee_labels", ["money", "delivery"],
     "Write `fee_labels(distances_m: list[int]) -> list[str]`: the delivery fee for each distance (given in "
     "metres) as a price label in our usual format. Use our helpers.",
     "def fee_labels(distances_m):\n    return [cents_to_kes(kes_to_cents(delivery_fee_kes(d))) "
     "for d in distances_m]\n",
     [[[500, 2000, 2001]], [[10500]], [[3999, 4000, 4001]]]),
    ("late_shift_cost", ["staff"],
     "Write `late_shift_cost(roles: list[str]) -> int`: what one late shift costs in cents for a team with these "
     "roles, each person's pay rounded down to the cent. Use our helpers.",
     "def late_shift_cost(roles):\n    return sum(hourly_rate_cents(r) * shift_minutes('late') // 60 "
     "for r in roles)\n",
     [[["cook", "cook", "waiter"]], [["cleaner"]], [["rider", "cashier", "waiter", "cook"]]]),
    ("menu_board", ["money", "kitchen"],
     "Write `menu_board(codes: list[str]) -> list[str]`: one line per code, the code, a space, and its price label "
     "in our usual format. Use our helpers.",
     "def menu_board(codes):\n    return [f'{c} {cents_to_kes(price_cents(c))}' for c in codes]\n",
     [[["PIL", "KKN"]], [["CHP"]], [["MND", "SAM", "NYC"]]]),
    ("split_labels", ["money"],
     "Write `split_labels(total_cents: int, people: int) -> list[str]`: split a bill exactly the way our money "
     "helpers split bills, and give each share as a price label.",
     "def split_labels(total_cents, people):\n    return [cents_to_kes(s) for s in split_bill(total_cents, people)]\n",
     [[1000, 3], [123457, 4], [99, 2]]),
]


def _namespace(needs: list[str]) -> dict:
    ns: dict = {}
    for name in needs:
        exec(compile(MODULES[name], f"mnk/{name}.py", "exec"), ns)
    return ns


def code_asks() -> list[CodeAsk]:
    """The 20 asks, each with its cases' expected values computed by running the reference solution."""
    out = []
    for i, (entry, needs, ask, ref, args) in enumerate(ASKS, start=1):
        ns = _namespace(needs)
        exec(compile(ref, f"<reference {entry}>", "exec"), ns)
        cases = [[a, json.loads(json.dumps(ns[entry](*a)))] for a in args]
        out.append(CodeAsk(f"code-{i:02d}", entry, ask, ref, cases, needs))
    return out


def plant_text(name: str) -> str:
    """The assistant's message that plants module ``name``."""
    return f"Here is `mnk/{name}.py`:\n\n```python\n{MODULES[name]}```"


# ---------------------------------------------------------------------------------------------------------------
# Running an answer. The answer is untrusted code, so the child never sees the expected values: it gets the entry
# name and the arguments on stdin with a one-time marker, prints what the function returned after that marker, and
# the parent compares. On macOS the child runs under sandbox-exec (no network, no forking or other programs, no
# reading the home folder or the temp folders, writing only in its own folder), with resource limits, in its own
# process group, and with a memory watch from the parent. Python starts with -S, so only the standard library and
# the planted ``mnk`` modules can be imported. Where sandbox-exec is missing (Linux) only the limits apply, and the
# result says so in ``isolation``.

MEMORY_MB = 1024  # resident memory the child may use before it is killed
OUTPUT_BYTES = 1 << 20  # largest file, stdout included, the child may write
TAIL_BYTES = 64 << 10  # how much of the end of stdout the parent reads

_CODE = re.compile(r"```([\w+-]*)[ \t]*\n(.*?)```", re.S)
_RUNNER = """import json, sys


def _main():
    spec = json.loads(sys.stdin.read())
    sys.stdin.close()
    marker, limits = spec.pop("marker"), spec.pop("limits")
    try:
        import resource
    except ImportError:
        resource = None
    for name, value in limits.items():
        try:
            resource.setrlimit(getattr(resource, name), (value, value))
        except (AttributeError, ValueError, OSError):
            pass
    out = {"results": [], "error": None}
    try:
        import answer
        fn = getattr(answer, spec["entry"])
    except BaseException as e:
        out["error"] = f"{type(e).__name__}: {e}"
    else:
        for args in spec["args"]:
            try:
                out["results"].append({"got": json.loads(json.dumps(fn(*args)))})
            except BaseException as e:
                out["results"].append({"error": f"{type(e).__name__}: {e}"})
    sys.stdout.write("\\n" + marker + json.dumps(out) + "\\n")
    sys.stdout.flush()


_main()
"""


def extract_code(answer: str) -> str | None:
    """The Python in an answer: its fenced python blocks (or unlabelled ones), else the bare text if it has a def."""
    blocks = [b for lang, b in _CODE.findall(answer) if lang.lower() in ("python", "py", "python3", "")]
    if blocks:
        return "\n\n".join(blocks)
    return answer if re.search(r"^\s*def \w+\(", answer, re.M) else None


@functools.lru_cache(maxsize=1)
def sandbox_exec() -> str | None:
    """The sandbox-exec binary when it can apply a profile here (macOS), else None."""
    exe = shutil.which("sandbox-exec") or ("/usr/bin/sandbox-exec" if Path("/usr/bin/sandbox-exec").exists() else None)
    if not exe:
        return None
    try:
        ok = subprocess.run([exe, "-p", "(version 1)(allow default)", "/usr/bin/true"], capture_output=True,
                            timeout=10, stdin=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    return exe if ok else None


def _quote(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sandbox_profile(workdir: str) -> str:
    """The sandbox-exec profile for one run: no network, no forking, no running other programs, no Apple events or
    system services, writes only in ``workdir``, and no reading of files in the home folder, /Users, /Volumes or the
    temp folders, except ``workdir`` and Python itself."""
    home = os.path.realpath(os.path.expanduser("~"))
    work = os.path.realpath(workdir)
    pythons = {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix,
               str(Path(os.path.realpath(sys.executable)).parent.parent)}
    readable = sorted({q for p in pythons for q in (p, os.path.realpath(p))
                       if q and q != "/" and not home.startswith(q.rstrip("/") + "/") and q != home})
    hidden = sorted({home, "/Users", "/Volumes", "/private/tmp", "/private/var/folders",
                     os.path.realpath(tempfile.gettempdir())})
    python = os.path.realpath(sys.executable)
    return "\n".join([
        "(version 1)",
        "(allow default)",
        "(deny network*)",
        "(deny process-fork)",
        "(deny process-exec)",
        "(allow process-exec " + " ".join(f"(literal {_quote(p)})" for p in sorted({sys.executable, python})) + ")",
        "(deny appleevent-send)",
        "(deny mach-lookup)",
        "(deny file-write*)",
        f"(allow file-write* (subpath {_quote(work)}) (literal \"/dev/null\"))",
        "(deny file-read-data " + " ".join(f"(subpath {_quote(p)})" for p in hidden) + ")",
        "(allow file-read-data " + " ".join(f"(subpath {_quote(p)})" for p in readable + [work]) + ")",
    ]) + "\n"


def _rss(pid: int) -> int | None:
    """Resident bytes of process ``pid``, or None when it cannot be read."""
    try:
        if sys.platform == "darwin":
            lib = _libproc()
            buf = ctypes.create_string_buffer(96)  # struct proc_taskinfo
            if lib.proc_pidinfo(pid, 4, 0, buf, 96) != 96:  # PROC_PIDTASKINFO
                return None
            return struct.unpack_from("QQ", buf.raw)[1]
        with open(f"/proc/{pid}/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, AttributeError, IndexError):
        return None


@functools.lru_cache(maxsize=1)
def _libproc():
    lib = ctypes.CDLL("/usr/lib/libproc.dylib")
    lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    return lib


def _kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    proc.wait()


def _tail(f) -> str:
    f.seek(0, os.SEEK_END)
    f.seek(max(0, f.tell() - TAIL_BYTES))
    return f.read().decode("utf-8", "replace")


def run_tests(spec: dict, code: str) -> dict:
    """Run the spec's cases on ``code`` in a sandboxed subprocess with a timeout, and compare what it returns with
    the expected values here. Returns passed/total/failures/error, and ``isolation``: how the child was fenced."""
    total = len(spec["cases"])
    timeout = float(spec.get("timeout", 10))
    preamble = "".join(f"from mnk.{m} import *\n" for m in spec["needs"])
    marker = "@@HAUL-" + secrets.token_hex(16) + "@@"
    limits = {"RLIMIT_CPU": int(timeout) + 1, "RLIMIT_FSIZE": OUTPUT_BYTES, "RLIMIT_NPROC": 0, "RLIMIT_NOFILE": 64,
              "RLIMIT_CORE": 0, "RLIMIT_AS": MEMORY_MB << 20}
    payload = json.dumps({"marker": marker, "limits": limits, "entry": spec["entry"],
                          "args": [args for args, _ in spec["cases"]]}).encode()
    sandbox = sandbox_exec()
    error = None
    with tempfile.TemporaryDirectory(prefix="haul-code-") as tmp, tempfile.TemporaryFile() as out, \
            tempfile.TemporaryFile() as err:
        root = Path(tmp)
        (root / "mnk").mkdir()
        (root / "mnk" / "__init__.py").write_text('"""Mama Njeri\'s Kitchen back office."""\n')
        for name, src in spec["modules"].items():
            (root / "mnk" / f"{name}.py").write_text(src)
        (root / "answer.py").write_text(preamble + "\n" + code + "\n")
        (root / "run.py").write_text(_RUNNER)
        env = {"PATH": "/usr/bin:/bin", "HOME": tmp, "TMPDIR": tmp, "PYTHONHASHSEED": "0",
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "LANG": "C.UTF-8"}
        cmd = [sys.executable, "-S", "-B", "run.py"]
        if sandbox:
            cmd = [sandbox, "-p", sandbox_profile(tmp)] + cmd
        proc = subprocess.Popen(cmd, cwd=root, stdin=subprocess.PIPE, stdout=out, stderr=err, env=env,
                                start_new_session=True)
        try:
            proc.stdin.write(payload)
            proc.stdin.close()
        except OSError:
            pass
        deadline = time.monotonic() + timeout
        while True:
            try:
                proc.wait(timeout=0.05)
                break
            except subprocess.TimeoutExpired:
                pass
            if time.monotonic() > deadline:
                error = "timed out"
            elif (_rss(proc.pid) or 0) > MEMORY_MB << 20:
                error = f"used more than {MEMORY_MB} MB of memory"
            if error:
                _kill(proc)
                break
        _kill(proc)  # nothing it started may outlive it
        stdout, stderr = _tail(out), _tail(err)
    isolation = "sandbox-exec" if sandbox else "rlimits only"
    if error:
        return {"passed": 0, "total": total, "failures": [], "error": error, "isolation": isolation}
    line = next((ln for ln in reversed(stdout.splitlines()) if ln.startswith(marker)), None)
    if line is None or proc.returncode != 0:
        last = (stderr.strip().splitlines() or [""])[-1]
        why = last or ("exited before its tests finished" if line is None else f"exited with {proc.returncode}")
        return {"passed": 0, "total": total, "failures": [], "error": why[:200], "isolation": isolation}
    try:
        got = json.loads(line[len(marker):])
        results = got["results"]
        if got["error"]:
            return {"passed": 0, "total": total, "failures": [], "error": str(got["error"])[:200],
                    "isolation": isolation}
        if not isinstance(results, list) or len(results) != total or not all(isinstance(r, dict) for r in results):
            raise ValueError("wrong number of results")
    except (ValueError, KeyError, TypeError):
        return {"passed": 0, "total": total, "failures": [], "error": "garbled test output", "isolation": isolation}
    passed, failures = 0, []
    for i, ((_, want), r) in enumerate(zip(spec["cases"], results)):
        if "got" not in r:
            failures.append(f"case {i}: {str(r.get('error'))[:160]}")
        elif r["got"] == want:
            passed += 1
        else:
            failures.append(f"case {i}: got {r['got']!r}, want {want!r}")
    return {"passed": passed, "total": total, "failures": failures, "error": None, "isolation": isolation}
