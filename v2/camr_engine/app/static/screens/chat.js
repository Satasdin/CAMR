// Chat: the eyepiece (DIRECTION.md, "2. Chat"). The conversation on the left in a 720 px column; on the right, a
// compact stage holding the memory being read and a three-row trace strip (SSD R, USED, WORDS).
//
// Under each answer, its path strip; words whose largest look went to a used moment carry a faint green underline,
// and hovering one flares that moment in the eyepiece. The composer's top edge is the context meter: the tokens in
// view against the model's window, with the whole history beside it. Above the input: the MEMORY switch, the reach
// picker (click to read a reach, shift-click to write there), the intent (TELL · ASK · ERRAND, chosen from the text
// unless you pick one) and the model. / focuses the composer.

import { makeParts } from "/static/stage/parts.js";
import { memoryFeed } from "/static/stage/feed.js";
import { Stage, fmtTok, ramFromState } from "/static/stage/stage.js";
import { Trace } from "/static/stage/trace.js";

const THIN = " ";
const INTENTS = ["tell", "ask", "errand"];
const TEXT_MAX = 4000; // characters in one message (the server refuses more, never cuts)

function short(repo) { return repo ? repo.split("/").pop() : "—"; }

function topNode(e, i) {
  const row = e?.looks?.[i];
  if (!row || !row.length) return null;
  let j = 0;
  for (let k = 1; k < row.length; k++) if (row[k] > row[j]) j = k;
  return { node: e.nodes[j], look: row[j] };
}

