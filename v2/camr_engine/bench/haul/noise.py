"""The everyday noise of the project: chat with the assistant, decisions, code, logs, meeting notes, WhatsApp
chatter, course notes and documents that have nothing to do with anything.

The noise names people and things but never states one of their planted attributes, never mentions a payment fee,
a main colour (outside the CSS it shows) or a port, and never uses the words the never-said questions turn on. It
follows the project's phases, so day 20 talks about checkout and day 80 about payroll.
"""

from __future__ import annotations

import datetime as dt
import json
import random

from camr_engine.bench.haul import maths, page
from camr_engine.bench.haul.words import (AREAS, ASIDES, BRANCHES, COMPONENTS, CONDITIONS, DISHES, FILES, FIXES, GREETINGS,
                                     MONTHS, PAGES, ROADS, SYMPTOMS, TOOLS, TOWNS, WEEKDAYS, cap, say)
from camr_engine.bench.haul.world import World

# The project in phases: (first day, name, tasks, things to choose between, requests from Mama Njeri).
PHASES = [
    (1, "kickoff", ["set up the repo and CI", "pick a host for the site", "sketch the wireframes", "plan the photo shoot",
                    "collect the menu from all branches", "write the content plan", "register the domain",
                    "draft the sitemap", "set up the staging server", "agree on the design tokens"],
     [("Django", "FastAPI"), ("a VPS", "a managed platform"), ("Tailwind", "plain CSS"), ("Postgres", "SQLite")],
     ["a photo of every dish on the menu", "Swahili and English on every page", "the branch hours on the home page"]),
    (8, "menu site", ["build the menu grid", "add filters by branch", "optimise the dish photos", "write the menu JSON",
                      "add structured data for search", "make the menu work offline", "add dish detail pages",
                      "lazy-load the photos", "add a print view of the menu", "test the menu on cheap phones"],
     [("WebP", "AVIF"), ("server rendering", "a single-page app"), ("htmx", "Alpine.js"), ("one menu", "per-branch menus")],
     ["a 'today's special' banner", "allergen labels on every dish", "the photos to load fast on 3G"]),
    (16, "ordering", ["build the cart", "wire up M-Pesa STK push", "handle the payment callback", "send order SMS",
                      "show order status", "add guest checkout", "write the receipts", "stop double orders",
                      "test the checkout flow end to end", "handle failed payments"],
     [("a cart in the session", "a cart in the database"), ("polling", "webhooks"), ("Celery", "a cron job"),
      ("SMS", "WhatsApp messages")],
     ["customers to pay with M-Pesa only", "an SMS when the rider leaves", "orders to close at the last hour"]),
    (31, "back office", ["model the stock", "build the supplier list", "write purchase orders", "add stock alerts",
                         "import the stock sheet", "track waste", "reconcile deliveries", "add the stock-take screen",
                         "export stock to CSV", "show stock per branch"],
     [("a stock ledger", "a stock snapshot"), ("barcodes", "manual counts"), ("daily alerts", "live alerts")],
     ["to see stock for all branches on one screen", "a warning before the charcoal runs out",
      "the purchase orders printed for the drivers"]),
    (46, "delivery", ["draw the delivery zones", "assign riders", "estimate delivery times", "show the rider on a map",
                      "price delivery by distance", "batch nearby orders", "handle cash on delivery",
                      "build the rider app screen", "test with a real rider", "log delivery times"],
     [("our own riders", "a courier partner"), ("live tracking", "status updates"), ("zones", "distance pricing")],
     ["delivery to the estates near Karen", "the riders to see the next order early", "a delivery map in the shop"]),
    (61, "rebrand and catering", ["apply the new colour", "build the catering quote form", "price catering orders",
                                  "take catering deposits", "send catering confirmations", "build the events calendar",
                                  "make the catering menu", "add the tasting booking", "write the catering terms",
                                  "update the photos for the rebrand"],
     [("a quote form", "a WhatsApp chat"), ("fixed packages", "pick your own menu"), ("PDF quotes", "web quotes")],
     ["catering quotes within an hour", "photos from the last wedding on the catering page", "a deposit by M-Pesa"]),
    (76, "staff and payroll", ["build the rota", "track shift swaps", "export payroll", "add staff roles",
                               "set permissions per role", "record overtime", "send rota SMS", "handle leave requests",
                               "add the clock-in tablet", "keep a log of who changed what"],
     [("weekly rotas", "monthly rotas"), ("a clock-in tablet", "phone clock-in"), ("roles", "per-user permissions")],
     ["the rota on the staff WhatsApp every Sunday", "overtime shown separately", "nobody seeing salaries but her"]),
    (91, "reports and speed", ["build the sales dashboard", "add daily reports", "speed up the menu page",
                               "add caching", "run a load test", "check the backups restore", "tune the database",
                               "cut the page weight", "add uptime alerts", "write the runbook"],
     [("Grafana", "a page of our own"), ("nightly reports", "live numbers"), ("more servers", "more caching")],
     ["a report of sales per dish every Monday", "to know at once when the site is down", "the site to feel instant"]),
    (106, "launch", ["run the bug bash", "freeze the features", "write the launch checklist", "switch the DNS",
                     "brief the staff", "watch the first orders", "fix the last bugs", "announce the launch",
                     "train the branch managers", "plan the week after launch"],
     [("a soft launch", "a big launch"), ("launch on a Monday", "launch on a Friday")],
     ["a launch party at Westlands", "every branch ready on the same day", "a discount for the first week"]),
]

CAUSES = ["a race between two requests", "the cache serving an old copy", "a missing index", "a timezone mix-up",
          "the phone number format", "a retry that isn't idempotent", "an unhandled empty list", "a stale session",
          "the image being twice the size it needs to be", "a slow query in a loop", "the callback arriving before "
          "the order is saved", "rounding in floats instead of cents", "a template that escapes twice",
          "the worker running out of memory", "a missing migration on staging", "the CSV having a BOM",
          "two tabs sharing one session", "the clock on the tablet being wrong", "a signal firing twice",
          "a form posting to the old URL", "an N+1 query in the template", "the font blocking the first paint"]
CONSEQUENCES = ["the second request wins", "customers see the old value for a few minutes", "the page takes seconds "
                "to load", "Monday's report is off by a day", "the SMS never goes out", "the order is charged twice",
                "the view crashes instead of showing an empty state", "people get logged out", "the menu feels slow",
                "the database does the same work a hundred times", "the totals drift by a shilling",
                "the browser shows raw HTML", "the job dies halfway", "the import skips the first column",
                "the rider sees the wrong address", "the stock goes negative", "the receipt prints twice"]
BENEFITS = ["it retries for us", "it keeps the logic in one place", "it is easy to test", "it fails loudly",
            "nobody has to remember to run it", "it works on bad networks", "it costs nothing at our size",
            "the staff can see what happened", "we can roll it back in a minute", "it is boring, which is good",
            "a new developer can read it in an afternoon", "it keeps working when the power flickers"]
