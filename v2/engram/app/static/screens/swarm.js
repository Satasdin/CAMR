// Swarm: the multi-well plate. N agents (up to eight) on one task, each with its own memory (its agent reach).
// Top: the plate, eight wells in a 2 × 4 grid, each the agent's own rooms as tiles (blue on the SSD, an amber ring
// while a copy sits in RAM, green where its last step used what it picked); click a well to fill the plate.
// Under it: the shared RAM bar, the one hot-room budget over time, sliced by which agent's rooms hold it.
// Then one channel row per agent on one clock: amber bands while it holds the desk, ticks for its reads (blue SSD,
// amber RAM, violet words, green used), grey connectors for what it posted to the others, and its tokens, tasks
// done and time. Agents are told apart by place and label, never by colour.
// The swarm's persona and memory switch are its own (kept in this browser, like the number of agents): the Code
// screen's choice is only where they start. An ask shows exactly what will run, and "allow once" wakes only after the
// card has been on screen a moment and scrolled to its end.

const N_KEY = "engram.swarm.n";
const PERSONA_KEY = "engram.swarm.persona";
const MEMORY_KEY = "engram.swarm.memory";
const LIVE = new Set(["queued", "thinking", "tool", "waiting", "measuring", "keeping"]);
const ASK_WAKE_MS = 700;
const HIDDEN = /[\p{Cc}\p{Cf}\p{Zl}\p{Zp}]/gu;

// control and invisible characters drawn visibly (new lines and tabs stay as they are)
function visible(text) {
  return String(text ?? "").replace(HIDDEN, (c) => (c === "\n" || c === "\t" ? c
    : `⟨U+${c.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}⟩`));
}

function stored(key) {
  try { const v = localStorage.getItem(key); return v == null ? null : JSON.parse(v); } catch { return null; }
}
function store(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private window */ }
}
const HALF = { read: 400, used: 4000 };
const STYLE = `
.sw { position: absolute; inset: 0; display: grid; grid-template-rows: auto minmax(220px, 55%) auto minmax(0, 1fr);
  min-height: 640px; background: var(--bed); }
.sw-bar { display: flex; align-items: flex-end; gap: var(--sp-3); padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--hair); background: var(--s1); flex-wrap: wrap; }
.sw-bar label { display: flex; flex-direction: column; gap: 4px; }
.sw-task { flex: 1 1 320px; }
.sw-task textarea { width: 100%; resize: none; height: 28px; min-height: 28px; max-height: 96px; background: var(--void);
  border: 1px solid var(--hair-2); border-radius: var(--r-mark); color: var(--ink); padding: 4px 8px;
  font: 400 14px/18px var(--f-text); }
.sw-task textarea::placeholder { color: var(--ink-3); }
.sw-bar select.field { min-width: 120px; }
.sw-pill { display: inline-flex; border: 1px solid var(--hair-2); border-radius: var(--r-pill); overflow: hidden; }
.sw-pill button { height: 26px; padding: 0 10px; border: 0; background: transparent; color: var(--ink-3);
  font: 500 10.5px/14px var(--f-mono); font-stretch: 87.5%; letter-spacing: .08em; text-transform: uppercase; }
.sw-pill button[aria-pressed="true"] { color: var(--void); background: var(--ink); }
.sw-status { color: var(--ink-2); white-space: nowrap; }
.sw-error { color: var(--fault); font: 400 12px/16px var(--f-mono); }
.sw-plate { position: relative; background: var(--void); border-bottom: 1px solid var(--hair); min-height: 0; }
.sw-plate canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
.sw-well { position: absolute; border: 1px solid transparent; background: transparent; padding: 6px 8px;
  text-align: left; color: var(--ink-3); display: flex; flex-direction: column; justify-content: space-between; }
.sw-well:hover { border-color: var(--hair-2); }
.sw-well[aria-pressed="true"] { border-color: var(--select); }
.sw-well[aria-pressed="true"] .t-label { color: var(--select); }
.sw-well .sub { color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sw-well .foot { color: var(--ink-3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sw-paused { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }
.sw-corner { position: absolute; right: var(--sp-3); bottom: 4px; color: var(--ink-3); }
.sw-ram { padding: 6px var(--sp-4) 8px; border-bottom: 1px solid var(--hair); background: var(--bed); }
.sw-ram .head { display: flex; justify-content: space-between; gap: var(--sp-3); margin-bottom: 4px; }
.sw-rows { overflow: auto; min-height: 0; padding: 0 var(--sp-4) var(--sp-4); }
.sw-rows svg { display: block; }
.sw-asks { padding: var(--sp-3) var(--sp-4) 0; }
.sw-ask { margin-bottom: var(--sp-2); padding: var(--sp-3); border: 1px solid var(--select); border-radius: var(--r-panel);
  background: var(--s1); }
.sw-ask pre { margin: 6px 0; padding: 8px; background: var(--void); border: 1px solid var(--hair); border-radius: var(--r-mark);
  color: var(--ink); font: 400 13px/20px var(--f-code); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 120px;
  overflow: auto; }
.sw-board { margin-top: var(--sp-3); }
.sw-post { display: grid; grid-template-columns: 56px 64px 1fr; gap: var(--sp-2); padding: 3px 0;
  border-top: 1px solid var(--hair); color: var(--ink-2); }
.sw-post .who { color: var(--ink); }
.sw-post .words { font: 400 13px/18px var(--f-text); overflow-wrap: anywhere; }
@media (max-width: 900px) {
  .sw { position: relative; inset: auto; display: flex; flex-direction: column; min-height: 0; }
  .sw-plate { height: 420px; flex: 0 0 auto; }
}
`;

