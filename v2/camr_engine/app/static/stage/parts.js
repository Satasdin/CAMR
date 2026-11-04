// Parts the memory screens share (DIRECTION.md, "Shared components"): the MEMORY toggle, the reach picker, the path
// strip under every answer, the light path's lanes and readouts, and the right-side sheet. Built with the vendored
// preact + htm the shell hands every screen (api.ui).

const THIN = " ";
export const KIND_ORDER = ["session", "project", "agent", "global"];

export function makeParts(api) {
  const { html, useState, useRef, useEffect } = api.ui;
  const { fmt } = api;
  const { Glyph } = api.parts;

  // -- a hardware two-position toggle: MEMORY off / on, live / vault (no label: the positions say it)

  function Toggle({ label = null, on, onChange, disabled = false, left = "off", right = "on" }) {
    return html`<button class=${`toggle${on ? " on" : ""}`} role="switch" aria-checked=${String(on)} disabled=${disabled}
      aria-label=${label ? null : right} onClick=${() => onChange(!on)}
      title=${`${label ? `${label} ` : ""}${on ? right : left}`}>
      ${label ? html`<span class="t-label">${label}</span>` : null}
      <span class="toggle-track"><span class="toggle-pos t-label">${left}</span><span class="toggle-pos t-label">${right}</span><i class="toggle-knob"></i></span>
    </button>`;
  }

  // -- the reach picker: four segments, several read, one written. PROJECT and AGENT ask for a name the first time;
  // after that their chevron (or alt-click) picks another

  function Rings({ k, read }) { // session innermost, global outermost; this segment's ring drawn bright
    return html`<svg class="reach-rings" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      ${[2.5, 4.5, 6.5, 8.25].map((r, i) => html`<circle cx="9" cy="9" r=${r} class=${i === k ? (read ? "ring on" : "ring mine") : "ring"} />`)}
    </svg>`;
  }

  function ReachPicker({ state, onChange, busy = false }) {
    const [ask, setAsk] = useState(null); // the kind whose name is being chosen
    const [name, setName] = useState("");
    const [err, setErr] = useState(null);
    const input = useRef(null);
    useEffect(() => { if (ask) input.current?.focus(); }, [ask]);
    if (!state?.reaches?.length) return html`<div class="reach-picker dim t-readout">${state?.why || "no reaches · this memory is read-only"}</div>`;
    const reaches = Object.fromEntries(state.reaches.map((r) => [r.kind, r]));
    async function send(body) {
      setErr(null);
      try { await onChange(body); } catch (e) { setErr(e.message); }
    }
    const named = (kind) => kind === "project" || kind === "agent";
    function rename(kind) { setAsk(ask === kind ? null : kind); setName(""); }
    function click(kind, ev) {
      const r = reaches[kind] || {};
      if (named(kind) && (!r.name || ev.altKey)) { rename(kind); return; }
      if (ev.shiftKey) { send({ writes: kind }); return; }
      const reads = state.reads.includes(kind) ? state.reads.filter((k) => k !== kind) : KIND_ORDER.filter((k) => k === kind || state.reads.includes(k));
      if (!reads.includes(state.writes)) { setErr(`${state.writes} is written to, so it stays read · shift-click another reach to write there`); return; }
      send({ reads });
    }
    function pick(kind, n) {
      const v = (n || "").trim();
      if (!v) return;
      setAsk(null);
      const reads = KIND_ORDER.filter((k) => k === kind || state.reads.includes(k));
      send({ [kind]: v, reads });
    }
    const names = ask === "project" ? state.projects || [] : ask === "agent" ? state.agents || [] : [];
    return html`<div class="reach-picker" role="group" aria-label="Reach: click to read or not, shift-click to write there">
      ${KIND_ORDER.map((kind, k) => {
        const r = reaches[kind] || {};
        const read = state.reads.includes(kind);
        const written = state.writes === kind;
        const label = named(kind) ? `${kind} ${r.name || "—"}` : kind;
        const seg = html`<button class=${`reach${read ? " read" : ""}${written ? " written" : ""}`} disabled=${busy}
          aria-pressed=${String(read)} title=${`${read ? "read" : "not read"}${written ? " · written to" : ""} · shift-click to write here${named(kind) && r.name ? ` · alt-click for another ${kind}` : ""}`}
          onClick=${(ev) => click(kind, ev)}>
          <${Rings} k=${k} read=${read} />
          <span class="reach-text"><span class="t-label reach-name">${label}</span>
            <span class="reach-size t-readout"><span class="n-notes">${r.notes == null ? "—" : fmt.int(r.notes)}${THIN}notes</span>
              <span class="n-bytes">${fmt.text(fmt.bytes(r.room_bytes))}</span></span></span>
        </button>`;
        if (!named(kind) || !r.name) return seg;
        return html`${seg}<button class="reach-rename" disabled=${busy} aria-label=${`choose another ${kind}`} title=${`choose another ${kind}`}
          aria-expanded=${String(ask === kind)} onClick=${() => rename(kind)}><${api.parts.Icon} name="chevron-down" /></button>`;
      })}
      ${ask ? html`<div class="reach-ask" role="dialog" aria-label=${`name the ${ask}`}>
        <span class="t-label">${ask}</span>
        ${names.map((n) => html`<button class="btn" onClick=${() => pick(ask, n)}>${n}</button>`)}
        <input class="field" ref=${input} placeholder=${`new ${ask} name`} value=${name}
          onInput=${(e) => setName(e.target.value)} onKeyDown=${(e) => { if (e.key === "Enter") pick(ask, name); if (e.key === "Escape") setAsk(null); }} />
        <button class="btn" onClick=${() => pick(ask, name)}>read</button>
        <button class="btn" onClick=${() => setAsk(null)}>cancel</button>
      </div>` : null}
      ${err ? html`<span class="reach-err t-readout fault-text"><${Glyph} kind="cross" /> ${err}</span>` : null}
    </div>`;
  }

  // -- the path strip: 20 px under every answer, to scale; question to first word in the first 60%, decode after

  function pathSegments(e, m) {
    const s = e?.seconds || {};
    const wait = (e?.wait_s ?? m?.first_word_s ?? 0) * 1000;
    const steps = [];
    for (const k of ["choose", "core", "fetch", "wake", "desk"]) if (s[k] != null) steps.push([k, s[k] * 1000]);
    const retrieval = steps.reduce((a, [, v]) => a + v, 0);
    steps.push(["prefill", Math.max(0, wait - retrieval)]);
    return { steps, wait, total: m?.total_s != null ? m.total_s * 1000 : null };
  }

  function PathStrip({ e, m, on = true, onOpen, width = 360, verdict = null }) {
    const h = 20;
    const W = width;
    const pre = W * 0.6, dec = W * 0.4 - 10;
    let marks = [];
    let right;
    if (!on || !e) {
      const total = m?.total_s;
      marks = [html`<rect class="ps-model" x="0" y="7" width=${W - 10} height="6" />`];
      right = html`<span class="dim">memory off</span> · ${fmt.text(fmt.s(m?.first_word_s))} · ${fmt.text(fmt.s(total))}`;
    } else {
      const { steps, wait, total } = pathSegments(e, m);
      let x = 0;
      for (const [k, v] of steps) {
        if (k === "fetch" && e.tier === "ram") { marks.push(html`<rect class="ps-ramhit" x=${x} y="2" width="2" height="16" />`); x += 2; continue; }
        const w = wait > 0 ? (v / wait) * pre : 0;
        const ww = v > 0 ? Math.max(1, w) : 0;
        if (ww) marks.push(html`<rect class=${`ps-${k}`} x=${x} y=${k === "prefill" ? 8 : 5} width=${ww} height=${k === "prefill" ? 4 : 10}><title>${k} ${fmt.text(fmt.ms(v))}</title></rect>`);
        x += ww;
      }
      marks.push(html`<rect class="ps-first" x=${pre - 1} y="0" width="1.5" height=${h} />`);
      marks.push(html`<text class="ps-break" x=${pre + 5} y="14" text-anchor="middle">//</text>`);
      const n = (e.words || []).length;
      if (total != null && n) {
        marks.push(html`<rect class="ps-decode" x=${pre + 10} y="9.5" width=${dec} height="1" />`);
      }
      const used = (e.used || []).length;
      const picked = Math.max(0, (e.nodes || []).length - used);
      const gbps = e.read_bytes && e.seconds?.fetch > 0 ? e.read_bytes / e.seconds.fetch / 1e9 : null;
      right = html`<${Glyph} kind="dot" cls="g-used" /> ${used} used <${Glyph} kind="ring" cls="g-picked" /> ${picked} picked
        · ${e.tier === "ram" ? "RAM hit" : html`<${api.parts.Val} v=${fmt.bytes(e.read_bytes)} />`}
        · <${api.parts.Val} v=${fmt.gbps(gbps)} /> · <${api.parts.Val} v=${fmt.s(wait / 1000)} /> · <${api.parts.Val} v=${fmt.s(total == null ? null : total / 1000)} />
        ${verdict === "false_memory" ? html` <span class="fault-text"><${Glyph} kind="cross" /> false memory</span>` : null}`;
    }
    return html`<div class="pathstrip" role=${onOpen ? "button" : null} tabindex=${onOpen ? "0" : null}
      onClick=${onOpen} onKeyDown=${(ev) => { if (ev.key === "Enter" && onOpen) onOpen(); }} title=${onOpen ? "open the light path" : null}>
      <svg width=${W} height=${h} aria-hidden="true">${marks}</svg>
      <span class="ps-read t-readout">${right}</span>
    </div>`;
  }

  // -- the light path's lanes: VAULT, SSD, RAM, MODEL on one ruler with the break after the first word

  function Lanes({ e, m, summary, width = 600 }) {
    if (!e) return null;
    const W = width - 72;
    const { steps, wait, total } = pathSegments(e, m);
    const tot = total ?? wait + (e.words || []).length * 50;
    const x = (t) => (t <= wait ? (t / Math.max(1, wait)) * W * 0.55 : W * 0.55 + ((t - wait) / Math.max(1, tot - wait)) * W * 0.45);
    const at = {};
    let t = 0;
    for (const [k, v] of steps) { at[k] = [t, t + v]; t += v; }
    const lane = (y, label, kids) => html`<g transform=${`translate(0 ${y})`}>
      <text class="ln-label" x="0" y="14">${label}</text><line class="ln-rule" x1="72" x2=${width} y1="23.5" y2="23.5" />
      <g transform="translate(72 0)">${kids}</g></g>`;
    const slice = (cls, a, b, label) => html`<rect class=${cls} x=${x(a)} y="6" width=${Math.max(1, x(b) - x(a))} height="12" />
      ${label ? html`<text class="ln-slice" x=${x(a) + Math.max(1, x(b) - x(a)) + 4} y="15">${label}</text>` : null}`;
    const whisk = (k, base) => {
      const p = summary?.retrieval_ms?.[k];
      if (!p?.p50 || !at[k]) return null;
      return html`<line class="ln-whisk" x1=${x(base + p.p50)} x2=${x(base + (p.p90 ?? p.p50))} y1="21" y2="21" />`;
    };
    const n = (e.words || []).length;
    const ticks = [];
    for (let i = 0; i < n; i++) ticks.push(html`<rect class="ln-word" x=${x(wait + (i * (tot - wait)) / Math.max(1, n))} y="9" width="1" height="6" />`);
    const ssd = at.fetch && e.tier === "ssd" ? slice("ln-ssd", at.fetch[0], at.fetch[1], `${fmt.text(fmt.bytes(e.read_bytes))} · ${fmt.text(fmt.ms((e.seconds?.fetch || 0) * 1000))}`) : null;
    return html`<svg class="lanes" width=${width} height="112" role="img" aria-label="the answer's lanes">
      ${lane(0, "VAULT", [(e.closest || []).length && at.desk ? slice("ln-vault", at.desk[0], at.desk[1], `${e.closest.length} moments as words`) : null,
        at.wake ? slice("ln-vault", at.wake[0], at.wake[1], "wake") : null])}
      ${lane(28, "SSD", [ssd, whisk("fetch", at.fetch?.[0] || 0)])}
      ${lane(56, "RAM", [html`<rect class="ln-core" x="0" y="11" width=${x(tot)} height="2" />`, at.desk ? slice("ln-ram", at.desk[0], at.desk[1], "desk") : null, whisk("desk", at.desk?.[0] || 0)])}
      ${lane(84, "MODEL", [at.prefill ? slice("ln-model", at.prefill[0], at.prefill[1], "prefill") : null,
        html`<rect class="ln-first" x=${x(wait)} y="0" width="1.5" height="24" />`, ...ticks])}
      <text class="ln-break" x=${72 + W * 0.55} y="10" text-anchor="middle">//</text>
    </svg>`;
  }

  function Readouts({ e, m, verdict }) {
    const row = (label, value) => html`<div class="readout"><span class="t-label">${label}</span><span class="t-readout">${value}</span></div>`;
    const V = api.parts.Val;
    const ms = m?.retrieval_ms || {};
    const right = verdict === "right" ? "right" : verdict === "wrong" ? html`<span class="fault-text"><${Glyph} kind="cross" /> wrong</span>`
      : verdict === "false_memory" ? html`<span class="fault-text"><${Glyph} kind="cross" /> false memory</span>`
      : verdict === "honest" || verdict === "declined" ? "honest" : verdict || "—";
    return html`<div class="readouts">
      ${row("answer", right)}
      ${row("first word", html`<${V} v=${fmt.s(m?.first_word_s ?? e?.wait_s)} />`)}
      ${row("total", html`<${V} v=${fmt.s(m?.total_s)} />`)}
      ${row("prefill", html`<${V} v=${fmt.tps(m?.prefill_tps)} />`)}
      ${row("decode", html`<${V} v=${fmt.tps(m?.decode_tps)} />`)}
      ${["choose", "core", "fetch", "wake", "desk"].map((k) => row(k, html`<${V} v=${fmt.ms(ms[k])} />`))}
      ${row("read", html`<${V} v=${fmt.bytes(m?.read_bytes ?? e?.read_bytes)} /> · <${V} v=${fmt.gbps(m?.gbps)} />`)}
      ${row("share of wait", m?.read_share == null ? "—" : `${(m.read_share * 100).toFixed(1)}${THIN}%`)}
      ${row("context", html`<${V} v=${fmt.tok(m?.context_tokens)} /> of <${V} v=${fmt.tok(m?.history_tokens)} />`)}
      ${row("peak RAM", html`<${V} v=${fmt.ram(m?.peak_ram_bytes)} />`)}
      ${row("disk", html`<${V} v=${fmt.bytes(m?.disk_bytes)} />`)}
      ${row("tier", m?.tier ?? e?.tier ?? "—")}
    </div>`;
  }

  // -- the sheet: a right-side panel over the screen

  function Sheet({ title, sub, wide = false, onClose, children }) {
    return html`<aside class=${`sheet${wide ? " wide" : ""}`} aria-label=${title}>
      <header class="sheet-head"><div><div class="t-head">${title}</div>${sub ? html`<div class="t-readout dim">${sub}</div>` : null}</div>
        <button class="btn sheet-close" onClick=${onClose} aria-label="close (Esc)"><${api.parts.Icon} name="x" /></button></header>
      <div class="sheet-body">${children}</div>
    </aside>`;
  }

  return { Toggle, ReachPicker, PathStrip, Lanes, Readouts, Sheet, pathSegments };
}
