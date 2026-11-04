// Bench: the evidence (design/DIRECTION.md, "5. Bench"). The headline is Qwen 27B with memory against without. Five
// tabs, one per question, each with one hero chart drawn from the dated records and its run table under it: past the
// window (score, first word and peak RAM against history length, each model's window a wall the memory lines run
// through), how far it grows (retrieval ms and GB/s against the memory's size on the SSD, the ruler's lives, decode
// tok/s), which reach, sleep (rooms awake and asleep) and the gap (LMArena's WebDev history). Under every
// tab sits the Long Haul probe matrix per contender and cut, with the generated catering page as its real
// headless-browser screenshot. The right column is the yardstick: what Claude cost, against the night's cap.
// Records keep arriving while benchmarks run: new results land as dots that flare and decay. Measured or nothing.

const TAB_KEY = "camr_engine.bench.tab";
const TABS = [
  { id: "window", label: "Past the window" },
  { id: "grows", label: "How far it grows" },
  { id: "reach", label: "Which reach" },
  { id: "sleep", label: "Sleep" },
  { id: "gap", label: "The gap" },
];
const POLL_MS = 10000;
const POLL_MEASURING_MS = 3000; // results land faster while a suite runs
const FLARE_MS = 2400; // six half-lives of 400 ms
const ROWS = 8; // run table rows before "show all"
const MEMORY = { tensors: "tensors", words: "words", none: "no memory", claude: "claude alone", ram: "in RAM" };
const TASKS = { longhaul: "Long Haul", babilong: "BABILong", memoryagentbench: "MemoryAgentBench",
  longmemeval: "LongMemEval", math500: "MATH-500", aime: "AIME", harp: "HARP", mathcheck: "MathCheck" };
const LEGEND = { tensors: "tensors · the engine's saved keys and values", words: "words · memory read as text",
  none: "no memory", claude: "Claude alone", ram: "hot in RAM", open: "open weights", mac: "runs on this Mac" };
const LOG10 = Math.log10;

