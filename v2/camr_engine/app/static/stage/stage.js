// The Stage: the memory on a black stage like a specimen under a microscope (DIRECTION.md, "The live memory visual").
// Three regions left to right, matching the data path: the SSD plate (rooms as layer-by-token tiles, one band per
// reach), the bus (a 0–8 GB/s scale that reads cross as beams sized to their bytes), and the RAM plate (a 24 GB ruler,
// then a magnified inset: the core, the hot shelf and the desk). Under it, the vault drawer: one dot per note.
//
// Every light is a measured event: an answer from the log is played step by step (choose, core, fetch by tier, lay
// the desk, prefill, each written word's looks on the watched rows, settle), at the chosen timebase. The frame loop
// runs only while a mark is within six half-lives of its event, a beam is in flight or the user pans; it stops at
// rest, while hidden and while a benchmark measures. A stage not on show plays no word steps: an answer heard then
// settles at once (its lights would be long gone), and one hidden mid-answer drops the words it had left. A word step
// more than six half-lives late is dropped too, never run in a burst.
//
// Modes: live (Memory), compact (Chat's eyepiece), path (one answer in the light path sheet), vault (notes and doors
// at the same positions).

import { DOT, F, NEVER, RECT, Renderer, S, SEG } from "/static/stage/gl.js";
import { CH, HL, STEP, palette } from "/static/stage/palette.js";
import { LABEL_H, bands, cells, placeBand } from "/static/stage/place.js";

const GB = 1e9;
const GIB = 1024 ** 3;
const MB2 = 2e6; // a beam is 1 px thick per 2 MB
const BUS_MAX = 8; // GB/s at the top of the bus scale
const WATCHED = [12, 16, 20, 24];
const THIN = " ";
const DESK_ROWS = 28;

class Pool {
  constructor(width) { this.n = width; this.a = new Float32Array(width * 512); this.count = 0; this.lo = Infinity; this.hi = -1; this.full = true; }
  clear() { this.count = 0; this.full = true; }
  add(vals) {
    if ((this.count + 1) * this.n > this.a.length) {
      const b = new Float32Array(this.a.length * 2);
      b.set(this.a);
      this.a = b;
      this.full = true;
    }
    const i = this.count++;
    this.a.set(vals, i * this.n);
    this.mark(i);
    return i;
  }
  put(i, off, vals) { this.a.set(vals, i * this.n + off); this.mark(i); }
  get(i, off) { return this.a[i * this.n + off]; }
  mark(i) { this.lo = Math.min(this.lo, i); this.hi = Math.max(this.hi, i + 1); }
  flush(gl, kind) {
    if (this.full) gl.set(kind, this.a, this.count);
    else if (this.hi > this.lo) gl.update(kind, this.lo, Math.min(this.hi, this.count), this.count);
    this.full = false; this.lo = Infinity; this.hi = -1;
  }
}

// rect instance: see gl.js for the layout
function R({ x, y, w, h, r = 2, ol = 0, flags = 0, bc = CH.ssd, b = 0, fc = null, t = 0, hl = 0, peak = 0,
  on = -NEVER, off = NEVER, drain = 200, reveal = 0, dx = 0, dy = 0, move = 0 }) {
  return [x, y, w, h, r, ol, flags, bc, b, fc ?? bc, t, hl, peak, on, off, drain, reveal, dx, dy, move];
}
// seg instance
function G({ x0, y0, x1, y1, w = 1, flags = 0, c0 = CH.ssd, c1 = null, base = 0, peak = 1, start = 0, land = 0,
  decay = 0, hl = 400 }) {
  return [x0, y0, x1, y1, w, flags, c0, c1 ?? c0, base, peak, start, land, decay, hl, 0, 0];
}
// dot instance
function D({ x, y, r = 1, flags = 0, bc = CH.vault, b = STEP.rest, fc = null, t = 0, hl = 0, peak = 0, rc = CH.vault, ring = 0 }) {
  return [x, y, r, flags, bc, b, fc ?? bc, t, hl, peak, rc, ring];
}

function hash(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967296;
}

export function fmtBytes(n) {
  if (n == null || !Number.isFinite(n)) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, x = Math.abs(n);
  while (x >= 1000 && i < u.length - 1) { x /= 1000; i++; }
  return `${i === 0 ? Math.round(x) : x >= 100 ? x.toFixed(0) : x >= 10 ? x.toFixed(1) : x.toFixed(2)}${THIN}${u[i]}`;
}

export function fmtRam(n) {
  if (n == null || !Number.isFinite(n)) return "—";
  return `${(n / GIB).toFixed(n >= 10 * GIB ? 1 : 2)}${THIN}GB`;
}

// One reach of the snapshot, indexed for the stage.
export function index(snap) {
  const out = new Map();
  for (const r of snap.reaches || []) {
    const moments = r.moments.map(([room, day, tokens, start], id) => ({ id, room, day, tokens, start, text: r.texts?.[id] }));
    const rooms = new Map();
    for (const [id, tokens, asleep, hot] of r.rooms) rooms.set(id, { id, tokens, asleep: !!asleep, hot: !!hot, members: [] });
    for (const m of moments) rooms.get(m.room)?.members.push(m.id);
    for (const room of rooms.values()) room.members.sort((a, b) => moments[a].start - moments[b].start);
    const notes = (r.notes || []).map(([id, moment, day, strength, asleep, into, pinned, core]) => ({ id, moment, day, strength, asleep: !!asleep, into, pinned: !!pinned, core: !!core }));
    out.set(r.label, { ...r, moments, rooms, notesList: notes, token_bytes: snap.token_bytes });
  }
  return out;
}

export class Stage {
  constructor(host, api, opts = {}) {
    this.api = api;
    this.host = host;
    this.mode = opts.mode || "live";
    this.small = this.mode === "compact";
    this.drawer = opts.drawer ?? this.mode === "live";
    this.onSelect = opts.onSelect || (() => {});
    this.onWord = opts.onWord || (() => {});
    this.onNote = opts.onNote || (() => {});
    this.onVault = opts.onVault || (() => {});
    host.classList.add("stage", `stage-${this.mode}`);
    this.canvas = document.createElement("canvas");
    this.canvas.className = "stage-canvas";
    this.canvas.setAttribute("role", "img");
    this.canvas.setAttribute("aria-label", "memory stage: rooms on the SSD, reads across the bus, the desk in RAM");
    this.overlay = document.createElement("div");
    this.overlay.className = "stage-overlay";
    this.tip = document.createElement("div");
    this.tip.className = "stage-tip t-readout";
    this.tip.hidden = true;
    this.chip = document.createElement("div");
    this.chip.className = "stage-chip t-readout";
    this.chip.hidden = true;
    host.append(this.canvas, this.overlay, this.chip, this.tip);
    this.pal = palette();
    this.gl = new Renderer(this.canvas, this.pal);
    this.canvas = this.gl.canvas; // the renderer swaps in a fresh canvas when WebGL fails after starting
    this.pools = { rects: new Pool(RECT), dyn: new Pool(RECT), dots: new Pool(DOT), segs: new Pool(SEG), beams: new Pool(SEG) };
    this.epoch = performance.now();
    this.pausedAt = null;
    this.pausedTotal = 0;
    this.view = { k: 1, x: 0, y: 0 };
    this.data = null;
    this.snap = null;
    this.read = null;
    this.keep = new Map();
    this.flares = new Map(); // mark key -> {fc, t, hl, peak}: re-applied after a rebuild
    this.touched = new Map(); // mark key -> {chan, hits}: the session's heat, for infinite persistence
    this.queue = [];
    this.held = [];
    this.busyUntil = 0;
    this.raf = null;
    this.lastDraw = 0;
    this.visible = false;
    this.selected = null;
    this.ram = null;
    this.on = true;
    this.vaultMode = this.mode === "vault";
    this.playing = null; // {label, until, timed}
    this.desk = null;
    this.size = { w: 0, h: 0 };
    this.overlayState = {};
    this.ro = new ResizeObserver(() => this.layout());
    this.ro.observe(host);
    this.bindPointer();
  }

  // -- time: display milliseconds since the stage began, frozen while stopped (Space)

  now() { return (this.pausedAt ?? performance.now()) - this.epoch - this.pausedTotal; }

  setRunning(on) {
    if (!on && this.pausedAt === null) this.pausedAt = performance.now();
    if (on && this.pausedAt !== null) {
      this.pausedTotal += performance.now() - this.pausedAt;
      this.pausedAt = null;
      const held = this.held;
      this.held = [];
      for (const fn of held) fn();
      this.kick(this.now());
    }
  }

  // -- data

  setSnapshot(snap) {
    this.snap = snap;
    this.data = index(snap);
    this.ram = snap.ram || this.ram;
    this.on = snap.on !== false;
    this.build();
  }

  share(other) { // draw from another stage's memory as it stands now (with the moments it has heard of since)
    this.snap = other.snap;
    this.data = other.data;
    this.ram = other.ram;
    this.on = other.on;
    this.build();
  }