export function mount(el, api) {
  const { html, render, signal, effect, useRef, useEffect, useState } = api.ui;
  const { Glyph, Empty } = api.parts;
  const { fmt } = api;
  api.css("/static/stage/stage.css");
  api.css("/static/stage/chat.css");
  const P = makeParts(api);

  const st = signal(null); // /api/chat/state
  const turns = signal([]);
  const text = signal("");
  const picked = signal(null); // an intent chosen by hand, until the next send
  const sending = signal(false);
  const playing = signal(null); // {key, i}: the word the eyepiece is playing
  const popover = signal(null); // {x, y, text}
  const lightpath = signal(null); // the turn whose light path is open
  const summary = signal(null);
  const inputRef = { current: null };
  const threadRef = { current: null };

  const intent = () => picked.value || (text.value.trim().endsWith("?") ? "ask" : "tell");

  // -- data

  async function loadState() {
    try { st.value = await api.get("/api/chat/state"); } catch (e) { st.value = { ready: false, why: e.message, reaches: [] }; }
  }

  // The server keeps a turn only once its step is done, so the thread it sends lacks a send still pending: that pair is
  // kept on top of it (unless the thread already ends with it). A thread asked for before a send finished may lack that
  // send's turns: it is asked for again.
  let inflight = null; // [mine, wait] while a send is pending
  let sent = 0; // sends finished
  const words = (x) => (x || "").split(/\s+/).filter(Boolean).join(" "); // as the server keeps it
  async function loadThread() {
    const at = sent;
    try {
      const got = await api.get("/api/chat/thread");
      if (at !== sent) { loadThread(); return; }
      const server = got.turns.map((t, k) => ({ ...t, id: `t${k}` }));
      const tail = server.slice(-2);
      const has = inflight && tail.length === 2 && tail[0].who === "you" && words(tail[0].text) === words(inflight[0].text)
        && !(Date.parse(tail[0].at) < inflight[0].sent - 2000); // the server's local time, as this page's
      turns.value = inflight && !has ? [...server, ...inflight] : server;
      scrollDown();
    } catch { /* an app with no chat: the empty state says so */ }
  }

  let seq = 0;
  async function send() {
    const t = text.value.trim();
    if (!t || sending.value) return;
    const kind = intent();
    const mine = { who: "you", text: t, intent: kind, id: `n${++seq}`, sent: Date.now() };
    const wait = { who: "camr", pending: true, intent: kind, id: `n${++seq}` };
    inflight = [mine, wait];
    turns.value = [...turns.value, mine, wait];
    text.value = "";
    picked.value = null;
    sending.value = true;
    scrollDown();
    const settle = (turn) => {
      inflight = null;
      sent++;
      if (turns.value.includes(wait)) turns.value = turns.value.map((x) => (x === wait ? { ...turn, id: wait.id } : x));
      else loadThread(); // the thread was loaded again meanwhile and already ends with this send
    };
    try {
      const got = await api.post(kind === "errand" ? "/api/errand" : "/api/chat", { text: t, intent: kind });
      settle({ who: "camr", ...got });
      if (got.event) feed.inject(got.event, got.metric);
    } catch (e) {
      settle({ who: "camr", error: e.message, intent: kind });
    } finally {
      sending.value = false;
      loadState();
      scrollDown();
    }
  }

  async function settings(body) {
    st.value = await api.post("/api/chat/settings", body);
    feed.reset();
    await loadSnap();
  }

  async function loadSnap() {
    try {
      const s = await api.get("/api/memory/stage");
      snapTokenBytes = s.token_bytes || 0;
      stage.setSnapshot(s);
    } catch { /* the eyepiece shows its empty state */ }
  }

  function scrollDown() {
    requestAnimationFrame(() => { const t = threadRef.current; if (t) t.scrollTop = t.scrollHeight; });
  }

  const moments = new Map();
  async function momentText(reach, id) {
    const k = `${reach}/${id}`;
    if (!moments.has(k)) {
      moments.set(k, api.get("/api/memory/moment", { reach: reach ?? "", id }).then((m) => m.text).catch(() => null));
    }
    return moments.get(k);
  }

  // -- parts of the conversation

  function Words({ turn }) {
    const e = turn.event;
    const words = turn.words || [];
    if (!e || !words.length || !turn.on) return html`<span>${turn.reply}</span>`;
    const used = new Set(e.used || []);
    const key = `${e.src ?? e.reach}/${e.i}`;
    const at = playing.value?.key === key ? playing.value.i : -1;
    return html`<span>${words.map((w, i) => {
      const top = topNode(e, i);
      const lean = top && used.has(top.node);
      const cls = `w${lean ? " lean" : ""}${i === at ? " now" : ""}`;
      return html`<span class=${cls} onMouseEnter=${async (ev) => {
        if (!top) return;
        stage.nodeFlare(e.reach ?? e.src, top.node, lean);
        const r = ev.currentTarget.getBoundingClientRect();
        const base = el.getBoundingClientRect();
        popover.value = { x: r.left - base.left, y: r.bottom - base.top + 4, text: "…", node: top.node, look: top.look };
        const t = await momentText(e.reach ?? e.src, top.node);
        if (popover.value?.node === top.node) popover.value = { ...popover.value, text: t || "—" };
      }} onMouseLeave=${() => { popover.value = null; }}>${w}</span>`;
    })}</span>`;
  }

  function Receipt({ turn }) {
    const e = turn.event;
    const pieces = turn.words || [];
    const joined = pieces.join("");
    const used = new Set(e?.used || []);
    const leans = (value) => { // did the words that wrote this value look hardest at a used moment?
      if (!e || !value) return false;
      const at = joined.indexOf(String(value));
      if (at < 0) return false;
      let pos = 0;
      for (let i = 0; i < pieces.length; i++) {
        const end = pos + pieces[i].length;
        if (end > at && pos < at + String(value).length) {
          const top = topNode(e, i);
          if (top && used.has(top.node)) return true;
        }
        pos = end;
      }
      return false;
    };
    const args = Object.entries(turn.args || {});
    return html`<div class="receipt t-code">
      <div>${turn.tool || "no tool"}(${args.map(([k, v], n) => html`${n ? ", " : ""}${k}="<span class=${leans(v) ? "lean" : ""}>${v}</span>"`)})</div>
      <div class="dim">${turn.result}</div>
    </div>`;
  }

  function Turn({ turn }) {
    if (turn.who === "you") return html`<div class="turn you"><div class="bubble t-chat">${turn.text}</div></div>`;
    if (turn.pending) return html`<div class="turn camr"><span class="t-readout dim">${turn.intent === "tell" ? "keeping it" : "reading"}…</span></div>`;
    if (turn.error) return html`<div class="turn camr"><span class="t-readout fault-text"><${Glyph} kind="cross" /> ${turn.error}</span></div>`;
    const e = turn.event;
    const m = turn.metric;
    if (turn.intent === "tell") {
      return html`<div class="turn camr"><div class="t-chat">${turn.reply}</div>
        ${turn.kept ? html`<div class="t-readout dim">kept in ${turn.reach} · moment ${turn.moment} · room ${turn.room} · ${turn.tokens}${THIN}tok</div>` : null}</div>`;
    }
    return html`<div class="turn camr">
      ${turn.intent === "errand" ? html`<${Receipt} turn=${turn} />` : html`<div class="t-chat answer"><${Words} turn=${turn} /></div>`}
      <${P.PathStrip} e=${turn.on ? e : null} m=${m} on=${turn.on && !!e} width=${300}
        onOpen=${() => { lightpath.value = turn; loadSummary(); if (e) stage.playAnswer({ e, m }, { replay: true, label: `replay · answer ${e.i ?? ""}` }); }} />
    </div>`;
  }

  async function loadSummary() {
    try { summary.value = await api.get("/api/memory/summary"); } catch { summary.value = null; }
  }

  // -- the composer

  function Meter() {
    const s = st.value;
    const last = [...turns.value].reverse().find((t) => t.metric?.context_tokens)?.metric || s?.last;
    const inView = last?.context_tokens;
    const win = s?.model?.window;
    const frac = inView && win ? Math.min(1, inView / win) : 0;
    return html`<div class="ctx">
      <div class="ctx-line" role="meter" aria-label="context in view against the model's window" aria-valuenow=${inView || 0} aria-valuemax=${win || 0}>
        <i class="ctx-in" style=${{ width: `${(frac * 100).toFixed(2)}%` }}></i></div>
      <span class="ctx-read t-readout">in view ${inView ? fmt.int(inView) : "—"} / window ${win ? fmt.int(win) : "—"} · history ${fmtTok(s?.history_tokens)}</span>
    </div>`;
  }

  function Controls() {
    const s = st.value;
    const kind = intent();
    const ready = s?.can !== false;
    return html`<div class="controls">
      <${P.Toggle} label="memory" on=${s ? s.on : true} disabled=${!ready || !s}
        onChange=${(on) => settings({ on }).catch((e) => { st.value = { ...st.value, why: e.message }; })} />
      ${ready && s?.reaches?.length ? html`<${P.ReachPicker} state=${s} onChange=${settings} busy=${!!s.busy || sending.value} />` : null}
      <div class="seg" role="group" aria-label="Intent">
        ${INTENTS.map((k) => html`<button aria-pressed=${String(kind === k)} title=${picked.value === k ? "chosen by hand" : "chosen from the text"}
          onClick=${() => { picked.value = picked.value === k ? null : k; inputRef.current?.focus(); }}>${k}</button>`)}
      </div>
      <span class="model-chip t-readout" title=${s?.picked && s.picked !== s?.model?.repo ? `${short(s.picked)} is picked on Models; chat reads with the memory's own reader, whose notes these rooms are` : s?.model?.repo || ""}>
        ${short(s?.model?.repo)}${s?.picked && s.picked !== s?.model?.repo ? html`<span class="dim"> · ${short(s.picked)} picked</span>` : null}</span>
    </div>`;
  }

  function Composer() {
    const s = st.value;
    const blocked = s && s.can === false;
    const measuring = api.measuring.value;
    return html`<div class="composer">
      <${Meter} />
      <${Controls} />
      <div class="input-row">
        <span class="prompt t-readout">›</span>
        <textarea class="t-chat" ref=${(x) => { inputRef.current = x; }} rows="1" aria-label="tell, ask, or give an errand"
          placeholder=${blocked ? s.why || "this memory is read-only" : measuring ? "a benchmark is measuring · chat waits" : "tell me something, or ask (end with ?)   /"}
          disabled=${blocked} value=${text.value} maxlength=${TEXT_MAX}
          onInput=${(e) => { text.value = e.target.value; e.target.style.height = "auto"; e.target.style.height = `${Math.min(140, e.target.scrollHeight)}px`; }}
          onKeyDown=${(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}></textarea>
        <button class="btn" onClick=${send} disabled=${blocked || sending.value || !text.value.trim()}>${intent()}</button>
      </div>
      ${s?.why && !blocked ? html`<div class="t-readout fault-text"><${Glyph} kind="cross" /> ${s.why}</div>` : null}
    </div>`;
  }

  function Thread() {
    const list = turns.value;
    return html`<div class="thread" ref=${(x) => { threadRef.current = x; }}>
      ${list.length ? list.map((t) => html`<${Turn} key=${t.id} turn=${t} />`)
        : html`<div class="thread-empty"><${Empty}>${st.value?.can === false ? st.value.why : "no conversation yet · tell me something, or ask"}<//></div>`}
    </div>`;
  }

  function LightPath() {
    const t = lightpath.value;
    return t ? html`<${LightPathSheet} t=${t} />` : null;
  }

  function LightPathSheet({ t }) {
    const e = t.event;
    const m = t.metric;
    const ref = useRef(null);
    const stageRef = useRef(null);
    const [w, setW] = useState(600);
    useEffect(() => {
      const ro = new ResizeObserver(([x]) => setW(Math.floor(x.contentRect.width)));
      if (ref.current) ro.observe(ref.current);
      return () => ro.disconnect();
    }, []);
    useEffect(() => { // the path stage: this answer's room, the bus and the desk, played once on opening
      if (!e || !stageRef.current || !stage.data) return undefined;
      const st = new Stage(stageRef.current, api, { mode: "path" });
      st.share(stage);
      st.setPath({ e, m });
      st.show();
      st.playAnswer({ e, m }, { replay: true, label: `replay · answer ${e.i ?? ""}` });
      pathStage = st;
      if (api.debug) window.camrPathStage = st; // ?debug=1: for looking inside from the console
      return () => { st.destroy(); if (pathStage === st) pathStage = null; };
    }, [t]);
    return html`<div class="lightpath" role="dialog" aria-label="the light path of one answer">
      <header class="sheet-head"><div><div class="t-head">${t.intent === "errand" ? `${t.tool}(…)` : (t.reply || "").slice(0, 80)}</div>
        <div class="t-readout dim">${e ? `${e.reach} · room ${e.room} · ${(e.nodes || []).length} on the desk · ${(e.used || []).length} used · R replays` : "memory off · the plain model"}</div></div>
        <button class="btn" onClick=${() => { lightpath.value = null; }} aria-label="close (Esc)"><${api.parts.Icon} name="x" /></button></header>
      ${e ? html`<div class="lp-stage" ref=${stageRef}></div>` : null}
      <div class="lp-body" ref=${ref}>
        <${P.Lanes} e=${e} m=${m} summary=${summary.value} width=${Math.max(320, w - 32)} />
        <${P.Readouts} e=${e} m=${m} verdict=${t.verdict} />
      </div>
    </div>`;
  }

  function Pop() {
    const p = popover.value;
    if (!p) return null;
    return html`<div class="word-pop t-readout" style=${{ left: `${p.x}px`, top: `${p.y}px` }}>
      <span class="t-label">moment ${p.node} · look ${p.look.toFixed(2)}</span><div>${p.text}</div></div>`;
  }

  function Screen() {
    return html`<div class="chat">
      <section class="conv">
        <${Thread} />
        <${Composer} />
      </section>
      <section class="eyepiece" aria-label="the eyepiece: the memory being read">
        <div class="eye-stage"></div>
        <div class="eye-trace"></div>
      </section>
      <${LightPath} />
      <${Pop} />
    </div>`;
  }

  render(html`<${Screen} />`, el);
  let snapTokenBytes = 0;
  let pathStage = null;
  const stage = new Stage(el.querySelector(".eye-stage"), api, {
    mode: "compact",
    onWord: (i, e) => { playing.value = i < 0 ? null : { key: `${e.src ?? e.reach}/${e.i}`, i }; },
  });
  const trace = new Trace(el.querySelector(".eye-trace"), api, { rows: ["ssdR", "used", "words"], tokenBytes: () => snapTokenBytes });
  const feed = memoryFeed(api);
  const subscriptions = [
    feed.on("event", (e) => { if (e.live) { stage.event(e); trace.addEvent(e); } }),
    feed.on("answer", (rec) => { trace.addAnswer(rec); stage.playAnswer(rec); }),
    feed.on("history", (list) => { for (const rec of list) trace.addAnswer(rec); }),
    feed.on("reaches", () => loadSnap()),
  ];
  for (const rec of feed.answers) trace.addAnswer(rec); // what the feed already heard (on Memory, say)

  effect(() => { const s = st.value; if (s) stage.setOn(s.on !== false); });
  effect(() => {
    const s = api.state.value;
    if (!s || !stage.data) return;
    const ram = ramFromState(s, stage.data, snapTokenBytes);
    if (ram) stage.setRam(ram);
  });
  effect(() => { api.timebase.value; api.reducedMotion.value; stage.renderOverlay(); });
  effect(() => { api.measuring.value; stage.renderOverlay(); stage.kick(stage.now()); }); // blank while measuring, back after
  effect(() => { stage.setRunning(api.running.value); });

  let timer = null;
  return {
    show() {
      loadState();
      loadThread();
      loadSnap();
      stage.show();
      trace.show();
      feed.start();
      clearInterval(timer);
      timer = setInterval(loadState, 3000);
    },
    hide() {
      stage.hide();
      trace.hide();
      feed.stop();
      clearInterval(timer);
      popover.value = null;
    },
    key(e, { typing }) {
      if (e.key === "Escape" && lightpath.value) { lightpath.value = null; return true; }
      if (typing) return false;
      if (e.key === "/") { inputRef.current?.focus(); return true; }
      if ((e.key === "r" || e.key === "R") && lightpath.value?.event) {
        const rec = { e: lightpath.value.event, m: lightpath.value.metric };
        const label = `replay · answer ${rec.e.i ?? ""}`;
        stage.playAnswer(rec, { replay: true, label });
        pathStage?.playAnswer(rec, { replay: true, label });
        return true;
      }
      return false;
    },
    subscriptions,
  };
}
