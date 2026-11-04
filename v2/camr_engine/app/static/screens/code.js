// Code: the workbench. The local model works in a folder you choose, with the engine as its memory.
// Left: threads (each ending in its last answer's path strip) and the workspace's files. Centre: the editor with
// tabs and the memory gutter (green: written while leaning on memory; violet: from a saved fix; a violet tick: your
// fix, kept), then the run trace above the transcript, and the read-only terminal. Right: the rack (the model and
// the memory switch, personas with their reaches, tools, MCP servers and skills).
// Nothing the model asks to run (a shell command, an MCP call) runs until you allow that one call here. The card shows
// it exactly as it will run (control and invisible characters drawn as ⟨U+202E⟩), with its lines and characters
// counted, and "allow once" wakes only after the card has been on screen a moment and scrolled to its end.

const LANGS = { py: "python", js: "javascript", mjs: "javascript", cjs: "javascript", ts: "javascript",
  tsx: "javascript", jsx: "javascript", json: "javascript", html: "html", htm: "html", css: "css", md: "markdown" };
const TOOLS = ["read_file", "list_files", "search", "write_file", "edit_file", "run_shell", "load_skill"];
const ASKS = ["run_shell"]; // tools that wait for you (and every MCP tool)
const REACHES = ["session", "project", "agent", "global"];
const LIVE = new Set(["queued", "thinking", "tool", "waiting", "measuring", "keeping"]);
const THREAD_KEY = "camr_engine.code.thread";
const TABS_KEY = "camr_engine.code.tabs";
const MAX_TABS = 12;
const ASK_WAKE_MS = 700; // an ask's "allow once" stays asleep this long, so a double click never allows the next one
const HIDDEN = /[\p{Cc}\p{Cf}\p{Zl}\p{Zp}]/gu;

// control and invisible characters drawn visibly (new lines and tabs stay as they are)
function visible(text) {
  return String(text ?? "").replace(HIDDEN, (c) => (c === "\n" || c === "\t" ? c
    : `⟨U+${c.codePointAt(0).toString(16).toUpperCase().padStart(4, "0")}⟩`));
}

// what an ask will run, as text: the command, or the MCP call's arguments
function askText(a) {
  return a.kind === "shell" ? a.what.command : JSON.stringify(a.what.arguments, null, 2);
}

