"""Word pools and a small phrase engine, so the Long Haul never says the same thing the same way twice.

``say(rng, "[Hi|Habari] {name}, [the|our] {thing} is ready", name=..., thing=[...])`` picks one choice from every
``[a|b|c]`` group (innermost first, an empty choice allowed) and then fills every ``{slot}``. A slot given a list
or tuple picks one item; a callable is called. Slot values are put in after the choices, so brackets inside them
are safe.
"""

from __future__ import annotations

import datetime as dt
import random
import re

_ALT = re.compile(r"\[([^\[\]]*)\]")
_SLOT = re.compile(r"\{(\w+)\}")
_SPACE = re.compile(r"[ \t]{2,}")
_BEFORE_PUNCT = re.compile(r"[ \t]+([,.;:!?])")


def say(rng: random.Random, template: str, **slots) -> str:
    """One way of saying ``template`` (see the module docstring)."""
    t = template
    while True:
        m = _ALT.search(t)
        if not m:
            break
        t = t[:m.start()] + rng.choice(m.group(1).split("|")) + t[m.end():]

    def fill(m: re.Match) -> str:
        v = slots[m.group(1)]
        if callable(v):
            v = v()
        elif isinstance(v, (list, tuple)):
            v = rng.choice(v)
        return str(v)

    t = _SLOT.sub(fill, t)
    return _BEFORE_PUNCT.sub(r"\1", _SPACE.sub(" ", t)).strip()


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def pick(rng: random.Random, seq, k: int | None = None):
    """One item, or ``k`` distinct items, of ``seq``."""
    if k is None:
        return seq[rng.randrange(len(seq))]
    return rng.sample(list(seq), k)


def money(n: int) -> str:
    return f"{n:,}"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def long_date(d: dt.date) -> str:
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


# People. Otieno, Wanjiru and Njeri are kept out of these pools: Otieno (payments) never gets a surname, the two
# Wanjirus are the look-alikes, and Mama Njeri owns the kitchen. Kamau and Njoroge are the Wanjirus' surnames only.
FIRST = ["Amina", "Kamande", "Achieng", "Baraka", "Zawadi", "Imani", "Juma", "Akinyi", "Kiprono", "Chebet", "Mutua",
         "Nduta", "Wekesa", "Halima", "Omondi", "Atieno", "Wairimu", "Nafula", "Cherono", "Makena", "Kibet", "Rotich",
         "Auma", "Musa", "Fatuma", "Kerubo", "Moraa", "Ouma", "Wambui", "Kiptoo", "Jeptoo", "Mumbua", "Onyango",
         "Sanaipei", "Lemayian", "Gathoni", "Barasa", "Wafula", "Nyambura", "Koech", "Adhiambo", "Kipkemboi",
         "Muthoni", "Esther", "Brian", "Faith", "Kevin", "Mercy", "Dennis", "Grace", "Collins", "Joy", "Victor",
         "Purity", "Edwin", "Lilian", "Felix", "Caroline", "Moses", "Diana", "Stephen", "Beatrice", "Samuel",
         "Winnie", "Patrick", "Ruth", "Hassan", "Salma", "Ibrahim", "Naliaka", "Tabitha", "Gideon", "Sharon",
         "Emmanuel", "Lydia", "Abdi", "Hawa", "Josphat", "Eunice", "Kennedy", "Rehema", "Tobias", "Pauline",
         "Silas", "Agnes", "Nelson", "Florence", "Dorcas", "Elijah", "Mwende", "Kioko", "Ndinda", "Mueni"]
SURNAMES = ["Ochieng", "Mwangi", "Kariuki", "Wafula", "Kiplagat", "Achola", "Mutiso", "Gitau", "Chege", "Owino",
            "Kimani", "Maina", "Ndegwa", "Odhiambo", "Wanyama", "Korir", "Langat", "Muriuki", "Nyaga", "Kipchumba",
            "Omollo", "Barasa", "Simiyu", "Kahindi", "Mohamed", "Abdalla", "Kilonzo", "Musyoka", "Ngugi", "Waweru",
            "Karanja", "Mbugua", "Onsongo", "Nyamweya", "Ruto", "Cheruiyot", "Sang", "Mutai", "Kemboi", "Wekesa",
            "Masika", "Nekesa", "Juma", "Okoth", "Oduya", "Nderitu", "Gachanja", "Kibe", "Mburu", "Njenga",
            "Kinyua", "Muthee", "Kirui", "Tanui", "Bett", "Rono", "Biwott", "Lagat", "Oyugi", "Opiyo", "Atieno",
            "Mwita", "Chacha", "Marwa", "Nyakundi", "Ombati", "Moraa", "Momanyi", "Ondieki", "Kerubo", "Mwiti",
            "Kirimi", "Murithi", "Gikonyo", "Wachira", "Githinji"]

BRANCHES = ["Westlands", "Kilimani", "Karen", "South B", "Lavington", "Parklands", "Ruaka", "Rongai", "Kasarani",
            "Upper Hill", "Langata", "Embakasi"]