CLOSERS = ["Want me to write the test for it too?", "Shall I open a branch for this?", "I can do the migration next.",
           "Try it on staging first.", "Tell me what the logs say after.", "Ping me if the numbers still look off.",
           "That should hold up for the lunch rush.", "Let me know when Mama Njeri has seen it.",
           "We can tidy the naming later.", "Run the tests before you push.", "If it still fails, send me the "
           "traceback.", "Happy to pair on it after lunch.", ""]
OPENERS = ["Good question.", "Let's fix that.", "Two likely causes here.", "Here's what I'd do.", "Short answer: yes.",
           "That one bites everyone.", "Easy to miss.", "I'd go the simple way.", "Makes sense.", "Right, so.",
           "I looked at it.", "This is a classic.", "Agreed, it's worth doing now.", "Let's not overthink it.",
           "Yes, and it's quicker than it sounds.", "Not quite what I'd expect, so let's look closer.",
           "Okay, step by step.", "I think I see it.", "Fair point."]
EXPLAIN = [
    "The usual cause is {cause}, which means {cons}.", "If that happens {k}, {cons}.",
    "{Tool} is a good fit here because {ben}.", "I'd {fix} and leave the rest alone.", "The fix is small: {fix}.",
    "Before anything else, check whether {cause} is the issue.", "We can {t} later; it doesn't block this.",
    "Keep {comp} [dumb|thin|simple] and put the logic in [one function|a helper in {file}|the model].", "Write it so it can run twice without harm, because "
    "otherwise {cons}.", "{Comp} should not know about payments at all.", "[Log the input|Print the payload|Save a copy of the request] before you change anything[, so we can compare|, otherwise we are guessing|].",
    "On our traffic this is fine; it only matters past [a few hundred|a thousand|five hundred] orders [an hour|a day at one branch].",
    "I checked {file}: the logic there assumes one branch, which is why {comp} {s} {k}.",
    "There are two ways to do it: {fix}, or {fix2}. The first is simpler and {ben}.",
    "My guess is {cause}; the giveaway is that it only happens {k}.", "Don't patch {comp} directly; {fix} instead.",
    "We had the same shape of bug with {comp2} last week, and we fixed it when we decided to {fix}.",
    "Test it {k}, because that is exactly when {cons}.", "{Tool} gives us this for free if we {fix}.",
    "It is not {cause}: I ruled that out by reading the logs from {w}.",
    "[Put a comment on it saying why|Leave a note in {file} explaining it|Write the reason in the commit], or someone will undo it [in a month|by accident|during the next refactor].",
    "The quickest check is to open {file} and see whether we {fix}.",
    "Once {comp} is fixed, {comp2} gets faster too, since they share the query.",
    "Mama Njeri won't see any of this; she'll just notice that {comp} stops misbehaving.",
]
CONCEPTS = {
    "idempotency": ["An idempotent job gives the same result however many times it runs.",
                    "M-Pesa can send the same callback twice, so the handler must check whether it has seen it.",
                    "The usual trick is a unique key per payment and an insert that ignores duplicates.",
                    "Retries are only safe once the work is idempotent."],
    "caching": ["A cache keeps a computed answer so the next request skips the work.",
                "The hard part is knowing when the cached copy is stale.", "For the menu, a few minutes of staleness "
                "is fine; for stock levels it is not.", "Cache by key, and delete the key when the data changes."],
    "indexes": ["An index lets the database find rows without reading the whole table.", "Every index costs a little "
                "on every insert.", "Index the columns you filter and sort by, not every column.",
                "EXPLAIN ANALYZE tells you whether the index is used."],
    "transactions": ["A transaction makes several changes happen together or not at all.", "Taking stock and "
                     "creating the order belong in one transaction.", "Keep transactions short; long ones block "
                     "other writers.", "Row locks stop two cashiers selling the last plate twice."],
    "webhooks": ["A webhook is the other system calling us when something happens.", "We must answer quickly and do "
                 "the slow work in the background.", "Always verify where a webhook came from.",
                 "Store the raw body first, so we can replay it if our code fails."],
    "responsive images": ["Send each phone the smallest image that still looks sharp on it.", "srcset lets the "
                          "browser choose between widths.", "WebP is usually a third smaller than JPEG.",
                          "Always set width and height so the page doesn't jump."],
    "accessibility": ["Screen readers read the alt text instead of the image.", "Buttons need text, not just icons.",
                      "Colour contrast matters in bright sunlight too.", "Every form field needs a label."],
    "migrations": ["A migration changes the database schema in a recorded, repeatable way.", "Run migrations on "
                   "staging before production.", "Adding a column with a default can lock a big table.",
                   "Never edit a migration that already ran in production."],
    "rate limiting": ["A rate limit caps how many requests one client can make.", "It protects the SMS budget from "
                      "a stuck loop.", "Return a clear error, not a silent failure.",
                      "Limit by user and by IP, not just one."],
}


