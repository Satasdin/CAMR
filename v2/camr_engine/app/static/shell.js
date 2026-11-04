// camr's shell: the top strip (the name, six screen keys, live meters and the bus line), the keyboard, the polling,
// and the `api` object every screen is given. Screens live in /static/screens/<name>.js and export
// mount(el, api); screens/README.md is the contract.

import * as ui from "/static/vendor/ui.js";
import { icons } from "/static/vendor/icons.js";

const { html, render, signal, computed, effect } = ui;

export const SCREENS = [
  { id: "models", label: "Models" }, { id: "chat", label: "Chat" }, { id: "code", label: "Code" },
  { id: "swarm", label: "Swarm" }, { id: "memory", label: "Memory" }, { id: "bench", label: "Bench" },
];
const DEFAULT = "models";
const TIMEBASES = [1, 10, 100];
const PERSISTENCE = ["variable", "infinite", "off"];
const BUS_HALF_LIFE_MS = 400;
const BIG_READ = 32e6; // reads over 32 MB flare the bus line 2 px thick
const THIN = " "; // a unit follows its value after a thin space
const TOKEN = document.querySelector('meta[name="camr-token"]')?.content || "";
const DEBUG = new URLSearchParams(location.search).get("debug") === "1";

// -- the API client

export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

const pending = signal(0); // POSTs in flight: the logs are polled 4 times a second meanwhile
const online = signal(true);
const restarted = signal(false);

async function call(method, path, body) {
  const opt = { method, headers: { "X-CAMR-Token": TOKEN }, cache: "no-store", credentials: "same-origin" };
  if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(path, opt);
  let data = null;
  try { data = await r.json(); } catch { /* an empty or broken body */ }
  if (r.status === 403) restarted.value = true; // a new launch token: the page must be reloaded
  if (!r.ok) throw new ApiError(r.status, (data && data.error) || `HTTP ${r.status}`);
  return data;
}

function get(path, params) {
  const q = params ? new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null)) : null;
  return call("GET", q && [...q].length ? `${path}?${q}` : path);
}

async function post(path, body = {}) {
  pending.value++;
  schedule(true);
  try { return await call("POST", path, body); } finally { pending.value--; }
}

// -- events: one emitter, plus signals for the latest of each kind

const listeners = new Map();
function on(name, fn) {
  if (!listeners.has(name)) listeners.set(name, new Set());
  listeners.get(name).add(fn);
  return () => listeners.get(name).delete(fn);
}
function emit(name, data) {
  for (const fn of listeners.get(name) || []) {
    try { fn(data); } catch (e) { console.error(e); }
  }
}

const state = signal(null); // /api/state
const sys = signal(null); // /api/sys
const lastAnswer = signal(null); // the latest answer or agent event
const lastMetric = signal(null); // the latest metrics record
const lastRead = signal(null); // {bytes, gbps, at}: the latest SSD read
const measuring = computed(() => state.value?.measuring || null);
const fixture = computed(() => !!state.value?.fixture);
const timebase = signal(1);
const persistence = signal("variable");
const running = signal(true);
const motionQuery = matchMedia("(prefers-reduced-motion: reduce)");
const reducedMotion = signal(motionQuery.matches);
motionQuery.addEventListener("change", (e) => { reducedMotion.value = e.matches; });
const current = signal(null);
const fps = signal(0);

// -- formatting: every number with its unit, or a dash when it was not measured

const fmt = {
  THIN,
  num(x, digits) {
    if (x == null || !Number.isFinite(x)) return "—";
    if (digits !== undefined) return x.toFixed(digits);
    const a = Math.abs(x);
    return a >= 100 ? x.toFixed(0) : a >= 10 ? x.toFixed(1) : x.toFixed(2);
  },
  // [value, unit]; RAM in binary units as macOS counts it, files and disks in decimal as Finder does
  bytes(n, binary = false) {
    if (n == null || !Number.isFinite(n)) return ["—", ""];
    const k = binary ? 1024 : 1000;
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    let x = Math.abs(n);
    while (x >= k && i < units.length - 1) { x /= k; i++; }
    return [i === 0 ? String(Math.round(x)) : fmt.num(x), units[i]];
  },
  ram(n) { return fmt.bytes(n, true); },
  gbps(x) { return x == null ? ["—", ""] : [fmt.num(x), "GB/s"]; },
  s(x) {
    if (x == null || !Number.isFinite(x)) return ["—", ""];
    return [x >= 100 ? x.toFixed(0) : x >= 10 ? x.toFixed(1) : x.toFixed(2), "s"];
  },
  ms(x) { return x == null ? ["—", ""] : [x >= 10 ? x.toFixed(0) : x.toFixed(1), "ms"]; },
  tps(x) { return x == null ? ["—", ""] : [x >= 100 ? x.toFixed(0) : x.toFixed(1), "tok/s"]; },
  int(n) { return n == null ? "—" : Math.round(n).toLocaleString("en-US"); },
  tok(n) {
    if (n == null) return ["—", ""];
    if (n >= 1e6) return [fmt.num(n / 1e6) + "M", "tok"];
    if (n >= 1e4) return [fmt.num(n / 1e3) + "K", "tok"];
    return [fmt.int(n), "tok"];
  },
  params(n) {
    if (!n) return ["—", ""];
    return n >= 1e9 ? [fmt.num(n / 1e9), "B"] : [fmt.num(n / 1e6), "M"];
  },
  duration(sec) {
    if (sec == null || !Number.isFinite(sec)) return "—";
    const m = Math.floor(sec / 60), s = Math.round(sec % 60);
    return m ? `${m}${THIN}m ${s}${THIN}s` : `${s}${THIN}s`;
  },
  text([v, u]) { return u ? `${v}${THIN}${u}` : v; },
};