  setRead(labels) { // the aperture: reaches outside it draw at the far step
    this.read = labels ? new Set(labels) : null;
    this.build();
  }

  setRam(ram) { // the hot shelf from the tiers' state; rooms that left it drain
    const before = new Set((this.ram?.hot || []).map((h) => `${h.reach}/${h.room}`));
    const after = new Set((ram?.hot || []).map((h) => `${h.reach}/${h.room}`));
    const same = before.size === after.size && [...before].every((k) => after.has(k))
      && (this.ram?.core_bytes ?? null) === (ram?.core_bytes ?? null);
    this.ram = ram;
    if (!same) this.build();
  }

  setOn(on) {
    if (this.on === on) return;
    this.on = on;
    this.build();
  }

  setVault(on) {
    this.vaultMode = on;
    this.build();
  }

  reachOf(label) {
    if (!this.data) return null;
    return this.data.get(label) || this.data.get(label ?? "memory") || (this.data.size === 1 ? [...this.data.values()][0] : null);
  }

  isRead(label) {
    const r = this.data?.get(label);
    return r?.read !== false && (!this.read || this.read.has(label));
  }

  // -- geometry

  layout() {
    const r = this.host.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return; // a hidden screen measures 0 × 0: keep the last real size
    const w = Math.floor(r.width), h = Math.floor(r.height);
    if (w === this.size.w && h === this.size.h) return;
    this.size = { w, h };
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.gl.resize(w, h, this.dpr);
    this.build();
  }

  regions() {
    const { w: W, h: H } = this.size;
    const pad = this.small ? 10 : 16;
    const top = pad + (this.small ? 14 : 20);
    const drawerH = this.drawer ? 64 : 0;
    const bottom = H - pad - drawerH - (this.drawer ? 8 : 0) - (this.small ? 4 : 18);
    if (this.mode === "path") {
      return { pad, top, bottom, ssd: { x: pad, y: top, w: W * 0.28 - pad, h: bottom - top },
        bus: { x: W * 0.28, w: W * 0.16, y: top, h: bottom - top }, ram: { x: W * 0.44 + 8, w: W * 0.56 - 8 - pad, y: top, h: bottom - top },
        drawer: null };
    }
    return {
      pad, top, bottom,
      ssd: { x: pad, y: top, w: W * 0.46 - pad, h: Math.max(40, bottom - top) },
      bus: { x: W * 0.46, w: W * 0.14, y: top, h: Math.max(40, bottom - top) },
      ram: { x: W * 0.6 + 8, w: Math.max(40, W * 0.4 - 8 - pad), y: top, h: Math.max(40, bottom - top) },
      drawer: this.drawer ? { x: pad, y: H - pad - drawerH, w: W - 2 * pad, h: drawerH } : null,
    };
  }

  // the RAM plate's inset: core, hot shelf, desk
  inset(ram) {
    // ruler, then (magnified) the core, the hot shelf and the desk; rows step down until it fits the plate's height
    const s = this.small;
    const fits = [[3, 5, 1], [3, 4, 1], [2, 4, 1], [2, 3, 0.75], [2, 2, 0.6], [1, 2, 0.5]].map(([c, d, g]) => [s ? Math.min(c, 2) : c, s ? Math.min(d, 3) : d, s ? 0.6 : g]);
    const need = ([c, d, g]) => (s ? 10 : 20) + 30 * g + 3 * (s ? 13 : 16) + 2 * 12 * g + 28 * c + (s ? 14 : 24) + 28 * d + (s ? 0 : 18);
    const [coreRow, deskRow, gap] = fits.find((f) => need(f) <= ram.h) || fits[fits.length - 1];
    const ruler = { x: ram.x, y: ram.y, w: ram.w, h: s ? 10 : 20 };
    let y = ruler.y + ruler.h + Math.round(30 * gap);
    const lab = s ? 13 : 16;
    const core = { x: ram.x, y: y + lab, w: 0, h: DESK_ROWS * coreRow };
    y = core.y + core.h + Math.round(12 * gap);
    const hot = { x: ram.x, y: y + lab, w: ram.w, h: s ? 14 : 24 };
    y = hot.y + hot.h + Math.round(12 * gap);
    const desk = { x: ram.x + (s ? 0 : 28), y: y + lab, w: ram.w - (s ? 0 : 28), h: DESK_ROWS * deskRow, row: deskRow };
    return { ruler, core, hot, desk, legend: desk.y + desk.h + 4, roomy: coreRow >= 3 };
  }

  busY(gbps) {
    const g = this.geo;
    const b = g.bus;
    const v = Math.max(0, Math.min(BUS_MAX, gbps || 0));
    return b.y + b.h - (v / BUS_MAX) * b.h;
  }

  build() {
    if (!this.size.w || !this.data) { this.renderOverlay(); this.kick(this.now()); return; }
    const P = this.pools;
    P.rects.clear(); P.dots.clear(); P.segs.clear();
    this.tiles = new Map(); this.cellAt = new Map(); this.noteAt = new Map(); this.dotAt = new Map();
    this.hotAt = new Map();
    const g = this.regions();
    this.geo = g;
    if (this.mode === "path") { this.buildPath(g); return; }
    const inset = this.inset(g.ram);
    this.geo.inset = inset;
    const reaches = [...this.data.values()].filter((r) => this.mode !== "path");
    const shown = reaches.map((r) => ({ ...r, history_tokens: r.history_tokens, token_bytes: r.token_bytes || 1 }));
    this.bands = bands(shown, g.ssd);
    const off = !this.on;
    for (const band of this.bands) {
      const r = this.data.get(band.label);
      const read = this.isRead(band.label) && !off;
      const rooms = [...r.rooms.values()].filter((x) => x.tokens > 0);
      if (!this.keep.has(band.label)) this.keep.set(band.label, new Map());
      const placed = placeBand(band, rooms, r.layout || [], this.keep.get(band.label));
      if (!Number.isFinite(placed.h0)) continue; // never draw or pick a tile at NaN
      band.h0 = placed.h0;
      band.inner = placed.inner;
      for (const t of placed.tiles) {
        const key = `${band.label}/${t.id}`;
        const room = t.room;
        const tile = { key, reach: band.label, room, x: t.x, y: t.y, w: t.w, h: t.h };
        this.tiles.set(key, tile);
        if (this.vaultMode) continue;
        if (room.asleep) {
          tile.outline = P.rects.add(R({ x: t.x, y: t.y, w: t.w, h: t.h, ol: 1, flags: F.PLATE | F.DASHED, bc: CH.ink4, b: read ? 1 : 0.4 }));
          continue;
        }
        const mm = room.members.map((id) => r.moments[id]);
        for (const c of cells(t, mm)) {
          const ck = `${band.label}/${c.id}`;
          const base = read ? STEP.cell : STEP.far * 0.5;
          const i = P.rects.add(R({ x: c.x, y: c.y, w: c.w, h: c.h, r: 0, flags: F.PLATE | F.ROWS | F.WATCHED, bc: CH.ssd, b: base, fc: CH.used }));
          this.cellAt.set(ck, { i, rect: c, tile });
          this.heat(`cell:${ck}`, P.rects, i, base);
        }
        tile.outline = P.rects.add(R({ x: t.x, y: t.y, w: t.w, h: t.h, ol: 1, flags: F.PLATE, bc: CH.ssd, b: read ? STEP.rest : STEP.far, fc: CH.ssd }));
        this.heat(`tile:${key}`, P.rects, tile.outline, read ? STEP.rest : STEP.far);
        if (room.hot && read) tile.ring = P.rects.add(R({ x: t.x - 1, y: t.y - 1, w: t.w + 2, h: t.h + 2, ol: 1, flags: F.PLATE | F.STEADY, bc: CH.ram, b: 0, fc: CH.ram, peak: STEP.resident }));
      }
    }
    if (this.vaultMode) this.buildVault();
    this.buildRam(inset);
    if (g.drawer) this.buildDrawer(g.drawer);
    if (this.selected && this.tiles.has(this.selected) && !this.vaultMode) {
      const t = this.tiles.get(this.selected);
      this.selRing = P.rects.add(R({ x: t.x - 1.5, y: t.y - 1.5, w: t.w + 3, h: t.h + 3, ol: 1, flags: F.PLATE | F.STEADY, bc: CH.select, b: 0, fc: CH.select, peak: 1 }));
    }
    for (const [k, f] of this.flares) this.reflare(k, f);
    this.grid();
    this.renderOverlay();
    this.kick(this.now());
  }

  // path mode: one answer's room, magnified with its 28 rows, the bus, and the desk; its words under the desk
  setPath(rec) {
    this.pathRec = rec;
    this.build();
  }