class Noise:
    """Noise for the days of one script, drawn from its own random stream."""

    def __init__(self, rng: random.Random, world: World, dates: list[dt.date]):
        self.rng = rng
        self.world = world
        self.dates = dates
        self.names = world.noise_names()
        self.lesson_family = 0

    # -- helpers -------------------------------------------------------------------------------------------------
    def phase(self, day: int):
        return [p for p in PHASES if p[0] <= day][-1]

    def name(self) -> str:
        return self.rng.choice(self.names)

    def aside(self, text: str, end: bool = False) -> str:
        """Now and then a Swahili aside, or (at the end of a line only) a missing full stop."""
        r = self.rng.random()
        if r < 0.12 and text.endswith("."):
            return text[:-1] + ", " + self.rng.choice(ASIDES) + "."
        if r < 0.2 and end and text.endswith("."):
            return text[:-1]
        return text

    def greeting(self) -> str:
        return self.rng.choice(GREETINGS) if self.rng.random() < 0.6 else ""

    def slots(self, day: int) -> dict:
        rng = self.rng
        return dict(cause=CAUSES, cons=CONSEQUENCES, k=CONDITIONS, tool=TOOLS, Tool=TOOLS, ben=BENEFITS, fix=FIXES,
                    fix2=FIXES, t=self.phase(day)[2], comp=COMPONENTS, comp2=COMPONENTS,
                    Comp=lambda: cap(rng.choice(COMPONENTS)), file=FILES, s=SYMPTOMS,
                    w=["this morning", "last night", "yesterday", "the weekend"])

    def sentence(self, day: int) -> str:
        """One line of project chatter that tells nothing."""
        rng = self.rng
        _, _, tasks, options, requests = self.phase(day)
        return cap(say(rng, rng.choice([
            "{n} [said|thinks|reckons] {c} {s} {k}.", "[Still|Also] need to {t}.", "{n} [is|was] [busy trying to|"
            "working out how to|about to] {t2} [today|this morning|this afternoon].", "[Power cut|Blackout|Internet "
            "down] at {b} for [an hour|twenty minutes|most of the morning], [the generator kicked in|we worked off "
            "phones|sigh].", "Traffic on {r} was [terrible|mad|fine for once].", "Mama Njeri wants {q}.",
            "[Lunch was|We tested] {d} [today|for the staff], [really good|a bit salty|gone in ten minutes].",
            "[We should|Let's] {t} [before Friday|this week|after the rush].", "{n} and {n2} [covered|ran] the "
            "[lunch|evening] rush at {b}.", "[Rain|Heavy rain|Sun] all day in {a}, [orders went up|deliveries were "
            "slow|quiet afternoon].", "{c} [is fine now|looks better|still needs a look].", "[Note to self|Reminder]: "
            "{t}.", "{n} [brought|made] {d} for everyone[, asante|].", "The {b} team [hit|missed] their target "
            "[yesterday|on {w}].", "[Got|Had] a call from a customer in {a} about {d}.", "{n} is [off sick|on leave|"
            "travelling] [today|until {w}].", "The matatu strike on {r} [made everyone late|is over].",
            "[Spent the morning|Wasted an hour] on {c}.", "{n} [fixed|found] the [problem|bug] with {c}."]),
            n=self.name, n2=self.name, c=COMPONENTS, s=SYMPTOMS, k=CONDITIONS, t=tasks, t2=tasks, b=BRANCHES,
            r=ROADS, q=requests, d=DISHES, a=AREAS, w=WEEKDAYS[:5]))

    def sentences(self, day: int, k: int) -> str:
        return " ".join(self.aside(self.sentence(day)) for _ in range(k))

    def long_date(self, day: int) -> str:
        d = self.dates[day - 1]
        return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"

    # -- planted statements get a natural home ---------------------------------------------------------------------
    def host(self, day: int, statement: str, genre: str | None = None) -> list[tuple[str, str, str]]:
        """A planted statement inside an ordinary message, notes or notice. Returns (kind, role, text) events."""
        rng = self.rng
        genre = genre or rng.choice(["chat", "chat", "chat", "chat", "meeting", "meeting", "whatsapp", "notice"])
        if genre == "chat":
            ask = self.ask(day) if rng.random() < 0.7 else ""
            parts = [self.greeting(), self.sentences(day, rng.randrange(0, 3)), statement,
                     self.sentences(day, rng.randrange(0, 2)), ask]
            out = [("chat", "user", " ".join(x for x in parts if x))]
            if ask or rng.random() < 0.5:
                out.append(("chat", "assistant", self.reply(day, short=not ask)))
            return out
        if genre == "meeting":
            return [self.meeting(day, planted=statement)]
        if genre == "whatsapp":
            lines = [f"{self.name()}: {self.aside(self.sentence(day), end=True)}" for _ in range(rng.randrange(3, 9))]
            lines.insert(rng.randrange(len(lines) + 1), f"{rng.choice(['Mama Njeri', self.name()])}: {statement}")
            head = say(rng, "[Forwarding from the kitchen WhatsApp group:|From the staff group chat today:|Pasted from "
                            "WhatsApp:|Kitchen group, this morning:]")
            return [("chat", "user", head + "\n" + "\n".join(lines))]
        head = say(rng, "[Notice from Mama Njeri|Memo to all branches|Admin note|For the record|Office update]")
        body = " ".join([self.sentences(day, rng.randrange(1, 4)), statement, self.sentences(day, rng.randrange(1, 3))])
        return [("doc", "user", f"{head}, {self.long_date(day)}:\n{body}")]

    # -- chat ----------------------------------------------------------------------------------------------------
    def ask(self, day: int) -> str:
        rng = self.rng
        _, _, tasks, options, requests = self.phase(day)
        a, b = rng.choice(options)
        return cap(say(rng, rng.choice([
            "[How do I|What's the cleanest way to|Can you help me] {t}[?| without breaking {c}?]",
            "{C} {s} {k}. [Any idea why?|Where do I even start?|Thoughts?|Help.]",
            "[Should we|Do we] go with {a} or {b} for this?", "I pushed the change to {f} [but|and now] {c} {s}.",
            "Mama Njeri wants {q}. [Doable this week?|How long would that take?|Can we fit it in?]",
            "[Reviewing|Looking at] {f}: why do we {fix} there?", "{n} [asked|wants to know] if we can {t}.",
            "[Next up|Today's job]: {t}. [Where would you start?|Any traps?|What's the plan?]",
            "Can you explain {concept} [like I'm new to it|in plain words|quickly]?",
            "[Is it worth it to|Would it help to] {fix} [in|for] {f}?", "Getting this when I {t}: {err}. [What does it "
            "mean?|Ideas?]", "What would you test first if {c} {s}?"]),
            t=tasks, c=COMPONENTS, C=lambda: cap(rng.choice(COMPONENTS)), s=SYMPTOMS, k=CONDITIONS, a=a, b=b, f=FILES,
            q=requests, fix=FIXES, n=self.name, concept=list(CONCEPTS),
            err=lambda: rng.choice(["KeyError: 'branch'", "IntegrityError: duplicate key value", "TimeoutError: read "
                                    "timed out", "TypeError: 'NoneType' object is not subscriptable", "502 Bad Gateway",
                                    "CSRF verification failed", "ValueError: invalid literal for int()"])))

    def reply(self, day: int, short: bool = False) -> str:
        rng = self.rng
        _, _, tasks, _, _ = self.phase(day)
        slots = self.slots(day)
        if short:
            return say(rng, "[Noted.|Got it.|Okay, noted.|Thanks, I'll keep that in mind.|Sawa.]") + " " + \
                say(rng, rng.choice(EXPLAIN), **slots)
        parts = [rng.choice(OPENERS)]
        parts += [say(rng, t, **slots) for t in rng.sample(EXPLAIN, rng.randrange(2, 5))]
        text = " ".join(parts)
        if rng.random() < 0.6:
            steps = rng.sample(FIXES + tasks, rng.randrange(3, 6))
            text += "\n\n" + "\n".join(f"{i}. {cap(s)}." for i, s in enumerate(steps, 1))
        if rng.random() < 0.45:
            text += "\n\n" + self.code_block(day)
        closer = rng.choice(CLOSERS)
        return text + ("\n\n" + closer if closer else "")

    def chat(self, day: int) -> list[tuple[str, str, str]]:
        rng = self.rng
        out = []
        for turn in range(rng.choice([1, 1, 1, 2, 2, 3])):
            if turn == 0:
                user = " ".join(x for x in [self.greeting(), self.sentences(day, rng.randrange(0, 2)),
                                            self.aside(self.ask(day), end=True)] if x)
            else:
                user = self.aside(say(rng, "[Ok.|Thanks.|Done.|Tried it.|That worked.|Still stuck.] {q}",
                                      q=lambda: self.ask(day)), end=True)
            concept = next((c for c in CONCEPTS if c in user), None)
            if concept:
                facts = rng.sample(CONCEPTS[concept], rng.randrange(2, 5))
                reply = " ".join([rng.choice(OPENERS)] + facts + [say(rng, rng.choice(EXPLAIN), **self.slots(day))])
            else:
                reply = self.reply(day)
            out += [("chat", "user", user), ("chat", "assistant", reply)]
        return out

    def decision(self, day: int) -> list[tuple[str, str, str]]:
        rng = self.rng
        _, phase, tasks, options, _ = self.phase(day)
        a, b = rng.choice(options)
        if rng.random() < 0.5:
            a, b = b, a
        text = say(rng, "[Decision|Decided|We're going with this|Settled]: {a}[ for the {p} work|], not {b}. [Why|Reason]: "
                        "{ben}[, and {ben2}|]. [Revisit|We can revisit] [after launch|if it hurts|in a month]. "
                        "[{n} and Mama Njeri agreed.|Logged in the decisions file.|]", a=a, b=b, p=phase, ben=BENEFITS,
                   ben2=BENEFITS, n=self.name)
        return [("decision", "user", text)]

    # -- code ----------------------------------------------------------------------------------------------------
    VERBS = ["fetch", "sync", "build", "load", "save", "format", "parse", "count", "group", "merge", "send", "mark",
             "check", "clean", "split", "rank", "list", "export", "import", "refresh", "queue", "archive", "flag"]
    NOUNS = ["orders", "menu_items", "stock_levels", "riders", "receipts", "suppliers", "shifts", "branches",
             "photos", "reviews", "deliveries", "invoices", "events", "bookings", "alerts", "reports", "carts",
             "customers", "batches", "waste_entries", "purchase_orders", "zones", "tables"]
    FIELDS = ["branch", "created_at", "status", "total_cents", "rider_id", "supplier_id", "qty", "unit", "note",
              "updated_at", "code", "name", "phone", "area", "paid", "due_on", "shift", "role", "week"]

    def ident(self) -> str:
        return f"{self.rng.choice(self.VERBS)}_{self.rng.choice(self.NOUNS)}"

    def code_block(self, day: int) -> str:
        r = self.rng.random()
        if r < 0.5:
            return "```python\n" + self.python(day) + "```"
        if r < 0.62:
            return "```js\n" + self.js() + "```"
        if r < 0.74:
            return "```css\n" + self.css(day) + "```"
        if r < 0.86:
            return "```sql\n" + self.sql() + "```"
        if r < 0.94:
            return "```yaml\n" + self.yaml() + "```"
        return "```bash\n" + self.shell() + "```"

    def python(self, day: int) -> str:
        rng = self.rng
        noun = rng.choice(self.NOUNS)
        one = noun[:-1] if noun.endswith("s") else noun
        model = "".join(w.title() for w in one.split("_"))
        f1, f2, f3 = rng.sample(self.FIELDS, 3)
        fn = self.ident()
        kind = rng.randrange(8)
        if kind == 0:
            code = (f"def {fn}(rows, {f1}=None):\n    \"\"\"{cap(fn.replace('_', ' '))} for the {rng.choice(PAGES)}.\"\"\"\n"
                    f"    out = []\n    for row in rows:\n        if {f1} is not None and row.{f1} != {f1}:\n"
                    f"            continue\n        out.append({{'id': row.id, '{f2}': row.{f2}}})\n"
                    f"    return sorted(out, key=lambda r: r['{f2}'])\n")
        elif kind == 1:
            code = (f"class {model}(models.Model):\n    {f1} = models.CharField(max_length={rng.choice([20, 40, 80, 120])})\n"
                    f"    {f2} = models.{rng.choice(['IntegerField()', 'DateTimeField(auto_now_add=True)', 'BooleanField(default=False)'])}\n"
                    f"    {f3} = models.ForeignKey('{rng.choice(['Branch', 'Supplier', 'Rider', 'Customer'])}', "
                    f"on_delete=models.PROTECT)\n\n    class Meta:\n        ordering = ['-{f2}']\n"
                    f"        indexes = [models.Index(fields=['{f1}', '{f2}'])]\n\n    def __str__(self):\n"
                    f"        return f\"{{self.{f1}}} ({{self.pk}})\"\n")
        elif kind == 2:
            code = (f"@shared_task(bind=True, max_retries={rng.randrange(2, 6)}, default_retry_delay={rng.choice([10, 30, 60])})\n"
                    f"def {fn}(self, {one}_id):\n    {one} = {model}.objects.get(pk={one}_id)\n"
                    f"    try:\n        gateway.{rng.choice(['send', 'push', 'notify'])}({one}.{f1}, "
                    f"template='{rng.choice(['ready', 'late', 'paid', 'reminder'])}')\n"
                    f"    except GatewayTimeout as exc:\n        raise self.retry(exc=exc)\n"
                    f"    {one}.{f2} = timezone.now()\n    {one}.save(update_fields=['{f2}'])\n")
        elif kind == 3:
            code = (f"def test_{fn}_{rng.choice(['handles_empty', 'keeps_order', 'skips_closed', 'is_idempotent'])}(client, db):\n"
                    f"    make_{one}({f1}={rng.randrange(1, 99)})\n    res = client.get('/api/{noun}?{f1}={rng.randrange(1, 99)}')\n"
                    f"    assert res.status_code == {rng.choice([200, 200, 404])}\n"
                    f"    assert len(res.json()) == {rng.randrange(0, 4)}\n")
        elif kind == 4:
            code = (f"@login_required\ndef {one}_list(request):\n    qs = {model}.objects.filter(branch=request.user.branch)\n"
                    f"    if request.GET.get('{f1}'):\n        qs = qs.filter({f1}=request.GET['{f1}'])\n"
                    f"    page = Paginator(qs.order_by('-{f2}'), {rng.choice([20, 25, 50])}).get_page(request.GET.get('page'))\n"
                    f"    return render(request, '{noun}/list.html', {{'page': page}})\n")
        elif kind == 5:
            code = (f"def {fn}(path):\n    \"\"\"Read the {noun.replace('_', ' ')} sheet the branches send on "
                    f"{rng.choice(WEEKDAYS[:5])}s.\"\"\"\n    with open(path, newline='', encoding='utf-8-sig') as fh:\n"
                    f"        rows = list(csv.DictReader(fh))\n    bad = [r for r in rows if not r.get('{f1}')]\n"
                    f"    if bad:\n        log.warning('%d rows without {f1}', len(bad))\n"
                    f"    return [r for r in rows if r.get('{f1}')]\n")
        elif kind == 6:
            code = (f"def {fn}(items):\n    totals = defaultdict(int)\n    for it in items:\n"
                    f"        totals[it['{f1}']] += it.get('{f2}', 0)\n"
                    f"    return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:{rng.choice([5, 10, 20])}])\n")
        else:
            code = (f"class {''.join(w.title() for w in fn.split('_'))}(BaseCommand):\n    help = '{cap(fn.replace('_', ' '))} "
                    f"for every branch'\n\n    def handle(self, *args, **opts):\n        for branch in Branch.objects.all():\n"
                    f"            n = {fn}(branch)\n            self.stdout.write(f'{{branch.name}}: {{n}}')\n")
        if day >= _plant_day("kitchen") and rng.random() < 0.15:
            code += "\n\ndef line_total(code, qty):\n    return add_vat(price_cents(code) * qty)\n"
        elif day >= _plant_day("money") and rng.random() < 0.1:
            code += "\n\ndef label(cents):\n    return cents_to_kes(cents)\n"
        return code

    def js(self) -> str:
        rng = self.rng
        name = "".join(w.title() if i else w for i, w in enumerate(self.ident().split("_")))
        sel = rng.choice(["#cart", ".menu-grid", "#branch-select", ".order-status", "#search", ".rider-map"])
        if rng.random() < 0.5:
            return (f"export async function {name}(el = document.querySelector('{sel}')) {{\n"
                    f"  const res = await fetch('/api/{rng.choice(self.NOUNS)}?limit={rng.choice([10, 20, 50])}');\n"
                    f"  if (!res.ok) {{ el.dataset.state = 'error'; return; }}\n  const rows = await res.json();\n"
                    f"  el.innerHTML = rows.map(r => `<li data-id=\"${{r.id}}\">${{r.name}}</li>`).join('');\n"
                    f"  el.dataset.state = rows.length ? 'ready' : 'empty';\n}}\n")
        return (f"document.querySelector('{sel}').addEventListener('{rng.choice(['input', 'change', 'click'])}', "
                f"debounce(async (ev) => {{\n  const q = ev.target.value?.trim() ?? '';\n"
                f"  const res = await fetch(`/api/{rng.choice(self.NOUNS)}?q=${{encodeURIComponent(q)}}`);\n"
                f"  render(await res.json());\n}}, {rng.choice([150, 250, 300, 400])}));\n")

    def css(self, day: int) -> str:
        rng = self.rng
        main = page.NEW_COLOUR if day >= page.CHANGE_DAY else page.OLD_COLOUR
        if day < page.DESIGN_DAY:
            main = rng.choice(["#2255CC", "#1E40AF"])
        sel = rng.choice([".menu-card", ".cart-drawer", ".order-status", ".branch-list li", ".btn-primary",
                          ".hero", ".price-tag", ".rider-badge", ".catering-form", ".site-nav a", ".dish-photo",
                          ".footer-links", ".stock-table td"])
        sp = rng.choice([4, 8, 16, 24, 32])
        return (f"{sel} {{\n  color: {rng.choice([main, page.TEXT_COLOUR])};\n"
                f"  padding: {sp}px {rng.choice([8, 16, 24])}px;\n  border-radius: {rng.choice([4, 6, 8, 12])}px;\n"
                f"  {rng.choice(['background: ' + main, 'border: 1px solid ' + main, 'background: ' + page.SURFACE])};\n}}\n"
                f"{sel}:hover {{ opacity: .{rng.choice([8, 85, 9])}; }}\n"
                + (f"@media (max-width: {rng.choice([480, 600, 768])}px) {{\n  {sel} {{ padding: {rng.choice([4, 8])}px; }}\n}}\n"
                   if rng.random() < 0.5 else ""))

    def sql(self) -> str:
        rng = self.rng
        t = rng.choice(self.NOUNS)
        if rng.random() < 0.5:
            cols = rng.sample(self.FIELDS, rng.randrange(3, 6))
            return (f"CREATE TABLE {t} (\n  id bigserial PRIMARY KEY,\n" +
                    ",\n".join(f"  {c} {rng.choice(['text', 'integer', 'timestamptz', 'bigint'])}" for c in cols) +
                    "\n);\n" + f"CREATE INDEX {t}_{cols[0]}_idx ON {t} ({cols[0]});\n")
        return (f"SELECT branch, count(*) AS n, sum(total_cents) AS cents\nFROM {t}\n"
                f"WHERE created_at >= now() - interval '{rng.randrange(1, 30)} days'\nGROUP BY branch\n"
                f"ORDER BY cents DESC\nLIMIT {rng.choice([5, 10, 20])};\n")

    def yaml(self) -> str:
        rng = self.rng
        return (f"name: {rng.choice(['ci', 'tests', 'lint', 'nightly'])}\non:\n  push:\n    branches: [\"*\"]\njobs:\n"
                f"  test:\n    runs-on: ${{{{ vars.RUNNER }}}}\n    steps:\n      - uses: actions/checkout@main\n"
                f"      - run: pip install -r requirements.txt\n      - run: pytest -q -k \"{self.ident()}\"\n")

    def shell(self) -> str:
        rng = self.rng
        return (f"#!/usr/bin/env bash\nset -euo pipefail\ncd /srv/app\ngit pull --ff-only\n"
                f"python manage.py {rng.choice(['migrate', 'collectstatic --noinput', 'check --deploy'])}\n"
                f"sudo systemctl restart {rng.choice(['mnk-web', 'mnk-worker', 'mnk-beat'])}\n"
                f"echo \"deployed $(git rev-parse --short HEAD) at $(date +%H:%M)\"\n")

    def code(self, day: int) -> list[tuple[str, str, str]]:
        rng = self.rng
        lead = say(rng, "[Here's the {w}.|Pushed this {w} to {f}.|Draft {w} for {f}, have a look:|Refactored the {w}:|"
                        "The {w} from this morning's work on {f}:]",
                   w=["helper", "view", "query", "component", "test", "style", "migration", "job"], f=FILES)
        blocks = "\n\n".join(self.code_block(day) for _ in range(rng.randrange(1, 4)))
        tail = "" if rng.random() < 0.5 else "\n\n" + say(rng, rng.choice(EXPLAIN), **self.slots(day))
        return [("code", rng.choice(["assistant", "assistant", "user"]), lead + "\n\n" + blocks + tail)]

    # -- logs ----------------------------------------------------------------------------------------------------
    def stamp(self, day: int) -> dt.datetime:
        d = self.dates[day - 1]
        return dt.datetime(d.year, d.month, d.day, self.rng.randrange(6, 23), self.rng.randrange(60),
                           self.rng.randrange(60))

    def log(self, day: int) -> list[tuple[str, str, str]]:
        rng = self.rng
        kind = rng.choice(["access", "app", "app", "ci", "mpesa", "cron", "docker", "sentry"])
        t = self.stamp(day)
        lines = []
        if kind == "access":
            paths = ["/", "/menu", "/menu?branch=" + rng.choice(BRANCHES).lower().replace(" ", "-"), "/catering",
                     "/api/orders", "/api/orders/" + str(rng.randrange(1000, 99999)), "/static/img/" +
                     rng.choice(DISHES).replace(" ", "-") + "-800.webp", "/api/menu.json", "/contact", "/cart",
                     "/checkout", "/sitemap.xml", "/robots.txt", "/api/stock?branch=" + rng.choice(BRANCHES)[:3].lower()]
            uas = ["Mozilla/5.0 (Linux; Android 13; TECNO KI5q)", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5)",
                   "Mozilla/5.0 (Linux; Android 12; Infinix X6816)", "Googlebot/2.1", "curl/8.4.0",
                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "UptimeRobot/2.0"]
            for _ in range(rng.randrange(10, 28)):
                t += dt.timedelta(seconds=rng.randrange(1, 90))
                ip = f"{rng.choice([41, 102, 105, 154, 196, 197])}.{rng.randrange(256)}.{rng.randrange(256)}." \
                     f"{rng.randrange(1, 255)}"
                status = rng.choice([200] * 12 + [304, 301, 404, 499, 500, 502])
                lines.append(f'{ip} - - [{t:%d/%b/%Y:%H:%M:%S} +0300] "{rng.choice(["GET"] * 6 + ["POST"])} '
                             f'{rng.choice(paths)} HTTP/1.1" {status} {rng.randrange(200, 90000)} "-" '
                             f'"{rng.choice(uas)}"')
            head = "nginx access log, " + rng.choice(["production", "staging"])
        elif kind == "app":
            mods = ["orders.api", "payments.mpesa", "inventory.tasks", "sms.gateway", "menu.views", "staff.rota",
                    "delivery.zones", "reports.daily", "core.auth"]
            for _ in range(rng.randrange(8, 26)):
                t += dt.timedelta(milliseconds=rng.randrange(5, 40000))
                lvl = rng.choice(["INFO"] * 8 + ["WARNING", "WARNING", "ERROR", "DEBUG"])
                msg = say(rng, rng.choice([
                    "order {b}-{n} created items={i} total_cents={c}", "stock for {d} at {br} below alert level",
                    "sms queued to 2547******{m} template={tp}", "callback for checkout ws_CO_{n}{n2} result={r}",
                    "rota published for week {w}", "cache miss key=menu:{br2} rebuilt in {ms} ms",
                    "slow query {ms} ms: SELECT ... FROM {tb}", "login ok user={u}", "retrying job {j} attempt {a}",
                    "rider {n3} picked up {b}-{n}", "report {rp} written rows={i}"]),
                    b=["WL", "KL", "KR", "LV", "PK"], n=lambda: f"{rng.randrange(100000):06d}",
                    i=lambda: rng.randrange(1, 9), c=lambda: rng.randrange(5, 900) * 100, d=DISHES, br=BRANCHES,
                    m=lambda: f"{rng.randrange(100):02d}", tp=["order_ready", "rider_left", "otp", "rota"],
                    n2=lambda: rng.randrange(10 ** 6), r=["0", "0", "0", "1032", "1037", "2001"],
                    w=lambda: rng.randrange(1, 23), br2=lambda: rng.choice(BRANCHES).lower(),
                    ms=lambda: rng.randrange(3, 4000), tb=self.NOUNS,
                    u=lambda: rng.choice(self.names).split()[0].lower(), j=self.ident, a=lambda: rng.randrange(1, 5),
                    n3=lambda: rng.randrange(1, 40), rp=["daily_sales", "stock", "waste", "riders"])
                lines.append(f"{t:%Y-%m-%d %H:%M:%S},{rng.randrange(1000):03d} {lvl:<7} {rng.choice(mods):<16} {msg}")
                if lvl == "ERROR" and rng.random() < 0.5:
                    f = rng.choice(FILES)
                    lines += ["Traceback (most recent call last):", f'  File "/srv/app/{f}", line '
                              f'{rng.randrange(10, 400)}, in {self.ident()}', f"    {self.ident()}(row)",
                              f"{rng.choice(['KeyError', 'ValueError', 'TimeoutError', 'IntegrityError'])}: "
                              f"{rng.choice(['branch', 'qty', 'duplicate key', 'read timed out', 'code'])}"]
            head = "app log"
        elif kind == "ci":
            tests = [f"tests/test_{rng.choice(self.NOUNS)}.py::test_{self.ident()}" for _ in range(rng.randrange(6, 18))]
            lines = [f"$ pytest -q {rng.choice(['', '-x', '-k ' + self.ident()])}".rstrip()]
            for tname in tests:
                lines.append(f"{tname} {rng.choice(['PASSED'] * 9 + ['FAILED', 'SKIPPED'])}")
            lines.append(f"==== {len(tests) - 1} passed, 1 skipped in {rng.randrange(2, 90)}.{rng.randrange(10)}s ====")
            head = "CI run"
        elif kind == "mpesa":
            for _ in range(rng.randrange(2, 4)):
                body = {"Body": {"stkCallback": {
                    "MerchantRequestID": f"{rng.randrange(10000, 99999)}-{rng.randrange(10 ** 7, 10 ** 8)}-1",
                    "CheckoutRequestID": f"ws_CO_{t:%d%m%Y%H%M%S}{rng.randrange(10 ** 5, 10 ** 6)}",
                    "ResultCode": rng.choice([0, 0, 0, 1032]), "ResultDesc": "The service request is processed "
                    "successfully.", "CallbackMetadata": {"Item": [
                        {"Name": "Amount", "Value": rng.randrange(100, 9000)},
                        {"Name": "MpesaReceiptNumber", "Value": "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789")
                                                                        for _ in range(10))},
                        {"Name": "PhoneNumber", "Value": "2547******" + f"{rng.randrange(100):02d}"}]}}}}
                lines.append(json.dumps(body))
                t += dt.timedelta(seconds=rng.randrange(5, 600))
            head = "M-Pesa callbacks (phones masked)"
        elif kind == "cron":
            for job in rng.sample(["backup_db", "stock_report", "send_rota", "prune_sessions", "rebuild_sitemap",
                                   "resize_photos", "reconcile_mpesa", "daily_sales"], rng.randrange(3, 7)):
                t += dt.timedelta(minutes=rng.randrange(1, 50))
                lines.append(f"{t:%b %d %H:%M:%S} mnk-prod CRON[{rng.randrange(1000, 40000)}]: "
                             f"({rng.choice(['app', 'root'])}) CMD (/srv/app/bin/{job})")
                lines.append(f"{t:%b %d %H:%M:%S} mnk-prod {job}[{rng.randrange(1000, 40000)}]: done in "
                             f"{rng.randrange(1, 300)}s, {rng.randrange(0, 5000)} rows")
            head = "cron"
        elif kind == "sentry":
            for _ in range(rng.randrange(3, 8)):
                lines.append(say(rng, "- {e} in {f} ({n} events, {u} users, last seen {h}h ago)", e=[
                    "KeyError: 'branch'", "IntegrityError", "TimeoutError", "ValueError: bad qty",
                    "TypeError: NoneType", "PermissionDenied"], f=FILES, n=lambda: rng.randrange(1, 400),
                    u=lambda: rng.randrange(1, 60), h=lambda: rng.randrange(1, 48)))
            head = "Sentry digest"
        else:
            for _ in range(rng.randrange(8, 24)):
                t += dt.timedelta(seconds=rng.randrange(1, 300))
                svc = rng.choice(["web-1", "worker-1", "worker-2", "redis-1", "db-1", "beat-1"])
                lines.append(f"{svc}  | {t:%Y-%m-%dT%H:%M:%S}Z " + say(rng, rng.choice([
                    "[INFO] Booting worker with pid: {p}", "Ready to accept connections", "[INFO] Task {j}[{h}] "
                    "succeeded in {s}s", "checkpoint complete: wrote {p} buffers", "[WARNING] Worker exceeded memory "
                    "soft limit", "GET /metrics 200", "[INFO] Received task: {j}[{h}]"]),
                    p=lambda: rng.randrange(10, 9000), j=self.ident, h=lambda: f"{rng.randrange(16 ** 8):08x}",
                    s=lambda: f"{rng.random() * 3:.3f}"))
            head = "docker compose logs"
        lead = say(self.rng, "[{h}:|Here's the {h} from {w}:|{h}, pasted:|{h} ({w})|Can you look at this {h}?]",
                   h=head, w=["this morning", "last night", "just now", "after the deploy", "the lunch rush"])
        return [("log", "tool", lead + "\n" + "\n".join(lines))]

    # -- meetings, chat groups and documents ---------------------------------------------------------------------
    def meeting(self, day: int, planted: str | None = None) -> tuple[str, str, str]:
        rng = self.rng
        _, phase, tasks, options, requests = self.phase(day)
        title = say(rng, "[Standup|Weekly ops meeting|Kitchen briefing|Branch managers' call|Catering planning|"
                         "Tech sync|Monday planning|Friday wrap-up]")
        people = list(dict.fromkeys(self.name() for _ in range(rng.randrange(3, 7))))
        a, b = rng.choice(options)
        templates = rng.sample([
            "{n} [is going to|will|plans to] {t}, then {t2}.", "{n} [flagged|raised] that {c} {s} {k}.",
            "Agreed to {t} [before|after] the weekend.", "Mama Njeri [asked for|wants] {q}.",
            "[Discussed|Talked about] {a} vs {b}; [no decision yet|parked it|leaning {a}].",
            "{n} [will|to] {t} [by {w}|this week|asap].", "Numbers: {o} orders [yesterday|on {w}], {p}% on M-Pesa.",
            "[Complaint|Feedback] from a customer about {d}: [too cold|late|great|portion too small].",
            "{n} [reported|mentioned] the {b2} [fridge|fryer|printer|tablet] is [acting up|fixed|back].",
            "[Reminder|Note]: [uniform checks|deep clean|stock count] on {w}.", "{n} [demoed|showed] {c} on staging; "
            "[looks good|needs work|Mama Njeri liked it].", "[Waste|Leftovers] at {b2} [down|up] {p2}% this week.",
            "[Still open|Carried over]: {t}.", "[Training|Onboarding] for [two|three] new staff at {b2} on {w}."],
            rng.randrange(4, 10))
        bullets = [say(rng, tpl, n=people, t=tasks, t2=tasks, c=COMPONENTS, s=SYMPTOMS, k=CONDITIONS, q=requests,
                       a=a, b=b, w=WEEKDAYS[:5], o=lambda: rng.randrange(40, 400), p=lambda: rng.randrange(70, 98),
                       d=DISHES, b2=BRANCHES, p2=lambda: rng.randrange(2, 20)) for tpl in templates]
        if planted:
            bullets.insert(rng.randrange(len(bullets) + 1), planted)
        actions = list(dict.fromkeys(say(rng, "- [ ] {n} to {t}[ by {w}|]", n=people, t=tasks, w=WEEKDAYS[:5])
                                     for _ in range(rng.randrange(1, 4))))
        text = (f"{title}, {self.long_date(day)}\nPresent: {', '.join(people)}\n" + "\n".join(f"- {b}" for b in bullets)
                + "\nActions:\n" + "\n".join(actions))
        return ("meeting", "user", text)

    def notes(self, day: int) -> list[tuple[str, str, str]]:
        return [self.meeting(day)]

    def whatsapp(self, day: int) -> list[tuple[str, str, str]]:
        lines = [f"{self.name()}: {self.aside(self.sentence(day), end=True)}" for _ in range(self.rng.randrange(4, 14))]
        return [("chat", "user", say(self.rng, "[From the staff group chat:|Kitchen WhatsApp, today:|Forwarded:]") + "\n" +
                 "\n".join(lines))]

    def lesson(self, day: int) -> list[tuple[str, str, str]]:
        rng = self.rng
        names = [n for n in maths.FAMILIES if n != "fee"]
        fam = names[self.lesson_family % len(names)]
        self.lesson_family += 1
        topic = {"squares": "solving quadratic congruences and counting by blocks", "union": "inclusion-exclusion "
                 "with least common multiples", "powers": "last digits of large powers", "spacing": "choosing "
                 "places with gaps", "share": "stars and bars with minimums", "starter": "linear recurrences",
                 "packs": "linear Diophantine equations", "grid": "lattice paths with obstacles",
                 "remainders": "the Chinese remainder theorem"}[fam]
        q, steps = maths.lesson_example(rng, fam)
        exercises = [maths.lesson_example(rng, fam)[0] for _ in range(rng.randrange(1, 4))]
        text = (say(rng, "[Course notes|Maths course, week {w}|Notes from the evening class], {d}: {t}.", w=day // 5 + 1,
                    d=self.long_date(day), t=topic) + "\nWorked example. " + q + "\n" + steps + "\nExercises:\n" +
                "\n".join(f"{i}. {e}" for i, e in enumerate(exercises, 1)))
        return [("maths", "user", text)]

    def doc(self, day: int) -> list[tuple[str, str, str]]:
        rng = self.rng
        kind = rng.choice(["prices", "recipe", "weather", "matatu", "manual", "article", "football", "newsletter",
                           "county", "handbook", "article", "minutes"])
        if kind == "prices":
            items = rng.sample(["maize (90 kg bag)", "beans (kg)", "onions (net)", "tomatoes (crate)", "potatoes (bag)",
                                "rice (25 kg)", "sugar (50 kg)", "cooking fat (10 kg)", "cabbage (each)",
                                "carrots (kg)", "green grams (kg)", "sorghum (kg)", "millet flour (2 kg)",
                                "avocado (each)", "pineapple (each)", "kales (bunch)", "spinach (bunch)",
                                "ginger (kg)", "garlic (kg)", "watermelon (each)"], rng.randrange(8, 16))
            lines = [f"{i:<22} KES {rng.randrange(20, 9000):,}" for i in items]
            text = f"Market prices at {rng.choice(['Wakulima', 'Gikomba', 'Kangemi', 'Marikiti', 'Toi'])} market, " \
                   f"{self.long_date(day)} (from a trader's flyer, not our suppliers):\n" + "\n".join(lines)
        elif kind == "recipe":
            dish = rng.choice(DISHES)
            ing = rng.sample(["2 onions", "4 tomatoes", "1 tbsp ginger", "3 cloves garlic", "500 g beef", "2 cups rice",
                              "1 tsp cumin", "coriander", "salt", "3 tbsp oil", "1 cup coconut milk", "2 carrots",
                              "1 green chilli", "a bunch of dhania", "500 g potatoes", "1 tsp turmeric",
                              "2 cups flour", "1 cup warm water", "a pinch of cardamom"], rng.randrange(6, 11))
            steps = rng.sample(["Fry the onions until golden.", "Add the garlic and ginger and stir for a minute.",
                                "Add the tomatoes and cook down to a paste.", "Season and taste.",
                                "Simmer with the lid on for twenty minutes.", "Stir in the coconut milk.",
                                "Rest for five minutes before serving.", "Garnish with dhania.",
                                "Brown the meat in batches.", "Wash the rice until the water runs clear.",
                                "Knead the dough until smooth.", "Leave it covered for half an hour."],
                               rng.randrange(4, 8))
            text = (f"Recipe a customer emailed in, '{dish}, the way my aunt makes it' (not ours):\nServes "
                    f"{rng.randrange(2, 9)}\n" + "\n".join("- " + i for i in ing) + "\n" +
                    "\n".join(f"{n}. {s}" for n, s in enumerate(steps, 1)))
        elif kind == "weather":
            text = " ".join(say(rng, s, t=TOWNS, a=AREAS, r=ROADS, n=lambda: rng.randrange(5, 60),
                                c=lambda: rng.randrange(12, 31)) for s in rng.sample([
                "Weather for {a}: [morning showers|clear skies|cloudy|heavy afternoon rain], highs of {c}°C.",
                "Motorists on {r} are advised to expect delays after flooding near the bridge.",
                "The forecast for {t} shows {n} mm of rain over the weekend.", "Night temperatures in {a} drop to "
                "{c}°C.", "Farmers in {t} welcomed the early rains.", "Winds of up to {n} km/h are expected along "
                "the coast.", "Residents of {a} reported power interruptions during the storm.",
                "The long rains are expected to start late in {t}.", "Fog is likely on {r} early in the morning.",
                "Schools in {t} closed early because of the flooding."], rng.randrange(4, 8)))
            text = "Weather bulletin pasted from the weather site:\n" + text
        elif kind == "matatu":
            text = say(rng, "Notice to commuters: matatus on route {n} will use {r} instead of {r2} from {w} because "
                            "of roadworks near {a}. Fares stay at KES {f}. [The county apologises for the "
                            "inconvenience.|Expect delays at peak hours.] [Stages near {a2} move a short walk "
                            "away.|Night services are not affected.]", n=lambda: rng.randrange(4, 140), r=ROADS,
                       r2=ROADS, w=WEEKDAYS[:5], a=AREAS, a2=AREAS, f=lambda: rng.randrange(5, 15) * 10)
        elif kind == "manual":
            model = f"{rng.choice(['Jiko', 'Moto', 'Sawa', 'Imara'])} {rng.choice(['Pro', 'Max', 'Plus'])} " \
                    f"{rng.randrange(2, 9)}0"
            faults = ['door open', 'sensor fault', 'overheat', 'low gas pressure', 'fan blocked', 'water level low',
                      'probe missing', 'steam valve stuck']
            codes = [f"E{rng.randrange(10, 99)}: {rng.choice(faults)}" for _ in range(rng.randrange(4, 10))]
            text = (f"From the {model} oven manual, troubleshooting section:\n" + "\n".join(codes) +
                    f"\nClean the filter every {rng.randrange(2, 8)} weeks. Do not use the oven above "
                    f"{rng.randrange(260, 320)}°C. Service every {rng.randrange(6, 13)} months. Keep "
                    f"{rng.randrange(10, 40)} cm clear around the vents.")
        elif kind == "article":
            pool = ["Small restaurants in {t} are moving their menus online.", "Owners say {d} still sells best.",
                    "One cafe in {a} saw orders grow by {n}% after adding photos.", "Delivery costs remain the biggest "
                    "worry.", "Customers want to pay by phone.", "Many kitchens still take orders on WhatsApp.",
                    "Food safety rules are being reviewed by the county.", "Young cooks are mixing old recipes with "
                    "new ideas.", "Rent in {a} has gone up again.", "Some owners share riders to cut costs.",
                    "A bakery in {t} now sells half its bread through a website.", "Power cuts still cost kitchens "
                    "a day's trade every month.", "Gas prices rose {n}% this year.", "Customers in {a} ask for "
                    "smaller portions at lunch.", "Reviews matter more than adverts, owners say.",
                    "The best-selling time is between noon and two.", "Students order most on Fridays.",
                    "A caterer in {t} says weddings are back to their old size."]
            paras = [" ".join(say(rng, s, t=TOWNS, d=DISHES, n=lambda: rng.randrange(2, 40), a=AREAS)
                              for s in rng.sample(pool, rng.randrange(3, 6))) for _ in range(rng.randrange(2, 5))]
            text = say(rng, "Article someone shared, '[Kitchens go digital|Eating out in {t}|The lunch trade]':",
                       t=TOWNS) + "\n" + "\n\n".join(paras)
        elif kind == "football":
            a, b = rng.sample(["Gor Mahia", "AFC Leopards", "Tusker FC", "Bandari", "Kariobangi Sharks", "Nzoia Sugar",
                               "Ulinzi Stars", "Police FC", "Kakamega Homeboyz", "Shabana"], 2)
            text = (f"Match report: {a} {rng.randrange(0, 4)}, {b} {rng.randrange(0, 4)}. "
                    + say(rng, "The game at {v} was [tight|open|scrappy] in the first half. A [header|long shot|penalty] "
                               "in the {m}th minute changed it. The crowd of {c} [sang to the end|left early]. "
                               "[The coach praised the defence.|The coach blamed the pitch.|Both sides looked tired "
                               "after the midweek game.]",
                          v=["Kasarani", "Nyayo", "Kenyatta stadium", "Bukhungu"], m=lambda: rng.randrange(5, 90),
                          c=f"{rng.randrange(2000, 30000):,}"))
        elif kind == "newsletter":
            text = say(rng, "{a} residents' newsletter: the water company will [flush the pipes|fix the main] on {w}. "
                            "[The chama meets|Choir practice is] on {w2} at {h} pm. [Lost: a blue umbrella at the "
                            "shopping centre.|Found: a set of keys near the chemist.] Security patrols continue at "
                            "night. [The road by the school will be graded next week.|Rubbish collection moves to "
                            "{w2}s.] [Please slow down near the playground.|Thank you to everyone who came to the "
                            "clean-up.]", a=AREAS, w=WEEKDAYS, w2=WEEKDAYS, h=lambda: rng.randrange(2, 8))
        elif kind == "county":
            text = say(rng, "County notice: food handlers' certificates must be renewed every {n} months. "
                            "[Single business permits|Fire certificates] are due by the end of {m}. Premises in {a} "
                            "will be visited [in the coming weeks|before the holidays]. Keep the certificates on the "
                            "wall where customers can see them. [Waste must be sorted at source.|Grease traps must be "
                            "cleaned monthly.]", n=[6, 12], m=MONTHS, a=AREAS)
        elif kind == "minutes":
            text = say(rng, "Minutes of the {a} traders' association: [{n} members present.|Quorum reached.] Matters: "
                            "[parking on the main road|the new market stalls|night security|the drainage]. "
                            "[Resolved to write to the county.|To be raised again next month.] Treasurer reported a "
                            "balance of KES {k}. Next meeting on {w}.", a=AREAS, n=lambda: rng.randrange(8, 40),
                       k=lambda: f"{rng.randrange(5000, 90000):,}", w=WEEKDAYS)
        else:
            text = say(rng, "From the staff handbook, section {n}: [uniforms|hygiene|breaks|leave|safety]. "
                            "[Hair nets in the kitchen at all times.|Wash hands for twenty seconds.|Report any cut, "
                            "however small.|Swap shifts only through the rota screen.|No phones on the line.] "
                            "[Breaks are thirty minutes.|Annual leave is requested two weeks ahead.|Lost property goes "
                            "to the branch office.] [Closed shoes only.|Label everything in the cold room with the "
                            "date.|First in, first out.]", n=lambda: rng.randrange(2, 14))
        return [("doc", "user", text)]


def _plant_day(name: str) -> int:
    from camr_engine.bench.haul.codefit import PLANT_DAYS
    return PLANT_DAYS[name]