const STYLE = `
.bx { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: var(--sp-5); min-height: 100%;
  padding: var(--sp-5) var(--sp-5) var(--sp-7); background: var(--bed); }
.bx-main { min-width: 0; display: flex; flex-direction: column; gap: var(--sp-5); }
.bx-note { display: flex; gap: var(--sp-3); align-items: center; color: var(--ink-3); }
.bx-note .on { color: var(--ink); }
.bx-head { display: flex; align-items: flex-start; align-content: flex-end; gap: var(--sp-4) var(--sp-6); flex-wrap: wrap;
  min-height: calc(0.28 * (100vh - var(--strip-h))); padding-bottom: var(--sp-2); }
.bx-fig { display: flex; flex-direction: column; gap: var(--sp-2); min-width: 0; max-width: calc(50% - var(--sp-6)); }
.bx-fig .t-hero { color: var(--ink); white-space: nowrap; }
.bx-fig .of { font: 300 28px/32px var(--f-mono); color: var(--ink-3); margin-left: var(--sp-2); }
.bx-fig .src { color: var(--ink-3); background: none; border: 0; padding: 0; text-align: left; cursor: pointer;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.bx-fig .src:hover { color: var(--ink-2); }
.bx-claim { color: var(--ink-2); padding-bottom: var(--sp-3); flex-basis: 100%; }
.bx-tabs { display: flex; gap: 0; border-bottom: 1px solid var(--hair); overflow-x: auto; }
.bx-tab { height: 36px; padding: 0 var(--sp-4); background: none; border: 0; color: var(--ink-3); position: relative;
  font: 500 10.5px/14px var(--f-mono); font-stretch: 87.5%; text-transform: uppercase; letter-spacing: .08em;
  white-space: nowrap; transition: color var(--ui-fast) linear; }
.bx-tab:hover { color: var(--ink-2); }
.bx-tab[aria-selected="true"] { color: var(--ink); }
.bx-tab[aria-selected="true"]::after { content: ""; position: absolute; left: 0; right: 0; bottom: -1px; height: 2px;
  background: var(--select); }
.bx-tab .n { color: var(--ink-4); margin-left: 6px; }
.bx-panel { display: flex; flex-direction: column; gap: var(--sp-4); min-width: 0; }
.bx-twins { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--sp-4); }
.bx-chart { position: relative; min-width: 0; background: var(--void); border: 1px solid var(--hair);
  border-radius: var(--r-panel); padding: var(--sp-3) var(--sp-3) var(--sp-2); }
.bx-chart-head { display: flex; justify-content: space-between; align-items: center; gap: var(--sp-3);
  min-height: 26px; flex-wrap: wrap; }
.bx-chart svg { display: block; overflow: visible; }
.bx-chart .empty { border: 0; padding: var(--sp-6) var(--sp-4); text-align: center; }
.bx-ax { stroke: var(--ink-4); stroke-width: 1; }
.bx-grid { stroke: var(--hair); stroke-width: 1; }
.bx-tick { fill: var(--ink-3); font: 400 10.5px/14px var(--f-mono); font-variant-numeric: tabular-nums; }
.bx-axlabel { fill: var(--ink-3); font: 500 10px/14px var(--f-mono); font-stretch: 87.5%; letter-spacing: .08em;
  text-transform: uppercase; }
.bx-cutline { stroke: var(--ink-4); stroke-dasharray: 2 3; }
.bx-wall { stroke: var(--hair-2); stroke-width: 2; }
.bx-wall-label { fill: var(--ink-2); font: 500 10px/14px var(--f-mono); font-stretch: 87.5%; letter-spacing: .06em;
  text-transform: uppercase; }
.bx-ref { stroke: var(--ink-2); stroke-width: 1; }
.bx-ref-label { fill: var(--ink-2); font: 500 10px/14px var(--f-mono); font-stretch: 87.5%; letter-spacing: .06em;
  text-transform: uppercase; }
.bx-ln { fill: none; stroke-width: 1.5; stroke-linejoin: round; stroke-linecap: round;
  transition: opacity var(--ui-fast) linear; }
.bx-ln.tensors { stroke: var(--ssd); filter: drop-shadow(0 0 2px color-mix(in srgb, var(--ssd) 45%, transparent)); }
.bx-ln.words { stroke: var(--vault); }
.bx-ln.ram { stroke: var(--ram); }
.bx-ln.none { stroke: var(--ink-3); stroke-width: 1; }
.bx-ln.claude { stroke: var(--ink-2); stroke-width: 1.2; stroke-dasharray: 5 3; }
.bx-ln.open { stroke: var(--ink); stroke-width: 1.5; }
.bx-ln.mac { stroke: var(--ink-3); stroke-width: 1.2; stroke-dasharray: 1 3; }
.bx-band { stroke: none; fill: var(--ink-4); opacity: .35; }
.bx-band.open { opacity: .5; }
.bx-pt { stroke-width: 1.2; transition: opacity var(--ui-fast) linear; cursor: pointer; }
.bx-pt.tensors { fill: var(--ssd); stroke: var(--ssd); }
.bx-pt.words { fill: var(--vault); stroke: var(--vault); }
.bx-pt.ram { fill: var(--ram); stroke: var(--ram); }
.bx-pt.none { fill: var(--ink-3); stroke: var(--ink-3); }
.bx-pt.claude { fill: var(--void); stroke: var(--ink-2); }
.bx-pt.open, .bx-pt.mac { fill: var(--ink-2); stroke: var(--ink-2); }
.bx-pt.hot { stroke: var(--select); stroke-width: 1.5; }
.bx-wh { stroke-width: 1; opacity: .6; }
.bx-wh.tensors { stroke: var(--ssd); } .bx-wh.words { stroke: var(--vault); } .bx-wh.ram { stroke: var(--ram); }
.bx-wh.none { stroke: var(--ink-3); } .bx-wh.claude { stroke: var(--ink-2); }
.bx-end { fill: var(--ink-2); font: 400 10px/12px var(--f-mono); font-variant-numeric: tabular-nums;
  transition: opacity var(--ui-fast) linear; }
.bx-fm { stroke: var(--fault); stroke-width: 1.3; stroke-linecap: round; }
.bx-fm-more { fill: var(--fault); font: 400 10px/12px var(--f-mono); }
.bx-dim { opacity: .18; }
.bx-flare { pointer-events: none; animation: bx-flare 2400ms linear forwards; }
.bx-flare.tensors { fill: var(--ssd); } .bx-flare.words { fill: var(--vault); } .bx-flare.none { fill: var(--ink-3); }
.bx-flare.claude { fill: var(--ink-2); } .bx-flare.ram { fill: var(--ram); }
@keyframes bx-flare { 0% { opacity: .9; } 16.7% { opacity: .45; } 33.3% { opacity: .22; } 50% { opacity: .11; }
  66.7% { opacity: .06; } 83.3% { opacity: .03; } 100% { opacity: 0; } }
@keyframes bx-flare-still { 0% { opacity: .9; } 99.9% { opacity: .9; } 100% { opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .bx-flare { animation: bx-flare-still 600ms linear forwards; } }
.bx-legend { display: flex; flex-wrap: wrap; gap: 2px var(--sp-4); padding-top: var(--sp-2); color: var(--ink-2); }
.bx-legend span { display: inline-flex; align-items: center; gap: 6px; cursor: default; white-space: nowrap; }
.bx-legend svg { flex: none; }
.bx-legend .fault-text { gap: 4px; }
.bx-tip { position: absolute; z-index: 5; pointer-events: none; background: var(--s2); border: 1px solid var(--hair-2);
  border-radius: var(--r-mark); padding: 6px 8px; color: var(--ink); max-width: 340px; }
.bx-tip div + div { color: var(--ink-2); }
.bx-tip .dim { color: var(--ink-3); }
.bx-runs { width: 100%; border-collapse: collapse; }
.bx-runs th { text-align: left; font-weight: 500; padding: 0 var(--sp-2) 6px 0; white-space: nowrap; }
.bx-runs th.r, .bx-runs td.r { text-align: right; }
.bx-runs td { padding: 0 var(--sp-3) 0 0; height: 28px; border-top: 1px solid var(--hair); white-space: nowrap;
  color: var(--ink-2); max-width: 200px; overflow: hidden; text-overflow: ellipsis; }
.bx-runs th { padding-right: var(--sp-3); }
@media (max-width: 1600px) { .bx-runs .cuts { display: none; } }
@media (max-width: 1400px) { .bx-runs .read { display: none; } .bx-runs td { max-width: 170px; }
  .bx-runs td, .bx-runs th { padding-right: var(--sp-2); } }
.bx-runs td.c { color: var(--ink); }
.bx-runs tbody tr { cursor: pointer; }
.bx-runs tbody tr:hover { background: var(--s2); }
.bx-runs tbody tr:focus-visible { outline: 2px solid var(--select); outline-offset: -2px; }
.bx-runs .glyph { margin-right: 6px; }
.bx-wrap { overflow-x: auto; }
.bx-more { margin-top: var(--sp-2); }
.bx-sub { display: flex; justify-content: space-between; align-items: center; gap: var(--sp-3); flex-wrap: wrap; }
.bx-matrix { display: grid; gap: 1px; background: var(--hair); border: 1px solid var(--hair);
  border-radius: var(--r-panel); overflow: hidden; min-width: min-content; }
.bx-mcell { background: var(--void); padding: 6px var(--sp-2); min-height: 40px; display: flex; flex-direction: column;
  justify-content: center; gap: 4px; min-width: 0; }
.bx-mcell.lab { color: var(--ink-2); }
.bx-mcell.head .t-label { white-space: normal; }
.bx-mcell.head { justify-content: flex-end; min-height: 52px; }
.bx-mcell.head .t-readout { color: var(--ink); display: inline-flex; align-items: center; gap: 6px; }
.bx-mcell.all { background: var(--s1); }
.bx-sq { display: flex; gap: 3px; align-items: center; }
.bx-sq i { display: block; width: 12px; height: 12px; border-radius: 1px; }
.bx-sq i.miss { border: 1px dashed var(--hair-2); }
.bx-sq i.none { border: 1px solid var(--hair); }
.bx-sq i.sel { box-shadow: 0 2px 0 -1px var(--ink-2); }
.bx-sq .cutn { color: var(--ink-4); width: 12px; text-align: center; font: 500 8px/10px var(--f-mono); }
.bx-counts { display: flex; gap: var(--sp-2); color: var(--ink-2); }
.bx-counts .x { color: var(--fault); }
.bx-counts .e { color: var(--ink-3); }
.bx-thumb { display: block; width: 100%; max-width: 200px; height: 132px; border: 1px solid var(--hair-2); border-radius: var(--r-mark);
  overflow: hidden; background: var(--s1); padding: 0; cursor: pointer; }
.bx-thumb img { display: block; width: 100%; height: auto; }
.bx-thumb.wait { display: flex; align-items: center; justify-content: center; color: var(--ink-3); cursor: default; }
.bx-thumb.shoot { cursor: pointer; transition: color var(--ui-fast) linear, border-color var(--ui-fast) linear; }
.bx-thumb.shoot:hover { color: var(--ink); border-color: var(--ink-3); }
.bx-thumb.shoot.fault-text:hover { color: var(--fault); }
.bx-yard { position: sticky; top: 0; align-self: start; display: flex; flex-direction: column; gap: var(--sp-4);
  border-left: 1px solid var(--hair); padding-left: var(--sp-5); min-width: 0; }
.bx-yard .t-figure { color: var(--ink); }
.bx-cap { position: relative; height: 2px; background: var(--ink-4); margin-top: var(--sp-2); }
.bx-cap i { position: absolute; left: 0; top: 0; bottom: 0; background: var(--ink-2); }
.bx-cap b { position: absolute; top: -4px; width: 1px; height: 10px; background: var(--ink-3); }
.bx-model { border-top: 1px solid var(--hair); padding-top: var(--sp-3); display: flex; flex-direction: column;
  gap: 4px; }
.bx-model .name { display: flex; justify-content: space-between; color: var(--ink); }
.bx-kv { display: flex; justify-content: space-between; gap: var(--sp-3); color: var(--ink-2); }
.bx-kv .k { color: var(--ink-3); }
.bx-sheet { position: fixed; top: var(--strip-h); right: 0; bottom: 0; width: 440px; max-width: 100vw; z-index: 20;
  background: var(--s1); border-left: 1px solid var(--hair); overflow: auto; padding: var(--sp-4) var(--sp-5)
  var(--sp-7); display: flex; flex-direction: column; gap: var(--sp-4); }
.bx-sheet.wide { width: 680px; }
.bx-sheet-top { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--sp-3); }
.bx-sheet .t-head { color: var(--ink); }
.bx-sheet .path { color: var(--ink-3); word-break: break-all; }
.bx-group { border-top: 1px solid var(--hair); padding-top: var(--sp-3); display: flex; flex-direction: column;
  gap: var(--sp-2); }
.bx-group.at > .t-label { color: var(--ink); }
.bx-chips { display: flex; flex-wrap: wrap; gap: 4px var(--sp-3); color: var(--ink-2); }
.bx-chips .k { color: var(--ink-3); }
.bx-ans { display: flex; flex-direction: column; gap: 2px; padding: 6px 0; border-top: 1px solid var(--hair); }
.bx-ans .q { color: var(--ink); font: 400 13px/18px var(--f-text); }
.bx-ans .a { color: var(--ink-2); font: 400 12px/17px var(--f-code); white-space: pre-wrap; max-height: 9em;
  overflow: auto; }
.bx-ans .why { color: var(--ink-3); }
.bx-ans .id { color: var(--ink-3); display: flex; gap: 6px; align-items: center; }
.bx-ans .ok { color: var(--ink-2); } .bx-ans .bad { color: var(--fault); }
.bx-shot { width: 100%; border: 1px solid var(--hair-2); border-radius: var(--r-mark); background: var(--s2); }
.bx-x { background: none; border: 0; color: var(--ink-3); padding: 2px; }
.bx-x:hover { color: var(--ink); }
.bx-bars { display: flex; flex-direction: column; gap: var(--sp-2); }
.bx-bar { display: grid; grid-template-columns: 220px minmax(0, 1fr) 140px; gap: var(--sp-3); align-items: center; }
.bx-bar .track { height: 6px; background: var(--hair); border-radius: 1px; position: relative; }
.bx-bar .track i { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 1px; }
.bx-fill-tensors { background: var(--ssd); } .bx-fill-words { background: var(--vault); }
.bx-fill-none { background: var(--ink-3); } .bx-fill-claude { background: var(--ink-2); }
.bx-errors { color: var(--ink-3); }
@media (max-width: 900px) {
  .bx { grid-template-columns: minmax(0, 1fr); padding: var(--sp-4); }
  .bx-yard { position: static; border-left: 0; border-top: 1px solid var(--hair); padding: var(--sp-4) 0 0; }
  .bx-twins { grid-template-columns: minmax(0, 1fr); }
  .bx-head { gap: var(--sp-5); min-height: 0; }
  .bx-fig { max-width: 100%; }
  .bx-fig .t-hero { font-size: 56px; line-height: 56px; }
  .bx-bar { grid-template-columns: 140px minmax(0, 1fr) 100px; }
}
`;

function style() {
  if (document.querySelector('style[data-screen="bench"]')) return;
  const s = document.createElement("style");
  s.dataset.screen = "bench";
  s.textContent = STYLE;
  document.head.appendChild(s);
}

// -- scales and ticks

function scale(kind, [d0, d1], [r0, r1]) {
  if (kind === "log") {
    const a = LOG10(d0), b = LOG10(d1);
    return (v) => r0 + ((LOG10(Math.max(v, d0 / 100)) - a) / (b - a || 1)) * (r1 - r0);
  }
  return (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);
}

function niceStep(span, n = 5) {
  const raw = span / n;
  const p = 10 ** Math.floor(LOG10(raw));
  const m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
}

function linTicks(d0, d1, n = 5) {
  const s = niceStep(d1 - d0 || 1, n);
  const out = [];
  for (let v = Math.ceil(d0 / s) * s; v <= d1 + s * 1e-9; v += s) out.push(+v.toFixed(10));
  return out;
}

function niceMax(v, n = 5) {
  if (!(v > 0)) return 1;
  const s = niceStep(v, n);
  return Math.ceil((v * 1.08) / s) * s;
}

function decades(d0, d1) {
  const out = [];
  for (let e = Math.ceil(LOG10(d0) - 1e-9); e <= LOG10(d1) + 1e-9; e++) out.push(10 ** e);
  return out;
}

