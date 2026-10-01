// CAMR Personal front end: plain JavaScript, no build step, works offline.
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const app = $("#app"), thread = $("#thread"), input = $("#input");
const S = { state: null, chats: [], current: null, streaming: null, rememberMode: false, lastSources: null };
const KIND = { note: "note", file: "file", chat: "said in chat", learned: "approved answer" };

// ---------- utilities ----------
const store = {
  get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts,
    body: opts.body && typeof opts.body !== "string" ? JSON.stringify(opts.body) : opts.body });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.add("hidden"), 2600);
}
// Tiny, safe Markdown: escape first, then code fences, inline code, bold, italics, links, lists.
function md(src) {
  const blocks = []; let s = esc(src);
  s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, l, c) => { blocks.push(`<pre><code>${c.replace(/\n$/, "")}</code></pre>`); return `\u0000${blocks.length - 1}\u0000`; });
  s = s.replace(/`([^`\n]+)`/g, "<code>$1</code>")
       .replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>")
       .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>")
       .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  const out = []; let list = null;
  for (const line of s.split("\n")) {
    const m = line.match(/^\s*(?:[-*•]|(\d+)\.)\s+(.*)$/);
    if (m) { const tag = m[1] ? "ol" : "ul"; if (!list || list.tag !== tag) { if (list) out.push(`</${list.tag}>`); list = { tag }; out.push(`<${tag}>`); } out.push(`<li>${m[2]}</li>`); continue; }
    if (list) { out.push(`</${list.tag}>`); list = null; }
    out.push(line.trim() ? `<p>${line}</p>` : "");
  }
  if (list) out.push(`</${list.tag}>`);
  return out.join("").replace(/<p>\u0000(\d+)\u0000<\/p>|\u0000(\d+)\u0000/g, (_, a, b) => blocks[a ?? b]);
}
function ago(iso) {
  const d = new Date(iso), now = new Date(), day = 864e5;
  const diff = (new Date(now.toDateString()) - new Date(d.toDateString())) / day;
  return diff <= 0 ? "Today" : diff === 1 ? "Yesterday" : diff < 7 ? "Previous 7 days" : diff < 30 ? "Previous 30 days" : "Older";
}

// ---------- theme ----------
function setTheme(t) { document.documentElement.dataset.theme = t; store.set("camr-theme", t); }
setTheme(store.get("camr-theme", matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));
$("#theme-btn").onclick = () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

// ---------- state & setup ----------
async function refresh() {
  S.state = await api("/api/state");
  const st = S.state;
  if (!st.ready) return renderSetup(st);
  $("#setup").classList.add("hidden");
  $("#composer").classList.remove("hidden");
  renderStats(st.stats);
  renderModels(st);
}
function renderSetup(st) {
  $("#setup").classList.remove("hidden"); $("#composer").classList.add("hidden"); $("#hero").classList.add("hidden");
  thread.innerHTML = "";
  const pull = st.pull || {};
  const embedOk = st.ollama && pull.status !== "pulling" && st.ready;
  const pct = pull.total ? Math.round(100 * pull.completed / pull.total) : 0;
  $("#setup").innerHTML = `
    <div class="hero-ring"></div>
    <h1>Bring a model. CAMR brings the memory.</h1>
    <p class="muted">Three quick steps, all on your computer.</p>
    <div class="step ${st.ollama ? "ok" : "todo"}"><div class="st">${st.ollama ? "✓" : "1"}</div><div>
      <b>Ollama is ${st.ollama ? "running" : "not running"}</b>
      ${st.ollama ? `<span class="muted">Found at ${esc(st.host)}</span>` : `Install it from <a class="link" href="https://ollama.com/download" target="_blank" rel="noopener">ollama.com/download</a> and open it. This page checks again every few seconds.`}</div></div>
    <div class="step ${st.models.length ? "ok" : "todo"}"><div class="st">${st.models.length ? "✓" : "2"}</div><div>
      <b>A chat model</b> ${st.models.length ? `<span class="muted">${st.models.length} found: ${esc(st.models.map((m) => m.name).join(", "))}</span>`
      : `In a terminal: <code>ollama pull qwen2.5:1.5b</code> <span class="muted">(1 GB; in our benchmarks it beat a cloud model on personal facts once it had memory)</span>`}</div></div>
    <div class="step ${embedOk ? "ok" : "todo"}"><div class="st">${embedOk ? "✓" : "3"}</div><div>
      <b>Memory model</b> <span class="muted">${esc(st.embed_model)}: turns your notes into searchable memory (≈270 MB, once)</span>
      ${pull.status === "pulling" ? `<div class="progress"><i style="width:${pct}%"></i></div><small class="muted">${esc(pull.status)} ${pct}%</small>`
      : pull.status === "error" ? `<div class="muted">Download failed: ${esc(pull.error)}</div>` : ""}
      ${st.ollama && pull.status !== "pulling" ? `<div style="margin-top:8px"><button class="primary" id="pull-btn">Download memory model</button></div>` : ""}
    </div></div>`;
  const b = $("#pull-btn"); if (b) b.onclick = async () => { await api("/api/setup", { method: "POST", body: {} }); poll(); };
  poll();
}
function poll() { clearTimeout(poll.t); poll.t = setTimeout(async () => { await refresh(); if (S.state.ready) boot(); }, 1500); }

function renderModels(st) {
  const cur = st.settings.model;
  $("#model-name").textContent = cur || "choose a model";
  $("#model-menu").innerHTML = st.models.map((m) => `<button type="button" class="${m.name === cur ? "sel" : ""}" data-model="${esc(m.name)}">
      <span>${esc(m.name)}</span><small>${esc(m.parameters)} · ${m.size_gb} GB</small></button>`).join("")
    + `<div class="hint">Add more with <code>ollama pull llama3.2:3b</code>. Measured on a laptop CPU: 1.5–4B models are the sweet spot.</div>`;
  $$("#model-menu [data-model]").forEach((b) => b.onclick = async () => {
    await api("/api/settings", { method: "POST", body: { model: b.dataset.model } });
    $("#model-menu").classList.add("hidden"); await refresh(); toast(`Using ${b.dataset.model}`);
  });
}
$("#model-btn").onclick = (e) => { e.stopPropagation(); $("#model-menu").classList.toggle("hidden"); };
document.addEventListener("click", () => $("#model-menu").classList.add("hidden"));

function renderStats(stats) {
  const n = stats.notes;
  $("#mem-badge").textContent = n.toLocaleString();
  $("#brand-sub").textContent = n ? `${n.toLocaleString()} memories` : "memory that grows";
  // ring fills on a log scale: 10 memories ≈ a quarter, 1,000 ≈ three quarters, 10,000 = full
  const frac = Math.min(1, Math.log10(1 + n) / 4);
  $("#ring-fill").setAttribute("stroke-dasharray", `${(frac * 88).toFixed(1)} 88`);
  if (!$("#panel-growth").classList.contains("hidden")) renderGrowth(stats);
}

// ---------- chats ----------
async function loadChats() {
  S.chats = await api("/api/conversations");
  const q = $("#chat-search").value.toLowerCase();
  const groups = {};
  for (const c of S.chats.filter((c) => c.title.toLowerCase().includes(q))) (groups[ago(c.updated_at)] ||= []).push(c);
  $("#chats").innerHTML = Object.entries(groups).map(([g, cs]) => `<div class="chat-group">${g}</div>` + cs.map((c) =>
    `<div class="chat-item ${c.id === S.current ? "active" : ""}" data-id="${c.id}"><span>${esc(c.title)}</span><button class="del" data-del="${c.id}" title="Delete chat">✕</button></div>`).join("")).join("")
    || `<div class="muted small" style="padding:10px">No chats yet.</div>`;
  $$("#chats .chat-item").forEach((el) => el.onclick = (e) => { if (!e.target.dataset.del) openChat(+el.dataset.id); });
  $$("#chats [data-del]").forEach((b) => b.onclick = async () => {
    if (!confirm("Delete this chat? What CAMR learned from it stays in memory.")) return;
    await api(`/api/conversations/${b.dataset.del}`, { method: "DELETE" });
    if (S.current === +b.dataset.del) newChat(); else loadChats();
  });
}
$("#chat-search").oninput = loadChats;

function newChat() {
  S.current = null; thread.innerHTML = ""; $("#chat-title").textContent = "";
  app.classList.add("empty"); $("#hero").classList.remove("hidden");
  const n = S.state?.stats?.notes || 0;
  $("#hero-title").textContent = n ? "What do you want to know?" : "What should I remember?";
  $("#hero-sub").textContent = n ? `${n.toLocaleString()} memories ready. Your model stays the same; what it knows grows with you.`
    : "Teach me notes and files, or say “remember that…”. Your model stays the same; what it knows grows with you.";
  loadChats(); input.focus(); closeMobile();
}
async function openChat(id) {
  S.current = id; app.classList.remove("empty"); $("#hero").classList.add("hidden");
  const turns = await api(`/api/conversations/${id}`);
  $("#chat-title").textContent = S.chats.find((c) => c.id === id)?.title || "";
  thread.innerHTML = "";
  for (const t of turns) { addUser(t.question); const el = addAssistant(); renderRecall(el, t.sources, t.abstained, t.retrieval_ms); finish(el, t); }
  thread.scrollTop = thread.scrollHeight; loadChats(); closeMobile();
}
$("#new-chat").onclick = newChat;

// title rename (click to edit, Enter to save)
$("#chat-title").ondblclick = () => { if (!S.current) return; const t = $("#chat-title"); t.contentEditable = "true"; t.focus(); };
$("#chat-title").onkeydown = async (e) => { if (e.key === "Enter") { e.preventDefault(); e.target.blur(); } };
$("#chat-title").onblur = async (e) => {
  if (e.target.contentEditable !== "true") return; e.target.contentEditable = "false";
  await api(`/api/conversations/${S.current}`, { method: "PATCH", body: { title: e.target.textContent } }); loadChats();
};

// ---------- messages ----------
function addUser(text) {
  const d = document.createElement("div"); d.className = "msg user"; d.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  thread.appendChild(d); return d;
}
function addAssistant() {
  const d = document.createElement("div"); d.className = "msg assistant";
  d.innerHTML = `<div class="avatar" aria-hidden="true"></div><div class="body">
    <details class="recall thinking"><summary><span>✦</span> <b>Searching your memory…</b><span class="chev">▾</span></summary></details>
    <div class="answer cursor"></div><div class="actions"></div></div>`;
  thread.appendChild(d); return d;
}
function memCard(s) {
  return `<div class="mem-card"><div class="meta"><span class="kind ${s.kind}">${KIND[s.kind] || s.kind}</span>${s.title ? `<span>${esc(s.title)}</span>` : ""}
    ${s.via_bridge ? `<span title="Pulled in because a recalled note names it">↳ linked</span>` : ""}
    <span class="simbar" title="similarity ${s.similarity}"><i style="width:${Math.max(8, Math.round(100 * s.similarity))}%"></i></span></div>
    <div class="txt">${esc(s.text)}</div></div>`;
}
function renderRecall(el, sources, abstained, ms) {
  const r = $(".recall", el); r.classList.remove("thinking");
  if (!sources || !sources.length) {
    r.classList.add("none");
    r.innerHTML = `<summary><span>✦</span> ${abstained ? "No matching memories, so this answer comes from the model alone" : "Saved directly to memory"}</summary>`;
    return;
  }
  r.innerHTML = `<summary><span>✦</span> Recalled <b>${sources.length} ${sources.length === 1 ? "memory" : "memories"}</b>
    <span class="muted">· ${Math.round(ms || 0)} ms</span><span class="chev">▾</span></summary><div class="mem-cards">${sources.map(memCard).join("")}</div>`;
  S.lastSources = sources; renderRecallPanel();
}
function finish(el, t) {
  const a = $(".answer", el); a.classList.remove("cursor"); a.innerHTML = md(t.answer);
  const g = t.grounded;
  const gcol = g == null ? "" : g >= 0.6 ? "var(--good)" : g >= 0.3 ? "#e3b341" : "var(--warn)";
  const stored = t.saved_to_memory && !(t.sources || []).length && !t.abstained;  // a "remember that" turn
  $(".actions", el).innerHTML = (t.turn_id && stored ? `<button class="act copy" title="Copy">⧉ Copy</button>` : t.turn_id ? `
    <button class="act copy" title="Copy">⧉ Copy</button>
    <button class="act up ${t.feedback === 1 ? "on" : ""}" title="Good answer: save it to memory">👍 ${t.feedback === 1 ? "Learned" : "Teach this"}</button>
    <button class="act down ${t.feedback === -1 ? "on" : ""}" title="Not helpful">👎</button>` : "")
    + (g != null ? `<span class="ground" title="Share of the answer's words found in the memories it read"><span class="meter"><i style="width:${Math.round(100 * g)}%;background:${gcol}"></i></span>grounded ${Math.round(100 * g)}%</span>` : "")
    + (t.generation_ms ? `<span class="timing">${Math.round(t.retrieval_ms)} ms memory · ${(t.generation_ms / 1000).toFixed(1)} s answer</span>` : "");
  if (stored) a.insertAdjacentHTML("beforeend", `<div class="saved-note">✦ Stored in memory</div>`);
  const up = $(".up", el), down = $(".down", el), copy = $(".copy", el);
  if (copy) copy.onclick = () => { navigator.clipboard?.writeText(t.answer); toast("Copied"); };
  if (up) up.onclick = async () => { await api("/api/feedback", { method: "POST", body: { turn_id: t.turn_id, helpful: true } });
    up.classList.add("on"); up.textContent = "👍 Learned"; toast("Saved to memory: CAMR will reuse this answer"); refresh(); };
  if (down) down.onclick = async () => { await api("/api/feedback", { method: "POST", body: { turn_id: t.turn_id, helpful: false } });
    down.classList.add("on"); toast("Thanks, noted. Tip: correct it with “remember that …”"); };
}

async function send(text) {
  text = text.trim(); if (!text || S.streaming) return;
  if (S.rememberMode && !/^\s*remember/i.test(text)) text = "remember that " + text;
  input.value = ""; autosize(); app.classList.remove("empty"); $("#hero").classList.add("hidden");
  addUser(text); const el = addAssistant(); thread.scrollTop = thread.scrollHeight;
  const ctrl = new AbortController(); S.streaming = ctrl; setSending(true);
  let answer = "", conv = S.current;
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, signal: ctrl.signal,
      body: JSON.stringify({ message: text, conversation_id: S.current }) });
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let i; while ((i = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, i); buf = buf.slice(i + 2);
        if (!line.startsWith("data: ")) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.type === "recall") { conv = ev.conversation_id; renderRecall(el, ev.sources, ev.abstained, ev.retrieval_ms); }
        else if (ev.type === "token") { answer += ev.text; $(".answer", el).innerHTML = md(answer); $(".answer", el).classList.add("cursor"); thread.scrollTop = thread.scrollHeight; }
        else if (ev.type === "done") finish(el, ev.turn);
        else if (ev.type === "error") throw new Error(ev.error);
      }
    }
  } catch (e) {
    if (e.name !== "AbortError") { $(".answer", el).classList.remove("cursor"); $(".answer", el).innerHTML = `<p class="muted">⚠ ${esc(e.message)}</p>`; }
    else finish(el, { answer: answer + " …", turn_id: null });
  } finally {
    S.streaming = null; setSending(false);
    if (S.current == null && conv != null) { S.current = conv; }
    await loadChats(); $("#chat-title").textContent = S.chats.find((c) => c.id === S.current)?.title || "";
    refresh();
  }
}
function setSending(on) { const b = $("#send"); b.classList.toggle("stop", on); b.textContent = on ? "■" : "↑"; b.setAttribute("aria-label", on ? "Stop" : "Send"); }

// ---------- composer ----------
function autosize() { input.style.height = "auto"; input.style.height = Math.min(220, input.scrollHeight) + "px"; }
input.addEventListener("input", autosize);
input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); } });
$("#composer").onsubmit = (e) => { e.preventDefault(); if (S.streaming) { S.streaming.abort(); return; } send(input.value); };
$("#remember-toggle").onclick = () => {
  S.rememberMode = !S.rememberMode; $("#remember-toggle").classList.toggle("on", S.rememberMode);
  $(".composer-box").classList.toggle("remember", S.rememberMode);
  input.placeholder = S.rememberMode ? "Type a fact to store in memory…" : (matchMedia("(max-width: 600px)").matches ? "Ask, or “remember that …”" : "Ask anything, or start with “remember that …”"); input.focus();
};
$$("#suggestions [data-fill]").forEach((b) => b.onclick = () => { input.value = b.dataset.fill; autosize(); input.focus(); });
$("#suggestions [data-action=teach]").onclick = () => openTeach();
document.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); newChat(); } });

// ---------- teaching ----------
async function teachFiles(files) {
  let total = 0;
  for (const f of files) {
    const buf = new Uint8Array(await f.arrayBuffer()); let bin = "";
    for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    try { total += (await api("/api/teach", { method: "POST", body: { filename: f.name, data_base64: btoa(bin) } })).notes; }
    catch (e) { toast(`${f.name}: ${e.message}`); }
  }
  toast(`✦ Learned ${total} memor${total === 1 ? "y" : "ies"} from ${files.length} file${files.length === 1 ? "" : "s"}`); refresh();
}
$("#file-input").onchange = (e) => { teachFiles([...e.target.files]); e.target.value = ""; };
function openTeach() { $("#teach-dlg").showModal(); $("#teach-text").focus(); }
$("#open-teach").onclick = openTeach;
$("#teach-files").onchange = (e) => { teachFiles([...e.target.files]); e.target.value = ""; $("#teach-dlg").close(); };
$("#teach-save").onclick = async (e) => {
  const text = $("#teach-text").value.trim(); if (!text) return;
  e.preventDefault();
  const r = await api("/api/teach", { method: "POST", body: { text, title: $("#teach-title").value } });
  $("#teach-text").value = ""; $("#teach-title").value = ""; $("#teach-dlg").close();
  toast(r.notes ? `✦ Saved ${r.notes} memor${r.notes === 1 ? "y" : "ies"}` : "Already in memory"); refresh();
};
// drag & drop anywhere
let dragDepth = 0;
addEventListener("dragenter", (e) => { if ([...e.dataTransfer.types].includes("Files")) { dragDepth++; $("#dropping").classList.remove("hidden"); } });
addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#dropping").classList.add("hidden"); } });
addEventListener("dragover", (e) => e.preventDefault());
addEventListener("drop", (e) => { e.preventDefault(); dragDepth = 0; $("#dropping").classList.add("hidden"); if (e.dataTransfer.files.length) teachFiles([...e.dataTransfer.files]); });

// ---------- memory panel ----------
function openPanel(tab) { app.classList.add("panel-open"); if (tab) selectTab(tab); }
$("#panel-btn").onclick = () => app.classList.toggle("panel-open");
$("#close-panel").onclick = () => app.classList.remove("panel-open");
$$("[data-panel=memory]").forEach((b) => b.onclick = () => { openPanel("memory"); closeMobile(); });
$$(".tab").forEach((t) => t.onclick = () => selectTab(t.dataset.tab));
function selectTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  for (const n of ["recall", "memory", "growth"]) $(`#panel-${n}`).classList.toggle("hidden", n !== name);
  if (name === "memory") loadMemory(); if (name === "growth") renderGrowth(S.state.stats);
}
function renderRecallPanel() {
  const s = S.lastSources;
  $("#panel-recall").innerHTML = s?.length ? `<p class="muted small">What the model read for the last answer, best match first.</p>` + s.map(memCard).join("")
    : `<p class="muted">Ask something and the memories it read appear here.</p>`;
}
async function loadMemory() {
  const q = encodeURIComponent($("#mem-search").value), k = $("#mem-kind").value;
  const items = await api(`/api/memory?q=${q}&kind=${k}`);
  $("#mem-list").innerHTML = items.length ? items.map((m) => `<div class="mem-item"><div class="meta"><span class="kind ${m.kind}">${KIND[m.kind] || m.kind}</span>
      ${m.title ? `<b>${esc(m.title)}</b>` : ""}<span>${esc(m.added.slice(0, 10))}</span><button class="forget" data-src="${m.source_id}">Forget</button></div>
      <div>${esc(m.text.slice(0, 280))}${m.text.length > 280 ? "…" : ""}</div></div>`).join("")
    : `<p class="muted">Nothing here yet. Teach a note, drop a file, or say “remember that …”.</p>`;
  $$("#mem-list [data-src]").forEach((b) => b.onclick = async () => { await api(`/api/memory/${b.dataset.src}`, { method: "DELETE" }); toast("Forgotten"); loadMemory(); refresh(); });
}
$("#mem-search").oninput = () => { clearTimeout(loadMemory.t); loadMemory.t = setTimeout(loadMemory, 200); };
$("#mem-kind").onchange = loadMemory;
function renderGrowth(st) {
  const days = st.sources_per_day || []; let acc = 0; const pts = days.map(([d, n]) => [d, (acc += n)]);
  const max = Math.max(1, ...pts.map((p) => p[1])), w = 320, h = 80;
  const path = pts.length > 1 ? pts.map((p, i) => `${i ? "L" : "M"}${(i / (pts.length - 1) * w).toFixed(1)},${(h - p[1] / max * (h - 8) - 4).toFixed(1)}`).join(" ") : "";
  const kinds = Object.entries(st.notes_by_kind || {}), km = Math.max(1, ...kinds.map((k) => k[1]));
  $("#panel-growth").innerHTML = `
    <div class="stat-grid">
      <div class="stat"><div class="k">Memories</div><div class="v">${st.notes.toLocaleString()}</div></div>
      <div class="stat"><div class="k">On disk</div><div class="v">${st.store_mb} MB</div></div>
      <div class="stat"><div class="k">Answered from memory</div><div class="v">${st.answered_with_memory == null ? "–" : Math.round(100 * st.answered_with_memory) + "%"}</div></div>
      <div class="stat"><div class="k">Memory lookup</div><div class="v">${st.median_retrieval_ms == null ? "–" : Math.round(st.median_retrieval_ms) + " ms"}</div></div>
    </div>
    <div class="stat"><div class="k">Growth</div>${path ? `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <defs><linearGradient id="sg" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="var(--accent)" stop-opacity=".35"/><stop offset="1" stop-color="var(--accent)" stop-opacity="0"/></linearGradient></defs>
      <path d="${path} L${w},${h} L0,${h} Z" fill="url(#sg)"/><path d="${path}" fill="none" stroke="var(--accent-2)" stroke-width="2"/></svg>`
      : `<p class="muted small">Day one. Come back tomorrow to see the curve.</p>`}</div>
    <div class="stat"><div class="k" style="margin-bottom:8px">Where its knowledge comes from</div>
      ${kinds.map(([k, v]) => `<div class="kindbar"><span>${KIND[k] || k}</span><span class="bar"><i style="width:${100 * v / km}%"></i></span><span>${v}</span></div>`).join("") || `<p class="muted small">Nothing yet.</p>`}</div>
    <p class="muted small">👍 ${st.helpful} · 👎 ${st.not_helpful} · ${st.turns} questions. The model's weights never change: every gain here is memory.</p>`;
}

