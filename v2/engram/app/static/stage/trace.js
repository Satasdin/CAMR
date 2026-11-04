// The trace strip: stacked 28 px rows on --void with a 72 px label gutter (DIRECTION.md, "Trace strip").
// - roll: the last 60 s, now at the right, in real time (redrawn when data lands, and once a second while anything
//   is in the window; never a frame loop);
// - answer: one answer, x in ms from the question, 55% of the width up to the first word, a // break, 45% for
//   decode. C shows two cursors that read Δt, bytes and mean GB/s between them.
// Rows: SSD R, SSD W, RAM, HOT, DESK, USED, WORDS, TTFT (any subset, in that order).

const GUTTER = 72;
const ROW = 28;
const WINDOW_MS = 60000;
const THIN = " ";

export const ROWS = ["ssdR", "ssdW", "ram", "hot", "desk", "used", "words", "ttft"];
const LABELS = { ssdR: "SSD R", ssdW: "SSD W", ram: "RAM", hot: "HOT", desk: "DESK", used: "USED", words: "WORDS", ttft: "TTFT" };

function time(at) {
  const t = Date.parse(at);
  return Number.isFinite(t) ? t : Date.now();
}

export class Trace {
  constructor(host, api, { rows = ROWS, tokenBytes = () => 0 } = {}) {
    this.api = api;
    this.host = host;
    this.rows = rows;
    this.tokenBytes = tokenBytes;
    host.classList.add("trace");
    this.canvas = document.createElement("canvas");
    this.canvas.className = "trace-canvas";
    this.canvas.setAttribute("role", "img");
    this.canvas.setAttribute("aria-label", `trace strip: ${rows.map((r) => LABELS[r]).join(", ")}`);
    this.readout = document.createElement("div");
    this.readout.className = "trace-readout t-readout";
    host.append(this.canvas, this.readout);
    this.answers = []; // {e, m, t0, wait, total}
    this.writes = [];
    this.ram = [];
    this.hot = [];
    this.selected = null;
    this.cursors = null;
    this.timer = null;
    this.visible = false;
    this.colours();
    this.ro = new ResizeObserver(() => this.draw());
    this.ro.observe(host);
    this.bindCursors();
  }

  colours() {
    const cs = getComputedStyle(document.documentElement);
    const v = (n) => cs.getPropertyValue(n).trim();
    this.c = { void: v("--void"), hair: v("--hair"), ink4: v("--ink-4"), ink3: v("--ink-3"), ink2: v("--ink-2"), ink: v("--ink"),
      ssd: v("--ssd"), ram: v("--ram"), used: v("--used"), vault: v("--vault"), select: v("--select"),
      ramRest: v("--ram-rest"), usedHold: v("--used-hold") };
    this.font = `500 10.5px ${v("--f-mono") || "monospace"}`;
  }

  height() { return this.rows.reduce((a, r) => a + this.rowH(r), 0); }

  rowH(r) {
    if (r === "used" && this.selected) return Math.max(ROW, Math.min(16, this.selected.e.nodes?.length || 0) * 4 + 8);
    return ROW;
  }

  // -- data

  addAnswer({ e, m }) {
    if (!e) return;
    const wait = (e.wait_s ?? m?.first_word_s ?? 0) * 1000;
    const n = (e.words || []).length;
    const total = m?.total_s != null ? m.total_s * 1000 : wait + n * 50;
    const end = m ? time(m.at) : time(e.at);
    this.answers.push({ e, m, t0: end - total, wait, total, timed: !!m });
    if (this.answers.length > 200) this.answers.shift();
    this.draw();
  }

  addEvent(e) {
    if (e.type === "remember") {
      this.writes.push({ t: time(e.at), bytes: (e.tokens || 0) * this.tokenBytes() });
    } else if (e.type === "wake") {
      this.writes.push({ t: time(e.at), bytes: null, wake: true });
    } else return;
    if (this.writes.length > 400) this.writes.shift();
    this.draw();
  }

  addSys(sys) {
    if (!sys?.process_bytes) return;
    this.ram.push({ t: Date.now(), bytes: sys.process_bytes, total: sys.total_bytes });
    const cut = Date.now() - WINDOW_MS - 2000;
    while (this.ram.length && this.ram[0].t < cut) this.ram.shift();
  }

  addHot(ram) {
    if (!ram?.budget_bytes) return;
    this.hot.push({ t: Date.now(), used: ram.used_bytes, budget: ram.budget_bytes });
    const cut = Date.now() - WINDOW_MS - 2000;
    while (this.hot.length && this.hot[0].t < cut) this.hot.shift();
  }

  select(rec) {
    this.selected = rec ? this.answers.find((a) => a.e === rec.e) || { e: rec.e, m: rec.m, ...this.timing(rec) } : null;
    if (!this.selected) this.cursors = null;
    this.host.style.setProperty("--trace-h", `${this.height()}px`);
    this.draw();
  }