function logDomain(values, floor = null, ceil = null) {
  const v = values.filter((x) => x > 0);
  if (!v.length) return [floor || 1, ceil || 10];
  let lo = 10 ** Math.floor(LOG10(Math.min(...v)));
  let hi = 10 ** Math.ceil(LOG10(Math.max(...v)) + 1e-9);
  if (floor != null) lo = Math.min(lo, floor);
  if (ceil != null) hi = Math.max(hi, ceil);
  if (hi <= lo) hi = lo * 10;
  return [lo, hi];
}

function tokShort(v) {
  if (v >= 1e6) return `${+(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${+(v / 1e3).toFixed(v >= 1e4 ? 0 : 1)}K`;
  return `${Math.round(v)}`;
}

function windowShort(v) {
  if (v >= 1 << 20 && v % (1 << 20) === 0) return `${v / (1 << 20)}M`;
  if (v % 1024 === 0 && v < 1e6) return `${v / 1024}K`;
  return tokShort(v);
}

function allPoints(series) {
  return series.flatMap((s) => s.points);
}

export function mount(el, api) {
  const { html, render, signal, useRef, useState, useLayoutEffect, useEffect } = api.ui;
  const { Val, Glyph, Icon, Empty } = api.parts;
  const { fmt } = api;
  const THIN = fmt.THIN;
  style();

  const data = signal(null);
  const loadError = signal(null);
  const tab = signal(readTab());
  const task = signal("longhaul");
  const cutPick = signal(null);
  const sheet = signal(null); // {type: "record", path, cut} or {type: "shot", page}
  const record = signal(null);
  const webdev = signal(null);
  const shots = signal({}); // key -> {png, width, height, bytes} | {error}
  const shooting = signal(null); // the key being shot
  const shootErrors = signal({}); // key -> why it failed: a real fault, shown in red until tried again
  const shootWait = signal({}); // key -> why the server said wait (a run measuring, another shot): cleared each load
  const showAll = signal({});
  const tick = signal(0); // bumps when results land, so flares draw
  const vh = signal(window.innerHeight);
  const fresh = new Map(); // point key -> when it landed
  let seen = null;
  let timer = null;
  let shown = false;

  function readTab() {
    try {
      const t = localStorage.getItem(TAB_KEY);
      return TABS.some((x) => x.id === t) ? t : "window";
    } catch { return "window"; }
  }

  function setTab(id) {
    tab.value = id;
    try { localStorage.setItem(TAB_KEY, id); } catch { /* a private window */ }
    if (id === "gap" && !webdev.value) loadWebdev();
  }

  // -- formats: every number with its unit, or a dash

  const pct = (x) => (x == null ? ["—", ""] : [(100 * x).toFixed(0), "%"]);
  const gb = (x) => (x == null ? ["—", ""] : fmt.bytes(x * 1e9));
  const usd = (x) => (x == null ? ["—", ""] : x === 0 ? ["$0", ""] : [`$${x >= 100 ? x.toFixed(0) : x >= 1 ? x.toFixed(2) : x >= 0.01 ? x.toFixed(3) : x.toFixed(4)}`, ""]);
  const T = (pair) => fmt.text(pair);
  const when = (iso) => (iso ? iso.replace("T", " ").slice(5, 16) : "—");

  // -- data

  async function load() {
    try {
      const d = await api.get("/api/bench");
      const keys = new Set([...d.series.flatMap((s) => s.points.map((p) => p.key)), ...d.runs.map((r) => r.path)]);
      if (seen) {
        const now = performance.now();
        for (const k of keys) if (!seen.has(k)) fresh.set(k, now);
      }
      seen = keys;
      shootWait.value = {};
      data.value = d;
      loadError.value = null;
      tick.value++;
      if (tab.peek() === "gap" && !webdev.peek()) loadWebdev();
      shootNext();
    } catch (e) {
      loadError.value = e.message;
    }
  }

  async function loadWebdev() {
    try { webdev.value = await api.get("/api/bench/webdev"); } catch (e) { webdev.value = { present: false, error: e.message }; }
  }

  async function openRecord(path, cut = null) {
    sheet.value = { type: "record", path, cut };
    record.value = null;
    try {
      const r = await api.get("/api/bench/record", { path });
      if (sheet.peek()?.path === path) record.value = r;
    } catch (e) {
      if (sheet.peek()?.path === path) record.value = { error: e.message };
    }
  }

  async function fetchShot(key) {
    if (!key || shots.peek()[key]) return;
    shots.value = { ...shots.peek(), [key]: { loading: true } };
    try {
      const s = await api.get("/api/bench/shot", { key });
      shots.value = { ...shots.peek(), [key]: s };
    } catch (e) {
      shots.value = { ...shots.peek(), [key]: { error: e.message } };
    }
  }

  // Pages with HTML and no screenshot yet are shot one at a time, at the cut on show. The screen shoots on its own
  // only while the board says all is quiet (nothing measuring, no benchmark process, no record changed lately);
  // otherwise a page waits for its "shoot" click, so a run's timings never share the CPU with a browser.
  async function shootNext() {
    const d = data.peek();
    if (!d || !shown || shooting.peek() || api.measuring.peek() || d.measuring || !d.shoot?.auto) return;
    const cut = matrixCut(cutPick.peek());
    const want = d.pages.find((p) => p.cut === cut && p.qid === "page-catering" && p.key && !p.shot
      && !shootErrors.peek()[p.key] && !shootWait.peek()[p.key]);
    if (!want) return;
    if ((await shoot(want, false)) && shown) setTimeout(shootNext, 50);
  }

  // A 409 saying a run measures, a benchmark runs or another page is being shot is a wait, not a fault.
  const isWait = (e) => e?.status === 409 && /is measuring|being shot|^waiting/.test(e.message || "");

  async function shoot(page, asked) {
    if (shooting.peek()) return false;
    shooting.value = page.key;
    try {
      await api.post("/api/bench/shot", { path: page.path, cut: page.cut, qid: page.qid, asked });
      page.shot = true;
      data.value = { ...data.peek() };
      return true;
    } catch (e) {
      if (isWait(e)) shootWait.value = { ...shootWait.peek(), [page.key]: e.message };
      else shootErrors.value = { ...shootErrors.peek(), [page.key]: e.message };
      return false;
    } finally {
      shooting.value = null;
    }
  }

  function shootNow(e, page) {
    e.stopPropagation();
    const { [page.key]: _e, ...errors } = shootErrors.peek();
    const { [page.key]: _w, ...waits } = shootWait.peek();
    const { [page.key]: _s, ...kept } = shots.peek();
    shootErrors.value = errors;
    shootWait.value = waits;
    shots.value = kept;
    if (page.shot) fetchShot(page.key);
    else shoot(page, true);
  }

  function schedule() {
    clearTimeout(timer);
    if (!shown) return;
    const measuring = api.measuring.peek() || data.peek()?.measuring;
    timer = setTimeout(async () => {
      if (!document.hidden) await load();
      schedule();
    }, measuring ? POLL_MEASURING_MS : POLL_MS);
  }

  function onResize() { vh.value = window.innerHeight; }

  // -- parts

  function useWidth() {
    const ref = useRef(null);
    const [w, setW] = useState(0);
    useLayoutEffect(() => {
      const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
      ro.observe(ref.current);
      return () => ro.disconnect();
    }, []);
    return [ref, w];
  }

  function MemGlyph({ memory }) {
    const kind = memory === "claude" ? "ring" : memory === "none" ? "ring" : "dot";
    return html`<span class=${`bx-g-${memory}`} style=${{ color: memColour(memory), display: "inline-flex" }}>
      <${Glyph} kind=${kind} title=${MEMORY[memory] || memory} /></span>`;
  }

  function memColour(memory) {
    return { tensors: "var(--ssd)", words: "var(--vault)", ram: "var(--ram)", none: "var(--ink-3)",
      claude: "var(--ink-2)", open: "var(--ink)", mac: "var(--ink-3)" }[memory] || "var(--ink-3)";
  }

  function Swatch({ memory }) {
    const dash = memory === "claude" ? "5 3" : memory === "mac" ? "1 3" : null;
    const hollow = memory === "claude";
    return html`<svg width="22" height="10" viewBox="0 0 22 10" aria-hidden="true">
      <line x1="0" y1="5" x2="22" y2="5" stroke=${memColour(memory)} stroke-width=${memory === "none" ? 1 : 1.5}
        stroke-dasharray=${dash} />
      <circle cx="11" cy="5" r="2.6" fill=${hollow ? "var(--void)" : memColour(memory)} stroke=${memColour(memory)}
        stroke-width="1.2" /></svg>`;
  }

  function Counts({ t }) {
    if (!t || !t.graded) return html`<span class="bx-counts t-readout dim">—</span>`;
    const wrong = (t.wrong || 0) + (t.stale || 0) + (t.false_memory || 0);
    const title = `${t.right} right · ${t.wrong} wrong · ${t.stale} stale · ${t.false_memory} false memories · ${t.declined} declined · ${t.graded} graded`;
    return html`<span class="bx-counts t-readout" title=${title}>
      <span><${Glyph} kind="check" /> ${t.right}</span>
      <span class="x"><${Glyph} kind="cross" /> ${wrong}</span>
      <span class="e"><${Glyph} kind="empty" /> ${t.declined || 0}</span></span>`;
  }

  // One chart: a calibrated SVG plot. Lines and points in the contender's memory hue; Claude a hollow dashed grey;
  // false memories hang under their point as red crosses, one each; walls are context windows.
  function Chart({ label, head = null, series, x, y, height = 220, walls = [], cuts = [], refs = [], dots = true,
    bands = false, fm = false, ends = true, legendBy = "memory", empty, tip, onPick = pick }) {
    const [ref, W] = useWidth();
    const [hover, setHover] = useState(null);
    const [focus, setFocus] = useState(null); // a series id, or "class:<memory>"
    const has = series.some((s) => s.points.length);
    const M = { l: 58, r: ends ? 150 : 20, t: 22, b: 34 };
    const ph = height - M.t - M.b;
    const pw = Math.max(20, W - M.l - M.r);
    const sx = scale(x.kind, x.domain, [M.l, M.l + pw]);
    const sy = scale(y.kind, y.domain, [M.t + ph, M.t]);
    const inX = (v) => v >= x.domain[0] * 0.999 && v <= x.domain[1] * 1.001;
    const inY = (v) => v != null && (y.kind !== "log" || v > 0);
    const clampY = (v) => Math.max(M.t, Math.min(M.t + ph, sy(v)));
    const now = performance.now();
    tick.value; // redraw when results land

    const dimmed = (s) => focus && focus !== s.id && focus !== `class:${s.memory}`;

    function nearest(mx, my) {
      let best = null;
      for (const s of series) {
        if (dimmed(s)) continue;
        for (const p of s.points) {
          if (!inX(p.x) || !inY(p.y)) continue;
          const dx = sx(p.x) - mx, dy = clampY(p.y) - my;
          const d = dots ? dx * dx + dy * dy : dx * dx;
          if (!best || d < best.d) best = { d, p, s };
        }
      }
      if (!best) return null;
      if (dots && best.d > 18 * 18) return null;
      if (!dots) { // a time chart: every series at that x
        const at = best.p.x;
        const rows = series.map((s) => ({ s, p: s.points.reduce((a, q) => (Math.abs(q.x - at) < Math.abs((a?.x ?? Infinity) - at) ? q : a), null) }))
          .filter((r) => r.p && Math.abs(r.p.x - at) < 4 * 86400e3);
        return { ...best, rows };
      }
      return best;
    }

    function move(e) {
      const r = e.currentTarget.getBoundingClientRect();
      setHover(nearest(e.clientX - r.left, e.clientY - r.top));
    }

    const xt = x.ticks || (x.kind === "log" ? decades(...x.domain) : linTicks(...x.domain, 6));
    const yt = y.ticks || (y.kind === "log" ? decades(...y.domain) : linTicks(...y.domain, Math.max(2, Math.round(ph / 44))));
    const lines = [], points = [], marks = [], areas = [];
    for (const s of series) {
      const pts = s.points.filter((p) => inX(p.x) && inY(p.y));
      if (!pts.length) continue;
      const dim = dimmed(s) ? " bx-dim" : "";
      if (bands && s.points.some((p) => p.lo != null && p.hi != null)) {
        const up = pts.map((p) => `${sx(p.x).toFixed(1)},${clampY(p.hi).toFixed(1)}`);
        const down = pts.slice().reverse().map((p) => `${sx(p.x).toFixed(1)},${clampY(p.lo).toFixed(1)}`);
        areas.push(html`<polygon key=${`a${s.id}`} class=${`bx-band ${s.memory}${dim}`} points=${[...up, ...down].join(" ")} />`);
      }
      if (pts.length > 1) {
        const d = pts.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)} ${clampY(p.y).toFixed(1)}`).join("");
        lines.push(html`<path key=${`l${s.id}`} class=${`bx-ln ${s.memory}${dim}`} d=${d} />`);
      }
      if (!dots) continue;
      for (const p of pts) {
        const cx = sx(p.x), cy = clampY(p.y);
        if (!bands && (p.hi != null || p.lo != null)) {
          const a = clampY(p.lo ?? p.y), b = clampY(p.hi ?? p.y);
          if (Math.abs(a - b) > 1) marks.push(html`<line key=${`w${p.key}${s.id}`} class=${`bx-wh ${s.memory}${dim}`} x1=${cx} x2=${cx} y1=${a} y2=${b} />`);
        }
        const landed = fresh.get(p.key);
        if (landed && now - landed < FLARE_MS) {
          marks.push(html`<circle key=${`f${p.key}${s.id}${landed}`} class=${`bx-flare ${s.memory}`} cx=${cx} cy=${cy} r="9" />`);
        }
        const hot = hover && hover.p === p;
        points.push(html`<circle key=${`p${p.key}${s.id}`} class=${`bx-pt ${s.memory}${hot ? " hot" : ""}${dim}`}
          cx=${cx} cy=${cy} r=${hot ? 4.5 : 3.2} />`);
        if (fm && p.fm) {
          const n = Math.min(p.fm, 8);
          for (let i = 0; i < n; i++) {
            const yy = cy + 10 + i * 7;
            marks.push(html`<path key=${`x${p.key}${s.id}${i}`} class=${`bx-fm${dim}`} d=${`M${cx - 2.5} ${yy - 2.5}L${cx + 2.5} ${yy + 2.5}M${cx + 2.5} ${yy - 2.5}L${cx - 2.5} ${yy + 2.5}`} />`);
          }
          if (p.fm > n) marks.push(html`<text key=${`xm${p.key}${s.id}`} class="bx-fm-more" x=${cx + 6} y=${cy + 10 + (n - 1) * 7 + 3}>+${p.fm - n}</text>`);
        }
      }
    }

    const labels = [];
    if (ends && W > 0) {
      const placed = [];
      const cands = series.map((s) => {
        const pts = s.points.filter((p) => inX(p.x) && inY(p.y));
        if (!pts.length) return null;
        const p = pts[pts.length - 1];
        const text = s.short || s.label;
        const w = text.length * 6.3;
        const px = sx(p.x);
        const right = px + 8 + w <= W - 4;
        return { s, text, y: clampY(p.y) + 3.5, x0: right ? px + 8 : px - 8 - w, x1: right ? px + 8 + w : px - 8, anchor: right ? "start" : "end", tx: right ? px + 8 : px - 8 };
      }).filter(Boolean).sort((a, b) => a.y - b.y);
      const top = M.t + 8, bottom = M.t + ph + 2;
      const free = (c, yy) => !placed.some((q) => q.x0 < c.x1 && c.x0 < q.x1 && Math.abs(q.y - yy) < 11);
      for (const c of cands) {
        const want = Math.max(top, Math.min(bottom, c.y));
        let at = want;
        for (let k = 0; k < 60; k++) { // the nearest free row, below or above
          const yy = want + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * 11;
          if (yy < top || yy > bottom) continue;
          if (free(c, yy)) { at = yy; break; }
        }
        c.y = at;
        placed.push(c);
        labels.push(html`<text key=${`e${c.s.id}`} class=${`bx-end${dimmed(c.s) ? " bx-dim" : ""}`} x=${c.tx} y=${c.y}
          text-anchor=${c.anchor} onMouseEnter=${() => setFocus(c.s.id)} onMouseLeave=${() => setFocus(null)}>${c.text}</text>`);
      }
    }

    let tipEl = null;
    if (hover && W) {
      const left = sx(hover.p.x), top = clampY(hover.p.y);
      const lines_ = tip ? tip(hover) : [hover.s.label];
      const flip = left > W - 300;
      tipEl = html`<div class="bx-tip t-readout" style=${{ left: `${flip ? left - 312 : left + 14}px`, top: `${Math.max(0, top + 10)}px` }}>
        ${lines_.map((l) => html`<div>${l}</div>`)}</div>`;
    }

    const classes = [...new Set(series.filter((s) => s.points.length).map((s) => s.memory))];
    const faults = series.filter((s) => s.faults?.length);
    const anyFm = fm && series.some((s) => s.points.some((p) => p.fm));
    return html`<div class="bx-chart" ref=${ref}>
      <div class="bx-chart-head"><span class="t-label">${label}</span>${head}</div>
      ${!has ? html`<div class="empty" style=${{ minHeight: `${Math.max(80, height - 40)}px` }}>${empty}</div>`
        : W > 0 ? html`<svg width=${W - 2} height=${height} role="img" aria-label=${label}
            onMouseMove=${move} onMouseLeave=${() => setHover(null)}
            onClick=${() => hover && onPick(hover.p, hover.s)}>
          ${yt.map((v) => html`<line key=${`gy${v}`} class="bx-grid" x1=${M.l} x2=${M.l + pw} y1=${sy(v)} y2=${sy(v)} />`)}
          ${yt.map((v) => html`<text key=${`ty${v}`} class="bx-tick" x=${M.l - 8} y=${sy(v) + 3.5} text-anchor="end">${y.fmt(v)}</text>`)}
          ${xt.filter(inX).map((v) => html`<g key=${`tx${v}`}><line class="bx-ax" x1=${sx(v)} x2=${sx(v)} y1=${M.t + ph} y2=${M.t + ph + 4} />
            <text class="bx-tick" x=${sx(v)} y=${M.t + ph + 16} text-anchor="middle">${x.fmt(v)}</text></g>`)}
          <line class="bx-ax" x1=${M.l} x2=${M.l + pw} y1=${M.t + ph + 0.5} y2=${M.t + ph + 0.5} />
          <line class="bx-ax" x1=${M.l - 0.5} x2=${M.l - 0.5} y1=${M.t} y2=${M.t + ph} />
          ${cuts.filter((c) => inX(c.tokens)).map((c) => html`<g key=${`c${c.name}`}>
            <line class="bx-cutline" x1=${sx(c.tokens)} x2=${sx(c.tokens)} y1=${M.t - 4} y2=${M.t + ph} />
            <text class="bx-axlabel" x=${sx(c.tokens)} y=${M.t - 8} text-anchor="middle">${c.name}</text></g>`)}
          ${walls.filter((w) => inX(w.tokens)).map((w, i) => html`<g key=${`w${w.label}`}>
            <line class="bx-wall" x1=${sx(w.tokens)} x2=${sx(w.tokens)} y1=${M.t} y2=${M.t + ph} />
            <text class="bx-wall-label" x=${sx(w.tokens) + 5} y=${M.t + ph - 6 - i * 13}>${w.label}</text></g>`)}
          ${refs.map((r) => html`<g key=${`r${r.label}`}><line class="bx-ref" x1=${M.l} x2=${M.l + pw} y1=${sy(r.y)} y2=${sy(r.y)} />
            <text class="bx-ref-label" x=${M.l + pw} y=${sy(r.y) - 5} text-anchor="end">${r.label}</text></g>`)}
          ${areas}${lines}${marks}${points}${labels}
          ${hover && !dots ? html`<line class="bx-ax" x1=${sx(hover.p.x)} x2=${sx(hover.p.x)} y1=${M.t} y2=${M.t + ph} />` : null}
          <text class="bx-axlabel" x=${M.l + pw} y=${M.t + ph + 30} text-anchor="end">${x.label}</text>
          <text class="bx-axlabel" x="2" y=${M.t - 8} text-anchor="start">${y.label}</text>
        </svg>` : html`<div style=${{ height: `${height}px` }}></div>`}
      ${tipEl}
      ${has ? html`<div class="bx-legend t-readout">
        ${legendBy === "series" ? series.filter((s) => s.points.length).map((s) => html`<span key=${s.id}
            onMouseEnter=${() => setFocus(s.id)} onMouseLeave=${() => setFocus(null)}><${Swatch} memory=${s.memory} />${s.label}</span>`)
          : classes.map((m) => html`<span key=${m} onMouseEnter=${() => setFocus(`class:${m}`)} onMouseLeave=${() => setFocus(null)}>
          <${Swatch} memory=${m} />${LEGEND[m] || m}</span>`)}
        ${faults.map((s) => html`<span key=${`fault${s.id}`} class="fault-text" title=${s.faults.join(" · ")}><${Glyph} kind="cross" /> ${s.short || s.label}: ${s.faults.join(" · ")}</span>`)}
        ${anyFm ? html`<span class="fault-text"><${Glyph} kind="cross" /> one per false memory</span>` : null}
      </div>` : null}
    </div>`;
  }

  function pick(p) {
    if (p.path) openRecord(p.path, p.cut);
  }

  // -- axes

  const HISTORY = (series) => {
    const xs = allPoints(series).map((p) => p.x);
    const lo = Math.min(1e3, ...xs.filter((v) => v > 0).map((v) => 10 ** Math.floor(LOG10(v))));
    return { kind: "log", domain: [lo, 2.4e6], fmt: tokShort, label: "history told · tokens · log" };
  };
  const PCT = { kind: "lin", domain: [0, 1], ticks: [0, 0.25, 0.5, 0.75, 1], fmt: (v) => `${Math.round(v * 100)}%`, label: "right" };
  const PCT_FM = { ...PCT, domain: [-0.16, 1] }; // room under 0% for false memories to hang
  const SECONDS = (series) => {
    const ys = allPoints(series).flatMap((p) => [p.y, p.hi]).filter((v) => v > 0);
    return { kind: "log", domain: logDomain(ys, 0.01, 10), fmt: (v) => `${v >= 1 ? v : +v.toFixed(3)}${THIN}s`, label: "first word · log" };
  };
  const LIN = (series, label, unit, floor = 0, digits = null) => {
    const ys = allPoints(series).flatMap((p) => [p.y, p.hi]).filter((v) => v != null);
    const hi = niceMax(Math.max(floor, ...ys));
    return { kind: "lin", domain: [0, hi], label, fmt: (v) => `${digits != null ? v.toFixed(digits) : +v.toFixed(2)}${unit ? THIN + unit : ""}` };
  };
  const BYTES_X = (series) => {
    const xs = allPoints(series).map((p) => p.x);
    return { kind: "log", domain: logDomain(xs), fmt: (v) => { const [n, u] = fmt.bytes(v); return `${+n}${THIN}${u}`; },
      label: "memory on the SSD · log" };
  };
  const TOKENS_X = (series, label) => {
    const xs = allPoints(series).map((p) => p.x);
    return { kind: "log", domain: logDomain(xs), fmt: tokShort, label };
  };

  // -- what a point says when hovered

  function scoreTip({ p, s }) {
    return [
      html`${s.label}${p.cut ? html` <span class="dim">· ${p.cut}</span>` : null}`,
      html`<${Val} v=${pct(p.y)} /> right · ${p.right ?? "—"} of ${p.n ?? "—"} · ${p.fm ?? 0} false · ${p.declined ?? 0} declined`,
      p.tokens ? html`told <${Val} v=${fmt.tok(p.tokens)} />` : null,
      html`<span class="dim">${(p.path || "").split("/").pop()} · click to open</span>`,
    ].filter(Boolean);
  }

  function valueTip(unitFn, what) {
    return ({ p, s }) => [
      html`${s.label}${p.cut ? html` <span class="dim">· ${p.cut}</span>` : null}`,
      html`${what} <${Val} v=${unitFn(p.y)} />${p.hi != null ? html` · p90 <${Val} v=${unitFn(p.hi)} />` : null}${p.lo != null ? html` · lowest <${Val} v=${unitFn(p.lo)} />` : null}`,
      p.history ? html`history <${Val} v=${fmt.tok(p.history)} />` : null,
      p.notes != null ? html`vault notes ${fmt.int(p.notes)} · naps ${p.naps ?? "—"}` : null,
      p.n != null && s.chart === "life" ? html`${p.n} lives · knew ${p.right} of ${p.told} · ${p.fm} false · first word <${Val} v=${fmt.s(p.wait_s)} />` : null,
      p.path ? html`<span class="dim">${p.path.split("/").pop()} · click to open</span>` : null,
    ].filter(Boolean);
  }

  // -- the headline

  function Headline() {
    const h = data.value?.headline;
    const side = (label, v) => html`<div class="bx-fig">
      <span class="t-label">${label}</span>
      <span class="t-hero">${v ? (v.lo === v.hi ? v.lo : `${v.lo}–${v.hi}`) : "—"}<span class="of">/${THIN}${v?.told ?? "—"}</span></span>
      ${v ? html`<button class="src t-readout" title=${v.paths.join("\n")} onClick=${() => openRecord(v.paths[0])}>
          records/${v.paths[0]}${v.paths.length > 1 ? ` +${v.paths.length - 1}` : ""}</button>
        <span class="t-readout dim">${v.lives} ${v.lives === 1 ? "life" : "lives"} · ${v.contenders.join(", ")}</span>
        <span class="t-readout dim">first word <${Val} v=${fmt.s(v.wait_s)} /> median · peak RAM <${Val} v=${gb(v.peak_ram_gb)} /></span>`
        : html`<span class="t-readout dim">no ruler lives recorded</span>`}
    </div>`;
    return html`<div class="bx-head">
      ${side(`${h?.model || "Qwen 27B"} · with memory · knew of what it was told`, h?.with)}
      ${side("without", h?.without)}
      <div class="bx-claim t-body">better, never heavier</div>
    </div>`;
  }

  // -- the tabs

  function counts() {
    const d = data.value;
    if (!d) return {};
    const out = {};
    for (const t of TABS) out[t.id] = runsFor(t.id).length;
    return out;
  }

  function runsFor(id) {
    const runs = data.value?.runs || [];
    const suite = (r) => r.kind === "suite";
    if (id === "window") return runs.filter((r) => r.task === "longhaul" || suite(r) || r.kind === "ruler-speed");
    if (id === "grows") return runs.filter((r) => ["speed", "throughput", "life", "errands", "ruler-speed"].includes(r.kind)
      || (r.task === "longhaul" && (r.memory === "tensors" || r.memory === "words")));
    if (id === "reach") return runs.filter((r) => /reach/.test(r.task || ""));
    if (id === "sleep") return runs.filter((r) => /sleep/.test(r.task || "") || r.kind === "speed"
      || (r.task === "longhaul" && r.memory === "tensors"));
    if (id === "gap") return runs.filter((r) => r.kind === "webdev");
    return [];
  }

  function Tabs() {
    const n = counts();
    return html`<div class="bx-tabs" role="tablist" aria-label="Bench questions">
      ${TABS.map((t) => html`<button class="bx-tab" role="tab" aria-selected=${tab.value === t.id ? "true" : "false"}
        tabindex=${tab.value === t.id ? 0 : -1} data-tab=${t.id} onClick=${() => setTab(t.id)}>${t.label}<span class="n">${n[t.id] ?? 0}</span></button>`)}
    </div>`;
  }

  function heroH() { return Math.max(240, Math.min(420, Math.round((vh.value - 44) * 0.36))); }
  function twinH() { return Math.max(210, Math.min(320, Math.round((vh.value - 44) * 0.28))); }

  function walls(series) {
    const d = data.value;
    const out = new Map();
    for (const s of series) {
      const w = s.window || (s.model && d.windows[s.model]);
      if (!w) continue;
      const name = s.memory === "claude" ? "claude" : s.model;
      out.set(`${name}${w}`, { tokens: w, label: `${name} · ${windowShort(w)} window` });
    }
    return [...out.values()].sort((a, b) => a.tokens - b.tokens);
  }

  function chartSeries(chart, filter = () => true) {
    return (data.value?.series || []).filter((s) => s.chart === chart && filter(s));
  }

  function PastTheWindow() {
    const d = data.value;
    const all = chartSeries("score");
    const tasks = [...new Set(all.map((s) => s.task))].sort((a, b) => (a === "longhaul" ? -1 : b === "longhaul" ? 1 : a.localeCompare(b)));
    const t = tasks.includes(task.value) ? task.value : tasks[0] || "longhaul";
    const score = all.filter((s) => s.task === t);
    const ttft = chartSeries("ttft");
    const peak = chartSeries("peak");
    const ram = d.ram_gb;
    const head = tasks.length > 1 ? html`<div class="seg">${tasks.map((k) => html`<button aria-pressed=${k === t ? "true" : "false"}
      onClick=${() => { task.value = k; }}>${TASKS[k] || k}</button>`)}</div>` : null;
    return html`<div class="bx-panel">
      <${Chart} label=${`Score against history · ${TASKS[t] || t}`} head=${head} series=${score} x=${HISTORY(score)} y=${PCT_FM}
        height=${heroH()} walls=${walls(score)} cuts=${t === "longhaul" ? d.cuts : []} fm=${true} tip=${scoreTip}
        empty=${"no scored runs yet · python -m camr_engine.bench.longhaul or camr_engine.bench.local longhaul fills this"} />
      <div class="bx-twins">
        <${Chart} label="First word against history" series=${ttft} x=${HISTORY(ttft)} y=${SECONDS(ttft)} height=${twinH()}
          cuts=${d.cuts} tip=${valueTip(fmt.s, "first word")}
          empty=${"no first-word times yet · any Long Haul run or the throughput test fills this"} />
        <${Chart} label="Peak RAM against history" series=${peak} x=${HISTORY(peak)} y=${LIN(peak, "peak RAM", "GB", ram || 0)}
          height=${twinH()} cuts=${d.cuts} refs=${ram ? [{ y: ram, label: `RAM ${ram}${THIN}GB` }] : []} tip=${valueTip(gb, "peak")}
          empty=${"no peak RAM yet · local Long Haul runs record it"} />
      </div>
      <${Runs} id="window" />
    </div>`;
  }

  function HowFar() {
    const retr = chartSeries("retrieval");
    const gbps = chartSeries("gbps");
    const life = chartSeries("life");
    const decode = chartSeries("decode");
    const weeks = allPoints(life).map((p) => p.x);
    const lifeX = { kind: "lin", domain: [1, Math.max(12, ...weeks)], ticks: linTicks(1, Math.max(12, ...weeks), 6).filter((v) => v >= 1),
      fmt: (v) => `${v}`, label: "week of the life" };
    const bx = BYTES_X([...retr, ...gbps]);
    return html`<div class="bx-panel">
      <${Chart} label="Retrieval against the memory's size · choose, read, lay the desk" series=${retr} x=${bx}
        y=${LIN(retr, "retrieval", "ms")} height=${heroH()} tip=${valueTip(fmt.ms, "retrieval")}
        empty=${"no retrieval times yet · python -m camr_engine.bench.local speed fills this as the memory grows"} />
      <${Chart} label="SSD read speed against the memory's size" series=${gbps} x=${bx}
        y=${LIN(gbps, "read", "GB/s", 8)} height=${Math.round(twinH() * 0.8)} tip=${valueTip(fmt.gbps, "read")}
        empty=${"no SSD reads yet"} />
      <div class="bx-twins">
        <${Chart} label="The ruler's lives · knew of what was told" series=${life} x=${lifeX} y=${PCT} height=${twinH()}
          bands=${false} tip=${valueTip(pct, "knew")} empty=${"no ruler lives yet · python -m camr_engine.ruler fills this"} />
        <${Chart} label="Decode speed against desk tokens" series=${decode} x=${TOKENS_X(decode, "tokens read · log")}
          y=${LIN(decode, "decode", "tok/s")} height=${twinH()} tip=${valueTip(fmt.tps, "decode")}
          empty=${"no decode speeds yet · the throughput test fills this"} />
      </div>
      <${Runs} id="grows" />
    </div>`;
  }

  function Sleep() {
    const rooms = chartSeries("rooms");
    return html`<div class="bx-panel">
      <${Chart} label="Rooms awake on the SSD, asleep in the vault, hot in RAM" series=${rooms} x=${HISTORY(rooms)}
        y=${LIN(rooms, "rooms", "")} height=${heroH()} cuts=${data.value.cuts} tip=${valueTip((v) => [fmt.int(v), "rooms"], "")}
        empty=${"no sleep yet · the engine's Long Haul records its naps and the rooms it puts to sleep"} />
      <${Runs} id="sleep" />
    </div>`;
  }

  function Generic({ id, what }) {
    const runs = runsFor(id);
    return html`<div class="bx-panel">
      ${runs.length ? html`<div class="bx-chart"><div class="bx-chart-head"><span class="t-label">score by run</span></div>
        <div class="bx-bars">${runs.map((r) => html`<div class="bx-bar t-readout" key=${r.path}>
          <span><${MemGlyph} memory=${r.memory} /> ${r.label}</span>
          <span class="track"><i class=${`bx-fill-${r.memory}`} style=${{ width: `${100 * Math.min(1, r.score ?? 0)}%` }}></i></span>
          <span class="r"><${Val} v=${pct(r.score)} /> · ${r.right ?? "—"} of ${r.graded ?? "—"}</span></div>`)}</div></div>`
        : html`<${Empty}>${what}<//>`}
      <${Runs} id=${id} />
    </div>`;
  }

  function Gap() {
    const w = webdev.value;
    if (!w) return html`<div class="bx-panel"><${Empty}>reading the WebDev Arena history…<//></div>`;
    if (!w.present) return html`<div class="bx-panel"><${Empty}>no WebDev Arena history · python -m camr_engine.bench.suites webdev fills this${w.error ? ` · ${w.error}` : ""}<//></div>`;
    const t = (s) => Date.parse(`${s}T00:00:00Z`);
    const mk = (id, label, memory, items) => ({ id, label, memory, chart: "gap",
      points: (items || []).map((i) => ({ x: t(i.date), y: i.rating, lo: i.lo, hi: i.hi, model: i.model, date: i.date, key: `${id}${i.date}` })) });
    const series = [mk("claude", "best Claude", "claude", w.series.claude), mk("open", "best open weights", "open", w.series.open)];
    for (const [k, items] of Object.entries(w.series)) {
      if (k.startsWith("mac:")) series.push(mk(k, `${k.slice(4)} · runs on this Mac`, "mac", items));
    }
    const pts = allPoints(series);
    if (!pts.length) return html`<div class="bx-panel"><${Empty}>the WebDev Arena history holds no overall ratings<//></div>`;
    const ys = pts.flatMap((p) => [p.lo, p.hi]).filter((v) => v != null);
    const lo = Math.floor(Math.min(...ys) / 100) * 100, hi = Math.ceil(Math.max(...ys) / 100) * 100;
    const xs = pts.map((p) => p.x);
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    const months = [];
    const d0 = new Date(x0);
    for (let d = new Date(Date.UTC(d0.getUTCFullYear(), d0.getUTCMonth() + 1, 1)); d.getTime() <= x1; d.setUTCMonth(d.getUTCMonth() + 2)) months.push(d.getTime());
    const x = { kind: "lin", domain: [x0, x1], ticks: months, label: "publication",
      fmt: (v) => new Date(v).toLocaleDateString("en-GB", { month: "short", year: "2-digit", timeZone: "UTC" }) };
    const y = { kind: "lin", domain: [lo, hi], label: "rating", fmt: (v) => `${v}` };
    const last = (s) => s.points[s.points.length - 1];
    const lc = last(series[0]), lo_ = last(series[1]);
    const tip = (h) => [html`<span class="dim">${new Date(h.p.x).toISOString().slice(0, 10)}</span>`,
      ...h.rows.map((r) => html`${r.s.label}: ${r.p.model} · ${r.p.y.toFixed(0)} <span class="dim">(${r.p.lo.toFixed(0)}–${r.p.hi.toFixed(0)})</span>`)];
    return html`<div class="bx-panel">
      <${Chart} label="WebDev Arena · how models rated at building web pages · overall board" series=${series} x=${x} y=${y}
        height=${heroH()} dots=${false} bands=${true} legendBy="series" tip=${tip} onPick=${() => {}}
        head=${lc && lo_ ? html`<span class="t-readout">gap now <${Val} v=${[(lc.y - lo_.y).toFixed(0), "points"]} /> · <span class="dim">${lc.model} against ${lo_.model}</span></span>` : null} />
      <div class="t-readout dim">${w.publications} publications · ${w.models ?? "—"} models · ${w.source || "lmarena-ai/leaderboard-dataset"} · bands are 95% intervals · records/${w.path}</div>
      <${Runs} id="gap" />
    </div>`;
  }

  // -- the run table: each row opens its dated record with Enter

  function Runs({ id }) {
    const runs = runsFor(id);
    if (!runs.length) return null;
    const all = showAll.value[id];
    const rows = all ? runs : runs.slice(0, ROWS);
    const open = (r) => openRecord(r.path);
    return html`<div class="bx-wrap"><table class="bx-runs t-readout">
      <thead><tr class="t-label">
        <th>When</th><th>Task</th><th>Contender</th><th class="cuts">Cuts</th><th class="r">Right</th><th class="r">False</th>
        <th class="r">First word</th><th class="r">Decode</th><th class="r">Retrieval</th><th class="r read">Read</th>
        <th class="r">Peak RAM</th><th class="r">Cost</th></tr></thead>
      <tbody>${rows.map((r) => html`<tr key=${r.path} tabindex="0" title=${`records/${r.path}${r.cuts?.length ? ` · ${r.cuts.join(" ")}` : ""}`}
        onClick=${() => open(r)} onKeyDown=${(e) => { if (e.key === "Enter") { e.preventDefault(); open(r); } }}>
        <td>${when(r.started)}</td>
        <td>${TASKS[r.task] || r.task}</td>
        <td class="c"><${MemGlyph} memory=${r.memory} />${r.label}${r.persona ? html` <span class="dim">· ${r.persona}</span>` : null}</td>
        <td class="cuts" title=${r.limit ? `at most ${r.limit} questions asked` : null}>${(r.cuts || []).join(" ") || "—"}${r.limit ? html` <span class="dim">· smoke</span>` : null}</td>
        <td class="r">${r.graded ? html`${r.right}/${r.graded} <span class="dim">${pct(r.score)[0]}%</span>` : r.publications ? `${r.publications} publ.` : "—"}</td>
        <td class="r">${r.false_memory ? html`<span class="fault-text"><${Glyph} kind="cross" /> ${r.false_memory}</span>` : r.graded ? "0" : "—"}</td>
        <td class="r"><${Val} v=${fmt.s(r.ttft_s)} /></td>
        <td class="r"><${Val} v=${fmt.tps(r.decode_tps)} /></td>
        <td class="r"><${Val} v=${fmt.ms(r.retrieval_ms)} /></td>
        <td class="r read"><${Val} v=${fmt.gbps(r.gbps)} /></td>
        <td class="r"><${Val} v=${gb(r.peak_ram_gb)} /></td>
        <td class="r">${T(usd(r.cost_usd))}</td></tr>`)}</tbody></table>
      ${runs.length > ROWS ? html`<button class="btn bx-more" onClick=${() => { showAll.value = { ...showAll.value, [id]: !all }; }}>
        ${all ? "fewer" : `all ${runs.length} runs`}</button>` : null}
    </div>`;
  }

  // -- the probe matrix: eight probes against every contender, four cuts in each cell

  // The cut on show: the one picked, else the furthest any local contender reached. The caller passes the pick, so
  // Matrix reads cutPick.value (and redraws on a click) while shootNext only peeks.
  function matrixCut(picked) {
    const d = data.peek();
    if (!d) return null;
    const names = d.cuts.map((c) => c.name);
    if (picked && names.includes(picked)) return picked;
    const has = (cut, local) => d.contenders.some((c) => (local ? c.memory !== "claude" : true) && d.matrix[c.id]?.[cut]);
    return [...names].reverse().find((cut) => has(cut, true)) || [...names].reverse().find((cut) => has(cut, false)) || names[0];
  }

  function Square({ cell, fam, memory, selected }) {
    const t = cell ? (fam ? cell.families[fam] : cell.all) : null;
    const cls = selected ? " sel" : "";
    if (!cell) return html`<i class=${`miss${cls}`} title="no run at this cut"></i>`;
    if (!t || !t.graded) return html`<i class=${`none${cls}`} title="not asked at this cut"></i>`;
    const f = Math.round(8 + 92 * (t.score || 0));
    const hue = { tensors: "--ssd", words: "--vault", ram: "--ram", claude: "--ink-2" }[memory] || "--ink-3";
    return html`<i class=${cls.trim()} style=${{ background: `color-mix(in srgb, var(${hue}) ${f}%, black)` }}
      title=${`${pct(t.score)[0]}% · ${t.right} of ${t.graded}`}></i>`;
  }

  function Thumb({ page }) {
    useEffect(() => { if (page?.key && page.shot && !shots.peek()[page.key]) fetchShot(page.key); }, [page?.key, page?.shot]);
    if (!page) return html`<span class="bx-thumb wait t-label">no run</span>`;
    if (!page.key) return html`<span class="bx-thumb wait t-label">${page.verdict === "declined" ? "declined" : "no page"}</span>`;
    const s = shots.value[page.key];
    if (s?.png) {
      return html`<button class="bx-thumb" title=${`${page.label} · ${page.cut} · ${page.verdict}: open the screenshot`}
        onClick=${(e) => { e.stopPropagation(); sheet.value = { type: "shot", page }; }}><img src=${s.png} alt=${`the catering page ${page.label} wrote`} /></button>`;
    }
    if (shooting.value === page.key) return html`<span class="bx-thumb wait t-label">shooting</span>`;
    const err = shootErrors.value[page.key] || s?.error;
    if (err) {
      return html`<button class="bx-thumb wait shoot t-label fault-text" title=${`${err} · click to try again`}
        onClick=${(e) => shootNow(e, page)}><${Glyph} kind="cross" /> not shot</button>`;
    }
    const d = data.value;
    if (api.measuring.value || d?.measuring) return html`<span class="bx-thumb wait t-label">after measuring</span>`;
    const wait = shootWait.value[page.key];
    if (d?.shoot?.auto && !wait) return html`<span class="bx-thumb wait t-label">waiting</span>`;
    return html`<button class="bx-thumb wait shoot t-label"
      title=${`${wait || d?.shoot?.why || "quiet"} · click to shoot it in a headless browser, network off`}
      onClick=${(e) => shootNow(e, page)}>shoot</button>`;
  }

  function Matrix() {
    const d = data.value;
    const cons = d.contenders;
    const cut = matrixCut(cutPick.value);
    tick.value;
    const head = html`<div class="bx-sub">
      <span class="t-label">Probe matrix · Long Haul · squares 64K 256K 1M 2M · counts at ${cut}</span>
      <div class="seg">${d.cuts.map((c) => html`<button aria-pressed=${c.name === cut ? "true" : "false"}
        onClick=${() => { cutPick.value = c.name; shootNext(); }}>${c.name}</button>`)}</div></div>`;
    if (!cons.length) return html`<div class="bx-panel">${head}<${Empty}>no Long Haul runs yet · python -m camr_engine.bench.longhaul claude or camr_engine.bench.local longhaul fills this<//></div>`;
    const cols = `150px repeat(${cons.length}, minmax(136px, 1fr))`;
    const pageOf = (c) => d.pages.find((p) => p.contender === c.id && p.cut === cut && p.qid === "page-catering");
    const cell = (c, fam, last = false) => {
      const row = d.matrix[c.id] || {};
      const at = row[cut];
      const t = at ? (fam ? at.families[fam] : at.all) : null;
      return html`<div class=${`bx-mcell${last ? " all" : ""}`} key=${c.id + (fam || "all")}
        onClick=${() => at && openRecord(at.path, cut)} style=${{ cursor: at ? "pointer" : "default" }}>
        <span class="bx-sq">${d.cuts.map((k) => html`<${Square} key=${k.name} cell=${row[k.name]} fam=${fam} memory=${c.memory} selected=${k.name === cut} />`)}</span>
        <${Counts} t=${t} />
        ${fam === "page" ? html`<${Thumb} page=${at ? pageOf(c) : null} />` : null}
      </div>`;
    };
    return html`<div class="bx-panel">${head}<div class="bx-wrap">
      <div class="bx-matrix" style=${{ gridTemplateColumns: cols }} role="table" aria-label="Long Haul probe matrix">
        <div class="bx-mcell lab head t-label">probe</div>
        ${cons.map((c) => html`<div class="bx-mcell head" key=${`h${c.id}`}>
          <span class="t-readout"><${MemGlyph} memory=${c.memory} />${c.label}</span>
          <span class="t-label">${MEMORY[c.memory] || c.memory}</span>
          <span class="t-label">${c.window ? `${windowShort(c.window)} window` : "window —"}</span></div>`)}
        ${d.families.map((f) => html`
          <div class="bx-mcell lab t-body" key=${`f${f.id}`}>${f.label}</div>
          ${cons.map((c) => cell(c, f.id))}`)}
        <div class="bx-mcell lab all t-label">all probes</div>
        ${cons.map((c) => cell(c, null, true))}
      </div></div></div>`;
  }

  // -- the yardstick: what Claude cost, against the night's cap

  function Yardstick() {
    const L = data.value?.ledger;
    if (!L || !L.present) return html`<aside class="bx-yard"><span class="t-label">Yardstick · Claude alone</span>
      <${Empty}>no Claude calls yet · records/bench/claude-ledger.jsonl fills this<//></aside>`;
    const frac = Math.min(1, (L.spent_usd || 0) / L.cap_usd);
    const limit = (L.cap_usd - L.headroom_usd) / L.cap_usd;
    const kv = (k, v) => html`<div class="bx-kv t-readout"><span class="k">${k}</span><span>${v}</span></div>`;
    return html`<aside class="bx-yard" aria-label="Claude yardstick">
      <span class="t-label">Yardstick · Claude alone, no memory</span>
      <div><span class="t-figure"><${Val} v=${usd(L.spent_usd)} /></span><span class="t-readout dim"> of ${T(usd(L.cap_usd))} for the night</span>
        <div class="bx-cap" title=${`calls are refused past ${T(usd(L.cap_usd - L.headroom_usd))}`}>
          <i style=${{ width: `${100 * frac}%` }}></i><b style=${{ left: `${100 * limit}%` }}></b></div>
        <div class="t-readout dim" style=${{ marginTop: "6px" }}>held ${T(usd(L.held_usd))} · ${L.refused} refused · list prices</div></div>
      ${L.models.map((m) => html`<div class="bx-model" key=${m.model}>
        <div class="name t-readout"><span><${MemGlyph} memory="claude" /> ${m.label}</span><span>${T(usd(m.cost_usd))}</span></div>
        ${kv("input", T(fmt.tok(m.input_tokens)))}
        ${kv("cache read", T(fmt.tok(m.cache_read_tokens)))}
        ${kv("cache write", T(fmt.tok(m.cache_write_tokens)))}
        ${kv("output", html`${T(fmt.tok(m.output_tokens))}${m.thinking_tokens ? html` <span class="dim">· ${fmt.int(m.thinking_tokens)} thinking</span>` : null}`)}
        ${kv("calls", html`${m.calls}${m.failed ? html` · <span class="fault-text"><${Glyph} kind="cross" /> ${m.failed} failed</span>` : null}`)}
        ${m.longhaul ? kv("Long Haul right", `${m.longhaul.right} / ${m.longhaul.graded}`) : null}
        ${m.longhaul ? kv("per right answer", T(usd(m.longhaul.per_right_usd))) : null}
      </div>`)}
    </aside>`;
  }

  // -- sheets: a record, or a page's screenshot

  function RecordSheet() {
    const s = sheet.value;
    const r = record.value;
    const ref = useRef(null);
    useEffect(() => {
      if (r && s?.cut && ref.current) ref.current.querySelector(`[data-group="${CSS.escape(s.cut)}"]`)?.scrollIntoView({ block: "start" });
    }, [r, s?.cut]);
    const chip = (k, v) => (v == null || v === "" ? null : html`<span><span class="k">${k}</span> ${String(v)}</span>`);
    return html`<aside class="bx-sheet" ref=${ref} aria-label="Record">
      <div class="bx-sheet-top"><div>
        <div class="t-label">Record</div>
        <div class="t-head">${r?.label || "…"}</div>
        <div class="t-readout path">records/${s.path}</div></div>
        <button class="bx-x" title="close (Esc)" onClick=${close}><${Icon} name="x" /></button></div>
      ${!r ? html`<span class="t-readout dim">reading…</span>` : r.error ? html`<span class="t-readout fault-text"><${Glyph} kind="cross" /> ${r.error}</span>` : html`
        <div class="bx-chips t-readout">
          ${chip("kind", r.kind)}${chip("task", r.task)}${chip("memory", MEMORY[r.memory])}
          ${chip("started", r.started && when(r.started))}${chip("finished", r.finished && when(r.finished))}
          ${chip("size", T(fmt.bytes(r.bytes)))}
          ${Object.entries(r.environment || {}).map(([k, v]) => chip(k, v))}</div>
        ${r.groups.map((g) => html`<div class=${`bx-group${s.cut === g.name ? " at" : ""}`} data-group=${g.name} key=${g.name}>
          <span class="t-label">${g.name}</span>
          <div class="bx-chips t-readout">${Object.entries(g.summary || {}).slice(0, 24).map(([k, v]) => chip(k, typeof v === "number" ? +v.toFixed(4) : v))}</div>
          ${(g.rows || []).length ? html`<div class="bx-chips t-readout">${g.rows.map((row) => html`<div>${Object.entries(row).map(([k, v]) => chip(k, v))}</div>`)}</div>` : null}
          ${(g.answers || []).map((a) => html`<div class="bx-ans" key=${a.id}>
            <span class="id t-readout"><span class=${a.right === true || a.verdict === "right" || a.verdict === "right_abstain" ? "ok" : (a.verdict === "declined" ? "" : "bad")}>
              <${Glyph} kind=${a.right === true || /^right/.test(a.verdict || "") ? "check" : a.verdict === "declined" ? "empty" : "cross"} /></span>
              ${a.id} · ${a.verdict || "—"}${a.ttft_s != null ? html` · <${Val} v=${fmt.s(a.ttft_s)} />` : null}</span>
            ${a.question ? html`<span class="q">${a.question}</span>` : null}
            ${a.expected ? html`<span class="t-readout why">expected ${a.expected}</span>` : null}
            ${a.answer ? html`<span class="a">${a.answer}</span>` : null}
            ${a.reason ? html`<span class="t-readout why">${a.reason}</span>` : null}
          </div>`)}
        </div>`)}`}
    </aside>`;
  }

  function ShotSheet() {
    const p = sheet.value.page;
    const s = shots.value[p.key];
    return html`<aside class="bx-sheet wide" aria-label="Page screenshot">
      <div class="bx-sheet-top"><div>
        <div class="t-label">The page that grows · ${p.cut}</div>
        <div class="t-head">${p.label}</div>
        <div class="t-readout path">records/${p.path} · ${p.qid}</div></div>
        <button class="bx-x" title="close (Esc)" onClick=${close}><${Icon} name="x" /></button></div>
      <div class="t-readout ${p.verdict === "right" ? "" : "fault-text"}">${p.verdict === "right" ? html`<${Glyph} kind="check" /> passes every check` : html`<${Glyph} kind="cross" /> ${p.verdict}${p.reason ? ` · ${p.reason}` : ""}`}</div>
      ${s?.png ? html`<img class="bx-shot" src=${s.png} alt=${`the catering page ${p.label} wrote, shot in a headless browser`} />
        <span class="t-readout dim">a real headless-browser screenshot · network off · ${s.width} × ${s.height}${THIN}px · ${T(fmt.bytes(s.bytes))}</span>
        <button class="btn" style=${{ alignSelf: "flex-start" }} onClick=${() => openRecord(p.path, p.cut)}>open the record</button>`
        : html`<span class="t-readout dim">${s?.error || "loading…"}</span>`}
    </aside>`;
  }

  function close() {
    sheet.value = null;
    record.value = null;
  }

  // -- the screen

  function Screen() {
    const d = data.value;
    if (!d) {
      return loadError.value ? html`<${Empty} fill=${true}><span class="fault-text"><${Glyph} kind="cross" /></span> the records could not be read · ${loadError.value}<//>`
        : html`<${Empty} fill=${true}>reading the records…<//>`;
    }
    const m = api.measuring.value || d.measuring;
    const t = tab.value;
    return html`<div class="bx">
      <div class="bx-main">
        ${m ? html`<div class="bx-note t-label"><span class="on">measuring · ${m.job}</span> results flare as they land · pages are shot after it</div>` : null}
        ${loadError.value ? html`<div class="bx-note t-readout fault-text"><${Glyph} kind="cross" /> ${loadError.value}</div>` : null}
        <${Headline} />
        <${Tabs} />
        ${t === "window" ? html`<${PastTheWindow} />` : t === "grows" ? html`<${HowFar} />` : t === "sleep" ? html`<${Sleep} />`
          : t === "gap" ? html`<${Gap} />`
          : html`<${Generic} id="reach" what="no reach runs yet · a run reading session, project, agent and global, one at a time and together, fills this" />`}
        <${Matrix} />
        ${d.errors.length ? html`<div class="bx-errors t-readout" title=${d.errors.map((e) => `${e.path}: ${e.error}`).join("\n")}>
          <span class="fault-text"><${Glyph} kind="cross" /></span> ${d.errors.length} ${d.errors.length === 1 ? "record" : "records"} could not be read (one may be being written)</div>` : null}
      </div>
      <${Yardstick} />
      ${sheet.value?.type === "record" ? html`<${RecordSheet} />` : sheet.value?.type === "shot" ? html`<${ShotSheet} />` : null}
    </div>`;
  }

  render(html`<${Screen} />`, el);

  return {
    show() {
      shown = true;
      window.addEventListener("resize", onResize);
      load().then(schedule);
    },
    hide() {
      shown = false;
      clearTimeout(timer);
      timer = null;
      window.removeEventListener("resize", onResize);
    },
    key(e, { typing }) {
      if (e.key === "Escape" && sheet.value) { close(); return true; }
      if (typing) return false;
      const on = document.activeElement?.dataset?.tab;
      if (on && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
        const i = TABS.findIndex((x) => x.id === on);
        const next = TABS[(i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length].id;
        setTab(next);
        setTimeout(() => el.querySelector(`[data-tab="${next}"]`)?.focus(), 0);
        return true;
      }
      return false;
    },
  };
}