const STYLE = `
.cd { position: absolute; inset: 0; display: grid; grid-template-columns: 240px minmax(0, 1fr) 300px;
  grid-template-rows: minmax(0, 1fr); min-height: 620px; background: var(--bed); }
.cd-col { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.cd-left { border-right: 1px solid var(--hair); background: var(--s1); }
.cd-rack { border-left: 1px solid var(--hair); background: var(--s1); overflow: auto; position: relative; }
.cd-block { padding: var(--sp-3) var(--sp-3) var(--sp-2); }
.cd-block + .cd-block { border-top: 1px solid var(--hair); }
.cd-head { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-2);
  margin-bottom: var(--sp-2); min-height: 20px; }
.cd-ws { color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cd-mini { height: 22px; padding: 0 8px; }
.cd-threads { overflow: auto; max-height: 34%; flex: 0 0 auto; }
.cd-thread { display: block; width: 100%; text-align: left; background: transparent; border: 1px solid transparent;
  border-radius: var(--r-mark); padding: 6px 8px 0; color: var(--ink-2); margin-bottom: 2px; }
.cd-thread:hover { background: var(--s2); }
.cd-thread[aria-current="true"] { border-color: var(--select); color: var(--ink); }
.cd-thread .tt { display: block; font: 400 13px/18px var(--f-text); white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.cd-thread .tm { display: block; color: var(--ink-3); font: 400 10.5px/14px var(--f-mono); }
.cd-thread .strip6 { display: block; height: 6px; margin: 4px 0 6px; }
.cd-files { flex: 1 1 auto; overflow: auto; padding-bottom: var(--sp-4); }
.cd-file { display: flex; align-items: center; gap: 6px; width: 100%; height: 24px; background: transparent;
  border: 0; color: var(--ink-2); font: 400 12.5px/18px var(--f-code); text-align: left; padding: 0 8px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border-radius: var(--r-mark); }
.cd-file:hover { background: var(--s2); color: var(--ink); }
.cd-file[aria-current="true"] { color: var(--ink); box-shadow: inset 2px 0 0 var(--select); }
.cd-file.secret, .cd-file:disabled { color: var(--ink-4); cursor: default; background: transparent; }
.cd-file .icon svg { width: 12px; height: 12px; }
.cd-centre { display: grid; grid-template-rows: 32px minmax(160px, 1fr) minmax(340px, 44%); min-width: 0;
  min-height: 0; }
.cd-tabs { display: flex; align-items: stretch; border-bottom: 1px solid var(--hair); background: var(--s1);
  overflow-x: auto; }
.cd-tab { display: flex; align-items: center; gap: 6px; padding: 0 10px; background: transparent; border: 0;
  border-right: 1px solid var(--hair); color: var(--ink-3); font: 400 12.5px/18px var(--f-code); white-space: nowrap; }
.cd-tab[aria-current="true"] { color: var(--ink); box-shadow: inset 0 -2px 0 var(--select); background: var(--void); }
.cd-tab .nm { display: flex; align-items: center; gap: 6px; background: none; border: 0; color: inherit; padding: 0;
  font: inherit; height: 100%; }
.cd-tab .x { color: var(--ink-4); background: none; border: 0; padding: 0 2px; display: flex; align-items: center; }
.cd-tab .x:hover { color: var(--ink); }
.cd-tab .dirty { width: 6px; height: 6px; border-radius: 50%; background: var(--ink-2); }
.cd-tabbar-end { margin-left: auto; display: flex; align-items: center; gap: var(--sp-2); padding: 0 var(--sp-2); }
.cd-editor { position: relative; min-height: 0; background: var(--void); overflow: hidden; }
.cd-editor .cm-editor { height: 100%; }
.cd-editor .empty.fill { inset: var(--sp-4); }
.cd-bottom { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); border-top: 1px solid var(--hair);
  min-height: 0; }
.cd-work { display: grid; grid-template-rows: auto minmax(0, 1fr) auto auto; min-width: 0; min-height: 0;
  border-right: 1px solid var(--hair); }
.cd-trace { height: 120px; background: var(--void); border-bottom: 1px solid var(--hair); overflow: hidden; }
.cd-trace svg { display: block; }
.cd-transcript { overflow: auto; padding: var(--sp-3) var(--sp-4); min-height: 0; }
.cd-turn { margin-bottom: var(--sp-3); }
.cd-you { color: var(--ink); font: 400 15px/24px var(--f-text); }
.cd-you::before { content: "›"; color: var(--ink-3); margin-right: 8px; }
.cd-words { color: var(--ink-2); font: 400 15px/24px var(--f-text); white-space: pre-wrap; overflow-wrap: anywhere; }
.cd-answer { color: var(--ink); font: 400 15px/24px var(--f-text); white-space: pre-wrap; overflow-wrap: anywhere; }
.cd-receipt { display: flex; align-items: center; gap: 8px; width: 100%; text-align: left; background: transparent;
  border: 0; border-left: 1px solid var(--hair-2); padding: 2px 8px; color: var(--ink-2);
  font: 400 13px/20px var(--f-code); }
.cd-receipt:hover { background: var(--s1); color: var(--ink); }
.cd-receipt .arg { color: var(--ink-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.cd-receipt .ms { color: var(--ink-3); font: 400 12px/16px var(--f-mono); white-space: nowrap; }
.cd-out { margin: 4px 0 0 9px; padding: 8px; background: var(--void); border: 1px solid var(--hair);
  border-radius: var(--r-mark); max-height: 280px; overflow: auto; color: var(--ink-2);
  font: 400 12.5px/18px var(--f-code); white-space: pre-wrap; overflow-wrap: anywhere; }
.cd-diff { margin: 4px 0 0 9px; border: 1px solid var(--hair); border-radius: var(--r-mark); max-height: 320px;
  overflow: auto; }
.cd-path { display: flex; align-items: center; gap: 8px; margin-top: 4px; color: var(--ink-3); }
.cd-path svg { flex: 0 0 auto; }
.cd-path .t-readout { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cd-path .used { color: var(--used); }
.cd-path .picked { color: var(--ram); }
.cd-kept { color: var(--ssd); }
.cd-ask { margin: 0 var(--sp-3) var(--sp-2); padding: var(--sp-3); border: 1px solid var(--select);
  border-radius: var(--r-panel); background: var(--s1); }
.cd-ask pre { margin: 6px 0; padding: 8px; background: var(--void); border: 1px solid var(--hair);
  border-radius: var(--r-mark); color: var(--ink); font: 400 13px/20px var(--f-code); white-space: pre-wrap;
  overflow-wrap: anywhere; max-height: 160px; overflow: auto; }
.cd-ask .row { display: flex; gap: var(--sp-2); align-items: center; flex-wrap: wrap; }
.cd-ask .who { color: var(--ink-2); }
.cd-composer { margin: 0 var(--sp-3) var(--sp-3); border: 1px solid var(--hair-2); border-radius: var(--r-panel);
  background: var(--s1); display: grid; grid-template-columns: auto 1fr auto; align-items: end; gap: var(--sp-2);
  padding: 6px var(--sp-2); }
.cd-composer .prompt { color: var(--ink-3); font: 400 15px/24px var(--f-text); padding-left: 4px; }
.cd-composer textarea { resize: none; background: transparent; border: 0; color: var(--ink);
  font: 400 15px/24px var(--f-text); min-height: 24px; max-height: 120px; padding: 0; }
.cd-composer textarea::placeholder { color: var(--ink-3); }
.cd-composer .why { grid-column: 1 / -1; color: var(--ink-3); }
.cd-termbox { display: grid; grid-template-rows: 28px minmax(0, 1fr); min-width: 0; min-height: 0;
  background: var(--void); }
.cd-termhead { display: flex; align-items: center; justify-content: space-between; padding: 0 var(--sp-3);
  border-bottom: 1px solid var(--hair); background: var(--s1); }
.cd-term { min-height: 0; padding: 6px 0 0 8px; overflow: hidden; }
.cd-term .xterm { height: 100%; }
.cd-module { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 2px var(--sp-2);
  min-height: var(--row-module); padding: 4px 8px; border: 1px solid var(--hair); border-radius: var(--r-mark);
  margin-bottom: 4px; background: transparent; color: var(--ink-2); text-align: left; width: 100%; }
button.cd-module:hover { background: var(--s2); }
.cd-module[aria-pressed="true"] { border-color: var(--select); color: var(--ink); }
.cd-module .ty { grid-column: 1; }
.cd-module .nm { grid-column: 1; font: 400 13px/18px var(--f-text); color: var(--ink); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.cd-module .mk { grid-column: 2; grid-row: 1 / span 2; display: flex; align-items: center; gap: 6px; }
.cd-module.off { opacity: .45; }
.cd-row { display: grid; grid-template-columns: 1fr auto; gap: 4px; align-items: start; }
.cd-row .btn { height: var(--row-module); }
.cd-module .rings { display: inline-flex; gap: 3px; }
.cd-ring { color: var(--ink-4); }
.cd-ring.read { color: var(--select); }
.cd-ring.writes { box-shadow: 0 2px 0 var(--select); }
.cd-active { color: var(--ink); }
.cd-idle { color: var(--ink-3); }
.cd-pill { display: inline-flex; border: 1px solid var(--hair-2); border-radius: var(--r-pill); overflow: hidden; }
.cd-pill button { height: 22px; padding: 0 10px; border: 0; background: transparent; color: var(--ink-3);
  font: 500 10.5px/14px var(--f-mono); font-stretch: 87.5%; letter-spacing: .08em; text-transform: uppercase; }
.cd-pill button[aria-pressed="true"] { color: var(--void); background: var(--ink); }
.cd-sheet { position: absolute; top: 0; right: 0; bottom: 0; width: 360px; max-width: 100%; background: var(--s1);
  border-left: 1px solid var(--hair-2); z-index: 5; display: flex; flex-direction: column; }
.cd-sheet.wide { width: 420px; }
.cd-sheet .body { padding: var(--sp-4); overflow: auto; flex: 1; display: flex; flex-direction: column;
  gap: var(--sp-3); }
.cd-sheet .top { display: flex; align-items: center; justify-content: space-between; padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--hair); }
.cd-sheet label { display: flex; flex-direction: column; gap: 4px; }
.cd-sheet textarea.field { height: 160px; padding: var(--sp-2); resize: vertical; font: 400 13px/20px var(--f-code); }
.cd-sheet .field { width: 100%; }
.cd-sheet .md { color: var(--ink-2); font: 400 14px/22px var(--f-text); }
.cd-sheet .md code, .cd-sheet .md pre { font: 400 12.5px/18px var(--f-code); color: var(--ink); }
.cd-sheet .md pre { background: var(--void); padding: 8px; border: 1px solid var(--hair); overflow: auto; }
.cd-recent { display: block; width: 100%; text-align: left; background: transparent; border: 1px solid var(--hair);
  border-radius: var(--r-mark); color: var(--ink-2); padding: 6px 8px; margin-bottom: 4px;
  font: 400 12px/16px var(--f-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cd-recent:hover { color: var(--ink); background: var(--s2); }
.cd-note { color: var(--ink-3); font: 400 12px/16px var(--f-mono); }
.cd-error { color: var(--fault); font: 400 12px/16px var(--f-mono); }
.cd-check { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.cd-check label { flex-direction: row; align-items: center; gap: 6px; color: var(--ink-2); }
.cd-pop { position: fixed; z-index: 20; max-width: 360px; background: var(--s2); border: 1px solid var(--hair-2);
  border-radius: var(--r-mark); padding: 8px 10px; color: var(--ink-2); pointer-events: none;
  font: 400 12px/16px var(--f-mono); }
.cd-pop .words { color: var(--ink); font: 400 13px/20px var(--f-text); margin-top: 4px; }
.cm-memory { width: 7px; }
.cm-memory .cm-gutterElement { padding: 0 2px 0 2px !important; }
.mg { width: 3px; height: 100%; min-height: 20px; }
.mg-used { background: var(--used); box-shadow: var(--glow-used); }
.mg-fix { background: var(--vault); }
.mg-yours { background: linear-gradient(var(--vault), var(--vault)) top / 3px 4px no-repeat; }
.mg-none { background: transparent; }
@media (max-width: 1280px) { .cd { grid-template-columns: 220px minmax(0, 1fr) 260px; } }
@media (max-width: 900px) {
  .cd { position: relative; inset: auto; display: flex; flex-direction: column; min-height: 0; }
  .cd-centre { order: 1; grid-template-rows: 32px 420px auto; }
  .cd-bottom { grid-template-columns: 1fr; }
  .cd-work { border-right: 0; min-height: 420px; }
  .cd-termbox { height: 260px; }
  .cd-left { order: 2; border-right: 0; border-top: 1px solid var(--hair); }
  .cd-threads { max-height: none; }
  .cd-rack { order: 3; border-left: 0; border-top: 1px solid var(--hair); overflow: visible; }
  .cd-sheet, .cd-sheet.wide { position: fixed; top: var(--strip-h); width: 100%; }
}
`;

function addStyle() {
  if (document.getElementById("code-screen-style")) return;
  const s = document.createElement("style");
  s.id = "code-screen-style";
  s.textContent = STYLE;
  document.head.appendChild(s);
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function load(key, fallback) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private window */ }
}