  buildPath(g) {
    const P = this.pools;
    const rec = this.pathRec;
    const rowH = Math.max(3, Math.min(6, Math.floor((g.ssd.h - 60) / 28)));
    const deskH = 28 * rowH;
    this.geo.inset = {
      ruler: { x: g.ram.x, y: -100, w: g.ram.w, h: 0 }, core: { x: g.ram.x, y: -100, w: 0, h: 0 },
      hot: { x: g.ram.x, y: -100, w: 0, h: 0 }, desk: { x: g.ram.x, y: g.ssd.y + 4, w: g.ram.w, h: deskH, row: rowH },
      legend: g.ssd.y + deskH + 8, roomy: false,
    };
    this.bands = [];
    const r = rec ? this.reachOf(rec.e.reach ?? rec.e.src) : null;
    const room = r?.rooms.get(rec.e.room);
    if (room) {
      const t = { x: g.ssd.x, y: g.ssd.y + 4, w: g.ssd.w, h: deskH };
      const key = `${r.label}/${room.id}`;
      const tile = { key, reach: r.label, room, ...t };
      this.tiles.set(key, tile);
      for (const c of cells(t, room.members.map((id) => r.moments[id]))) {
        const i = P.rects.add(R({ x: c.x, y: c.y, w: c.w, h: c.h, r: 0, flags: F.FORCE_ROWS | F.WATCHED, bc: CH.ssd, b: STEP.rest, fc: CH.used }));
        this.cellAt.set(`${r.label}/${c.id}`, { i, rect: c, tile });
      }
      tile.outline = P.rects.add(R({ ...t, ol: 1, bc: CH.ssd, b: STEP.rest, fc: CH.ssd }));
    }
    for (const [k, f] of this.flares) this.reflare(k, f);
    this.pick = new Map();
    this.renderOverlay();
    this.kick(this.now());
  }

  pathThreads(e, t) { // from each used moment's desk span, green threads to the three words that looked at it hardest
    if (!this.desk) return;
    const base = this.host.getBoundingClientRect();
    const words = [...this.overlay.querySelectorAll(".st-word")].map((w) => {
      const b = w.getBoundingClientRect();
      return [b.left - base.left + b.width / 2, b.top - base.top];
    });
    const used = new Set(e.used || []);
    const nodes = e.nodes || [];
    nodes.forEach((n, j) => {
      if (!used.has(n)) return; // picked-only moments get no thread: fetched and ignored
      const part = this.desk.parts.find((p) => p.node === n);
      if (!part) return;
      const order = (e.looks || []).map((row, i) => [i, row[j] || 0]).sort((a, b) => b[1] - a[1]).slice(0, 3);
      for (const [i, look] of order) {
        const to = words[i];
        if (!to || look <= 0) continue;
        this.pools.beams.add(G({ x0: part.x + part.w / 2, y0: part.y + part.h, x1: to[0], y1: to[1], w: Math.max(0.5, look * 6),
          c0: CH.used, base: STEP.hold * 0.6, peak: 1, start: t, land: t, decay: t, hl: HL.gaze }));
      }
    });
    this.kick(t + 6 * HL.gaze);
  }

  buildRam(inset) {
    const P = this.pools;
    const core = this.snap?.core || { on: false, tokens: 0 };
    const cols = Math.max(1, Math.ceil((core.tokens || 0) / 8));
    inset.core.w = core.on && core.tokens ? Math.min(this.geo.ram.w, cols * 4) : Math.min(this.geo.ram.w, 64);
    if (core.on && core.tokens) {
      this.coreIdx = P.rects.add(R({ ...inset.core, r: 1, flags: F.FORCE_ROWS | F.TICKS, bc: CH.ram, b: STEP.resident, fc: CH.ram }));
    } else {
      this.coreIdx = P.rects.add(R({ ...inset.core, ol: 1, bc: CH.ink4, b: 1, fc: CH.ram }));
    }
    // the hot shelf: least recent at the left; full width is the RAM budget less the core
    const ram = this.ram;
    const hot = inset.hot;
    if (ram && ram.budget_bytes) {
      const room = Math.max(1, ram.budget_bytes - (ram.core_bytes || 0));
      let x = hot.x;
      for (const h of ram.hot || []) {
        const w = Math.max(2, (hot.w * h.bytes) / room);
        const key = `${h.reach}/${h.room}`;
        const i = P.rects.add(R({ x, y: hot.y, w: Math.max(1, w - 1), h: hot.h, flags: F.ROWS, bc: CH.ram, b: STEP.resident, fc: CH.ram }));
        this.hotAt.set(key, { i, rect: { x, y: hot.y, w: Math.max(1, w - 1), h: hot.h } });
        x += w;
      }
      P.segs.add(G({ x0: hot.x + hot.w, y0: hot.y - 3, x1: hot.x + hot.w, y1: hot.y + hot.h + 3, w: 1, flags: S.DASHED, c0: CH.select, base: 0.3, peak: 0.3, start: -NEVER, land: -NEVER, decay: NEVER }));
    }
    // desk row ticks at the watched layers
    if (!this.small) {
      for (const L of WATCHED) {
        const y = inset.desk.y + L * inset.desk.row;
        P.rects.add(R({ x: inset.desk.x - 6, y, w: 4, h: inset.desk.row - 1, r: 0, bc: CH.ink2, b: 1 }));
      }
    }
  }

  buildDrawer(d) {
    const P = this.pools;
    const all = [];
    for (const r of this.data.values()) for (const n of r.notesList) all.push([r, n]);
    const days = all.map(([, n]) => n.day).filter((x) => x != null);
    const d0 = days.length ? Math.min(...days) : 0, d1 = days.length ? Math.max(...days) : 1;
    const strongest = Math.max(1e-6, ...all.map(([, n]) => n.strength || 0));
    for (const [r, n] of all) {
      const x = d.x + 4 + ((n.day ?? d0) - d0) / Math.max(1, d1 - d0) * (d.w - 8);
      const y = d.y + 8 + hash(n.id) * 48;
      const b = Math.max(0.1 * STEP.rest, STEP.rest * (n.strength || 0) / strongest) * (this.isRead(r.label) ? 1 : 0.4);
      const i = P.dots.add(D({ x, y, r: 1, b, fc: CH.vault, rc: CH.vault, ring: n.asleep ? STEP.hold : 0 }));
      this.dotAt.set(`${r.label}/${n.moment}`, { i, x, y });
    }
  }

  buildVault() { // vault mode: notes at their moments' positions, doors between them
    const P = this.pools;
    for (const band of this.bands) {
      const r = this.data.get(band.label);
      const inner = band.inner;
      const read = this.isRead(band.label);
      const strongest = Math.max(1e-6, ...r.notesList.map((n) => n.strength || 0));
      const pos = (mid) => {
        const xy = r.layout?.[mid];
        return xy ? [inner.x + 4 + xy[0] * (inner.w - 8), inner.y + 4 + xy[1] * (inner.h - 8)] : null;
      };
      const byId = new Map(r.notesList.map((n, k) => [k, n]));
      for (const [a, b, w] of r.doors || []) {
        const na = byId.get(a), nb = byId.get(b);
        const pa = na && pos(na.moment), pb = nb && pos(nb.moment);
        if (!pa || !pb) continue;
        const width = Math.max(0.5, Math.min(4, 0.6 + 1.4 * Math.log2(1 + w)));
        P.segs.add(G({ x0: pa[0], y0: pa[1], x1: pb[0], y1: pb[1], w: width, flags: S.PLATE0 | S.PLATE1, c0: CH.vault, base: read ? STEP.rest * 0.6 : STEP.far, peak: 0, start: -NEVER, land: -NEVER, decay: -NEVER, hl: 0 }));
      }
      const used = new Set(this.lastUsed?.reach === band.label ? this.lastUsed.used : []);
      const desk = new Set(this.lastUsed?.reach === band.label ? this.lastUsed.nodes : []);
      for (const n of r.notesList) {
        const p = n.moment != null ? pos(n.moment) : null;
        if (!p) continue;
        const room = r.moments[n.moment] ? r.rooms.get(r.moments[n.moment].room) : null;
        const b = Math.max(0.1 * STEP.rest, (STEP.hold * (n.strength || 0)) / strongest) * (read ? 1 : 0.3);
        const ring = desk.has(n.moment) ? [CH.ram, STEP.hold] : room && !room.asleep ? [CH.ssd, STEP.rest] : [CH.vault, 0];
        const i = P.dots.add(D({ x: p[0], y: p[1], r: 2 + Math.sqrt(n.into || 0), flags: 1, b, fc: CH.used,
          hl: used.has(n.moment) ? -1 : 0, peak: used.has(n.moment) ? STEP.hold : 0, rc: ring[0], ring: ring[1] }));
        this.noteAt.set(`${band.label}/${n.moment}`, { i, x: p[0], y: p[1], r: 2 + Math.sqrt(n.into || 0), note: n, reach: band.label });
      }
    }
  }