function addStyle() {
  if (document.getElementById("swarm-screen-style")) return;
  const s = document.createElement("style");
  s.id = "swarm-screen-style";
  s.textContent = STYLE;
  document.head.appendChild(s);
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function mount(el, api) {
  const { html, render, signal, useRef, useEffect, useState } = api.ui;
  const { Val, Glyph, Empty } = api.parts;
  const { fmt } = api;
  addStyle();

  const data = signal(null); // /api/swarm/state
  const err = signal(null);
  const picked = signal(null); // the well that fills the plate
  const task = signal("");
  const n = signal(readN());
  const persona = signal(stored(PERSONA_KEY)); // null: the Code screen's, until one is chosen here
  const memory = signal(stored(MEMORY_KEY));
  const going = signal(false);

  // the swarm's own choice when it still exists, else the Code screen's (the poll never changes these)
  function pickedPersona(d) {
    const p = persona.value;
    return p && (d?.personas || []).some((x) => x.id === p) ? p : d?.persona;
  }
  function pickedMemory(d) {
    const m = memory.value;
    return typeof m === "boolean" ? m : d?.memory;
  }
  const width = signal(el.clientWidth || 1200); // the screen's width, for the rows and the RAM bar
  new ResizeObserver(([e]) => { if (e.contentRect.width) width.value = Math.floor(e.contentRect.width); }).observe(el);
  const C = {}; // channel colours, read once from tokens.css

  function readN() {
    try { return Math.min(8, Math.max(1, Number(localStorage.getItem(N_KEY)) || 4)); } catch { return 4; }
  }

  // -- data

  let timer = null;
  let shown = false;
  async function poll() {
    clearTimeout(timer);
    try {
      data.value = await api.get("/api/swarm/state");
      err.value = null;
      noteEvents();
    } catch (e) {
      err.value = e.message;
    }
    if (shown) timer = setTimeout(poll, data.peek()?.swarm?.live ? 500 : 3000);
  }

  async function start() {
    if (going.peek()) return;
    going.value = true;
    try {
      const d = data.peek();
      await api.post("/api/swarm/start", { task: task.peek(), n: n.peek(), persona: pickedPersona(d),
        memory: pickedMemory(d) });
      picked.value = null;
      seen.clear();
      await poll();
    } catch (e) {
      err.value = e.message;
    } finally {
      going.value = false;
    }
  }

  async function stop() {
    try { await api.post("/api/swarm/stop", {}); } catch (e) { err.value = e.message; }
    poll();
  }

  async function decide(id, allow) {
    try { await api.post("/api/code/approve", { id, allow }); } catch (e) { err.value = e.message; }
    poll();
  }

  // -- afterglow: an agent's newest step flares its room, then decays; the loop runs only while something glows

  const seen = new Map(); // agent label -> the step it last showed
  const glow = new Map(); // agent label -> {at, room, tier, used, picked}
  function noteEvents() {
    const s = data.peek()?.swarm;
    if (!s || !api.running.peek()) return;
    for (const a of s.agents) {
      const key = `${a.run}:${a.steps}`;
      if (seen.get(a.label) === key) continue;
      const first = !seen.has(a.label);
      seen.set(a.label, key);
      if (first || !a.last) continue;
      glow.set(a.label, { at: performance.now(), room: a.last.room, reach: a.last.reach, tier: a.last.tier,
        used: (a.last.used || []).length, picked: (a.last.nodes || []).length });
    }
    wake();
  }

  // -- the plate (Canvas 2D: additive marks on black)

  const canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  let raf = 0;
  let lastFrame = 0;

  function wake() {
    if (!raf && shown) raf = requestAnimationFrame(draw);
  }

  function wells(w, h) {
    const s = data.peek()?.swarm;
    const count = 8;
    const sel = picked.peek();
    const out = [];
    const pad = 12;
    const foot = 18; // the stage's corner labels
    if (sel != null && s) {
      out.push({ i: sel, x: pad, y: pad, w: w - 2 * pad, h: h - 64 - 3 * pad - foot });
      const others = [...Array(count).keys()].filter((i) => i !== sel);
      const sw = (w - pad * (others.length + 1)) / others.length;
      others.forEach((i, k) => out.push({ i, x: pad + k * (sw + pad), y: h - 64 - pad - foot, w: sw, h: 64 }));
      return out;
    }
    const cw = (w - pad * 5) / 4;
    const ch = (h - pad * 3 - foot) / 2;
    for (let i = 0; i < count; i++) out.push({ i, x: pad + (i % 4) * (cw + pad), y: pad + Math.floor(i / 4) * (ch + pad), w: cw, h: ch });
    return out;
  }

  function bright(base, at, half, now) {
    if (api.reducedMotion.peek()) return now - at < 600 ? 1 : base;
    return base + (1 - base) * 2 ** (-(now - at) / half);
  }

  function draw(now) {
    raf = 0;
    if (!shown) return;
    if (now - lastFrame < 15) { raf = requestAnimationFrame(draw); return; } // 60 fps at most
    lastFrame = now;
    api.frame();
    const dpr = Math.min(2, devicePixelRatio || 1);
    const W = canvas.clientWidth;
    const H = canvas.clientHeight;
    if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) {
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
    }
    const g = canvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    if (api.measuring.peek()) return;
    const s = data.peek()?.swarm;
    let busy = false;
    for (const box of wells(W, H)) {
      g.strokeStyle = C.hair;
      g.lineWidth = 1;
      g.strokeRect(box.x + 0.5, box.y + 0.5, box.w - 1, box.h - 1);
      const agent = s?.agents?.[box.i];
      const reach = s?.wells?.[box.i]?.reach;
      if (!agent || !reach) continue;
      busy = drawWell(g, box, agent, reach, now) || busy;
    }
    if (busy && api.running.peek()) raf = requestAnimationFrame(draw);
  }

  // the agent's own rooms as tiles, packed in rows: width by tokens (a full room is 512), the same height each
  function drawWell(g, box, agent, reach, now) {
    const rooms = reach.rooms || [];
    const inner = { x: box.x + 10, y: box.y + 34, w: box.w - 20, h: box.h - 54 };
    if (inner.h < 8 || !rooms.length) return false;
    const area = inner.w * inner.h;
    const units = rooms.reduce((a, r) => a + 3.2 * Math.max(r.tokens, 32) / 512, 0);
    const h0 = Math.max(4, Math.min(22, Math.sqrt((0.4 * area) / Math.max(units, 1e-6))));
    const ev = glow.get(agent.label);
    let x = inner.x;
    let y = inner.y;
    let busy = false;
    g.save();
    for (const r of rooms) {
      const w = Math.max(0.5 * h0, (3.2 * h0 * r.tokens) / 512);
      if (x + w > inner.x + inner.w) { x = inner.x; y += h0 + 4; }
      if (y + h0 > inner.y + inner.h) break;
      const isLast = ev && ev.reach === reach.reach && ev.room === r.id;
      if (r.asleep) {
        g.setLineDash([2, 2]);
        g.strokeStyle = C.ink4;
        g.strokeRect(x + 0.5, y + 0.5, w - 1, h0 - 1);
        g.setLineDash([]);
      } else {
        g.globalAlpha = 0.12;
        g.fillStyle = C.ssd;
        g.fillRect(x, y, w, h0);
        g.globalAlpha = 1;
        g.strokeStyle = C.ssdRest;
        g.strokeRect(x + 0.5, y + 0.5, w - 1, h0 - 1);
      }
      if (isLast) {
        const b = bright(0, ev.at, HALF.read, now);
        if (b > 0.01) busy = true;
        g.globalAlpha = b;
        g.strokeStyle = ev.tier === "ram" ? C.ram : C.ssd;
        g.lineWidth = 1.5;
        g.strokeRect(x + 0.5, y + 0.5, w - 1, h0 - 1);
        g.lineWidth = 1;
        if (ev.used) { // used: a green fill with a tight halo, settling to the hold step
          const u = bright(0.6, ev.at, HALF.used, now);
          if (u > 0.61) busy = true;
          g.globalAlpha = u;
          g.fillStyle = C.void;
          g.fillRect(x + 1, y + 1, w - 2, h0 - 2);
          g.fillStyle = C.used;
          g.shadowColor = C.used;
          g.shadowBlur = 6 * u;
          g.globalAlpha = 0.85 * u;
          g.fillRect(x + 2, y + 2, w - 4, h0 - 4);
          g.shadowBlur = 0;
        }
        g.globalAlpha = 1;
      }
      if (r.hot || (isLast && ev.picked && !ev.used)) {
        g.strokeStyle = C.ram;
        g.lineWidth = 1.5;
        g.strokeRect(x - 1, y - 1, w + 2, h0 + 2);
        g.lineWidth = 1;
      }
      x += w + 3;
    }
    g.restore();
    return busy;
  }

  // -- parts

  function Plate() {
    const ref = useRef(null);
    const [size, setSize] = useState({ w: 0, h: 0 });
    useEffect(() => {
      ref.current.appendChild(canvas);
      const ro = new ResizeObserver(([e]) => { setSize({ w: e.contentRect.width, h: e.contentRect.height }); wake(); });
      ro.observe(ref.current);
      return () => ro.disconnect();
    }, []);
    const d = data.value;
    const s = d?.swarm;
    const sel = picked.value;
    const boxes = size.w ? wells(size.w, size.h) : [];
    useEffect(() => { wake(); }, [d, sel, size.w, size.h]);
    if (api.measuring.value) {
      return html`<div class="sw-plate" ref=${ref}><div class="sw-paused t-label">measuring · view paused</div></div>`;
    }
    return html`<div class="sw-plate" ref=${ref}>
      ${boxes.map((b) => {
        const a = s?.agents?.[b.i];
        const reach = s?.wells?.[b.i]?.reach;
        const small = b.h < 80;
        return html`<button class="sw-well" style=${{ left: `${b.x}px`, top: `${b.y}px`, width: `${b.w}px`, height: `${b.h}px` }}
          aria-pressed=${sel === b.i ? "true" : "false"} disabled=${!a}
          onClick=${() => { picked.value = sel === b.i ? null : b.i; }} title=${a?.task || ""}>
          <span><span class="t-label">A${b.i + 1}</span>
            ${!small && a ? html`<span class="t-readout sub"> · ${s.persona} · ${(a.model || "").split("/").pop()}</span>` : null}</span>
          ${!a ? html`<span class="t-readout foot">${s ? "no agent in this well" : b.i === 0 ? "no swarm run yet" : ""}</span>`
            : !small ? html`<span class="t-readout foot">${reach ? `${reach.reach} · ${reach.rooms.length} rooms · ${fmt.int(reach.moments)} moments` : a.memory ? "—" : "memory off · no rooms"}${a.task ? ` · ${a.state}` : ""}</span>` : null}
        </button>`;
      })}
      <span class="sw-corner t-label">timebase real · persistence ${api.persistence.value}</span>
    </div>`;
  }

  const ORDER = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "shared", "other"];

  function RamBar({ s, width }) {
    const G = 72;
    const H = 28;
    const ram = s?.ram || [];
    const end = Math.max(5, s?.now || 0);
    const sx = (t) => G + ((width - G - 8) * t) / end;
    const last = ram.at(-1);
    const top = last ? Object.entries(last.by).sort((a, b) => b[1] - a[1])[0] : null;
    const segs = [];
    ram.forEach((r, k) => {
      const t1 = k + 1 < ram.length ? ram[k + 1].t : end;
      const x0 = sx(r.t);
      const x1 = sx(t1);
      let y = H;
      for (const label of ORDER) {
        const b = r.by[label];
        if (!b) continue;
        const hh = Math.max(1, (H * b) / r.budget);
        y -= hh;
        segs.push(html`<g><rect x=${x0} y=${y} width=${Math.max(1, x1 - x0 - 0.5)} height=${hh - 0.5} fill="var(--ram-resident)" />
          ${x1 - x0 > 26 && hh >= 10 ? html`<text x=${x0 + 3} y=${y + hh - 2} fill="var(--ink)" style=${{ font: "500 9px var(--f-mono)" }}>${label}</text>` : null}</g>`);
      }
    });
    return html`<div class="sw-ram">
      <div class="head"><span class="t-label">Shared RAM · hot rooms over time</span>
        <span class="t-readout">${last ? html`HOT <${Val} v=${fmt.ram(last.used)} /> of <${Val} v=${fmt.ram(last.budget)} />${top ? ` · ${top[0]} holds ${fmt.text(fmt.ram(top[1]))}` : ""}` : s ? "memory off · no shared budget" : "—"}</span></div>
      <svg width=${width} height=${H} aria-label="shared RAM over time">
        <rect x=${G} y="0" width=${Math.max(0, width - G - 8)} height=${H} fill="var(--void)" />
        <text x="0" y="18" fill="var(--ink-3)" style=${{ font: "500 10px var(--f-mono)", letterSpacing: ".06em" }}>HOT</text>
        ${segs}
        <line x1=${G} x2=${width - 8} y1="0.5" y2="0.5" stroke="var(--select)" stroke-dasharray="3 3" />
      </svg>
    </div>`;
  }

  function Rows({ s, width }) {
    const G = 72;
    const R = 330; // the readout column
    const rowH = 44;
    const agents = s?.agents || [];
    const end = Math.max(5, s?.now || 0);
    const W = Math.max(width, 400);
    const sx = (t) => G + ((W - G - R - 8) * t) / end;
    const tickColor = { ssd: "var(--ssd)", ram: "var(--ram)", used: "var(--used)", vault: "var(--vault)", words: "var(--vault)" };
    const sel = picked.value;
    const H = agents.length * rowH + 22;
    const ticksAxis = [];
    const stepT = end > 60 ? 10 : end > 20 ? 5 : end > 8 ? 2 : 1;
    for (let t = 0; t <= end; t += stepT) ticksAxis.push(t);
    const row = (label) => agents.findIndex((a) => a.label === label);
    return html`<svg width=${W} height=${H} aria-label="channel rows">
      ${agents.map((a, i) => {
        const y = i * rowH;
        const on = sel === i;
        return html`<g transform=${`translate(0 ${y})`}>
          <rect x="0" y="0" width=${W} height=${rowH - 1} fill="var(--void)" stroke=${on ? "var(--select)" : "none"} />
          <text x="8" y="18" fill=${on ? "var(--select)" : "var(--ink-2)"} style=${{ font: "500 11px var(--f-mono)", letterSpacing: ".06em" }}>${a.label}</text>
          <text x="8" y="34" fill="var(--ink-3)" style=${{ font: "400 10px var(--f-mono)" }}>${a.state}</text>
          ${a.spans.map((sp) => {
            if (sp.kind === "model") {
              return html`<rect x=${sx(sp.t0)} y="26" width=${Math.max(1, sx(sp.t1) - sx(sp.t0))} height="12" fill="var(--ram-resident)"><title>${sp.label} · ${fmt.text(fmt.s(sp.t1 - sp.t0))}</title></rect>`;
            }
            // denied, timed out or stopped: your choice, grey with its word; failed: grey with a red ×
            const refused = sp.decision && sp.decision !== "allowed";
            const failed = sp.ok === false && !refused;
            return html`<g><rect x=${sx(sp.t0)} y="30" width=${Math.max(1, sx(sp.t1) - sx(sp.t0))} height="4" fill=${failed ? "var(--ink-2)" : "var(--ink-4)"}><title>${sp.label} · ${fmt.text(fmt.s(sp.t1 - sp.t0))}${refused ? ` · ${sp.decision}` : ""}${failed ? " · failed" : ""}</title></rect>
              ${failed ? html`<text x=${sx(sp.t1) + 2} y="36" fill="var(--fault)" style=${{ font: "600 10px var(--f-mono)" }}>×</text>` : null}</g>`;
          })}
          ${a.ticks.map((k) => html`<rect x=${sx(k.t) - 0.5} y=${k.kind === "used" ? 6 : 12} width="1.5" height=${k.kind === "used" ? 8 : 12} fill=${tickColor[k.kind] || "var(--ink-2)"} />`)}
          <g transform=${`translate(${W - R} 0)`}>
            <text x="0" y="16" fill="var(--ink)" style=${{ font: "400 11px var(--f-mono)" }}>${fmt.text(fmt.tok(a.tokens.prompt))} read · ${fmt.text(fmt.tok(a.tokens.written))} written</text>
            <text x="0" y="32" fill="var(--ink-2)" style=${{ font: "400 11px var(--f-mono)" }}>${a.done} ${a.done === 1 ? "task" : "tasks"}${a.failed ? ` · ${a.failed} failed` : ""} · ${fmt.text(fmt.s(a.busy_s.model))} model · ${fmt.text(fmt.s(a.busy_s.tool))} tools</text>
          </g>
        </g>`;
      })}
      ${(s?.board || []).map((m) => {
        const from = row(m.from);
        if (from < 0 || agents.length < 2) return null;
        const x = sx(m.t);
        const others = agents.map((_, i) => i).filter((i) => i !== from);
        const y0 = Math.min(from, ...others) * rowH + 4;
        const y1 = Math.max(from, ...others) * rowH + rowH - 6;
        return html`<g><line x1=${x} x2=${x} y1=${y0} y2=${y1} stroke="var(--ink-2)" stroke-width="1" />
          ${others.map((i) => { const yy = i * rowH + (i < from ? rowH - 6 : 4); const dir = i < from ? -1 : 1;
            return html`<path d=${`M${x - 3} ${yy - 3 * dir} L${x} ${yy} L${x + 3} ${yy - 3 * dir}`} fill="none" stroke="var(--ink-2)" />`; })}
          <title>${m.from} posted · ${m.text}</title></g>`;
      })}
      <g transform=${`translate(0 ${agents.length * rowH + 14})`}>
        ${ticksAxis.map((t) => html`<text x=${sx(t)} y="0" text-anchor="middle" fill="var(--ink-3)" style=${{ font: "400 10px var(--f-mono)" }}>${t}${fmt.THIN}s</text>`)}
      </g>
    </svg>`;
  }

  // one ask: exactly what will run, counted, with "allow once" asleep until the card has been seen whole
  function AskCard({ a }) {
    const ref = useRef(null);
    const [awake, setAwake] = useState(false);
    const [seen, setSeen] = useState(false);
    const body = a.kind === "shell" ? a.what.command : JSON.stringify(a.what.arguments, null, 2);
    const lines = body.split("\n").length;
    const marks = (body.match(HIDDEN) || []).filter((c) => c !== "\n" && c !== "\t").length;
    const check = () => {
      const box = ref.current;
      if (box && box.clientHeight > 0 && box.scrollTop + box.clientHeight >= box.scrollHeight - 2) setSeen(true);
    };
    useEffect(() => {
      const t0 = setTimeout(() => setAwake(true), ASK_WAKE_MS);
      const ro = new ResizeObserver(check);
      ro.observe(ref.current);
      check();
      return () => { clearTimeout(t0); ro.disconnect(); };
    }, []);
    return html`<div class="sw-ask" role="alertdialog" aria-label="allow this call?">
      <span class="t-label">${a.label} · ${a.kind === "shell" ? "shell · runs as you" : `mcp · ${a.what.server} · ${a.what.tool}`}</span>
      <pre ref=${ref} onScroll=${check}>${visible(body)}</pre>
      <div class="t-readout" style=${{ color: "var(--ink-3)", marginBottom: "6px" }}>${lines} ${lines === 1 ? "line" : "lines"} · ${fmt.int(body.length)} characters${marks ? html` · <span class="fault-text"><${Glyph} kind="cross" /> ${marks} invisible, shown as ⟨U+…⟩</span>` : ""}${seen ? "" : " · scroll to the end to allow"}</div>
      <div style=${{ display: "flex", gap: "8px", alignItems: "center" }}>
        <button class="btn" disabled=${!awake || !seen} onClick=${() => decide(a.id, true)}>allow once</button>
        <button class="btn" onClick=${() => decide(a.id, false)}>deny</button>
        <span class="t-readout" style=${{ color: "var(--ink-3)" }}>the agent waits until you choose</span></div></div>`;
  }

  function Asks({ s }) {
    const list = s?.waiting || [];
    if (!list.length) return null;
    return html`<div class="sw-asks">${list.map((a) => html`<${AskCard} a=${a} key=${a.id} />`)}</div>`;
  }

  function Bottom() {
    const w = Math.max(320, width.value - 32);
    const s = data.value?.swarm;
    return html`<div style=${{ display: "contents" }}>
      <${RamBar} s=${s} width=${w} />
      <div class="sw-rows">
        <${Asks} s=${s} />
        ${s ? html`<${Rows} s=${s} width=${w} />
          <div class="sw-board">
            <span class="t-label">Board · what each agent posted when it finished</span>
            ${(s.board || []).length ? s.board.slice(-12).reverse().map((m) => html`<div class="sw-post">
              <span class="t-readout who">${m.from}</span><span class="t-readout"><${Val} v=${fmt.s(m.t)} /></span>
              <span class="words">${m.text || "—"}</span></div>`) : html`<div class="t-readout" style=${{ color: "var(--ink-3)", marginTop: "4px" }}>nothing posted yet</div>`}
          </div>`
          : html`<div style=${{ marginTop: "12px" }}><${Empty}>no swarm run yet · give the agents a task above: one line for all of them, or one task per line for a shared queue<//></div>`}
      </div>
    </div>`;
  }

  function Bar() {
    const d = data.value;
    const s = d?.swarm;
    const why = d?.can_run;
    const running = !!s?.live;
    return html`<div class="sw-bar">
      <label class="sw-task"><span class="t-label">Task · one line for every agent, or one per line as a queue</span>
        <textarea id="swarm-task" value=${task.value} placeholder=${why || "Read src/fees.py and write one test for fee()"}
          onInput=${(e) => { task.value = e.target.value; e.target.style.height = "auto"; e.target.style.height = `${Math.min(96, e.target.scrollHeight)}px`; }}
          onKeyDown=${(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); start(); } }}></textarea></label>
      <label><span class="t-label">Agents</span>
        <span class="seg" role="group" aria-label="agents">${[1, 2, 3, 4, 5, 6, 7, 8].map((k) => html`<button aria-pressed=${n.value === k ? "true" : "false"}
          onClick=${() => { n.value = k; try { localStorage.setItem(N_KEY, String(k)); } catch { /* private window */ } }}>${k}</button>`)}</span></label>
      <label><span class="t-label">Persona</span>
        <select class="field" value=${pickedPersona(d)} onChange=${(e) => { persona.value = e.target.value; store(PERSONA_KEY, e.target.value); }}>
          ${(d?.personas || []).map((p) => html`<option value=${p.id}>${p.name}</option>`)}</select></label>
      <label><span class="t-label">Memory</span>
        <span class="sw-pill" role="group" aria-label="memory">
          <button aria-pressed=${d && pickedMemory(d) ? "true" : "false"} onClick=${() => { memory.value = true; store(MEMORY_KEY, true); }}>on</button>
          <button aria-pressed=${d && !pickedMemory(d) ? "true" : "false"} onClick=${() => { memory.value = false; store(MEMORY_KEY, false); }}>off</button></span></label>
      ${running ? html`<button class="btn" onClick=${stop}>stop</button>`
        : html`<button class="btn" onClick=${start} disabled=${!!why || going.value || !task.value.trim()}>run</button>`}
      <span class="t-readout sw-status">${s ? html`${s.done} / ${s.total} tasks · <${Val} v=${fmt.s(s.elapsed_s)} /> · ${s.mode === "same" ? "one task each" : `queue ${s.queue} left`}` : d ? `${d.model ? d.model.split("/").pop() : "no model"}${d.workspace ? ` · ${d.workspace}` : " · no workspace: no file tools"}` : "—"}</span>
      ${err.value ? html`<span class="sw-error"><${Glyph} kind="cross" /> ${err.value}</span>` : why && !s?.live ? html`<span class="t-readout" style=${{ color: "var(--ink-3)" }}>${why}</span>` : null}
    </div>`;
  }

  function App() {
    return html`<div class="sw"><${Bar} /><${Plate} /><${Bottom} /></div>`;
  }

  function readColours() {
    Object.assign(C, { void: cssVar("--void"), hair: cssVar("--hair"), ink4: cssVar("--ink-4"), ssd: cssVar("--ssd"), ssdRest: cssVar("--ssd-rest"),
      ram: cssVar("--ram"), used: cssVar("--used"), vault: cssVar("--vault") });
  }

  readColours();
  render(html`<${App} />`, el);
  const off = [api.on("escape", () => { picked.value = null; }), api.on("focus", () => document.getElementById("swarm-task")?.focus()),
    api.on("run", (on) => { if (on) wake(); })];

  return {
    show() { shown = true; poll(); wake(); },
    hide() {
      shown = false;
      clearTimeout(timer);
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    },
    key(e, { typing }) {
      if (typing) return false;
      const s = data.peek()?.swarm;
      if (e.key === "Escape" && picked.peek() != null) { picked.value = null; return true; }
      if (s && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
        const k = s.agents.length;
        const cur = picked.peek();
        picked.value = cur == null ? 0 : (cur + (e.key === "ArrowRight" ? 1 : k - 1)) % k;
        return true;
      }
      return false;
    },
    destroy() { off.forEach((f) => f()); },
  };
}