AREAS = ["Kileleshwa", "Hurlingham", "Gigiri", "Runda", "Donholm", "Buruburu", "Ngara", "Pangani", "Eastleigh",
         "Kitisuru", "Muthaiga", "Spring Valley", "Loresho", "Riverside", "Madaraka", "Nairobi West", "South C",
         "Umoja", "Kahawa", "Roysambu", "Syokimau", "Kitengela", "Ngong", "Thome", "Garden Estate", "Ridgeways"]
TOWNS = ["Nakuru", "Kisumu", "Eldoret", "Thika", "Nyeri", "Malindi", "Naivasha", "Kericho", "Machakos", "Kitale",
         "Embu", "Meru", "Kakamega", "Nanyuki", "Kilifi", "Narok", "Bungoma", "Voi", "Garissa", "Lamu", "Kitui",
         "Homa Bay", "Isiolo", "Murang'a", "Kiambu", "Kisii", "Migori", "Busia", "Siaya", "Nyahururu", "Webuye",
         "Mumias", "Maralal", "Wote", "Kapsabet", "Iten", "Ol Kalou", "Kerugoya", "Chuka", "Marsabit"]
ROADS = ["Thika Road", "Mombasa Road", "Ngong Road", "Waiyaki Way", "Langata Road", "Jogoo Road", "Outer Ring Road",
         "Limuru Road", "Kiambu Road", "Uhuru Highway", "Argwings Kodhek Road", "Lenana Road", "Dennis Pritt Road"]

DISHES = ["pilau", "biryani", "chapati", "mandazi", "beef samosa", "nyama choma", "githeri", "mukimo", "sukuma wiki",
          "ugali", "fried tilapia", "kuku kienyeji", "viazi karai", "bhajia", "mahamri", "kachumbari", "chai masala",
          "dawa", "passion juice", "mango juice", "uji", "mshikaki", "maharagwe", "kaimati", "matoke", "beef stew",
          "chicken curry", "fish fillet", "vegetable rice", "coconut beans", "managu", "terere", "omena",
          "mutura", "smokie pasua", "chips masala", "fruit salad", "chapati rolls", "lentil soup", "goat stew",
          "pumpkin soup", "sweet potato fries", "arrowroot chips", "pea stew", "roast chicken", "egg curry",
          "cabbage stir-fry", "ginger tea", "tamarind juice", "beef wet fry"]
SUPPLY_ITEMS = ["charcoal", "eggs", "maize flour", "wheat flour", "cooking oil", "rice", "milk", "tomatoes", "onions",
                "goat meat", "beef", "chicken", "tilapia", "sukuma", "potatoes", "sugar", "tea leaves", "spices",
                "packaging boxes", "napkins", "LPG gas", "bottled water", "fresh juice", "bananas", "beans",
                "cleaning supplies", "coriander", "ginger", "garlic", "carrots", "cabbages", "coconut milk",
                "yeast", "salt", "butter", "cream", "capsicum", "lemons", "mangoes", "passion fruit"]
SUPPLIER_WORDS = ["Traders", "Suppliers", "Fresh", "Farm", "Wholesalers", "Distributors", "Agencies", "Millers",
                  "Ventures", "Enterprises", "Depot", "Co-op", "Growers", "Packers"]
COMPANIES = ["Kilele Insurance", "Mvua Labs", "Baobab Logistics", "Twiga Freight", "Jua Solar", "Simba Media",
             "Kasuku Learning", "Ndovu Capital", "Tausi Health", "Pwani Shipping", "Mlima Engineering",
             "Faraja Hospice", "Umoja Sacco", "Nyota Pharmaceuticals", "Kifaru Security", "Zuri Interiors",
             "Rafiki Microfinance", "Chui Motors", "Sauti Records", "Bahari Hotels", "Mto Water Works",
             "Amani Schools", "Pamoja Church", "Jamii Clinic", "Neema Bakery", "Upepo Wind", "Kesho Bank",
             "Kijiji Foods", "Miale Studios", "Taji Events", "Mwanga Electric", "Safari Tech", "Ujuzi Academy",
             "Malkia Salons", "Ngao Insurance", "Shamba Agritech", "Kito Jewellers", "Tembo Breweries"]
VENUES = ["the Arboretum pavilion", "Ngong Hills Gardens", "the Karura forest picnic site", "the Ole Sereni terrace",
          "the KICC rooftop", "the Windsor club lawn", "the Muthaiga hall", "the Kilimani community centre",
          "the Two Rivers atrium", "the Railway club grounds", "the Brackenhurst marquee", "the Nairobi Gallery yard",
          "the Westlands sports club", "the Kenyatta University hall", "the Strathmore auditorium",
          "the Paradise Lost lawn", "the Lavington church hall", "the Uhuru gardens tent", "the Ngara warehouse loft",
          "the Garden City rooftop"]
LAPTOPS = ["ThinkPad T14", "MacBook Air M3", "Dell Latitude 5440", "HP EliteBook 840", "Lenovo IdeaPad 5",
           "Asus Zenbook 14", "Acer Swift 3", "Surface Laptop 5", "HP ProBook 450", "Dell XPS 13",
           "MacBook Pro 14", "ThinkPad X1 Carbon", "Huawei MateBook D15", "Lenovo Yoga 7", "Acer Aspire 7"]