  // infinite persistence: a touched mark keeps a base that grows with its hits, in the hue it was touched in
  heat(key, pool, i, base) {
    if (this.api.persistence.peek() !== "infinite") return;
    const h = this.touched.get(key);
    if (!h) return;
    const b = 0.22 + 0.38 * Math.min(1, Math.log2(1 + h.hits) / 4);
    if (b > base) pool.put(i, 7, [h.chan, b]);
  }

  touch(key, chan) {
    const h = this.touched.get(key) || { chan, hits: 0 };
    h.chan = chan;
    h.hits++;
    this.touched.set(key, h);
  }

  // -- marks

  hl(ms) {
    const p = this.api.persistence.peek();
    return p === "off" ? Math.min(ms, 120) : ms;
  }

  flare(key, { fc, t, hl, peak = 1 }) {
    const f = { fc, t, hl: this.hl(hl), peak };
    this.flares.set(key, f);
    this.reflare(key, f);
    if (key.startsWith("cell:") || key.startsWith("tile:")) this.touch(key, fc);
    this.kick(t + 6 * f.hl);
  }

  reflare(key, f) {
    if (f.hl > 0 && this.now() > f.t + 8 * f.hl) { this.flares.delete(key); return; }
    const [kind, rest] = [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)];
    let i = null;
    if (kind === "cell") i = this.cellAt.get(rest)?.i;
    else if (kind === "tile") i = this.tiles.get(rest)?.outline;
    else if (kind === "hot") i = this.hotAt.get(rest)?.i;
    else if (kind === "core") i = this.coreIdx;
    if (i == null) return;
    this.pools.rects.put(i, 9, [f.fc, f.t, f.hl]);
    this.pools.rects.put(i, 12, [f.peak]);
  }

  at(t, fn, settle = false) { // a step at display time t, kept in time order (inserted, never sorted again)
    const q = this.queue;
    let lo = 0, hi = q.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (q[mid].t <= t) lo = mid + 1; else hi = mid; }
    q.splice(lo, 0, { t, fn, settle });
    this.kick(t);
  }

  // -- events

  event(e) {
    if (!this.data || !e || !this.visible) return; // a screen shown again loads a fresh snapshot
    if (this.pausedAt !== null) { this.held.push(() => this.event(e)); return; }
    if (e.type === "remember") this.remembered(e);
    else if (e.type === "sleep" || e.type === "wake") this.slept(e);
  }

  remembered(e) {
    const r = this.reachOf(e.reach ?? e.src);
    if (!r || e.moment == null) return;
    if (!r.moments[e.moment]) {
      let room = r.rooms.get(e.room);
      if (!room) { room = { id: e.room, tokens: 0, asleep: false, hot: false, members: [] }; r.rooms.set(e.room, room); }
      r.moments[e.moment] = { id: e.moment, room: e.room, day: e.day, tokens: e.tokens, start: room.tokens, text: null };
      room.members.push(e.moment);
      room.tokens += e.tokens || 0;
      r.history_tokens = (r.history_tokens || 0) + (e.tokens || 0);
      this.build();
    }
    const now = this.now();
    const tile = this.tiles.get(`${r.label}/${e.room}`);
    const desk = this.geo?.inset?.desk;
    if (tile && desk) { // a dashed blue write from RAM to the room, right to left
      this.pools.beams.add(G({ x0: desk.x, y0: desk.y + desk.h / 2, x1: tile.x + tile.w, y1: tile.y + tile.h / 2, w: 1, flags: S.DASHED | S.PLATE1, c0: CH.ssd,
        start: now, land: now + HL.write, decay: now + HL.write, hl: this.hl(HL.write) }));
    }
    this.flare(`cell:${r.label}/${e.moment}`, { fc: CH.ssd, t: now + HL.write, hl: HL.write, peak: 1 });
    this.flare(`tile:${r.label}/${e.room}`, { fc: CH.ssd, t: now + HL.write, hl: HL.write, peak: 1 });
  }

  slept(e) {
    const r = this.reachOf(e.reach ?? e.src);
    if (!r) return;
    for (const rid of e.rooms || []) {
      const room = r.rooms.get(rid);
      if (room) room.asleep = e.type === "sleep";
    }
    for (const n of r.notesList) {
      const room = n.moment != null && r.moments[n.moment] ? r.rooms.get(r.moments[n.moment].room) : null;
      if (room && (e.rooms || []).includes(room.id)) n.asleep = e.type === "sleep";
    }
    this.build();
    const now = this.now();
    for (const rid of e.rooms || []) this.flare(`tile:${r.label}/${rid}`, { fc: e.type === "sleep" ? CH.ink4 : CH.ssd, t: now, hl: HL.sleep, peak: 1 });
  }

  // the desk for one answer: header, core, the room's moments, the closest moments as words, the question
  deskSpans(e, m, r) {
    const desk = this.geo.inset.desk;
    const header = this.snap?.header_tokens;
    const core = e.core_tokens ?? (this.snap?.core?.on ? this.snap.core.tokens : 0) ?? 0;
    const room = r.rooms.get(e.room);
    const members = room ? room.members : [];
    const tok = (id) => r.moments[id]?.tokens || 1;
    const roomTok = members.reduce((a, id) => a + tok(id), 0);
    const words = (e.closest || []).map((id) => [id, tok(id)]);
    const wordTok = words.reduce((a, [, n]) => a + n, 0);
    const known = (header || 0) + core + roomTok + wordTok;
    const question = m?.context_tokens ? Math.max(1, m.context_tokens - known) : 40;
    const parts = [];
    if (header) parts.push({ kind: "header", tokens: header });
    if (core) parts.push({ kind: "core", tokens: core });
    for (const id of members) parts.push({ kind: e.asleep ? "wordsroom" : "room", node: id, tokens: tok(id) });
    for (const [id, n] of words) parts.push({ kind: "words", node: id, tokens: n });
    parts.push({ kind: "question", tokens: question });
    const total = parts.reduce((a, p) => a + p.tokens, 0);
    // moment spans are at least 2 px wide; everything else shares what is left
    const minW = 2;
    let scale = desk.w / total;
    const small = parts.filter((p) => p.node != null && p.tokens * scale < minW);
    if (small.length) {
      const rest = parts.filter((p) => !small.includes(p)).reduce((a, p) => a + p.tokens, 0);
      scale = Math.max(0.01, (desk.w - small.length * minW) / Math.max(1, rest));
    }
    let x = desk.x;
    for (const p of parts) {
      const w = p.node != null ? Math.max(minW, p.tokens * scale) : p.tokens * scale;
      p.x = x; p.w = Math.max(0.5, w - (p.node != null && w >= 3 ? 1 : 0)); p.y = desk.y; p.h = desk.h;
      x += w;
    }
    return { parts, total, question, timedContext: !!m?.context_tokens };
  }

  toScreen(x, y) { return [x * this.view.k + this.view.x, y * this.view.k + this.view.y]; }

  // -- one answer, step by step (DIRECTION.md, "One answer, step by step")

  playAnswer({ e, m }, { replay = false, label = null } = {}) {
    if (!this.data || !this.geo || !e) return;
    if (this.pausedAt !== null) { this.held.push(() => this.playAnswer({ e, m }, { replay, label })); return; }
    if (this.api.measuring.peek()) return;
    const r = this.reachOf(e.reach ?? e.src);
    if (!r) return;
    const P = this.pools;
    P.dyn.clear();
    P.beams.clear();
    const f = this.api.timebase.peek();
    const reduced = this.api.reducedMotion.peek();
    const now = this.now();
    const t0 = now + 16;
    const s = e.seconds || {};
    const ms = (x) => (x || 0) * 1000 * f;
    const tCore = t0 + ms(s.choose);
    const tFetch = tCore + ms(s.core);
    const tWake = tFetch;
    const fetchEnd = tFetch + ms(s.wake) + Math.max(16, ms(s.fetch));
    const tDesk = fetchEnd;
    const deskMs = Math.max(16, ms(s.desk));
    const tDeskEnd = tDesk + deskMs;
    const wait = e.wait_s ?? m?.first_word_s ?? 0;
    const tFirst = Math.max(tDeskEnd, t0 + ms(wait));
    const words = e.words || [];
    const total = m?.total_s;
    const timed = !!m && total > wait && words.length > 0;
    const wordAt = (i) => (timed ? t0 + ms(wait + (i * (total - wait)) / words.length) : tFirst + i * 50 * f);
    const tEnd = wordAt(words.length);
    const key = `${r.label}/${e.room}`;
    const tile = this.tiles.get(key);
    const { parts } = this.deskSpans(e, m, r);
    this.desk = { e, m, r, parts };
    this.lastUsed = { reach: r.label, used: e.used || [], nodes: e.nodes || [] };
    this.playing = { label: label || (replay ? `replay · answer ${e.i ?? ""}` : "just now"), until: tEnd + 600, timed,
      reach: r.label, room: e.room, e, m };
    // 1 choose
    if (tile) this.flare(`tile:${key}`, { fc: CH.ssd, t: t0, hl: HL.choose, peak: 1 });
    // 2 core
    if (this.snap?.core?.on && this.snap.core.tokens) this.flare("core:", { fc: CH.ram, t: tCore, hl: HL.core, peak: 1 });
    // 4 the desk: spans appear as they are laid (room left to right, then words hatched, then the question)
    const desk = this.geo.inset.desk;
    const off = this.mode === "path" ? NEVER : tEnd + 300;
    const spanAt = new Map();
    for (const p of parts) {
      let spec;
      if (p.kind === "header") spec = { bc: CH.ink4, b: 1, on: tDesk };
      else if (p.kind === "core") spec = { bc: CH.ram, b: STEP.resident, on: tDesk };
      else if (p.kind === "room") spec = { bc: CH.ram, b: STEP.hold, on: tDesk, reveal: deskMs };
      else if (p.kind === "wordsroom" || p.kind === "words") spec = { bc: CH.ram, b: STEP.hold, on: tDeskEnd, flags: F.HATCH };
      else spec = { bc: CH.ink4, b: 1, on: tDeskEnd };
      const i = P.dyn.add(R({ x: p.x, y: p.y, w: p.w, h: p.h, r: 0, flags: F.FORCE_ROWS | F.WATCHED | (spec.flags || 0), bc: spec.bc, b: spec.b,
        fc: CH.used, on: reduced ? spec.on : spec.on, off, drain: 200, reveal: reduced ? 0 : spec.reveal || 0 }));
      if (p.node != null) {
        if (!spanAt.has(p.node)) spanAt.set(p.node, []);
        spanAt.get(p.node).push(i);
      }
      if (p.kind === "question") { // the question lights --ink-3 until the first word
        P.dyn.add(R({ x: p.x, y: p.y, w: p.w, h: p.h, r: 0, flags: F.FORCE_ROWS, bc: CH.ink3, b: 1, on: tDeskEnd, off: tFirst, drain: 200 }));
      }
    }
    this.spanAt = spanAt;
    // 3 fetch, by tier
    const roomSpan = parts.filter((p) => p.kind === "room" || p.kind === "wordsroom");
    const target = roomSpan.length ? [roomSpan[0].x, desk.y + desk.h / 2] : [desk.x, desk.y + desk.h / 2];
    const tier = e.tier || (e.asleep ? "vault" : e.seconds?.fetch > 0 ? "ssd" : null);
    if (tile && (tier === "ssd" || (tier === "vault" && s.wake))) {
      const gbps = e.read_bytes && s.fetch > 0 ? e.read_bytes / s.fetch / GB : m?.gbps;
      const thick = Math.max(1, Math.min(40, (e.read_bytes || 0) / MB2));
      const by = this.busY(gbps);
      const home = [tile.x + tile.w, tile.y + tile.h / 2];
      const a = this.toScreen(...home);
      const b0 = [this.geo.bus.x + 6, by], b1 = [this.geo.bus.x + this.geo.bus.w - 6, by];
      const pts = [a, b0, b1, target];
      const lens = [0, 1, 2].map((k) => Math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]));
      const L = lens.reduce((x, y) => x + y, 0) || 1;
      const start = tWake + ms(s.wake);
      const land = reduced ? start : start + Math.max(16, ms(s.fetch));
      if (tier === "vault" && s.wake) { // the dashed write first: the room's notes written again
        P.beams.add(G({ x0: desk.x, y0: desk.y + desk.h / 2, x1: home[0], y1: home[1], w: 1, flags: S.DASHED | S.PLATE1, c0: CH.ssd,
          start: tWake, land: tWake + ms(s.wake), decay: tWake + ms(s.wake), hl: this.hl(HL.wake) }));
      }
      let acc = 0;
      const chans = [[CH.ssd, CH.ssd], [CH.ssd, CH.ram], [CH.ram, CH.ram]];
      for (let k = 0; k < 3; k++) {
        const s0 = start + ((land - start) * acc) / L;
        acc += lens[k];
        const s1 = start + ((land - start) * acc) / L;
        const from = k === 0 ? home : pts[k];
        P.beams.add(G({ x0: from[0], y0: from[1], x1: pts[k + 1][0], y1: pts[k + 1][1], w: thick, flags: k === 0 ? S.PLATE0 : 0,
          c0: chans[k][0], c1: chans[k][1], start: s0, land: s1, decay: land, hl: this.hl(HL.read) }));
      }
      this.showChip({ bytes: e.read_bytes, ms: (s.fetch || 0) * 1000, gbps, f, x: (b0[0] + b1[0]) / 2, y: by, from: start, until: land + 1600 });
      this.kick(land + 6 * HL.read);
    } else if (tier === "ram") {
      const hot = this.hotAt.get(key);
      if (hot) {
        this.flare(`hot:${key}`, { fc: CH.ram, t: tFetch, hl: HL.ram, peak: 1 });
        const span = roomSpan[0];
        if (span) { // the copy slides into the desk: 240 ms, linear; the only sliding motion in the app
          P.dyn.add(R({ x: span.x, y: hot.rect.y, w: Math.min(hot.rect.w, desk.w), h: hot.rect.h, r: 0, bc: CH.ram, b: STEP.event,
            on: tFetch, off: tFetch + 240, drain: 1, dx: hot.rect.x - span.x, dy: 0, move: reduced ? 0 : 240 }));
        }
      }
      this.showChip({ ram: true, x: this.geo.bus.x + this.geo.bus.w / 2, y: this.geo.bus.y + this.geo.bus.h / 2, from: tFetch, until: tFetch + 1600 });
    } else if (tier === "vault" || e.asleep) { // asleep: the room's notes come in as violet threads, no beam
      for (const id of tile ? tile.room.members : []) {
        const dot = this.dotAt.get(`${r.label}/${id}`);
        if (!dot) continue;
        P.beams.add(G({ x0: dot.x, y0: dot.y, x1: target[0], y1: target[1], w: 0.5, c0: CH.vault, start: tFetch, land: tFetch, decay: tFetch, hl: this.hl(HL.words) }));
      }
    }
    // the home tile keeps an amber ring while its copy is on the desk
    if (tile) {
      P.dyn.add(R({ x: tile.x - 1, y: tile.y - 1, w: tile.w + 2, h: tile.h + 2, ol: 1.5, flags: F.PLATE | F.STEADY, bc: CH.ram, b: 0, fc: CH.ram, peak: STEP.hold, on: tDesk, off, drain: 200 }));
    }
    // words in: violet hairlines from the closest moments' cells to the desk's words span
    const wordsSpan = parts.find((p) => p.kind === "words");
    for (const id of e.closest || []) {
      const c = this.cellAt.get(`${r.label}/${id}`);
      if (!c || !wordsSpan) continue;
      P.beams.add(G({ x0: c.rect.x + c.rect.w / 2, y0: c.rect.y + c.rect.h / 2, x1: wordsSpan.x, y1: desk.y + desk.h / 2, w: 0.5, flags: S.PLATE0, c0: CH.vault, start: tDeskEnd, land: tDeskEnd, decay: tDeskEnd, hl: this.hl(HL.words) }));
    }
    // 6 decode: each word's looks on the watched rows of each node's spans, and on its home cell (only on show)
    const nodes = e.nodes || [];
    const looks = e.looks || [];
    for (let i = 0; this.visible && i < words.length; i++) {
      const at = wordAt(i);
      this.at(at, () => {
        const row = looks[i] || [];
        const top = Math.max(1e-9, ...row);
        for (let j = 0; j < nodes.length; j++) {
          const v = (row[j] || 0) / top;
          if (v < 0.02) continue;
          for (const k of spanAt.get(nodes[j]) || []) P.dyn.put(k, 10, [at, HL.gaze, v]);
          this.flare(`cell:${r.label}/${nodes[j]}`, { fc: CH.used, t: at, hl: HL.gaze, peak: v });
        }
        this.onWord(i, e);
        if (this.mode === "path") { this.playingWord = i; this.renderOverlay(); }
        this.kick(at + 6 * HL.gaze);
      });
    }
    // 7 settle: used nodes hold green, picked-only nodes keep amber rings; the desk drains
    const settle = () => {
      const used = new Set(e.used || []);
      for (const n of nodes) {
        const c = this.cellAt.get(`${r.label}/${n}`);
        if (!c) continue;
        if (used.has(n)) this.flare(`cell:${r.label}/${n}`, { fc: CH.used, t: tEnd, hl: HL.used, peak: STEP.hold });
        else if (this.api.persistence.peek() !== "off") {
          P.dyn.add(R({ x: c.rect.x, y: c.rect.y, w: c.rect.w, h: c.rect.h, ol: 1.5, r: 0, flags: F.PLATE, bc: CH.ram, b: 0, fc: CH.ram, t: tEnd, hl: HL.used, peak: STEP.hold, drain: 1 }));
        }
      }
      this.onWord(-1, e);
      if (this.mode === "path") this.pathThreads(e, tEnd);
      if (this.vaultMode) this.build();
    };
    if (this.visible) this.at(tEnd, settle, true);
    else settle();
    this.kick(tEnd + 6 * HL.used);
    this.renderOverlay();
  }

  showChip({ bytes, ms, gbps, f = 1, x, y, from, until, ram = false }) {
    clearTimeout(this.chipTimer);
    const show = () => {
      const pieces = ram ? ["RAM hit", `0${THIN}B from SSD`]
        : [fmtBytes(bytes), `${ms >= 10 ? ms.toFixed(0) : ms.toFixed(1)}${THIN}ms`, gbps ? `${gbps.toFixed(2)}${THIN}GB/s` : "—"];
      if (!ram && f > 1) pieces.push(`shown ×${f}`);
      this.chip.textContent = pieces.join(" · ");
      this.chip.hidden = false;
      const w = this.chip.offsetWidth;
      this.chip.style.left = `${Math.max(2, Math.min(this.size.w - w - 2, x - w / 2))}px`;
      this.chip.style.top = `${Math.max(2, y - 22)}px`;
      this.chipTimer = setTimeout(() => { this.chip.hidden = true; }, Math.max(400, until - this.now()));
    };
    const wait = from - this.now();
    if (wait > 8) this.chipTimer = setTimeout(show, wait); else show();
  }

  // a word hovered in the chat: its top node flares here
  nodeFlare(reach, mid, used = false) {
    const r = this.reachOf(reach);
    if (!r) return;
    const now = this.now();
    this.flare(`cell:${r.label}/${mid}`, { fc: used ? CH.used : CH.ram, t: now, hl: HL.choose, peak: 1 });
  }

  select(key) {
    this.selected = key;
    this.build();
  }

  // -- the frame loop

  kick(until) {
    this.busyUntil = Math.max(this.busyUntil, until);
    if (this.raf == null && !this.inTick && this.visible) this.raf = requestAnimationFrame((ts) => this.tick(ts));
  }

  tick(ts) {
    this.raf = null;
    if (!this.visible) return;
    if (ts - this.lastDraw < 15.5) { // at most 60 frames a second, even on a 120 Hz screen
      this.raf = requestAnimationFrame((t) => this.tick(t));
      return;
    }
    this.lastDraw = ts;
    const now = this.now();
    const measuring = !!this.api.measuring.peek();
    this.inTick = true; // what runs here asks for frames through busyUntil, not by scheduling its own
    try {
      let due = 0;
      while (due < this.queue.length && this.queue[due].t <= now) due++;
      const steps = due ? this.queue.splice(0, due) : [];
      for (const q of steps) if (q.settle || now - q.t <= 6 * HL.gaze) q.fn(); // a word that late would be dark already
      for (const [kind, pool] of Object.entries(this.pools)) pool.flush(this.gl, kind);
      const k = this.view;
      const clip = this.geo ? [this.geo.ssd.x - 1, this.geo.ssd.y - LABEL_H - 2, this.geo.ssd.x + this.geo.ssd.w + 1, this.geo.ssd.y + this.geo.ssd.h + 1] : [0, 0, 1e6, 1e6];
      this.gl.draw({ now, view: [k.k, k.x, k.y], clip, reduced: this.api.reducedMotion.peek(), halo: !this.small || this.mode === "path",
        blank: measuring || !this.data });
      this.api.frame();
      if (this.playing && now > this.playing.until) { this.playing = null; this.renderOverlay(); }
    } finally {
      this.inTick = false;
    }
    const busy = !measuring && this.pausedAt === null && (now < this.busyUntil || this.queue.length || this.dragging);
    if (busy && this.raf == null) this.raf = requestAnimationFrame((t) => this.tick(t));
  }

  show() {
    this.visible = true;
    this.layout();
    this.kick(this.now());
  }

  hide() {
    this.visible = false;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = null;
    this.tip.hidden = true;
    const left = this.queue; // the words left are dropped; the answer settles now
    this.queue = [];
    for (const q of left) if (q.settle) q.fn();
  }

  destroy() {
    this.hide();
    this.ro.disconnect();
    this.gl.destroy();
  }

  // -- picking: a CPU grid of 32 px cells over tiles and dots, in plate coordinates

  grid() {
    this.pick = new Map();
    const add = (item, x0, y0, x1, y1) => {
      for (let gx = Math.floor(x0 / 32); gx <= Math.floor(x1 / 32); gx++) for (let gy = Math.floor(y0 / 32); gy <= Math.floor(y1 / 32); gy++) {
        const k = `${gx},${gy}`;
        if (!this.pick.has(k)) this.pick.set(k, []);
        this.pick.get(k).push(item);
      }
    };
    if (this.vaultMode) for (const n of this.noteAt.values()) add({ kind: "note", ...n }, n.x - n.r, n.y - n.r, n.x + n.r, n.y + n.r);
    else for (const t of this.tiles.values()) add({ kind: "tile", ...t }, t.x, t.y, t.x + t.w, t.y + t.h);
  }

  hit(px, py) {
    const g = this.geo;
    if (!g) return null;
    if (px >= g.ssd.x && px <= g.ssd.x + g.ssd.w && py >= g.ssd.y - LABEL_H && py <= g.ssd.y + g.ssd.h) {
      const x = (px - this.view.x) / this.view.k, y = (py - this.view.y) / this.view.k;
      const list = this.pick?.get(`${Math.floor(x / 32)},${Math.floor(y / 32)}`) || [];
      for (const it of list) {
        if (it.kind === "tile" && x >= it.x - 1 && x <= it.x + it.w + 1 && y >= it.y - 1 && y <= it.y + it.h + 1) return it;
        if (it.kind === "note" && Math.hypot(x - it.x, y - it.y) <= it.r + 2) return it;
      }
      return null;
    }
    const d = this.geo.inset?.desk;
    if (this.desk && d && px >= d.x && px <= d.x + d.w && py >= d.y && py <= d.y + d.h) {
      const p = this.desk.parts.find((q) => px >= q.x && px <= q.x + q.w + 1);
      return p ? { kind: "span", part: p } : null;
    }
    if (g.drawer && py >= g.drawer.y && py <= g.drawer.y + g.drawer.h && px >= g.drawer.x && px <= g.drawer.x + g.drawer.w) return { kind: "drawer" };
    return null;
  }

  bindPointer() {
    const c = this.canvas;
    let drag = null;
    c.addEventListener("pointermove", (ev) => {
      const b = c.getBoundingClientRect();
      const px = ev.clientX - b.left, py = ev.clientY - b.top;
      if (drag) {
        this.view.x = drag.vx + (px - drag.x);
        this.view.y = drag.vy + (py - drag.y);
        drag.moved = drag.moved || Math.hypot(px - drag.x, py - drag.y) > 3;
        this.clampView();
        this.kick(this.now());
        return;
      }
      this.hover(this.hit(px, py), px, py);
    });
    c.addEventListener("pointerleave", () => { this.tip.hidden = true; });
    c.addEventListener("pointerdown", (ev) => {
      const b = c.getBoundingClientRect();
      const px = ev.clientX - b.left, py = ev.clientY - b.top;
      const g = this.geo;
      if (!g || this.small) return;
      if (px >= g.ssd.x && px <= g.ssd.x + g.ssd.w && py >= g.ssd.y && py <= g.ssd.y + g.ssd.h) {
        drag = { x: px, y: py, vx: this.view.x, vy: this.view.y, moved: false };
        this.dragging = true;
        c.setPointerCapture(ev.pointerId);
      }
    });
    c.addEventListener("pointerup", (ev) => {
      const b = c.getBoundingClientRect();
      const px = ev.clientX - b.left, py = ev.clientY - b.top;
      const was = drag;
      drag = null;
      this.dragging = false;
      if (was?.moved) return;
      const it = this.hit(px, py);
      if (it?.kind === "tile") this.onSelect(it);
      else if (it?.kind === "note") this.onNote(it);
      else if (it?.kind === "drawer") this.onVault();
      else if (!it && !this.small) this.onSelect(null);
    });
    c.addEventListener("wheel", (ev) => {
      const g = this.geo;
      if (!g || this.small) return;
      const b = c.getBoundingClientRect();
      const px = ev.clientX - b.left, py = ev.clientY - b.top;
      if (!(px >= g.ssd.x && px <= g.ssd.x + g.ssd.w && py >= g.ssd.y && py <= g.ssd.y + g.ssd.h)) return;
      ev.preventDefault();
      const k0 = this.view.k;
      const k1 = Math.max(1, Math.min(16, k0 * Math.exp(-ev.deltaY * 0.002)));
      this.view.x = px - ((px - this.view.x) * k1) / k0;
      this.view.y = py - ((py - this.view.y) * k1) / k0;
      this.view.k = k1;
      this.clampView();
      this.kick(this.now());
      this.renderOverlay();
    }, { passive: false });
    c.addEventListener("dblclick", () => { this.view = { k: 1, x: 0, y: 0 }; this.kick(this.now()); this.renderOverlay(); });
  }

  clampView() {
    const g = this.geo?.ssd;
    if (!g) return;
    const k = this.view.k;
    if (k <= 1) { this.view = { k: 1, x: 0, y: 0 }; return; }
    // keep the plate covering its own region
    const minX = g.x + g.w - (g.x + g.w) * k, maxX = g.x - g.x * k;
    const minY = g.y + g.h - (g.y + g.h) * k, maxY = g.y - g.y * k;
    this.view.x = Math.max(minX, Math.min(maxX, this.view.x));
    this.view.y = Math.max(minY, Math.min(maxY, this.view.y));
  }

  hover(it, px, py) {
    if (!it || it.kind === "drawer") {
      this.tip.hidden = true;
      this.canvas.style.cursor = it?.kind === "drawer" ? "pointer" : "";
      return;
    }
    this.canvas.style.cursor = it.kind === "span" ? "" : "pointer";
    let text = "";
    if (it.kind === "tile") {
      const r = this.data.get(it.reach);
      const st = r?.stats || {};
      const room = it.room;
      const reads = st.reads?.[room.id] ?? st.reads?.[String(room.id)] ?? 0;
      const share = st.last_share?.[room.id] ?? st.last_share?.[String(room.id)];
      text = [`room ${room.id}`, `${room.members.length} moments`, `${room.tokens.toLocaleString("en-US")}${THIN}tok`,
        room.asleep ? "asleep" : fmtBytes(room.tokens * (r.token_bytes || 0)), `read ${reads}×`, `last share ${share == null ? "—" : share.toFixed(2)}`].join(" · ");
    } else if (it.kind === "note") {
      const n = it.note;
      text = `${n.id} · day ${n.day ?? "—"} · strength ${(n.strength ?? 0).toFixed(2)} · ${n.into} links in`;
    } else if (it.kind === "span") {
      const p = it.part;
      if (p.node != null && this.desk) {
        const e = this.desk.e;
        const j = (e.nodes || []).indexOf(p.node);
        const share = j >= 0 ? e.share?.[j] : null;
        const words = this.desk.r.moments[p.node]?.text || "";
        text = `moment ${p.node} · ${p.kind === "room" ? "notes" : "words"} · share ${share == null ? "—" : share.toFixed(2)}${words ? ` · ${words.slice(0, 90)}` : ""}`;
      } else {
        text = `${p.kind} · ${p.tokens.toLocaleString("en-US")}${THIN}tok${p.kind === "question" && !this.desk?.m?.context_tokens ? " est." : ""}`;
      }
    }
    this.tip.textContent = text;
    this.tip.hidden = false;
    const w = this.tip.offsetWidth;
    this.tip.style.left = `${Math.max(4, Math.min(this.size.w - w - 4, px + 12))}px`;
    this.tip.style.top = `${Math.max(4, py + 14)}px`;
  }

  // -- labels, the ruler, the bus scale and the corners: DOM over the canvas

  renderOverlay() {
    const { html, render } = this.api.ui;
    const g = this.geo;
    if (!g || !this.size.w) { render(null, this.overlay); return; }
    const measuring = this.api.measuring.peek();
    if (measuring) {
      render(html`<div class="st-measuring t-label">measuring · view paused</div>`, this.overlay);
      return;
    }
    if (!this.data || !this.data.size) {
      render(html`<div class="st-center t-readout dim">no memory open yet</div>`, this.overlay);
      return;
    }
    if (this.mode === "path") { this.renderPath(); return; }
    const small = this.small;
    const sum = (fn) => [...this.data.values()].reduce((a, r) => a + fn(r), 0);
    const rooms = sum((r) => [...r.rooms.values()].filter((x) => x.tokens > 0).length);
    const asleep = sum((r) => [...r.rooms.values()].filter((x) => x.asleep).length);
    const bytes = sum((r) => r.room_bytes || 0);
    const inset = g.inset;
    const sys = this.api.sys.peek();
    const total = sys?.total_bytes;
    const proc = sys?.process_bytes;
    const other = sys ? Math.max(0, (sys.used_bytes || 0) - (proc || 0)) : 0;
    const weights = this.snap?.weights_bytes || 0;
    const camr = (this.ram?.used_bytes || 0) + (this.desk ? (this.desk.parts.reduce((a, p) => a + p.tokens, 0)) * (this.snap?.token_bytes || 0) : 0);
    const rx = (b) => (total ? (b / total) * inset.ruler.w : 0);
    const segs = [];
    let at = 0;
    for (const [cls, b] of [["r-other", other], ["r-weights", weights], ["r-camr", camr]]) {
      if (b > 0) segs.push(html`<rect class=${cls} x=${rx(at)} y="0" width=${Math.max(1, rx(b))} height=${inset.ruler.h} />`);
      at += b;
    }
    const ticks = [];
    if (total && !small) {
      for (let gb = 0; gb * GIB <= total + 1; gb++) {
        const x = rx(gb * GIB);
        ticks.push(html`<line class="r-tick" x1=${x + 0.5} x2=${x + 0.5} y1=${inset.ruler.h} y2=${inset.ruler.h + (gb % 4 ? 3 : 6)} />`);
        if (gb % 4 === 0) ticks.push(html`<text class="r-num" x=${x} y=${inset.ruler.h + 15} text-anchor=${gb ? "middle" : "start"}>${gb}</text>`);
      }
    }
    const e0 = rx(other + weights), e1 = rx(other + weights + camr);
    const shelfPerGB = this.ram?.budget_bytes ? inset.hot.w / ((this.ram.budget_bytes - (this.ram.core_bytes || 0)) / GB) : null;
    const rulerPerGB = total ? inset.ruler.w / (total / GB) : null;
    const zoom = shelfPerGB && rulerPerGB ? Math.round(shelfPerGB / rulerPerGB) : null;
    const core = this.snap?.core || { on: false };
    const tb = this.snap?.token_bytes || 0;
    const hot = this.ram?.hot || [];
    const hotBytes = hot.reduce((a, h) => a + h.bytes, 0);
    const desk = this.desk;
    const deskTok = desk ? desk.parts.reduce((a, p) => a + p.tokens, 0) : null;
    const est = desk && !desk.m?.context_tokens ? " est." : ""; // the question's tokens were made up
    const hist = sum((r) => r.history_tokens || 0);
    const m = desk?.m;
    const e = desk?.e;
    const read = e?.read_bytes;
    const fetchMs = e?.seconds?.fetch != null ? e.seconds.fetch * 1000 : null;
    const gbps = read && e?.seconds?.fetch > 0 ? read / e.seconds.fetch / GB : null;
    const share = m?.read_share;
    const tb_ = this.api.timebase.peek();
    const pers = this.api.persistence.peek();
    const busTicks = [0, 2, 4, 6, 8].map((v) => html`<span class="st-bus-n t-label" style=${{ left: `${g.bus.x}px`, top: `${this.busY(v) - 7}px` }}>${v}</span>`);
    const busLines = [];
    for (let v = 0; v <= BUS_MAX; v++) busLines.push(html`<i class="st-bus-tick" style=${{ left: `${g.bus.x + (small ? 0 : 14)}px`, top: `${this.busY(v)}px` }}></i>`);
    const band = this.bands.map((b) => {
      const r = this.data.get(b.label);
      const n = [...r.rooms.values()].filter((x) => x.tokens > 0).length;
      const far = !this.isRead(b.label) || !this.on;
      return this.bands.length > 1 || this.mode === "live"
        ? html`<span class=${`st-band t-label${far ? " far" : ""}`} style=${{ left: `${b.x}px`, top: `${b.y}px` }}>${b.label} · ${n} rooms${far ? " · not read" : ""}</span>` : null;
    });
    const deskLabels = !small && inset ? WATCHED.map((L) => html`<span class="st-row t-label" style=${{ left: `${g.ram.x}px`, top: `${inset.desk.y + L * inset.desk.row - 5}px` }}>L${L}</span>`) : null;
    render(html`
      ${!this.on ? html`<div class="st-center t-readout dim">memory off</div>` : null}
      <span class="st-plate t-label" style=${{ left: `${g.ssd.x}px`, top: `${g.pad - 2}px` }}>
        SSD · ${rooms.toLocaleString("en-US")} rooms · ${fmtBytes(bytes)}${asleep ? ` · ${asleep} asleep` : ""}${this.view.k > 1 ? ` · ×${this.view.k.toFixed(1)}` : ""}</span>
      ${band}
      ${small ? null : html`<span class="st-plate t-label" style=${{ left: `${g.bus.x}px`, top: `${g.pad - 2}px` }}>bus · GB/s</span>`}
      ${small ? null : busTicks}${busLines}
      <span class="st-plate t-label" style=${{ left: `${g.ram.x}px`, top: `${g.pad - 2}px` }}>
        RAM ${total ? fmtRam(total) : "—"}${small ? "" : ` · ${fmtRam(proc)} this process${m?.peak_ram_bytes ? ` · peak ${fmtRam(m.peak_ram_bytes)}` : ""}`}</span>
      <svg class="st-ruler" style=${{ left: `${inset.ruler.x}px`, top: `${inset.ruler.y}px` }} width=${inset.ruler.w + 2} height=${inset.ruler.h + 40}>
        <rect class="r-free" x="0.5" y="0.5" width=${Math.max(0, inset.ruler.w - 1)} height=${inset.ruler.h - 1} />
        ${segs}
        <line class="r-end" x1=${inset.ruler.w - 0.5} x2=${inset.ruler.w - 0.5} y1="0" y2=${inset.ruler.h + 6} />
        ${ticks}
        ${camr > 0 && !small ? html`
          <line class="r-zoom" x1=${e0} y1=${inset.ruler.h} x2="0" y2=${inset.ruler.h + 28} />
          <line class="r-zoom" x1=${Math.max(e1, e0 + 1)} y1=${inset.ruler.h} x2=${inset.ruler.w} y2=${inset.ruler.h + 28} />` : null}
      </svg>
      ${zoom && !small ? html`<span class="st-zoom t-label" style=${{ left: `${inset.ruler.x + inset.ruler.w}px`, top: `${inset.ruler.y + inset.ruler.h + 16}px` }}>×${zoom}</span>` : null}
      <span class="st-sub t-label" style=${{ left: `${inset.core.x}px`, top: `${inset.core.y - (small ? 13 : 16)}px` }}>
        ${core.on ? (core.tokens ? `core ${core.tokens}${THIN}tok · ${fmtBytes(core.bytes)}` : "core · empty") : "core · off"}</span>
      <span class="st-sub t-label" style=${{ left: `${inset.hot.x}px`, top: `${inset.hot.y - (small ? 13 : 16)}px` }}>
        ${this.ram ? `hot ${hot.length} rooms · ${fmtBytes(hotBytes)} / ${fmtBytes((this.ram.budget_bytes || 0) - (this.ram.core_bytes || 0))}` : "hot · not recorded"}</span>
      <span class="st-sub t-label" style=${{ left: `${inset.desk.x}px`, top: `${inset.desk.y - (small ? 13 : 16)}px` }}>
        desk${desk ? ` · ${deskTok.toLocaleString("en-US")}${THIN}tok${est}` : " · empty"}</span>
      ${!desk ? html`<span class="st-desk-empty t-readout dim" style=${{ left: `${inset.desk.x}px`, top: `${inset.desk.y + inset.desk.h / 2 - 8}px`, width: `${inset.desk.w}px` }}>no answer yet</span>` : null}
      ${deskLabels}
      ${small ? null : html`<span class="st-legend t-label" style=${{ left: `${inset.desk.x}px`, top: `${inset.legend}px`, width: `${inset.desk.w}px` }}>watched L12 L16 L20 L24 · mean of the four · ${Math.max(0, (this.snap?.layers || 28) - 4)} layers not watched</span>`}
      ${small || g.ram.w - 140 < 300 ? null : html`<div class=${`st-cluster ${inset.roomy ? "t-cluster" : "t-readout"}`} style=${{ left: `${g.ram.x + 140}px`, width: `${Math.max(0, g.ram.w - 140)}px`, top: `${inset.core.y - 4}px` }}>
        <div><span class="t-label">desk</span> ${deskTok == null ? "—" : html`${deskTok.toLocaleString("en-US")}<span class="u">${THIN}tok${est}</span>`} <span class="u">of</span> ${fmtTok(m?.history_tokens ?? hist)}</div>
        <div><span class="t-label">read</span> ${e ? (e.tier === "ram" ? "RAM hit · 0 B from SSD" : read ? html`${fmtBytes(read)} · ${gbps ? `${gbps.toFixed(2)}${THIN}GB/s` : "—"} · ${fetchMs == null ? "—" : `${fetchMs.toFixed(fetchMs >= 10 ? 0 : 1)}${THIN}ms`} · ${share == null ? "—" : `${(share * 100).toFixed(share < 0.1 ? 1 : 0)}%`} of wait` : "—") : "—"}</div>
        <div><span class="t-label">tier</span> ${e?.tier || (e?.asleep ? "vault" : "—")}</div>
        <div><span class="t-label">first word</span> ${m?.first_word_s != null ? `${m.first_word_s.toFixed(2)}${THIN}s` : e?.wait_s != null ? `${e.wait_s.toFixed(2)}${THIN}s` : "—"}${m?.total_s != null ? ` · ${m.total_s.toFixed(2)}${THIN}s total` : ""}</div>
      </div>`}
      ${g.drawer ? html`<span class="st-drawer t-label" style=${{ left: `${g.drawer.x}px`, top: `${g.drawer.y - 14}px` }}>
        vault · ${sum((r) => r.notesList.length).toLocaleString("en-US")} notes · ${fmtBytes(sum((r) => r.vault_bytes || 0))}</span>` : null}
      <span class="st-corner t-label bl">persistence ${pers}</span>
      <span class="st-corner t-label br">timebase ${tb_ === 1 ? "real" : `×${tb_} slow`}</span>
      ${this.playing ? html`<span class="st-corner t-label tc">${this.playing.label}${this.playing.timed ? "" : " · words not timed"}</span>` : null}
      ${this.gl.flat ? html`<span class="st-corner t-label tr">no WebGL · flat view</span>` : null}
    `, this.overlay);
  }
}