// -- parts every screen can use

function Val({ v }) {
  const [value, unit] = v;
  return html`<span class="v">${value}</span>${unit ? html`<span class="u">${THIN}${unit}</span>` : null}`;
}

function Readout({ label, size = "readout", children, cls = "" }) {
  return html`<div class="readout ${cls}"><span class="t-label">${label}</span><span class="t-${size}">${children}</span></div>`;
}

// glyphs the vendored latin subsets lack are drawn, never typed
const GLYPHS = {
  dot: html`<circle cx="5" cy="5" r="3.5" fill="currentColor"/>`,
  ring: html`<circle cx="5" cy="5" r="3.25" fill="none" stroke="currentColor" stroke-width="1.5"/>`,
  tri: html`<path d="M5 1.5 L8.8 8.5 H1.2 Z" fill="currentColor"/>`,
  cross: html`<path d="M2 2 L8 8 M8 2 L2 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
  check: html`<path d="M1.5 5.5 L4 8 L8.5 2.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>`,
  empty: html`<g fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="5" cy="5" r="3.2"/><path d="M1.5 8.5 L8.5 1.5"/></g>`,
};
function Glyph({ kind, cls = "", title }) {
  return html`<svg class="glyph ${cls}" width="10" height="10" viewBox="0 0 10 10" aria-hidden=${title ? null : "true"}
    role=${title ? "img" : null} aria-label=${title || null}>${GLYPHS[kind]}</svg>`;
}

function Icon({ name }) {
  return html`<span class="icon" aria-hidden="true" dangerouslySetInnerHTML=${{ __html: icons[name] || "" }}></span>`;
}

function Empty({ fill = false, children }) {
  return html`<div class=${fill ? "empty fill" : "empty"}>${children}</div>`;
}

const sheets = new Set();
function css(href) {
  if (sheets.has(href)) return;
  sheets.add(href);
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = href;
  document.head.appendChild(link);
}

let frames = 0;
function frame() { frames++; }
if (DEBUG) setInterval(() => { fps.value = frames; frames = 0; }, 1000);

export const api = {
  get, post, ApiError, on, emit,
  state, sys, lastAnswer, lastMetric, lastRead, measuring, fixture, timebase, persistence, running, reducedMotion,
  current, pending, online,
  goto: (id) => show(id), frame, css, fmt, ui, icons, debug: DEBUG, screens: SCREENS,
  parts: { Val, Readout, Glyph, Icon, Empty },
};

// -- the bus line: the strip's bottom hairline flares where memory moved, and never travels

let busEl = null;
function flare(kind, bytes = 0) {
  if (!busEl || !running.value) return;
  busEl.getAnimations().forEach((a) => a.cancel());
  busEl.className = `bus ${kind}${bytes > BIG_READ ? " big" : ""}`;
  if (reducedMotion.value) { // an instant fill that clears after 600 ms
    busEl.animate([{ opacity: 1 }, { opacity: 1, offset: 0.999 }, { opacity: 0 }], { duration: 600 });
    return;
  }
  const steps = 6; // six half-lives, sampled; linear between samples is close to the decay
  const kf = [];
  for (let k = 0; k <= steps; k++) kf.push({ opacity: k === steps ? 0 : 2 ** -k, offset: k / steps });
  busEl.animate(kf, { duration: steps * BUS_HALF_LIFE_MS, easing: "linear" });
}

