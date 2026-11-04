// The memory feed: every reach's events and metrics, merged in time order by the server (GET /api/memory/feed),
// polled once a second (4 times a second while a request is pending), and only while a screen that draws memory is
// on show. No EventSource: it cannot send the token header.
//
// Each answer waits for its metrics record (up to 1.2 s) so the stage can time its words; one that never gets a
// record plays at 20 words a second, marked "words not timed". Answers the chat already has (from its POST) are
// handed in with inject() and played at once; the poll that later brings them is ignored. The first poll, and the
// first after a reset, hands over "history": only the answers it brought, so nothing is heard twice.

const WAIT_FOR_METRIC_MS = 1200;
const HISTORY = 60;

let one = null;

export function memoryFeed(api) {
  if (!one) one = new Feed(api);
  return one;
}

function key(e) { return `${e.src ?? e.reach ?? "memory"}/${e.i}`; }

export function sameAnswer(e, m) {
  if (!e || !m) return false;
  if (m.question !== e.question || (m.room ?? null) !== (e.room ?? null)) return false;
  if ((m.reach ?? null) !== (e.reach ?? null) && m.reach != null && e.reach != null) return false;
  const a = Date.parse(e.at), b = Date.parse(m.at);
  return !Number.isFinite(a) || !Number.isFinite(b) || Math.abs(b - a) < 10000;
}

class Feed {
  constructor(api) {
    this.api = api;
    this.users = 0;
    this.timer = null;
    this.ev = null; // {reach: next line}; null until the first poll
    this.mx = null;
    this.seen = new Set();
    this.listeners = new Map();
    this.waiting = []; // answers waiting for their metrics record: {e, until}
    this.metrics = []; // recent records, for pairing
    this.answers = []; // recent answers with their records: {e, m}
    this.reaches = null;
  }

  on(name, fn) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set());
    this.listeners.get(name).add(fn);
    return () => this.listeners.get(name)?.delete(fn);
  }

  emit(name, data) {
    for (const fn of this.listeners.get(name) || []) {
      try { fn(data); } catch (err) { console.error(err); }
    }
  }

  start() {
    this.users++;
    if (this.users === 1) this.poll();
  }

  stop() {
    this.users = Math.max(0, this.users - 1);
    if (!this.users) { clearTimeout(this.timer); this.timer = null; }
  }

  reset() { // the reaches changed: start each one again from its end
    this.ev = this.mx = null;
    this.waiting = [];
    this.emit("reset", null);
    if (this.users) { clearTimeout(this.timer); this.poll(); }
  }

  inject(e, m) {
    if (!e || e.i == null) return;
    const k = key(e);
    if (this.seen.has(k)) return;
    this.seen.add(k);
    this.emit("event", { ...e, live: true });
    if (e.type === "answer" || e.type === "agent") this.answer(e, m || null, true);
  }

  cursor(c) { return c ? Object.entries(c).map(([k, v]) => `${k}@${v}`).join(",") : undefined; }

  async poll() {
    this.timer = null;
    if (!this.users) return;
    if (document.hidden || this.api.measuring.peek()) { this.schedule(); return; }
    const first = this.ev === null;
    const before = new Set(this.answers); // after a reset, "history" carries only the answers this poll brings
    try {
      const got = await this.api.get("/api/memory/feed", first ? { tail: HISTORY } : { ev: this.cursor(this.ev), mx: this.cursor(this.mx) });
      const reaches = (got.reaches || []).join(",");
      if (this.reaches !== null && reaches !== this.reaches && !first) {
        this.reaches = reaches;
        this.emit("reaches", got.reaches);
      }
      this.reaches = reaches;
      this.ev = { ...(this.ev || {}), ...got.ev };
      this.mx = { ...(this.mx || {}), ...got.mx };
      for (const m of got.metrics) this.metric(m, !first);
      for (const e of got.events) {
        const k = key(e);
        if (this.seen.has(k)) continue;
        this.seen.add(k);
        const live = !first;
        this.emit("event", { ...e, live });
        if (e.type === "answer" || e.type === "agent") {
          const m = this.metrics.find((x) => sameAnswer(e, x)) || null;
          this.answer(e, m, live);
        }
      }
      if (first) this.emit("history", this.answers.filter((x) => !before.has(x)));
    } catch (err) {
      if (err?.status === 403) return; // the server restarted: the shell asks for a reload
    }
    this.flush();
    this.schedule();
  }

  schedule() {
    if (!this.users) return;
    clearTimeout(this.timer);
    const soon = this.waiting.length || this.api.pending.peek() > 0;
    this.timer = setTimeout(() => this.poll(), soon ? 250 : 1000);
  }

  metric(m, live) {
    this.metrics.push(m);
    if (this.metrics.length > 200) this.metrics.shift();
    if (live) {
      this.api.lastMetric.value = m;
      if (m.read_bytes && m.gbps) this.api.lastRead.value = { bytes: m.read_bytes, gbps: m.gbps, at: m.at };
      this.emit("metric", m);
    }
    const w = this.waiting.findIndex((x) => sameAnswer(x.e, m));
    if (w >= 0) {
      const [x] = this.waiting.splice(w, 1);
      this.deliver(x.e, m, true);
    }
  }

  answer(e, m, live) {
    if (live && !m) {
      this.waiting.push({ e, until: performance.now() + WAIT_FOR_METRIC_MS });
      return;
    }
    this.deliver(e, m, live);
  }

  deliver(e, m, live) {
    const rec = { e, m };
    this.answers.push(rec);
    if (this.answers.length > HISTORY) this.answers.shift();
    if (live) {
      this.api.lastAnswer.value = e;
      const f = e.seconds?.fetch;
      if (e.tier === "ssd" && e.read_bytes && f > 0) this.api.lastRead.value = { bytes: e.read_bytes, gbps: e.read_bytes / f / 1e9, at: e.at };
      this.emit("answer", rec);
    }
  }

  flush() {
    const now = performance.now();
    const late = this.waiting.filter((x) => x.until <= now);
    this.waiting = this.waiting.filter((x) => x.until > now);
    for (const x of late) this.deliver(x.e, null, true);
  }
}