// ---------- settings ----------
$("#open-settings").onclick = () => {
  const s = S.state.settings; $("#set-budget").value = s.token_budget; $("#set-turns").value = s.history_turns; $("#set-chat").checked = s.remember_chat;
  $("#budget-val").textContent = s.token_budget + " tokens"; $("#turns-val").textContent = s.history_turns;
  $("#about").textContent = `CAMR Personal ${S.state.version} · memory model ${s.embed_model} · abstains below similarity ${s.min_similarity} · data in ${S.state.home}`;
  $("#settings-dlg").showModal(); closeMobile();
};
$("#set-budget").oninput = (e) => $("#budget-val").textContent = e.target.value + " tokens";
$("#set-turns").oninput = (e) => $("#turns-val").textContent = e.target.value;
$("#export-text").onchange = (e) => $("#export-link").href = "/api/export?text=" + (e.target.checked ? 1 : 0);
$("#settings-save").onclick = async () => {
  await api("/api/settings", { method: "POST", body: { token_budget: +$("#set-budget").value, history_turns: +$("#set-turns").value, remember_chat: $("#set-chat").checked } });
  toast("Settings saved"); refresh();
};

// ---------- sidebar (desktop collapse / mobile drawer) ----------
const mobile = () => matchMedia("(max-width: 900px)").matches;
$("#toggle-side").onclick = () => mobile() ? app.classList.toggle("side-mobile") : app.classList.toggle("side-closed");
$("#close-side").onclick = closeMobile;
function closeMobile() { app.classList.remove("side-mobile"); }

// short placeholder on phones
if (matchMedia("(max-width: 600px)").matches) input.placeholder = "Ask, or “remember that …”";

// ---------- boot ----------
async function boot() { await refresh(); if (!S.state.ready) return; await loadChats(); newChat(); renderRecallPanel(); }
boot().catch((e) => { document.body.insertAdjacentHTML("beforeend", `<div class="toast">${esc(e.message)}</div>`); });