export async function mount(el, api) {
  const { html, render, signal, computed, useRef, useEffect, useState } = api.ui;
  const { Val, Glyph, Icon, Empty } = api.parts;
  const { fmt } = api;
  addStyle();
  const cm = await import("/static/vendor/codemirror.js");

  // -- state

  const st = signal(null); // /api/code/state
  const stErr = signal(null);
  const files = signal([]);
  const folded = signal(new Set(load("camr_engine.code.folded", [])));
  const tabs = signal([]); // [{path, sha, dirty}]
  const active = signal(null);
  const threadId = signal(load(THREAD_KEY, null));
  const thread = signal(null);
  const run = signal(null);
  const sheet = signal(null); // {kind, ...}
  const unfolded = signal(new Set());
  const note = signal(null); // the last action's message
  const busy = signal(false);
  const task = signal("");
  const pop = signal(null);
  const states = new Map(); // path -> EditorState
  const momentCache = new Map();
  let termNext = 0;
  let termRun = null;

  const persona = computed(() => (st.value?.personas || []).find((p) => p.id === st.value?.persona) || null);
  const live = computed(() => run.value && LIVE.has(run.value.state));

  // -- the editor: CodeMirror with greys only (colour is kept for memory) and the memory gutter

  const theme = cm.EditorView.theme({
    "&": { color: "var(--ink)", backgroundColor: "var(--void)", height: "100%" },
    ".cm-content": { fontFamily: "var(--f-code)", fontSize: "13px", lineHeight: "20px", caretColor: "var(--ink)" },
    ".cm-scroller": { fontFamily: "var(--f-code)" },
    ".cm-gutters": { backgroundColor: "var(--void)", color: "var(--ink-4)", border: "none",
      fontFamily: "var(--f-mono)", fontSize: "11px" },
    ".cm-activeLine": { backgroundColor: "var(--s1)" },
    ".cm-activeLineGutter": { backgroundColor: "var(--s1)", color: "var(--ink-3)" },
    "&.cm-focused": { outline: "none" },
    "&.cm-focused .cm-cursor": { borderLeftColor: "var(--ink)" },
    "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground":
      { backgroundColor: "var(--hair-2)" },
    ".cm-matchingBracket, &.cm-focused .cm-matchingBracket": { backgroundColor: "var(--s2)",
      outline: "1px solid var(--ink-4)" },
    ".cm-searchMatch": { backgroundColor: "var(--s2)", outline: "1px solid var(--ink-3)" },
    ".cm-panels": { backgroundColor: "var(--s1)", color: "var(--ink-2)", borderTop: "1px solid var(--hair)" },
    ".cm-panels input, .cm-panels button": { color: "var(--ink)", backgroundColor: "var(--void)",
      border: "1px solid var(--hair-2)" },
    ".cm-tooltip": { backgroundColor: "var(--s2)", color: "var(--ink)", border: "1px solid var(--hair-2)" },
    ".cm-tooltip-autocomplete > ul > li[aria-selected]": { backgroundColor: "var(--hair-2)", color: "var(--ink)" },
    ".cm-foldPlaceholder": { backgroundColor: "var(--s2)", color: "var(--ink-3)", border: "1px solid var(--hair-2)" },
    // the diff view in greys: green and red mean memory and faults here, not added and removed
    ".cm-changedLine, .cm-insertedLine": { backgroundColor: "var(--s2) !important" },
    ".cm-changedText, .cm-insertedText": { background: "none !important",
      borderBottom: "1px solid var(--ink-2) !important" },
    ".cm-deletedChunk, .cm-deletedLine": { backgroundColor: "var(--s1) !important", color: "var(--ink-3)" },
    ".cm-deletedText": { background: "none !important", textDecoration: "line-through", color: "var(--ink-3)" },
    ".cm-changedLineGutter, .cm-deletedLineGutter": { background: "var(--ink-3) !important" },
  }, { dark: true });

  const t = cm.tags;
  const greys = cm.syntaxHighlighting(cm.HighlightStyle.define([
    { tag: [t.keyword, t.controlKeyword, t.moduleKeyword, t.operatorKeyword], color: "var(--ink)", fontWeight: "600" },
    { tag: [t.string, t.special(t.string), t.regexp], color: "var(--ink-2)" },
    { tag: [t.comment, t.lineComment, t.blockComment, t.docComment], color: "var(--ink-3)", fontStyle: "italic" },
    { tag: [t.number, t.bool, t.null, t.atom], color: "var(--ink-2)" },
    { tag: [t.definition(t.variableName), t.function(t.definition(t.variableName)), t.className],
      color: "var(--ink)", fontWeight: "500" },
    { tag: [t.typeName, t.propertyName, t.attributeName], color: "var(--ink)" },
    { tag: [t.punctuation, t.bracket, t.separator], color: "var(--ink-3)" },
    { tag: [t.operator, t.tagName], color: "var(--ink-2)" },
    { tag: [t.heading], color: "var(--ink)", fontWeight: "600" },
    { tag: [t.link, t.url], color: "var(--ink-2)", textDecoration: "underline" },
    { tag: [t.meta, t.processingInstruction], color: "var(--ink-3)" },
    { tag: t.invalid, color: "var(--ink)", textDecoration: "underline wavy var(--ink-3)" }, // red needs a ×
  ]));

  const setMarks = cm.StateEffect.define();
  class MarkG extends cm.GutterMarker {
    constructor(m) { super(); this.m = m; }
    eq(o) { return o.m === this.m; }
    toDOM() {
      const d = document.createElement("div");
      d.className = `mg mg-${this.m.kind}`;
      return d;
    }
  }
  const markField = cm.StateField.define({
    create: () => cm.RangeSet.empty,
    update(value, tr) {
      let v = value.map(tr.changes);
      for (const e of tr.effects) if (e.is(setMarks)) v = e.value;
      return v;
    },
  });
  function markSet(doc, marks) {
    const b = new cm.RangeSetBuilder();
    for (const n of Object.keys(marks || {}).map(Number).sort((a, c) => a - c)) {
      if (n >= 1 && n <= doc.lines) b.add(doc.line(n).from, doc.line(n).from, new MarkG(marks[n]));
    }
    return b.finish();
  }
  function markAt(view, pos) {
    let got = null;
    view.state.field(markField).between(pos, pos, (from, to, value) => { got = value.m; });
    return got;
  }
  const memoryGutter = [markField, cm.gutter({
    class: "cm-memory",
    markers: (v) => v.state.field(markField),
    initialSpacer: () => new MarkG({ kind: "none" }),
    domEventHandlers: {
      mousemove(view, line, ev) { hoverMark(markAt(view, line.from), ev); return false; },
      mouseleave() { pop.value = null; return false; },
    },
  })];

  async function hoverMark(m, ev) {
    if (!m) { pop.value = null; return; }
    const at = { x: ev.clientX + 14, y: ev.clientY + 10 };
    if (m.kind === "yours") {
      pop.value = { ...at, head: "your fix · kept", words: st.peek()?.memory
        ? "you changed this line · kept in the project's memory and told to the next run"
        : "you changed this line · told to the next run (memory is off, so it is not kept)" };
      return;
    }
    const head = `${m.kind === "fix" ? "from a saved fix" : "leaned on memory"} · look ${fmt.num(m.look, 2)} · ${m.reach || "—"}`;
    pop.value = { ...at, head, words: "…", strip: m.strip || null };
    const key = `${m.reach}#${m.node}`;
    if (!momentCache.has(key)) {
      momentCache.set(key, api.get("/api/code/moment", { reach: m.reach, id: m.node }).catch((e) => ({ error: e.message })));
    }
    const got = await momentCache.get(key);
    if (pop.value && pop.value.head === head) {
      pop.value = { ...at, head: got.error ? head : `${head} · room ${got.room} · day ${got.day}`,
        words: got.error ? "the moment's memory is not open now" : got.text, strip: m.strip || null };
    }
  }

  function language(path) {
    const ext = (path.split(".").pop() || "").toLowerCase();
    const name = LANGS[ext];
    if (!name) return [];
    if (name === "javascript") return [cm.javascript({ typescript: /tsx?$/.test(ext), jsx: /x$/.test(ext) })];
    return [cm[name]()];
  }

  const editorBox = document.createElement("div");
  editorBox.style.height = "100%";
  const view = new cm.EditorView({ parent: editorBox, state: cm.EditorState.create({ doc: "" }) });

  function newState(path, text, marks) {
    const s = cm.EditorState.create({
      doc: text,
      extensions: [cm.basicSetup, memoryGutter, theme, greys, language(path),
        cm.keymap.of([{ key: "Mod-s", run: () => { saveTab(); return true; } }]),
        cm.EditorView.updateListener.of((u) => { if (u.docChanged) markDirty(path, true); })],
    });
    return s.update({ effects: setMarks.of(markSet(s.doc, marks)) }).state;
  }

  function markDirty(path, dirty) {
    const next = tabs.peek().map((x) => (x.path === path && x.dirty !== dirty ? { ...x, dirty } : x));
    if (next.some((x, i) => x !== tabs.peek()[i])) tabs.value = next;
  }

  async function openFile(path, fresh = false) {
    if (!path) return;
    if (!fresh && states.has(path)) { switchTab(path); return; }
    try {
      const f = await api.get("/api/code/file", { path });
      states.set(f.path, newState(f.path, f.text, f.marks));
      let next = [...tabs.peek().filter((x) => x.path !== f.path), { path: f.path, sha: f.sha, dirty: false }];
      while (next.length > MAX_TABS) { // the oldest clean tab goes; a tab with unsaved edits never does
        const old = next.find((x) => !x.dirty && x.path !== f.path && x.path !== active.peek());
        if (!old) break;
        states.delete(old.path);
        next = next.filter((x) => x !== old);
      }
      tabs.value = next;
      switchTab(f.path);
    } catch (e) {
      note.value = { error: e.message };
    }
  }

  function switchTab(path) {
    const cur = active.peek();
    if (cur && states.has(cur)) states.set(cur, view.state);
    active.value = path;
    save(TABS_KEY, { open: tabs.peek().map((x) => x.path), active: path });
    if (path && states.has(path)) view.setState(states.get(path));
  }

  function closeTab(path) {
    const tab = tabs.peek().find((x) => x.path === path);
    if (tab?.dirty && !confirm(`Close ${path} without saving?`)) return;
    states.delete(path);
    tabs.value = tabs.peek().filter((x) => x.path !== path);
    if (active.peek() === path) {
      const next = tabs.peek().at(-1)?.path || null;
      active.value = null;
      if (next) switchTab(next);
      else view.setState(cm.EditorState.create({ doc: "" }));
    }
    save(TABS_KEY, { open: tabs.peek().map((x) => x.path), active: active.peek() });
  }

  async function saveTab() {
    const path = active.peek();
    const tab = tabs.peek().find((x) => x.path === path);
    if (!tab) return;
    try {
      const got = await api.post("/api/code/file", { path, text: view.state.doc.toString(), base: tab.sha });
      tabs.value = tabs.peek().map((x) => (x.path === path ? { ...x, sha: got.sha, dirty: false } : x));
      view.dispatch({ effects: setMarks.of(markSet(view.state.doc, got.marks)) });
      states.set(path, view.state);
      note.value = got.fix ? { text: got.kept ? `your fix · kept in ${got.kept} · the next run is told` : "your fix · the next run is told" }
        : { text: `saved ${path}` };
      refresh();
    } catch (e) {
      note.value = { error: e.message };
    }
  }

  // agent writes: reopen a written file if it is open and unchanged here, so its marks show
  const seenWrites = new Set();
  function followWrites(r) {
    for (const turn of r.turns || []) {
      if (turn.kind !== "call" || !turn.path || !turn.ok) continue;
      const key = `${r.id}:${turn.at}`;
      if (seenWrites.has(key)) continue;
      seenWrites.add(key);
      const tab = tabs.peek().find((x) => x.path === turn.path);
      if (!tab || !tab.dirty) openFile(turn.path, true);
    }
  }

  // -- the terminal: read-only xterm, in greys, with red kept for failures

  let term = null;
  let fit = null;
  const termBox = document.createElement("div");
  termBox.style.height = "100%";
  async function makeTerm() {
    try {
      api.css("/static/vendor/@xterm/xterm@6.0.0/css/xterm.css");
      const { Terminal } = await import("/static/vendor/@xterm/xterm@6.0.0/lib/xterm.mjs");
      const { FitAddon } = await import("/static/vendor/@xterm/addon-fit@0.11.0/lib/addon-fit.mjs");
      const ink = cssVar("--ink"), ink2 = cssVar("--ink-2"), ink3 = cssVar("--ink-3"), fault = cssVar("--fault");
      term = new Terminal({
        disableStdin: true, cursorBlink: false, cursorInactiveStyle: "none", scrollback: 5000, convertEol: true,
        fontFamily: cssVar("--f-code"), fontSize: 12.5, lineHeight: 1.44,
        theme: { background: cssVar("--void"), foreground: ink2, cursor: cssVar("--void"),
          selectionBackground: cssVar("--hair-2"), black: cssVar("--void"), red: fault, green: ink, yellow: ink2,
          blue: ink2, magenta: ink2, cyan: ink2, white: ink, brightBlack: ink3, brightRed: fault, brightGreen: ink,
          brightYellow: ink, brightBlue: ink, brightMagenta: ink, brightCyan: ink, brightWhite: ink },
      });
      fit = new FitAddon();
      term.loadAddon(fit);
      term.open(termBox);
      new ResizeObserver(() => { try { fit.fit(); } catch { /* hidden */ } }).observe(termBox);
    } catch (e) {
      termBox.textContent = `terminal unavailable · ${e.message}`;
    }
  }

  function feedTerm(r) {
    if (!term || !r) return;
    if (termRun !== r.id) {
      term.reset(); termRun = r.id; termNext = 0;
      if (r.term_cut) term.write(`\x1b[90m… ${fmt.int(r.term_cut)} characters left out …\x1b[0m\r\n`);
    }
    for (const chunk of r.term || []) term.write(chunk);
    termNext = r.term_next ?? termNext;
  }

  // -- data

  async function refresh() {
    try {
      st.value = await api.get("/api/code/state");
      stErr.value = null;
    } catch (e) {
      stErr.value = e.message;
    }
  }

  async function loadFiles() {
    try { files.value = (await api.get("/api/code/files")).files; } catch (e) { note.value = { error: e.message }; }
  }

  async function loadThread(id) {
    if (!id) { thread.value = null; run.value = null; return; }
    try {
      const t0 = await api.get("/api/code/thread", { id });
      thread.value = t0;
      const r = t0.live || t0.runs.at(-1) || null;
      run.value = r;
      if (r) { termRun = null; feedTerm(r); }
    } catch (e) {
      if (e.status === 404) { threadId.value = null; save(THREAD_KEY, null); thread.value = null; run.value = null; }
    }
  }

  function pickThread(id) {
    threadId.value = id;
    save(THREAD_KEY, id);
    unfolded.value = new Set();
    loadThread(id);
  }

  async function newThread() {
    try {
      const t0 = await api.post("/api/code/thread", { persona: st.peek()?.persona });
      await refresh();
      pickThread(t0.id);
      return t0.id;
    } catch (e) {
      note.value = { error: e.message };
      return null;
    }
  }

  async function startRun() {
    const text = task.peek().trim();
    if (!text || busy.peek()) return;
    busy.value = true;
    try {
      const id = threadId.peek() || (await newThread());
      if (!id) return;
      // the persona chosen in the rack runs, whatever the thread ran as before
      const r = await api.post("/api/code/run", { thread: id, task: text, memory: st.peek()?.memory, persona: st.peek()?.persona });
      task.value = "";
      run.value = r;
      termRun = null;
      feedTerm(r);
      note.value = null;
      pollRun();
    } catch (e) {
      note.value = { error: e.message };
    } finally {
      busy.value = false;
    }
  }

  async function stopRun() {
    const r = run.peek();
    if (!r) return;
    try { await api.post("/api/code/stop", { run: r.id }); } catch (e) { note.value = { error: e.message }; }
  }

  async function decide(id, allow) {
    try {
      await api.post("/api/code/approve", { id, allow });
    } catch (e) {
      note.value = { error: e.message };
    }
    pollRun();
    refresh();
  }

  async function post(path, body, after) {
    try {
      const got = await api.post(path, body);
      note.value = null;
      await refresh();
      if (after) after(got);
      return got;
    } catch (e) {
      note.value = { error: e.message };
      return null;
    }
  }

  // -- polling, only while the screen is on show

  let runTimer = null;
  let stateTimer = null;
  let shown = false;

  async function pollRun() {
    clearTimeout(runTimer);
    const r = run.peek();
    if (!shown || !r || !LIVE.has(r.state)) return;
    try {
      const have = r.turns?.length || 0;
      const next = await api.get("/api/code/run", { id: r.id, term: termRun === r.id ? termNext : 0, turns: have });
      if (next.turns_from) next.turns = [...(r.turns || []).slice(0, next.turns_from), ...next.turns];
      run.value = next;
      feedTerm(next);
      followWrites(next);
      if (!LIVE.has(next.state)) { refresh(); loadThread(threadId.peek()); loadFiles(); return; }
    } catch (e) {
      if (e.status === 404) { loadThread(threadId.peek()); return; }
    }
    runTimer = setTimeout(pollRun, 300);
  }

  function tickState() {
    clearTimeout(stateTimer);
    if (!shown) return;
    refresh().then(() => {
      const s = st.peek();
      const r = run.peek();
      if (s && r && !LIVE.has(r.state) && s.live?.some((id) => id.startsWith(threadId.peek() || "-"))) loadThread(threadId.peek());
      stateTimer = setTimeout(tickState, 3000);
    });
  }

  // -- parts

  function Mark({ kind }) { return html`<${Glyph} kind=${kind} />`; }

  function Rings({ p }) {
    return html`<span class="rings" title=${`reads ${p.reads.join(", ")} · writes ${p.writes}`}>
      ${REACHES.map((r) => html`<span class=${`cd-ring${p.reads.includes(r) ? " read" : ""}${p.writes === r ? " writes" : ""}`}
        title=${r}><${Glyph} kind="ring" /></span>`)}</span>`;
  }

  // the path strip: question to first word in the first 60%, a break, decode in the last 40%
  function PathStrip({ m, first, total, h = 20, w = 160, readout = true }) {
    const W = w;
    const H = h;
    if (!m) {
      return html`<span class="cd-path"><svg width=${W} height=${H} aria-hidden="true"><rect x="0" y=${H / 2 - 1} width=${W} height="2" fill="var(--ink-3)" /></svg>
        ${readout ? html`<span class="t-readout">memory off · <${Val} v=${fmt.s(first)} /> · <${Val} v=${fmt.s(total)} /></span>` : null}</span>`;
    }
    const sec = m.seconds || {};
    const wait = Math.max(first || 0, 1e-6);
    const pre = W * 0.6;
    const parts = [["choose", "var(--ink-3)"], ["core", "var(--ram-resident)"], ["fetch", m.tier === "ram" ? null : "var(--ssd)"],
      ["wake", "var(--vault)"], ["desk", "var(--ram)"]];
    let x = 0;
    const rects = [];
    for (const [k, color] of parts) {
      const s = sec[k] || 0;
      if (!s) continue;
      const dw = Math.max(1, (s / wait) * pre);
      if (color) rects.push(html`<rect x=${x} y=${H * 0.25} width=${dw} height=${H * 0.5} fill=${color} />`);
      x += dw;
    }
    if (m.tier === "ram") rects.push(html`<rect x=${Math.max(0, x - 1)} y=${H * 0.15} width="2" height=${H * 0.7} fill="var(--ram)" />`);
    rects.push(html`<rect x=${x} y=${H * 0.4} width=${Math.max(0, pre - x)} height=${H * 0.2} fill="var(--ink-2)" />`);
    rects.push(html`<rect x=${pre - 1} y="0" width="1.5" height=${H} fill="var(--ink)" />`);
    rects.push(html`<path d=${`M${pre + 3} ${H * 0.75} L${pre + 7} ${H * 0.25} M${pre + 6} ${H * 0.75} L${pre + 10} ${H * 0.25}`} stroke="var(--ink-3)" stroke-width="1" />`);
    rects.push(html`<rect x=${pre + 12} y=${H / 2 - 0.5} width=${W - pre - 12} height="1" fill="var(--ink-2)" />`);
    const used = (m.used || []).length;
    const picked = (m.nodes || []).length;
    return html`<span class="cd-path"><svg width=${W} height=${H} aria-hidden="true">${rects}</svg>
      ${readout ? html`<span class="t-readout"><span class="used"><${Glyph} kind="dot" /></span> ${used} used
        <span class="picked"><${Glyph} kind="ring" /></span> ${picked} picked ·
        ${m.tier === "ram" ? "RAM hit" : html`<${Val} v=${fmt.bytes(m.read_bytes)} />`} · <${Val} v=${fmt.gbps(m.gbps)} /> ·
        <${Val} v=${fmt.s(first)} /> · <${Val} v=${fmt.s(total)} /></span>` : null}</span>`;
  }

  function MiniStrip({ last }) {
    if (!last) return html`<svg class="strip6" width="200" height="6" aria-hidden="true"><rect x="0" y="2" width="200" height="1" fill="var(--hair-2)" /></svg>`;
    const m = last.memory === false ? null : { seconds: last.seconds || {}, tier: last.tier, used: Array(last.used || 0), nodes: Array(last.picked || 0) };
    return html`<span class="strip6"><${PathStrip} m=${m} first=${last.first_s} total=${last.total_s} h=${6} w=${200} readout=${false} /></span>`;
  }

  function Workspace() {
    const s = st.value;
    const ws = s?.workspace;
    return html`<div class="cd-block">
      <div class="cd-head"><span class="t-label">Workspace</span>
        <button class="btn cd-mini" onClick=${() => { sheet.value = { kind: "workspace" }; }}>${ws ? "change" : "choose"}</button></div>
      ${ws ? html`<div class="t-readout cd-ws" title=${ws.path}>${ws.path.length > 30 ? `…${ws.path.slice(-29)}` : ws.path}</div>
        <div class="cd-note">project reach · ${ws.project}</div>`
        : html`<div class="cd-note">no folder yet · the agent touches only the folder you choose</div>`}
    </div>`;
  }

  function Threads() {
    const s = st.value;
    const list = s?.threads || [];
    return html`<div class="cd-block cd-threads">
      <div class="cd-head"><span class="t-label">Threads</span>
        <button class="btn cd-mini" onClick=${newThread} disabled=${!s}>new</button></div>
      ${list.length ? list.map((x) => html`<button class="cd-thread" aria-current=${x.id === threadId.value ? "true" : "false"}
          onClick=${() => pickThread(x.id)}>
          <span class="tt">${x.title}</span>
          <span class="tm">${x.persona} · ${x.runs} ${x.runs === 1 ? "run" : "runs"}${x.live ? " · running" : ""}</span>
          <${MiniStrip} last=${x.last} />
        </button>`)
        : html`<div class="cd-note">no threads yet · give the agent a task below</div>`}
    </div>`;
  }

  function Files() {
    const s = st.value;
    const list = files.value;
    const shut = folded.value;
    if (!s?.workspace) return html`<div class="cd-block cd-files"><span class="t-label">Files</span></div>`;
    const rows = [];
    const hidden = [];
    for (const f of list) {
      if (hidden.some((h) => f.path.startsWith(`${h}/`))) continue;
      const depth = f.path.split("/").length - 1;
      const name = f.path.split("/").pop();
      if (f.dir) {
        const isShut = shut.has(f.path);
        if (isShut) hidden.push(f.path);
        rows.push(html`<button class="cd-file" style=${{ paddingLeft: `${8 + depth * 12}px` }} onClick=${() => {
          const next = new Set(shut);
          if (isShut) next.delete(f.path); else next.add(f.path);
          folded.value = next;
          save("camr_engine.code.folded", [...next]);
        }}><${Icon} name=${isShut ? "folder" : "folder-open"} />${name}</button>`);
      } else {
        rows.push(html`<button class=${f.secret ? "cd-file secret" : "cd-file"} disabled=${f.secret}
          title=${f.secret ? "looks like a file of secrets: not opened here" : f.path}
          aria-current=${active.value === f.path ? "true" : "false"} style=${{ paddingLeft: `${8 + depth * 12}px` }}
          onClick=${() => openFile(f.path)}><${Icon} name="file-code" />${name}</button>`);
      }
    }
    return html`<div class="cd-block cd-files">
      <div class="cd-head"><span class="t-label">Files</span>
        <button class="btn cd-mini" onClick=${loadFiles}>reload</button></div>
      ${rows.length ? rows : html`<div class="cd-note">the folder is empty</div>`}
    </div>`;
  }

  function Tabs() {
    return html`<div class="cd-tabs" role="tablist">
      ${tabs.value.map((x) => html`<span class="cd-tab" aria-current=${x.path === active.value ? "true" : "false"}>
          <button class="nm" role="tab" aria-selected=${x.path === active.value ? "true" : "false"} title=${x.path}
            onClick=${() => switchTab(x.path)}>${x.dirty ? html`<span class="dirty" title="not saved"></span>` : null}${x.path.split("/").pop()}</button>
          <button class="x" aria-label=${`close ${x.path}`} onClick=${() => closeTab(x.path)}><${Icon} name="x" /></button></span>`)}
      <div class="cd-tabbar-end">
        ${note.value ? html`<span class=${note.value.error ? "cd-error" : "cd-note"}>${note.value.error ? html`<${Glyph} kind="cross" /> ${note.value.error}` : note.value.text}</span>` : null}
        <button class="btn cd-mini" onClick=${saveTab} disabled=${!active.value}>save</button>
      </div>
    </div>`;
  }

  function EditorPane() {
    const ref = useRef(null);
    useEffect(() => { ref.current.appendChild(editorBox); }, []);
    return html`<div class="cd-editor">
      <div ref=${ref} style=${{ height: "100%", display: active.value ? "block" : "none" }}></div>
      ${!active.value ? html`<${Empty} fill=${true}>${st.value?.workspace ? "open a file on the left · lines the agent wrote leaning on memory get a green bar in the gutter" : "choose a workspace on the left to open its files"}<//>` : null}
    </div>`;
  }

  function trackName(tr) {
    if (tr.startsWith("mcp__")) return tr.split("__")[1].slice(0, 8);
    return { read_file: "read", list_files: "list", write_file: "write", edit_file: "edit", load_skill: "skill" }[tr] || tr.slice(0, 8);
  }

  // the run trace: one track for the model, one per tool, one for the shell; memory ticks inside model spans
  function Trace({ r }) {
    const ref = useRef(null);
    const [w, setW] = useState(600);
    useEffect(() => {
      const ro = new ResizeObserver(([e]) => setW(Math.max(200, Math.floor(e.contentRect.width))));
      ro.observe(ref.current);
      return () => ro.disconnect();
    }, []);
    const spans = r?.trace || [];
    const tracks = ["model", ...[...new Set(spans.map((s) => s.track))].filter((x) => x !== "model" && x !== "shell")];
    if (spans.some((s) => s.track === "shell")) tracks.push("shell");
    const H = 120;
    const G = 72;
    const rowH = Math.min(22, (H - 18) / Math.max(tracks.length, 1));
    const end = Math.max(r ? (r.ended ? r.elapsed_s : (Date.now() / 1000 - r.started)) : 1, ...spans.map((s) => s.t1), 1);
    const sx = (v) => G + ((w - G - 8) * v) / end;
    const color = { ssd: "var(--ssd)", ram: "var(--ram)", used: "var(--used)", vault: "var(--vault)", words: "var(--vault)" };
    return html`<div class="cd-trace" ref=${ref}>
      ${!r ? html`<svg width=${w} height=${H}><text x="12" y="64" fill="var(--ink-3)" class="t-label">run trace · model, tools and shell on one clock</text></svg>` : html`
      <svg width=${w} height=${H} aria-label="run trace">
        ${tracks.map((tr, i) => html`<g transform=${`translate(0 ${4 + i * rowH})`}>
          <text x="8" y=${rowH * 0.7} fill="var(--ink-3)" style=${{ font: "500 10px var(--f-mono)", letterSpacing: ".06em", textTransform: "uppercase" }}>${trackName(tr)}</text>
          <line x1=${G} x2=${w - 8} y1=${rowH - 1} y2=${rowH - 1} stroke="var(--hair)" />
          ${spans.filter((s) => s.track === tr).map((s) => {
            // a call you denied (or that timed out or was stopped) is your choice, in grey with its word;
            // a call that failed is grey too, with a red × at its end
            const refused = s.decision && s.decision !== "allowed";
            const failed = s.ok === false && !refused;
            return html`<g>
            <rect x=${sx(s.t0)} y=${rowH * 0.3} width=${Math.max(1.5, sx(s.t1) - sx(s.t0))} height=${rowH * 0.4}
              fill=${refused ? "var(--ink-4)" : "var(--ink-2)"} opacity=${tr === "model" ? 0.55 : 0.9}><title>${s.label} · ${fmt.text(fmt.ms((s.t1 - s.t0) * 1000))}${s.waited ? ` · ${s.decision || "waited for you"}` : ""}${failed ? " · failed" : ""}</title></rect>
            ${failed ? html`<text x=${sx(s.t1) + 2} y=${rowH * 0.78} fill="var(--fault)" style=${{ font: "600 10px var(--f-mono)" }}>×</text>` : null}
            ${(s.ticks || []).map((k) => html`<rect x=${sx(k.t) - 0.5} y=${k.kind === "used" ? rowH * 0.05 : rowH * 0.15} width="1.5"
              height=${k.kind === "used" ? rowH * 0.25 : rowH * 0.7} fill=${color[k.kind] || "var(--ink-2)"} />`)}
          </g>`;
          })}
        </g>`)}
        <text x=${w - 8} y=${H - 4} text-anchor="end" fill="var(--ink-3)" style=${{ font: "400 10px var(--f-mono)" }}>${fmt.text(fmt.s(end))}</text>
      </svg>`}
    </div>`;
  }

  function Diff({ before, after }) {
    const ref = useRef(null);
    useEffect(() => {
      const v = new cm.EditorView({
        parent: ref.current,
        state: cm.EditorState.create({ doc: after || "", extensions: [cm.minimalSetup, theme, greys,
          cm.EditorView.editable.of(false), cm.EditorState.readOnly.of(true),
          cm.unifiedMergeView({ original: before || "", mergeControls: false, gutter: true })] }),
      });
      return () => v.destroy();
    }, [before, after]);
    return html`<div class="cd-diff" ref=${ref}></div>`;
  }

  function Receipt({ turn, i }) {
    const open = unfolded.value.has(i);
    const arg = turn.args ? Object.entries(turn.args).map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join("  ") : "";
    const asked = turn.ask;
    const refused = asked && asked.decision !== "allowed"; // your choice, not a fault: its word in grey, no red ×
    return html`<div class="cd-turn">
      <button class="cd-receipt" aria-expanded=${open ? "true" : "false"} onClick=${() => {
        const next = new Set(unfolded.value);
        if (open) next.delete(i); else next.add(i);
        unfolded.value = next;
      }}>
        <${Icon} name=${open ? "chevron-down" : "chevron-right"} />
        ${turn.ok === false && !refused ? html`<span class="fault-text"><${Glyph} kind="cross" /></span>` : null}
        <span>${turn.tool}</span><span class="arg">${arg}</span>
        ${asked ? html`<span class="ms">${asked.decision}</span>` : null}
        <span class="ms"><${Val} v=${fmt.ms(turn.ms)} /></span>
      </button>
      ${open ? (turn.diff ? html`<${Diff} before=${turn.diff.before} after=${turn.diff.after} />`
        : html`<pre class="cd-out">${turn.output || turn.text}</pre>`) : null}
    </div>`;
  }

  function Turn({ turn, i }) {
    if (turn.kind === "you") return html`<div class="cd-turn cd-you">${turn.text}</div>`;
    if (turn.kind === "model") {
      return html`<div class="cd-turn">
        ${turn.text && turn.calls?.length ? html`<div class="cd-words">${turn.text}</div>` : null}
        <${PathStrip} m=${turn.memory} first=${turn.first_s} total=${turn.total_s} />
      </div>`;
    }
    if (turn.kind === "call") return html`<${Receipt} turn=${turn} i=${i} />`;
    if (turn.kind === "answer") return html`<div class="cd-turn cd-answer">${turn.text}</div>`;
    if (turn.kind === "kept") return html`<div class="cd-turn t-readout cd-kept">kept in ${turn.reach} · moment ${turn.moment} · room ${turn.room}</div>`;
    if (turn.kind === "error") return html`<div class="cd-turn cd-error"><${Glyph} kind="cross" /> ${turn.text}</div>`;
    if (turn.kind === "stopped") return html`<div class="cd-turn cd-note">stopped</div>`;
    return null;
  }

  function Transcript() {
    const r = run.value;
    const ref = useRef(null);
    const n = r?.turns?.length || 0;
    useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [n, r?.id]);
    if (!r) {
      return html`<div class="cd-transcript" ref=${ref}><div class="cd-note">${threadId.value ? "no runs in this thread yet" : "no thread yet"} · each tool call shows here as a one-line receipt that unfolds to its output</div></div>`;
    }
    return html`<div class="cd-transcript" ref=${ref} aria-live="polite">
      ${r.turns.map((turn, i) => html`<${Turn} turn=${turn} i=${i} key=${i} />`)}
      ${LIVE.has(r.state) ? html`<div class="cd-note">${r.state === "waiting" ? "waiting for you" : r.state === "measuring" ? "a benchmark is measuring · waiting" : r.state === "keeping" ? "keeping it in memory" : r.state} · step ${r.steps} of ${r.max_steps} · <${Val} v=${fmt.tok(r.tokens.written)} /> written</div>` : null}
    </div>`;
  }

  // one ask: exactly what will run, counted, with "allow once" asleep until the card has been seen whole
  function AskCard({ a }) {
    const ref = useRef(null);
    const [awake, setAwake] = useState(false);
    const [seen, setSeen] = useState(false);
    const body = askText(a);
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
    return html`<div class="cd-ask" role="alertdialog" aria-label="allow this call?">
      <div class="row"><span class="t-label">${a.kind === "shell" ? "Shell · runs as you" : `MCP · ${a.what.server} · ${a.what.tool}`}</span>
        <span class="t-readout who">${a.label}</span></div>
      <pre ref=${ref} onScroll=${check}>${visible(body)}</pre>
      <div class="cd-note">${lines} ${lines === 1 ? "line" : "lines"} · ${fmt.int(body.length)} characters${marks ? html` · <span class="fault-text"><${Glyph} kind="cross" /> ${marks} invisible ${marks === 1 ? "character" : "characters"}, shown as ⟨U+…⟩</span>` : ""}${seen ? "" : " · scroll to the end to allow"}</div>
      ${a.kind === "shell" ? html`<div class="cd-note" title=${a.what.cwd}>in the workspace (${a.what.cwd.split("/").pop()}) · stops after ${a.what.timeout_s}${fmt.THIN}s</div>` : null}
      <div class="row" style=${{ marginTop: "8px" }}>
        <button class="btn" disabled=${!awake || !seen} onClick=${() => decide(a.id, true)}>allow once</button>
        <button class="btn" onClick=${() => decide(a.id, false)}>deny</button>
        <span class="cd-note">nothing runs until you choose</span>
      </div></div>`;
  }

  function Asks() {
    const waiting = (st.value?.waiting || []).concat(run.value?.waiting || []);
    const seen = new Set();
    const list = waiting.filter((a) => !seen.has(a.id) && seen.add(a.id) && !(a.owner || "").startsWith("swarm-"));
    if (!list.length) return null;
    return html`${list.map((a) => html`<${AskCard} a=${a} key=${a.id} />`)}`;
  }

  function Composer() {
    const s = st.value;
    const why = s?.can_run;
    const r = run.value;
    const p = persona.value;
    return html`<div>
      <div class="cd-composer">
        <span class="prompt">›</span>
        <textarea rows="1" id="code-task" aria-label="task for the agent" placeholder=${why ? why : "a task for the agent · Enter runs, Shift+Enter is a new line"}
          value=${task.value} onInput=${(e) => { task.value = e.target.value; e.target.style.height = "auto"; e.target.style.height = `${Math.min(120, e.target.scrollHeight)}px`; }}
          onKeyDown=${(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); startRun(); } }}></textarea>
        ${live.value ? html`<button class="btn" onClick=${stopRun}><${Icon} name="pause" />stop</button>`
          : html`<button class="btn" onClick=${startRun} disabled=${!!why || busy.value || !task.value.trim()}><${Icon} name="play" />run</button>`}
        <span class="why t-readout">${s ? html`${s.memory ? "memory on" : "memory off"} · ${p ? p.name.toLowerCase() : "—"}${p && s.memory ? ` · reads ${p.reads.join(" ")} · writes ${p.writes}` : ""}${r ? html` · <${Val} v=${fmt.tok(r.tokens.prompt)} /> read · <${Val} v=${fmt.tok(r.tokens.written)} /> written` : ""}` : "—"}</span>
      </div>
    </div>`;
  }

  function TermPane() {
    const ref = useRef(null);
    useEffect(() => { ref.current.appendChild(termBox); try { fit?.fit(); } catch { /* hidden */ } }, []);
    return html`<div class="cd-termbox">
      <div class="cd-termhead"><span class="t-label">Terminal · read-only</span><span class="cd-note">commands you allowed</span></div>
      <div class="cd-term" ref=${ref}></div>
    </div>`;
  }

  function Module({ type, name, status, off = false, pressed, onClick, children, title }) {
    const mark = status === "active" ? html`<span class="cd-active" title="used this session"><${Glyph} kind="dot" /></span>`
      : status === "fault" ? html`<span class="fault-text" title="failing"><${Glyph} kind="cross" /></span>`
      : html`<span class="cd-idle" title="idle"><${Glyph} kind="ring" /></span>`;
    const body = html`<span class="t-label ty">${type}</span><span class="nm">${name}</span><span class="mk">${children}${mark}</span>`;
    return onClick ? html`<button class=${off ? "cd-module off" : "cd-module"} aria-pressed=${pressed ? "true" : "false"} onClick=${onClick} title=${title}>${body}</button>`
      : html`<div class=${off ? "cd-module off" : "cd-module"} title=${title}>${body}</div>`;
  }

  function Rack() {
    const s = st.value;
    if (!s) return html`<div class="cd-block"><span class="cd-note">${stErr.value ? html`<span class="cd-error"><${Glyph} kind="cross" /> ${stErr.value}</span>` : "—"}</span></div>`;
    const p = persona.value;
    const used = new Set(s.used_tools || []);
    return html`
      <div class="cd-block">
        <div class="cd-head"><span class="t-label">Model</span>
          <span class="cd-pill" role="group" aria-label="memory">
            <button aria-pressed=${s.memory ? "true" : "false"} onClick=${() => post("/api/code/settings", { memory: true })}>memory on</button>
            <button aria-pressed=${!s.memory ? "true" : "false"} onClick=${() => post("/api/code/settings", { memory: false })}>off</button>
          </span></div>
        <div class="t-readout" style=${{ color: "var(--ink)" }}>${s.model ? s.model.split("/").pop() : "no model loaded"}</div>
        <div class="cd-note">${s.memory ? "the engine lays the room the task is about on the desk before every step" : "the plain model: nothing read, nothing kept"}</div>
      </div>
      <div class="cd-block">
        <div class="cd-head"><span class="t-label">Personas</span>
          <button class="btn cd-mini" onClick=${() => { sheet.value = { kind: "persona", p: null }; }}>new</button></div>
        ${s.personas.map((x) => html`<div class="cd-row">
          <${Module} type="persona" name=${x.name} status=${x.id === s.persona ? "active" : "idle"}
            pressed=${x.id === s.persona} title=${x.system} onClick=${() => post("/api/code/settings", { persona: x.id })}>
            <${Rings} p=${x} /><//>
          <button class="btn cd-mini" aria-label=${`edit ${x.name}`} onClick=${() => { sheet.value = { kind: "persona", p: x }; }}>edit</button></div>`)}
      </div>
      <div class="cd-block">
        <div class="cd-head"><span class="t-label">Tools</span></div>
        ${TOOLS.map((n) => html`<${Module} type=${ASKS.includes(n) ? "tool · asks you" : "tool"} name=${n}
          status=${used.has(n) ? "active" : "idle"} off=${p ? !(p.tools == null || p.tools.includes(n)) : false}
          title=${n === "run_shell" ? "runs in the workspace only after you allow each command" : "confined to the workspace"} />`)}
      </div>
      <div class="cd-block">
        <div class="cd-head"><span class="t-label">MCP servers</span>
          <button class="btn cd-mini" onClick=${() => { sheet.value = { kind: "mcp" }; }}>add</button></div>
        ${s.servers.length ? s.servers.map((x) => html`<${Module} type=${`mcp · ${x.tools.length} tools · asks you`} name=${x.name}
            status=${x.state === "failed" ? "fault" : x.state === "connected" ? "active" : "idle"}
            title=${x.error || [x.command, ...x.args].join(" ")} onClick=${() => { sheet.value = { kind: "server", name: x.name }; }}>
            <span class="t-readout cd-note">${x.state}</span><//>`)
          : html`<div class="cd-note">none added · a server's tools wait for you on every call</div>`}
      </div>
      <div class="cd-block">
        <div class="cd-head"><span class="t-label">Skills</span>
          <button class="btn cd-mini" onClick=${() => { sheet.value = { kind: "skills" }; }}>folder</button></div>
        ${s.skills.length ? s.skills.map((x) => html`<${Module} type="skill" name=${x.name} title=${x.description}
            status=${used.has("load_skill") ? "active" : "idle"} onClick=${() => openSkill(x.name)} />`)
          : html`<div class="cd-note">none in ${s.skills_dir} · a skill is a Markdown file the model reads when it needs it</div>`}
      </div>`;
  }

  let md = null;
  async function openSkill(name) {
    try {
      if (!md) { const M = (await import("/static/vendor/markdown.js")).default; md = new M({ html: false, linkify: false }); }
      const got = await api.get("/api/code/skill", { name });
      sheet.value = { kind: "skill", name, html: md.render(got.text) };
    } catch (e) {
      note.value = { error: e.message };
    }
  }

  function Sheet() {
    const sh = sheet.value;
    const s = st.value;
    if (!sh || !s) return null;
    const close = () => { sheet.value = null; };
    let title = "";
    let body = null;
    if (sh.kind === "workspace") {
      title = "Workspace";
      body = html`<${WorkspaceForm} close=${close} />`;
    } else if (sh.kind === "persona") {
      title = sh.p ? `Persona · ${sh.p.name}` : "New persona";
      body = html`<${PersonaForm} p=${sh.p} close=${close} />`;
    } else if (sh.kind === "mcp") {
      title = "Add an MCP server";
      body = html`<${McpForm} close=${close} />`;
    } else if (sh.kind === "server") {
      const x = s.servers.find((y) => y.name === sh.name);
      title = `MCP · ${sh.name}`;
      body = x ? html`<${ServerView} x=${x} close=${close} />` : html`<div class="cd-note">removed</div>`;
    } else if (sh.kind === "skills") {
      title = "Skills folder";
      body = html`<${SkillsForm} close=${close} />`;
    } else if (sh.kind === "skill") {
      title = `Skill · ${sh.name}`;
      body = html`<div class="md" dangerouslySetInnerHTML=${{ __html: sh.html }}></div>`;
    }
    return html`<aside class=${sh.kind === "skill" ? "cd-sheet wide" : "cd-sheet"} aria-label=${title}>
      <div class="top"><span class="t-head" style=${{ fontSize: "17px" }}>${title}</span>
        <button class="btn cd-mini" onClick=${close} aria-label="close"><${Icon} name="x" /></button></div>
      <div class="body">${body}</div>
    </aside>`;
  }

  function WorkspaceForm({ close }) {
    const s = st.value;
    const [path, setPath] = useState(s.workspace?.path || "");
    const choose = (p) => post("/api/code/workspace", { path: p }, () => { close(); loadFiles(); tabs.value = []; states.clear(); active.value = null; });
    return html`
      <label><span class="t-label">Folder, by its full path</span>
        <input class="field" value=${path} onInput=${(e) => setPath(e.target.value)} placeholder="~/Desktop/project"
          onKeyDown=${(e) => { if (e.key === "Enter") choose(path); }} /></label>
      <div class="row"><button class="btn" onClick=${() => choose(path)}>use this folder</button></div>
      <div class="cd-note">The agent reads, writes and searches only inside it. It never touches .git, files that look like keys, or anything outside, and every shell command waits for you.</div>
      ${s.recent.length ? html`<span class="t-label">Recent</span>${s.recent.map((r) => html`<button class="cd-recent" title=${r} onClick=${() => choose(r)}>${r.length > 44 ? `…${r.slice(-43)}` : r}</button>`)}` : null}
      ${note.value?.error ? html`<div class="cd-error"><${Glyph} kind="cross" /> ${note.value.error}</div>` : null}`;
  }

  function PersonaForm({ p, close }) {
    const [f, setF] = useState(p ? { ...p, tools: p.tools } : { id: "", name: "", system: "", reads: ["session", "project", "global"], writes: "project", tools: null });
    const set = (k, v) => setF({ ...f, [k]: v });
    const toggleRead = (r) => set("reads", f.reads.includes(r) ? f.reads.filter((x) => x !== r) : [...f.reads, r]);
    const allTools = f.tools == null;
    return html`
      <label><span class="t-label">Id</span><input class="field" value=${f.id} disabled=${!!p} onInput=${(e) => set("id", e.target.value)} placeholder="lowercase-and-dashes" /></label>
      <label><span class="t-label">Name</span><input class="field" value=${f.name} onInput=${(e) => set("name", e.target.value)} /></label>
      <label><span class="t-label">System prompt</span><textarea class="field" value=${f.system} onInput=${(e) => set("system", e.target.value)}></textarea></label>
      <span class="t-label">Reads (click) · writes (the underlined one)</span>
      <div class="cd-check">${REACHES.map((r) => html`<label><input type="checkbox" checked=${f.reads.includes(r)} onChange=${() => toggleRead(r)} />${r}
        <input type="radio" name="writes" checked=${f.writes === r} onChange=${() => setF({ ...f, writes: r, reads: f.reads.includes(r) ? f.reads : [...f.reads, r] })} aria-label=${`writes ${r}`} /></label>`)}</div>
      <span class="t-label">Tools</span>
      <div class="cd-check"><label><input type="checkbox" checked=${allTools} onChange=${() => set("tools", allTools ? ["read_file", "list_files", "search", "load_skill"] : null)} />every tool</label>
        ${!allTools ? [...TOOLS, "mcp"].map((n) => html`<label><input type="checkbox" checked=${f.tools.includes(n)} onChange=${() => set("tools", f.tools.includes(n) ? f.tools.filter((x) => x !== n) : [...f.tools, n])} />${n}</label>`) : null}</div>
      <div class="row" style=${{ display: "flex", gap: "8px" }}>
        <button class="btn" onClick=${() => post("/api/code/persona", f, close)}>save</button>
        ${p && !p.built_in ? html`<button class="btn" onClick=${() => post("/api/code/persona/delete", { id: p.id }, close)}>delete</button>` : null}
        ${p && p.built_in ? html`<button class="btn" onClick=${() => post("/api/code/persona/delete", { id: p.id }, close)} title="bring back the built-in version">reset</button>` : null}
      </div>
      ${note.value?.error ? html`<div class="cd-error"><${Glyph} kind="cross" /> ${note.value.error}</div>` : null}`;
  }

  function McpForm({ close }) {
    const [name, setName] = useState("");
    const [command, setCommand] = useState("");
    const [env, setEnv] = useState("");
    const add = () => {
      const vars = {};
      for (const line of env.split("\n")) {
        const at = line.indexOf("=");
        if (at > 0) vars[line.slice(0, at).trim()] = line.slice(at + 1).trim();
      }
      post("/api/code/mcp/add", { name, command, env: vars }, close);
    };
    return html`
      <label><span class="t-label">Name</span><input class="field" value=${name} onInput=${(e) => setName(e.target.value)} placeholder="files" /></label>
      <label><span class="t-label">Command that starts it (stdio)</span><input class="field" value=${command} onInput=${(e) => setCommand(e.target.value)} placeholder="npx -y some-mcp-server ." /></label>
      <label><span class="t-label">Environment, one NAME=value a line</span><textarea class="field" style=${{ height: "80px" }} value=${env} onInput=${(e) => setEnv(e.target.value)}></textarea></label>
      <div class="cd-note">Kept in this Mac's camr folder, readable by you only; the page never shows the values again. The server starts only when you press connect, runs in the workspace folder, and each of its tool calls waits for you.</div>
      <div><button class="btn" onClick=${add}>add</button></div>
      ${note.value?.error ? html`<div class="cd-error"><${Glyph} kind="cross" /> ${note.value.error}</div>` : null}`;
  }

  function ServerView({ x, close }) {
    const [going, setGoing] = useState(false);
    const act = async (path) => { setGoing(true); await post(path, { name: x.name }); setGoing(false); };
    return html`
      <div class="t-readout" style=${{ color: "var(--ink)", overflowWrap: "anywhere" }}>${[x.command, ...x.args].join(" ")}</div>
      <div class="cd-note">${x.env.length ? `environment: ${x.env.join(", ")}` : "no environment of its own"}</div>
      <div class="t-readout">${x.state === "failed" ? html`<span class="fault-text"><${Glyph} kind="cross" /> ${x.error}</span>` : x.state} · ${x.calls} calls · ${x.failures} failed</div>
      <div style=${{ display: "flex", gap: "8px" }}>
        ${x.state === "connected" ? html`<button class="btn" disabled=${going} onClick=${() => act("/api/code/mcp/disconnect")}>disconnect</button>`
          : html`<button class="btn" disabled=${going} onClick=${() => act("/api/code/mcp/connect")}>${going ? "connecting…" : "connect"}</button>`}
        <button class="btn" disabled=${going} onClick=${() => post("/api/code/mcp/remove", { name: x.name }, close)}>remove</button>
      </div>
      ${x.tools.length ? html`<span class="t-label">Tools</span>${x.tools.map((tl) => html`<div><div class="t-readout" style=${{ color: "var(--ink)" }}>${tl.name}</div><div class="cd-note">${tl.description}</div></div>`)}` : null}`;
  }

  function SkillsForm({ close }) {
    const s = st.value;
    const [dir, setDir] = useState(s.skills_dir || "");
    return html`
      <label><span class="t-label">Folder of skills, by its full path</span><input class="field" value=${dir} onInput=${(e) => setDir(e.target.value)} /></label>
      <div class="cd-note">Each skill is name.md or name/SKILL.md, with an optional front matter (name, description). The model sees one line per skill and reads one whole only when it asks for it.</div>
      <div><button class="btn" onClick=${() => post("/api/code/settings", { skills: dir }, close)}>use this folder</button></div>`;
  }

  function Pop() {
    const p = pop.value;
    if (!p) return null;
    const s = p.strip; // that step's path strip
    const m = s && s.tier ? { seconds: s.seconds || {}, tier: s.tier, read_bytes: s.read_bytes, gbps: s.gbps,
      used: Array(s.used || 0), nodes: Array(s.picked || 0) } : null;
    return html`<div class="cd-pop" style=${{ left: `${Math.min(p.x, innerWidth - 380)}px`, top: `${Math.min(p.y, innerHeight - 170)}px` }}>
      <div>${p.head}</div><div class="words">${p.words}</div>
      ${s ? html`<div style=${{ marginTop: "6px" }}><${PathStrip} m=${m} first=${s.first_s} total=${s.total_s} /></div>` : null}</div>`;
  }

  function App() {
    return html`<div class="cd">
      <div class="cd-col cd-left"><${Workspace} /><${Threads} /><${Files} /></div>
      <div class="cd-centre">
        <${Tabs} />
        <${EditorPane} />
        <div class="cd-bottom">
          <div class="cd-work"><${Trace} r=${run.value} /><${Transcript} /><${Asks} /><${Composer} /></div>
          <${TermPane} />
        </div>
      </div>
      <div class="cd-col cd-rack"><${Rack} /><${Sheet} /></div>
      <${Pop} />
    </div>`;
  }

  render(html`<${App} />`, el);
  await makeTerm();
  await refresh();
  await loadFiles();
  const saved = load(TABS_KEY, { open: [], active: null });
  for (const p of saved.open || []) await openFile(p);
  if (saved.active && states.has(saved.active)) switchTab(saved.active);
  if (threadId.peek()) await loadThread(threadId.peek());

  const off = [api.on("focus", () => document.getElementById("code-task")?.focus()),
    api.on("escape", () => { sheet.value = null; pop.value = null; })];

  return {
    show() {
      shown = true;
      tickState();
      pollRun();
      try { fit?.fit(); } catch { /* hidden */ }
    },
    hide() {
      shown = false;
      clearTimeout(runTimer);
      clearTimeout(stateTimer);
      pop.value = null;
    },
    key(e, { typing }) {
      if (typing) return false;
      if (e.key === "Escape" && sheet.peek()) { sheet.value = null; return true; }
      return false;
    },
    destroy() { off.forEach((f) => f()); },
  };
}