function moved(e) {
  const fetchS = e.seconds?.fetch || 0;
  if (e.tier === "ram") return ["ram", 0];
  if (e.tier === "vault" || e.asleep) return ["words", 0];
  if (e.tier === "ssd" || (e.tier == null && e.room != null && fetchS > 0)) return ["read", e.read_bytes || 0];
  if (e.closest?.length) return ["words", 0];
  return null;
}

function read(r) { // the latest read wins, whichever log reported it first
  if (!lastRead.peek() || !r.at || !lastRead.peek().at || r.at >= lastRead.peek().at) lastRead.value = r;
}

function note(e, live) {
  if (e.type === "answer" || e.type === "agent") {
    lastAnswer.value = e;
    const fetchS = e.seconds?.fetch;
    if (e.tier === "ssd" && e.read_bytes && fetchS > 0) read({ bytes: e.read_bytes, gbps: e.read_bytes / fetchS / 1e9, at: e.at });
    if (live) {
      const m = moved(e);
      if (m) flare(m[0], m[1]);
    }
  }
  if (live) emit("event", e);
}

function noteMetric(m, live) {
  lastMetric.value = m;
  if (m.read_bytes && m.gbps) read({ bytes: m.read_bytes, gbps: m.gbps, at: m.at });
  if (live) emit("metric", m);
}

// -- polling: logs once a second (4 times while a request is pending), RAM once a second, state every 2 s; nothing
// while the tab is hidden. No EventSource: it cannot send the token header.

const cursor = { events: null, metrics: null };
let timer = null;
let lastSys = -1e9;
let lastState = -1e9;

async function pollLogs() {
  for (const kind of ["events", "metrics"]) {
    const first = cursor[kind] === null;
    const got = await get(`/api/${kind}`, first ? { tail: 1 } : { after: cursor[kind] });
    cursor[kind] = got.next;
    for (const item of got.events) (kind === "events" ? note : noteMetric)(item, !first);
  }
}

async function loop() {
  timer = null;
  if (document.hidden) return;
  const now = performance.now();
  const jobs = [pollLogs()];
  if (now - lastSys >= 1000) { lastSys = now; jobs.push(get("/api/sys").then((v) => { sys.value = v; })); }
  if (now - lastState >= 2000) { lastState = now; jobs.push(get("/api/state").then((v) => { state.value = v; })); }
  try {
    await Promise.all(jobs);
    online.value = true;
  } catch (e) {
    online.value = !(e instanceof TypeError); // a network error: the server is gone
  }
  schedule();
}

function schedule(soon = false) {
  if (document.hidden || restarted.value) return; // after a restart only a reload brings the new token
  if (timer && !soon) return;
  clearTimeout(timer);
  timer = setTimeout(loop, soon ? 0 : pending.value > 0 ? 250 : 1000);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) { lastSys = lastState = -1e9; schedule(true); }
});

// -- the top strip

function short(repo) {
  return repo ? repo.split("/").pop() : null;
}

function Meter({ label, children, optional = false }) {
  return html`<div class=${optional ? "meter optional" : "meter"}><span class="t-label">${label}</span>
    <span class="t-readout">${children}</span></div>`;
}

function RamMeter() {
  const y = sys.value;
  if (!y || !y.total_bytes) return html`<${Meter} label="RAM">—<//>`;
  const mine = y.process_bytes || 0;
  const other = Math.max(0, (y.used_bytes || 0) - mine);
  const pct = (b) => `${Math.min(100, (100 * b) / y.total_bytes)}%`;
  const crit = y.pressure === "critical";
  return html`<${Meter} label="RAM">
    <span class="ram-bar" title=${`other apps ${fmt.text(fmt.ram(other))} · this app ${fmt.text(fmt.ram(mine))} of ${fmt.text(fmt.ram(y.total_bytes))}`}>
      <i class="other" style=${{ left: 0, width: pct(other) }}></i><i class="mine" style=${{ left: pct(other), width: pct(mine) }}></i>
    </span><${Val} v=${fmt.ram(y.used_bytes)} />
    <span class=${crit ? "fault-text" : "dim"}> · ${crit ? html`<${Glyph} kind="cross" /> ` : null}${y.pressure || "—"}</span>
  <//>`;
}

