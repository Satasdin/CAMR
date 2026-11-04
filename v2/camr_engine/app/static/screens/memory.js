// Memory: the full stage (DIRECTION.md, "5. Memory: the stage"). A LIVE / VAULT toggle and the reach picker at the
// stage's top left; the stage itself (SSD plate, bus, RAM plate with the core, the hot shelf and the desk) with the
// vault drawer under it; then the eight-row trace strip. Room and note sheets open on the right.
//
// Everything that moves is a real event: answers, remembers, sleeps and wakes from every reach the chat reads, polled
// from /api/memory/feed, and what sits in RAM from /api/state. R replays the selected answer (or the last one), C shows
// the measuring cursors on the strip, Esc closes a sheet.

import { makeParts } from "/static/stage/parts.js";
import { memoryFeed } from "/static/stage/feed.js";
import { Stage, fmtBytes, ramFromState } from "/static/stage/stage.js";
import { Trace } from "/static/stage/trace.js";
import markdown from "/static/vendor/markdown.js";

const THIN = " ";

export function mount(el, api) {
  const { html, render, signal, effect } = api.ui;
  const { Empty, Glyph } = api.parts;
  api.css("/static/stage/stage.css");
  const P = makeParts(api);
  const md = markdown({ html: false, linkify: false });

  const chat = signal(null); // /api/chat/state, for the reach picker
  const snap = signal(null);
  const error = signal(null);
  const vault = signal(false);
  const sheet = signal(null); // {kind: room|note, data}
  const selected = signal(null); // the answer selected on the strip
  const count = signal(0);
  const answers = []; // recent answers with their records, newest last

  render(html`<${Screen} />`, el);
  const stageHost = el.querySelector(".mem-stage");
  const traceHost = el.querySelector(".mem-trace");
  const stage = new Stage(stageHost, api, {
    mode: "live",
    onSelect: (it) => openRoom(it),
    onNote: (it) => openNote(it.reach, it.note.id),
    onVault: () => setVault(true),
  });
  const trace = new Trace(traceHost, api, { tokenBytes: () => snap.value?.token_bytes || 0 });
  const feed = memoryFeed(api);

  // -- data

  async function loadSnap() {
    try {
      const s = await api.get("/api/memory/stage", vault.value ? { doors: 1 } : undefined);
      snap.value = s;
      error.value = null;
      stage.setSnapshot(s);
      count.value++;
    } catch (e) {
      error.value = e.message;
    }
  }

  async function loadChat() {
    try { chat.value = await api.get("/api/chat/state"); } catch { chat.value = null; }
  }

  async function settings(body) {
    const st = await api.post("/api/chat/settings", body);
    chat.value = st;
    feed.reset();
    await loadSnap();
  }

  function setVault(on) {
    vault.value = on;
    stage.setVault(on);
    loadSnap();
  }

  async function openRoom(it) {
    if (!it) { stage.select(null); sheet.value = null; return; }
    stage.select(it.key);
    try {
      const data = await api.get("/api/memory/room", { reach: it.reach, id: it.room.id });
      sheet.value = { kind: "room", data };
    } catch (e) {
      sheet.value = { kind: "error", data: e.message };
    }
  }

  async function openNote(reach, id) {
    try {
      const data = await api.get("/api/memory/note", { reach, id });
      sheet.value = { kind: "note", data };
    } catch (e) {
      sheet.value = { kind: "error", data: e.message };
    }
  }

  function replay() {
    const rec = selected.value || answers[answers.length - 1];
    if (!rec) return;
    stage.playAnswer(rec, { replay: true, label: `replay · answer ${rec.e.i ?? ""}` });
  }

  // -- the feed (subscribed for the page's life: the feed itself polls only while this screen is on show)

  const subscriptions = [
    feed.on("event", (e) => { if (e.live) { stage.event(e); trace.addEvent(e); } }),
    feed.on("answer", (rec) => {
      answers.push(rec);
      if (answers.length > 60) answers.shift();
      trace.addAnswer(rec);
      stage.playAnswer(rec);
      count.value++;
    }),
    feed.on("history", (list) => {
      for (const rec of list) { answers.push(rec); trace.addAnswer(rec); }
      count.value++;
    }),
    feed.on("reaches", () => loadSnap()),
  ];
  for (const rec of feed.answers) { answers.push(rec); trace.addAnswer(rec); } // what the feed already heard (in Chat, say)

  // signals the shell keeps: hot shelf, timebase, persistence, RUN/STOP, measuring
  effect(() => {
    const st = api.state.value;
    const data = stage.data;
    if (!st || !data || !snap.peek()) return;
    const ram = ramFromState(st, data, snap.peek().token_bytes || 0);
    if (ram) { stage.setRam(ram); trace.addHot(ram); }
  });
  effect(() => { api.timebase.value; api.reducedMotion.value; stage.renderOverlay(); });
  effect(() => { api.persistence.value; stage.build(); });
  effect(() => { stage.setRunning(api.running.value); });
  effect(() => { api.measuring.value; stage.renderOverlay(); stage.kick(stage.now()); });

  // -- the screen

  function Bar() {
    const st = chat.value;
    return html`<div class="mem-bar">
      <${P.Toggle} on=${vault.value} left="live" right="vault" onChange=${setVault} />
      ${st && st.can !== false ? html`<${P.ReachPicker} state=${st} onChange=${settings} busy=${!!st.busy} />`
        : html`<span class="t-readout dim">${snap.value?.fixture ? "a recorded memory · read-only" : st?.why || ""}</span>`}
      <span class="grow"></span>
      ${error.value ? html`<span class="t-readout fault-text"><${Glyph} kind="cross" /> ${error.value}</span>` : null}
      <span class="t-readout dim mem-hint">R replay · C cursors · [ ] timebase · P persistence · Space run/stop</span>
    </div>`;
  }

  function RoomSheet({ d }) {
    const lastLook = d.shares || {};
    const total = d.moments.reduce((a, m) => a + m.tokens, 0) || 1;
    const W = 320, rowH = 4;
    const cols = [];
    let x = 0;
    for (const m of d.moments) {
      const w = Math.max(1, (W * m.tokens) / total);
      const share = lastLook[m.id] ?? lastLook[String(m.id)] ?? 0;
      for (let r = 0; r < 28; r++) {
        const watched = r === 12 || r === 16 || r === 20 || r === 24;
        cols.push(html`<rect class=${watched && share > 0 ? "rs-lit" : "rs-cell"} x=${x} y=${r * (rowH + 1)} width=${Math.max(0.5, w - (w >= 3 ? 1 : 0))} height=${rowH}
          style=${watched && share > 0 ? { opacity: Math.min(1, 0.25 + share * 1.5) } : null} />`);
      }
      x += w;
    }
    return html`<${P.Sheet} title=${`room ${d.id}`} sub=${`${d.reach} · ${d.moments.length} moments · ${d.tokens.toLocaleString("en-US")}${THIN}tok`}
        onClose=${() => { sheet.value = null; stage.select(null); }}>
      <div class="rs-tile">
        <svg width=${W + 40} height=${28 * (rowH + 1)} role="img" aria-label="the room's notes: 28 layers by its tokens">
          <g transform="translate(40 0)">${cols}</g>
          ${[12, 16, 20, 24].map((L) => html`<text class="rs-l" x="0" y=${L * (rowH + 1) + 4}>L${L}</text>`)}
        </svg>
        <div class="t-label dim">watched rows lit with the last answer's share · the other 24 rows not watched</div>
      </div>
      <div class="sheet-grid">
        <div class="readout"><span class="t-label">on disk</span><span class="t-readout">${d.asleep ? "asleep · words only" : fmtBytes(d.file_bytes)}</span></div>
        <div class="readout"><span class="t-label">notes</span><span class="t-readout">${fmtBytes(d.bytes)}</span></div>
        <div class="readout"><span class="t-label">reads</span><span class="t-readout">${d.reads}×</span></div>
        <div class="readout"><span class="t-label">last share</span><span class="t-readout">${d.last_share == null ? "—" : d.last_share.toFixed(2)}</span></div>
        <div class="readout"><span class="t-label">in RAM</span><span class="t-readout">${d.hot ? "hot" : "no"}</span></div>
        <div class="readout"><span class="t-label">doors out</span><span class="t-readout">${d.doors.length ? d.doors.map((x) => `room ${x.room} ×${x.count}`).join(" · ") : "—"}</span></div>
      </div>
      <ol class="rs-moments">
        ${d.moments.map((m) => html`<li>
          <span class="t-label">day ${m.day} · ${m.tokens}${THIN}tok${m.used ? ` · used ${m.used}×` : ""}${(d.shares?.[m.id] ?? d.shares?.[String(m.id)]) != null ? ` · share ${(d.shares[m.id] ?? d.shares[String(m.id)]).toFixed(2)}` : ""}</span>
          <p class="t-body">${m.text}</p>
          ${m.note ? html`<button class="btn" onClick=${() => { setVault(true); openNote(d.reach, m.note); }}>open in vault</button>` : null}
        </li>`)}
      </ol>
    <//>`;
  }

  function NoteSheet({ d }) {
    const body = md.render(d.text || "");
    const link = (x) => html`<li><button class="linkish" onClick=${() => openNote(d.reach, x.id)}>${x.id}</button>
      <span class="t-readout dim"> · ${x.weight.toFixed(2)}</span>${x.head ? html`<div class="t-readout dim">${x.head}</div>` : null}</li>`;
    return html`<${P.Sheet} wide=${true} title=${d.id} sub=${`${d.reach} · day ${d.day ?? "—"} · strength ${(d.strength ?? 0).toFixed(2)}${d.asleep ? " · asleep" : ""}${d.pinned ? " · pinned" : ""}${d.tags?.length ? ` · ${d.tags.join(", ")}` : ""}`}
        onClose=${() => { sheet.value = null; }}>
      <div class="note-md t-body" dangerouslySetInnerHTML=${{ __html: body }}></div>
      <div class="t-label">doors · ${d.links.length}</div><ul class="note-links">${d.links.map(link)}</ul>
      <div class="t-label">backlinks · ${d.backlinks.length}</div><ul class="note-links">${d.backlinks.map(link)}</ul>
    <//>`;
  }

  function Answers() {
    void count.value;
    const list = answers.slice(-12).reverse();
    if (!list.length) return html`<span class="t-readout dim">no answers yet · ask something in Chat</span>`;
    return html`<div class="mem-answers" role="listbox" aria-label="recent answers">
      ${list.map((rec) => html`<button class=${`mem-ans${selected.value === rec ? " on" : ""}`} role="option" aria-selected=${String(selected.value === rec)}
        title=${rec.e.question || ""} onClick=${() => { const on = selected.value === rec ? null : rec; selected.value = on; trace.select(on); if (on) stage.playAnswer(on, { replay: true, label: `replay · answer ${on.e.i ?? ""}` }); }}>
        <span class="t-readout">${(rec.e.question || "").slice(0, 38)}</span>
        <span class="t-label">${rec.e.reach || ""} · ${rec.m ? `${rec.m.first_word_s.toFixed(2)}${THIN}s` : "—"}</span></button>`)}
    </div>`;
  }

  function Screen() {
    const s = sheet.value;
    return html`<div class="mem">
      <${Bar} />
      <div class="mem-stage"></div>
      <div class="mem-strip">
        <div class="mem-strip-head"><span class="t-label">trace · ${selected.value ? "answer" : "last 60 s"}</span><${Answers} /></div>
        <div class="mem-trace"></div>
      </div>
      ${s?.kind === "room" ? html`<${RoomSheet} d=${s.data} />` : null}
      ${s?.kind === "note" ? html`<${NoteSheet} d=${s.data} />` : null}
      ${s?.kind === "error" ? html`<${P.Sheet} title="not found" onClose=${() => { sheet.value = null; }}><${Empty}>${s.data}<//><//>` : null}
      ${snap.value && !snap.value.reaches.length ? html`<div class="mem-empty"><${Empty}>no memory open · tell something in Chat to start one<//></div>` : null}
    </div>`;
  }

  let chatTimer = null;
  return {
    show() {
      loadChat();
      loadSnap();
      stage.show();
      trace.show();
      feed.start();
      clearInterval(chatTimer);
      chatTimer = setInterval(loadChat, 3000);
    },
    hide() {
      stage.hide();
      trace.hide();
      feed.stop();
      clearInterval(chatTimer);
    },
    key(e, { typing }) {
      if (typing) return false;
      if (e.key === "r" || e.key === "R") { replay(); return true; }
      if (e.key === "c" || e.key === "C") { return trace.toggleCursors(); }
      if (e.key === "Escape") {
        if (sheet.value) { sheet.value = null; stage.select(null); return true; }
        if (selected.value) { selected.value = null; trace.select(null); return true; }
        if (vault.value) { setVault(false); return true; }
      }
      return false;
    },
  };
}