ROLES = ["sous chef", "line cook", "cashier", "delivery rider", "head waiter", "baker", "barista", "storekeeper",
         "dishwashing lead", "procurement officer", "social media manager", "driver", "security guard",
         "cleaning supervisor", "grill cook", "prep cook", "catering coordinator", "receptionist",
         "kitchen porter", "pastry assistant", "inventory clerk", "shift supervisor"]
ROUTES = ["11", "23", "33", "44", "46", "58", "102", "105", "111", "125", "237", "4W", "8", "15", "24", "34", "48",
          "100", "110", "119", "145"]

# Words of the project itself, used by the chat, meeting and code noise.
PAGES = ["home page", "menu page", "contact page", "about page", "order tracking page", "checkout", "cart drawer",
         "branch finder", "gallery", "admin dashboard", "stock screen", "rota screen", "receipts view",
         "supplier list", "purchase orders screen", "reports page", "login screen", "catering quote form"]
COMPONENTS = ["the menu grid", "the cart drawer", "the M-Pesa callback", "the stock alert job", "the rota export",
              "the SMS queue", "the image resizer", "the search box", "the branch selector", "the receipt printer",
              "the nightly backup", "the order webhook", "the price import", "the login form", "the sitemap",
              "the PDF invoice", "the delivery map", "the reorder report", "the CSV export", "the health check",
              "the cache layer", "the photo uploader", "the review widget", "the opening hours banner"]
SYMPTOMS = ["returns a 502", "is slow on 3G", "shows the wrong price", "double-charges", "times out", "loses the session",
            "renders blank on Safari", "throws a KeyError", "sends the SMS twice", "drops the last item",
            "shows yesterday's stock", "crashes on an empty cart", "ignores the branch filter", "logs out at random",
            "prints the receipt in tiny font", "skips Sunday", "rounds the total wrong", "hangs on upload",
            "spams the error log", "shows a broken image", "breaks the layout on small phones"]
CONDITIONS = ["when two people order at once", "after the 6pm rush", "only on the Westlands tablet", "when the power flickers",
              "if the phone number has spaces", "on the first load of the day", "when the network is on Safaricom 3G",
              "if the cart has more than ten items", "after a deploy", "on Mondays", "when the image is a PNG",
              "if the customer goes back a page", "when the printer is offline", "during the lunch rush",
              "if the branch is closed", "with the Swahili translation on"]
FIXES = ["add an index on orders.created_at", "debounce the input by 300 ms", "move it into a background worker",
         "cache the result for five minutes", "lock the row with select_for_update", "retry with backoff",
         "validate the payload before saving", "normalise the phone number first", "serve WebP with a JPEG fallback",
         "batch the inserts", "paginate the query", "use a database transaction", "add a unique constraint",
         "make the job idempotent", "set an explicit timeout", "lazy-load the images below the fold",
         "precompute the totals nightly", "split the view into two queries", "store money as integer cents",
         "pin the dependency version"]
TOOLS = ["Django", "FastAPI", "Postgres", "Redis", "nginx", "Docker", "GitHub Actions", "Celery", "Sentry",
         "Cloudflare", "pytest", "Playwright", "Alpine.js", "htmx", "Tailwind", "gunicorn", "uvicorn", "Grafana",
         "Prometheus", "Terraform", "Ansible", "Caddy", "SQLite", "MinIO"]
FILES = ["orders/views.py", "orders/models.py", "payments/mpesa.py", "menu/templates/menu.html", "static/css/site.css",
         "static/js/cart.js", "inventory/tasks.py", "inventory/models.py", "staff/rota.py", "reports/queries.py",
         "delivery/zones.py", "core/settings.py", "deploy/docker-compose.yml", ".github/workflows/ci.yml",
         "templates/base.html", "catering/forms.py", "sms/gateway.py", "tests/test_orders.py", "scripts/backup.sh",
         "nginx/site.conf"]
ASIDES = ["sawa", "poa", "eish", "aki", "si mbaya", "pole pole", "haha", "kwani", "tuko pamoja", "asante",
          "na kweli", "mambo ni mengi", "hakuna shida", "ni sawa"]
GREETINGS = ["Morning!", "Habari!", "Quick one.", "Back again.", "Sawa, next thing.", "Hey.", "Right.", "Mambo!",
             "Alright.", "Afternoon!", "Evening.", "One more thing.", "Hi again.", "Niaje!", "Ok.", "Hello.",
             "Good morning.", "Hey, you there?", "Sorry, me again.", "Two things.", "Update from my side.",
             "Back from lunch.", "Sasa!", "Small question.", "Need a hand."]


def poss(name: str) -> str:
    """ "Wanjiru Kamau's", "Kifaru Traders'"."""
    return name + ("'" if name.endswith("s") else "'s")


def plural(item: str) -> bool:
    """Whether an item name takes a plural verb: "eggs come", "charcoal comes", "LPG gas comes"."""
    return item.endswith("s") and not item.endswith(("ss", "gas", "us"))