function Strip() {
  const s = state.value;
  const cur = current.value;
  const read = lastRead.value;
  const m = lastMetric.value;
  const a = lastAnswer.value;
  const firstWord = m && (!a || !a.at || (m.at && m.at >= a.at)) ? m.first_word_s : a?.wait_s ?? null;
  const model = s?.model;
  return html`
    <div class="brand">
      <span class="name">camr</span>
      ${fixture.value ? html`<span class="badge" title="a recorded memory, served read-only">fixture</span>` : null}
      ${!running.value ? html`<span class="badge">stopped</span>` : null}
      ${restarted.value ? html`<span class="badge fault-text"><${Glyph} kind="cross" /> reload: the server restarted</span>`
        : !online.value ? html`<span class="badge fault-text"><${Glyph} kind="cross" /> server not answering</span>` : null}
    </div>
    <nav class="keys" aria-label="Screens">
      ${SCREENS.map((x, i) => html`<button class="key" aria-current=${cur === x.id ? "page" : null}
        aria-keyshortcuts=${String(i + 1)} onClick=${() => show(x.id)}><span class="n">${i + 1}</span><span class="w">${x.label}</span></button>`)}
    </nav>
    <div class="meters">
      ${measuring.value ? html`<${Meter} label="Measuring"><span class="measuring">${measuring.value.job} · view paused</span><//>` : null}
      <${RamMeter} />
      <${Meter} label="SSD" optional=${true}>${read ? html`<${Val} v=${fmt.bytes(read.bytes)} /> · <${Val} v=${fmt.gbps(read.gbps)} />` : "—"}<//>
      <${Meter} label="Model">${model?.loading ? html`<span class="dim">loading </span>${short(model.loading)}` : short(model?.repo) || "—"}<//>
      <${Meter} label="First word" optional=${true}><${Val} v=${fmt.s(firstWord)} /><//>
      ${DEBUG ? html`<${Meter} label="fps"><span class="fps">${fps.value}</span><//>` : null}
    </div>
    <div class="bus" ref=${(el) => { busEl = el; }}></div>`;
}

// -- screens: each mounted on its first visit, then shown and hidden

const sections = {};
const handles = {};
const main = document.getElementById("screens");
for (const s of SCREENS) {
  const el = document.createElement("section");
  el.className = `screen screen-${s.id}`;
  el.dataset.screen = s.id;
  el.setAttribute("aria-label", s.label);
  el.hidden = true;
  main.appendChild(el);
  sections[s.id] = el;
}

async function show(id) {
  const target = SCREENS.find((s) => s.id === id) || SCREENS.find((s) => s.id === DEFAULT);
  const prev = current.peek();
  if (prev === target.id) return;
  if (prev && handles[prev]) handles[prev].hide?.();
  for (const s of SCREENS) sections[s.id].hidden = s.id !== target.id;
  current.value = target.id;
  document.title = `camr · ${target.label.toLowerCase()}`;
  if (location.hash !== `#${target.id}`) history.replaceState(null, "", `#${target.id}`);
  if (target.id in handles) {
    handles[target.id]?.show?.();
    return;
  }
  handles[target.id] = null; // mounting
  let handle = {};
  try {
    const mod = await import(`/static/screens/${target.id}.js`);
    handle = (await mod.mount(sections[target.id], api)) || {};
  } catch (e) {
    console.error(e);
    render(html`<${Empty} fill=${true}><span class="fault-text"><${Glyph} kind="cross" /></span> this screen failed to load · ${e.message}<//>`,
      sections[target.id]);
  }
  handles[target.id] = handle;
  if (current.peek() === target.id) handle.show?.();
}

window.addEventListener("hashchange", () => show(location.hash.slice(1)));

// -- the keyboard: the screen on show gets each key first

function typing(t) {
  return t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));
}

document.addEventListener("keydown", (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey) return; // ⌘1–⌘6 belong to the browser
  const inField = typing(e.target);
  const handle = handles[current.peek()];
  if (handle?.key && handle.key(e, { typing: inField }) === true) {
    e.preventDefault();
    return;
  }
  if (inField) {
    if (e.key === "Escape") e.target.blur();
    return;
  }
  const k = e.key;
  if (/^[1-6]$/.test(k)) show(SCREENS[Number(k) - 1].id);
  else if (k === " ") running.value = !running.value;
  else if (k === "[") timebase.value = TIMEBASES[Math.max(0, TIMEBASES.indexOf(timebase.value) - 1)];
  else if (k === "]") timebase.value = TIMEBASES[Math.min(TIMEBASES.length - 1, TIMEBASES.indexOf(timebase.value) + 1)];
  else if (k === "p" || k === "P") persistence.value = PERSISTENCE[(PERSISTENCE.indexOf(persistence.value) + 1) % PERSISTENCE.length];
  else if (k === "r" || k === "R") emit("replay");
  else if (k === "c" || k === "C") emit("cursors");
  else if (k === "Escape") emit("escape");
  else if (k === "/") emit("focus");
  else return;
  e.preventDefault();
});

// RUN/STOP, the timebase and persistence are announced to screens as well as kept in signals
effect(() => emit("run", running.value));

render(html`<${Strip} />`, document.getElementById("strip"));
show(location.hash.slice(1) || DEFAULT);
schedule(true);