  timing({ e, m }) {
    const wait = (e.wait_s ?? m?.first_word_s ?? 0) * 1000;
    const total = m?.total_s != null ? m.total_s * 1000 : wait + (e.words || []).length * 50;
    return { wait, total, t0: time(e.at) - total, timed: !!m };
  }

  toggleCursors() {
    if (!this.selected) return false;
    const w = this.plotW();
    this.cursors = this.cursors ? null : [GUTTER + w * 0.2, GUTTER + w * 0.5];
    this.draw();
    return true;
  }

  // -- drawing

  plotW() { return Math.max(10, this.size().w - GUTTER - 8); }

  size() {
    const r = this.host.getBoundingClientRect();
    return { w: Math.max(1, Math.floor(r.width)), h: this.height() };
  }

  show() {
    this.visible = true;
    this.host.style.setProperty("--trace-h", `${this.height()}px`);
    this.draw();
    clearInterval(this.timer);
    this.timer = setInterval(() => {
      if (this.selected) return; // an answer does not roll
      this.addSys(this.api.sys.peek());
      if (this.liveInWindow()) this.draw();
    }, 1000);
  }

  hide() {
    this.visible = false;
    clearInterval(this.timer);
    this.timer = null;
  }

  liveInWindow() {
    const cut = Date.now() - WINDOW_MS;
    return this.ram.length > 0 || this.answers.some((a) => a.t0 + a.total > cut) || this.writes.some((w) => w.t > cut);
  }