Stage.prototype.renderPath = function renderPath() {
  const { html, render } = this.api.ui;
  const g = this.geo;
  const rec = this.pathRec;
  const inset = g.inset;
  if (!rec) { render(null, this.overlay); return; }
  const e = rec.e;
  const r = this.reachOf(e.reach ?? e.src);
  const room = r?.rooms.get(e.room);
  const at = this.playingWord ?? -1;
  const busTicks = [0, 2, 4, 6, 8].map((v) => html`<span class="st-bus-n t-label" style=${{ left: `${g.bus.x}px`, top: `${this.busY(v) - 7}px` }}>${v}</span>`);
  const tb = this.api.timebase.peek();
  render(html`
    <span class="st-plate t-label st-clip" style=${{ left: `${g.ssd.x}px`, top: `${g.pad - 2}px`, width: `${g.ssd.w}px` }}>
      room ${e.room} · ${room ? `${room.members.length} moments · ${room.tokens.toLocaleString("en-US")}${THIN}tok` : "—"}</span>
    <span class="st-plate t-label" style=${{ left: `${g.bus.x}px`, top: `${g.pad - 2}px` }}>bus · GB/s</span>
    ${busTicks}
    <span class="st-plate t-label" style=${{ left: `${g.ram.x}px`, top: `${g.pad - 2}px` }}>desk · ${this.desk ? this.desk.parts.reduce((a, p) => a + p.tokens, 0).toLocaleString("en-US") : "—"}${THIN}tok${this.desk && !this.desk.m?.context_tokens ? " est." : ""}</span>
    ${[12, 16, 20, 24].map((L) => html`<span class="st-row t-label" style=${{ left: `${g.ssd.x + g.ssd.w + 4}px`, top: `${inset.desk.y + L * inset.desk.row - 5}px` }}>L${L}</span>`)}
    <div class="st-words t-chat" style=${{ left: `${g.ram.x}px`, top: `${inset.desk.y + inset.desk.h + 36}px`, width: `${g.ram.w}px` }}>
      ${(e.words || []).map((w, i) => html`<span class=${`st-word${i === at ? " now" : ""}`}>${w}</span>`)}</div>
    <span class="st-corner t-label br">timebase ${tb === 1 ? "real" : `×${tb} slow`}</span>
    ${this.playing ? html`<span class="st-corner t-label tc">${this.playing.label}${this.playing.timed ? "" : " · words not timed"}</span>` : null}
  `, this.overlay);
};

export function fmtTok(n) {
  if (n == null) return "—";
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M${THIN}tok`;
  if (n >= 1e4) return `${(n / 1e3).toFixed(1)}K${THIN}tok`;
  return `${Math.round(n).toLocaleString("en-US")}${THIN}tok`;
}

// the hot shelf from /api/state's reaches (each reach's tiers list its hot rooms; the RAM budget is shared)
export function ramFromState(state, data, tokenBytes) {
  const reaches = state?.reaches;
  if (!reaches || !data) return null;
  let base = null;
  const hot = [];
  for (const [label, st] of Object.entries(reaches)) {
    const ram = st?.tiers?.ram;
    if (!ram) continue;
    base = base || ram;
    const r = data.get(label);
    for (const rid of ram.rooms || []) {
      const room = r?.rooms.get(rid);
      hot.push({ reach: label, room: rid, bytes: room ? room.tokens * tokenBytes : 0 });
    }
  }
  return base ? { budget_bytes: base.budget_bytes, used_bytes: base.used_bytes, core_bytes: base.core_bytes, hot } : null;
}