  draw() {
    if (!this.visible) return;
    const { w, h } = this.size();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const c = this.canvas;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
      c.width = Math.round(w * dpr);
      c.height = Math.round(h * dpr);
      c.style.height = `${h}px`;
    }
    const g = c.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = this.c.void;
    g.fillRect(0, 0, w, h);
    g.font = this.font;
    g.textBaseline = "middle";
    const x = this.selected ? this.answerX() : this.rollX();
    let y = 0;
    for (const r of this.rows) {
      const rh = this.rowH(r);
      g.fillStyle = this.selected && r === "used" ? this.c.ink3 : this.c.ink3;
      g.fillText(LABELS[r], 8, y + rh / 2);
      g.fillStyle = this.c.hair;
      g.fillRect(GUTTER, y + rh - 1, w - GUTTER, 1);
      g.save();
      g.beginPath();
      g.rect(GUTTER, y, w - GUTTER, rh);
      g.clip();
      this[`row_${r}`]?.(g, x, y, rh, w);
      g.restore();
      y += rh;
    }
    if (this.selected) this.drawBreak(g, h);
    this.drawCursors(g, h);
    this.readout.textContent = this.selected ? this.answerLine() : "";
  }

  rollX() {
    const now = Date.now();
    const w = this.plotW();
    return { at: (t) => GUTTER + ((t - (now - WINDOW_MS)) / WINDOW_MS) * w, ms: (d) => (d / WINDOW_MS) * w, roll: true };
  }

  answerX() {
    const s = this.selected;
    const w = this.plotW();
    const first = Math.max(1, s.wait);
    const dec = Math.max(1, s.total - s.wait);
    const at = (t) => {
      const d = t - s.t0;
      return d <= first ? GUTTER + (d / first) * w * 0.55 : GUTTER + w * 0.55 + ((d - first) / dec) * w * 0.45;
    };
    return { at, ms: (d) => (d / first) * w * 0.55, roll: false };
  }

  inView() {
    if (this.selected) return [this.selected];
    const cut = Date.now() - WINDOW_MS - 5000;
    return this.answers.filter((a) => a.t0 + a.total > cut);
  }

  row_ssdR(g, X, y, h) {
    for (const a of this.inView()) {
      const e = a.e;
      if (e.tier !== "ssd" || !e.read_bytes) continue;
      const s = e.seconds || {};
      const start = a.t0 + ((s.choose || 0) + (s.core || 0) + (s.wake || 0)) * 1000;
      const dur = (s.fetch || 0) * 1000;
      const gbps = s.fetch > 0 ? e.read_bytes / s.fetch / 1e9 : 0;
      const bh = Math.max(1, Math.min(1, gbps / 8) * (h - 4));
      const x0 = X.at(start);
      const bw = Math.max(2, X.at(start + dur) - x0);
      g.fillStyle = this.c.ssd;
      g.fillRect(x0, y + h - 2 - bh, bw, bh);
    }
  }

  row_ssdW(g, X, y, h) {
    g.strokeStyle = this.c.ssd;
    g.setLineDash([2, 2]);
    const items = this.selected ? [] : this.writes;
    for (const wr of items) {
      const x = X.at(wr.t);
      const hh = wr.bytes ? Math.max(3, Math.min(h - 4, Math.log10(Math.max(10, wr.bytes)) * 2.4)) : h - 6;
      g.beginPath(); g.moveTo(x + 0.5, y + h - 2); g.lineTo(x + 0.5, y + h - 2 - hh); g.stroke();
    }
    g.setLineDash([]);
  }

  row_ram(g, X, y, h, w) {
    const pts = this.selected ? [] : this.ram;
    if (pts.length) {
      const total = pts[pts.length - 1].total || Math.max(...pts.map((p) => p.bytes)) * 2;
      const yy = (b) => y + h - 2 - (b / total) * (h - 4) * 4; // the process is a sliver of 24 GB: scaled ×4, printed
      g.globalAlpha = 0.2;
      g.fillStyle = this.c.ram;
      g.beginPath();
      g.moveTo(X.at(pts[0].t), y + h - 2);
      for (const p of pts) g.lineTo(X.at(p.t), Math.max(y + 2, yy(p.bytes)));
      g.lineTo(X.at(pts[pts.length - 1].t), y + h - 2);
      g.fill();
      g.globalAlpha = 1;
      g.strokeStyle = this.c.ram;
      g.lineWidth = 1.5;
      g.beginPath();
      pts.forEach((p, i) => (i ? g.lineTo : g.moveTo).call(g, X.at(p.t), Math.max(y + 2, yy(p.bytes))));
      g.stroke();
      g.lineWidth = 1;
      g.fillStyle = this.c.ink3;
      g.textAlign = "right";
      g.fillText(`${(pts[pts.length - 1].bytes / 1024 ** 3).toFixed(2)}${THIN}GB · ×4`, w - 4, y + 9);
      g.textAlign = "left";
    }
    for (const a of this.inView()) {
      if (!a.m?.peak_ram_bytes) continue;
      g.fillStyle = this.c.ram;
      g.fillRect(X.at(a.t0 + a.total) - 1, y + 2, 2, 4);
    }
  }

  row_hot(g, X, y, h) {
    const pts = this.selected ? [] : this.hot;
    if (!pts.length) return;
    const budget = pts[pts.length - 1].budget;
    for (let i = 0; i < pts.length; i++) {
      const p = pts[i];
      const x0 = X.at(p.t), x1 = i + 1 < pts.length ? X.at(pts[i + 1].t) : X.at(Date.now());
      const bh = (p.used / budget) * (h - 6);
      g.fillStyle = this.c.ramRest;
      g.fillRect(x0, y + h - 2 - bh, Math.max(1, x1 - x0), bh);
    }
    g.strokeStyle = this.c.select;
    g.globalAlpha = 0.3;
    g.setLineDash([3, 3]);
    g.beginPath(); g.moveTo(GUTTER, y + 4.5); g.lineTo(this.size().w, y + 4.5); g.stroke();
    g.setLineDash([]);
    g.globalAlpha = 1;
  }

  row_desk(g, X, y, h) {
    for (const a of this.inView()) {
      const m = a.m;
      if (!m?.context_tokens || !m.history_tokens) continue;
      const x = X.at(a.t0 + a.wait);
      const top = Math.log10(Math.max(10, m.history_tokens));
      const v = Math.log10(Math.max(1, m.context_tokens)) / top;
      g.fillStyle = this.c.ink4;
      g.fillRect(x - 3, y + 2, 6, 1);
      g.fillStyle = this.c.ram;
      g.fillRect(x - 1, y + h - 2 - v * (h - 6), 2, v * (h - 6));
    }
  }

  row_used(g, X, y, h) {
    for (const a of this.inView()) {
      const e = a.e;
      const nodes = e.nodes || [];
      if (!nodes.length) continue;
      const order = nodes.map((n, j) => [j, e.share?.[j] || 0]).sort((p, q) => q[1] - p[1]).slice(0, this.selected ? 16 : 6);
      const used = new Set(e.used || []);
      const words = e.words || [];
      order.forEach(([j], k) => {
        const yy = y + 2 + k * 4;
        if (this.selected) { // the node's label: a green dot if used, an amber ring if only picked
          const lx = GUTTER - 10;
          if (used.has(nodes[j])) { g.fillStyle = this.c.used; g.beginPath(); g.arc(lx, yy + 1.5, 1.6, 0, 7); g.fill(); }
          else { g.strokeStyle = this.c.ram; g.beginPath(); g.arc(lx, yy + 1.5, 1.6, 0, 7); g.stroke(); }
        }
        for (let i = 0; i < words.length; i++) {
          const row = e.looks?.[i] || [];
          const top = Math.max(1e-9, ...row);
          const v = (row[j] || 0) / top;
          if (v < 0.05) continue;
          const t = a.t0 + a.wait + (i * (a.total - a.wait)) / Math.max(1, words.length);
          g.globalAlpha = Math.min(1, 0.15 + v);
          g.fillStyle = this.c.used;
          g.fillRect(X.at(t), yy, Math.max(1, this.selected ? 2 : 1), 3);
        }
        g.globalAlpha = 1;
      });
    }
  }

  row_words(g, X, y, h) {
    for (const a of this.inView()) {
      const n = (a.e.words || []).length;
      const xf = X.at(a.t0 + a.wait);
      g.fillStyle = this.c.ink;
      g.fillRect(xf, y + 2, 1, h - 4);
      g.fillStyle = this.c.ink2;
      for (let i = 1; i < n; i++) {
        const t = a.t0 + a.wait + (i * (a.total - a.wait)) / n;
        g.fillRect(X.at(t), y + h / 2, 1, h / 2 - 3);
      }
    }
  }

  row_ttft(g, X, y, h) {
    const yy = (s) => y + h - 3 - Math.min(1, s / 0.2) * (h - 6);
    g.strokeStyle = this.c.ink4;
    g.setLineDash([3, 3]);
    g.beginPath(); g.moveTo(GUTTER, yy(0.07) + 0.5); g.lineTo(this.size().w, yy(0.07) + 0.5); g.stroke();
    g.setLineDash([]);
    for (const a of this.inView()) {
      const s = a.m?.first_word_s ?? a.e.wait_s;
      if (s == null) continue;
      g.fillStyle = this.c.ink;
      g.beginPath();
      g.arc(X.at(a.t0 + a.wait), yy(s), 2, 0, 7);
      g.fill();
      if (s > 0.2) { g.fillRect(X.at(a.t0 + a.wait) - 2, y + 2, 4, 1); }
    }
  }

  drawBreak(g, h) {
    const x = GUTTER + this.plotW() * 0.55;
    g.fillStyle = this.c.void;
    g.fillRect(x - 3, 0, 6, h);
    g.fillStyle = this.c.ink3;
    g.textAlign = "center";
    g.fillText("//", x, 8);
    g.textAlign = "left";
  }

  // -- cursors

  bindCursors() {
    let drag = null;
    this.canvas.addEventListener("pointerdown", (ev) => {
      if (!this.cursors) return;
      const b = this.canvas.getBoundingClientRect();
      const x = ev.clientX - b.left;
      const k = Math.abs(x - this.cursors[0]) < Math.abs(x - this.cursors[1]) ? 0 : 1;
      if (Math.abs(x - this.cursors[k]) > 12) return;
      drag = k;
      this.canvas.setPointerCapture(ev.pointerId);
    });
    this.canvas.addEventListener("pointermove", (ev) => {
      if (drag === null) return;
      const b = this.canvas.getBoundingClientRect();
      this.cursors[drag] = Math.max(GUTTER, Math.min(b.width - 8, ev.clientX - b.left));
      this.draw();
    });
    this.canvas.addEventListener("pointerup", () => { drag = null; });
  }

  xToMs(x) {
    const s = this.selected;
    const w = this.plotW();
    const u = x - GUTTER;
    return u <= w * 0.55 ? (u / (w * 0.55)) * s.wait : s.wait + ((u - w * 0.55) / (w * 0.45)) * (s.total - s.wait);
  }

  drawCursors(g, h) {
    if (!this.cursors || !this.selected) return;
    g.fillStyle = this.c.select;
    for (const x of this.cursors) g.fillRect(Math.round(x), 0, 1, h);
  }

  cursorLine() {
    if (!this.cursors || !this.selected) return "";
    const [a, b] = this.cursors.map((x) => this.xToMs(x)).sort((p, q) => p - q);
    const e = this.selected.e;
    const s = e.seconds || {};
    const r0 = ((s.choose || 0) + (s.core || 0) + (s.wake || 0)) * 1000, r1 = r0 + (s.fetch || 0) * 1000;
    const overlap = Math.max(0, Math.min(b, r1) - Math.max(a, r0));
    const bytes = e.read_bytes && r1 > r0 ? (e.read_bytes * overlap) / (r1 - r0) : 0;
    const dt = b - a;
    const gbps = bytes && dt > 0 ? bytes / (dt / 1000) / 1e9 : null;
    return ` · Δt ${dt.toFixed(dt >= 10 ? 0 : 1)}${THIN}ms · ${(bytes / 1e6).toFixed(1)}${THIN}MB · ${gbps == null ? "—" : `${gbps.toFixed(2)}${THIN}GB/s`} mean`;
  }

  answerLine() {
    const s = this.selected;
    const label = `answer ${s.e.i ?? ""} · first word ${(s.wait / 1000).toFixed(2)}${THIN}s · ${(s.total / 1000).toFixed(2)}${THIN}s total`;
    return `${label}${s.timed ? "" : " · words not timed"}${this.cursorLine()}`;
  }

  destroy() {
    this.hide();
    this.ro.disconnect();
  }
}
