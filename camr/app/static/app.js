// CAMR Personal front end: plain JavaScript, no build step, works offline.
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const app = $("#app"), thread = $("#thread"), input = $("#input");
const S = { state: null, chats: [], current: null, streaming: null, rememberMode: false, lastSources: null, about: null, viewing: null, sel: null };
const KIND = { note: "note", file: "file", chat: "said in chat", learned: "approved answer", web: "looked up online", pack: "knowledge pack" };
// Answer action icons: 24-px line icons drawn in the text colour (paths adapted from Lucide, ISC licence).
const svg = (d) => `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICON = {
  copy: svg(`<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>`),
  up: svg(`<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/>`),
  down: svg(`<path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/>`),
};
const teachLabel = (learned) => `${ICON.up}<span>${learned ? "Learned" : "Teach this"}</span>`;

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
  renderPill(st.settings);
}
function renderPill(set) {
  const on = set?.learn_online;
  $("#learn-pill").classList.toggle("off", !on);
  $("#learn-pill-text").textContent = on ? "learning on" : "offline";
  $("#learn-pill").title = on ? "Looks up general questions it can't answer from memory, then remembers them" : "Answers from memory and the model only";
}
$("#learn-pill").onclick = () => openPanel("learning");
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
  $("#hero-sub").textContent = n ? `${n.toLocaleString()} memories ready. Ask me anything: what I don't know yet, I look up and remember.`
    : "Teach me notes and files, say “remember that…”, or just ask: what I don't know yet, I look up and remember. Your model stays the same; what it knows grows with you.";
  loadChats(); input.focus(); closeMobile();
}
async function openChat(id) {
  S.current = id; app.classList.remove("empty"); $("#hero").classList.add("hidden");
  const turns = await api(`/api/conversations/${id}`);
  $("#chat-title").textContent = S.chats.find((c) => c.id === id)?.title || "";
  thread.innerHTML = "";
  for (const t of turns) { addUser(t.question); const el = addAssistant();
    if (t.upload) { uploadCard(el, t.upload); continue; }
    if (!(t.sources || []).length && !t.abstained && !t.retrieval_ms) $(".recall", el)?.remove();  // small talk, "remember that"
    else renderRecall(el, t.sources, t.abstained, t.retrieval_ms, t.learned);
    finish(el, t); }
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
function host(u) { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } }
function memCard(s) {
  return `<div class="mem-card"><div class="meta"><span class="kind ${s.kind}">${KIND[s.kind] || s.kind}</span>${s.title ? `<span class="t">${esc(s.title)}</span>` : ""}
    ${s.url ? `<a class="src" href="${esc(s.url)}" target="_blank" rel="noopener" title="${esc(s.url)}">${esc(host(s.url))} ↗</a>` : ""}
    ${s.via_bridge ? `<span title="Pulled in because a recalled note names it">↳ linked</span>` : ""}
    ${s.kind === "file" ? `<button class="src show-in-file" data-note="${s.note_id}" title="Open the file with this memory's lines highlighted">Show in file</button>` : ""}
    <span class="simbar" title="similarity ${s.similarity}"><i style="width:${Math.max(8, Math.round(100 * s.similarity))}%"></i></span></div>
    <div class="txt">${esc(s.text)}</div></div>`;
}
function showLookup(el) {
  const r = $(".recall", el); r.classList.add("thinking", "looking");
  r.innerHTML = `<summary><span>◎</span> <span class="trace"><s>memory had nothing</s> → <b>looking it up online…</b></span></summary>`;
}
function learnedTrace(l) {
  if (!l) return "";
  const pages = (l.pages || []).map((p) => esc(p.title)).join(", ");
  return l.pages?.length ? `<span class="trace"><s>memory had nothing</s> → looked up <b>${pages}</b> → learned <b>${l.notes_added}</b> → </span>`
    : `<span class="trace"><s>memory had nothing</s> → looked online, found nothing → </span>`;
}
const openedLine = (ex) => ex && ex.length ? `<span class="opened" title="Only these experts were opened (and your shared memory); the rest of memory stayed closed">· opened ${ex.map((e) => `<b>${esc(e)}</b>`).join(", ")}</span>` : "";
function renderRecall(el, sources, abstained, ms, learned, experts) {
  const r = $(".recall", el); r.classList.remove("thinking", "looking");
  if (!sources || !sources.length) {
    r.classList.add("none");
    r.innerHTML = `<summary><span>✦</span> ${learned ? learnedTrace(learned) + "answering from the model alone"
      : abstained ? "No matching memories, so this answer comes from the model alone" : "Saved directly to memory"}</summary>`;
    return;
  }
  r.classList.toggle("learned", !!learned?.notes_added);
  r.innerHTML = `<summary><span>${learned?.notes_added ? "◎" : "✦"}</span> ${learnedTrace(learned)}Recalled <b>${sources.length} ${sources.length === 1 ? "memory" : "memories"}</b>
    <span class="muted">· ${Math.round(ms || 0)} ms</span>${openedLine(experts)}<span class="chev">▾</span></summary><div class="mem-cards">${sources.map(memCard).join("")}</div>`;
  S.lastSources = sources; renderRecallPanel();
}
function verifyBadge(v) {
  if (!v) return "";
  if (v.status === "verified") {
    const how = (v.by === "memory" ? "read straight from memory" : v.by === "cross-check" ? "confirmed by the answer's own article"
      : "checked against memory") + (v.revised_from ? ` (corrected from “${v.revised_from}”)` : "");
    return `<span class="verify ok" title="${esc(how + ": " + (v.evidence || ""))}">✓ Verified · ${esc(v.source || "memory")}</span>`;
  }
  if (v.status === "unverified") return `<span class="verify no" title="${esc(v.reason || "")}">! Not confirmed by memory</span>`;
  return `<span class="verify un" title="${esc(v.reason || "")}">○ Not checked</span>`;
}
// The tiers beside the notes: a skill card memory attached, or what the trust link did with the model's answer.
function tierBadge(t) {
  const k = t.skill, l = t.link;
  if (k) return `<span class="verify tier" title="${esc(`Memory named this skill, so its card answered (${k.model})${k.expression ? `; the calculator worked out ${k.expression}` : ""}`)}">◆ Skill card · ${esc(k.skill)}</span>`;
  if (!l || l.action === "keep") return "";
  if (l.action === "escalate") return `<span class="verify tier" title="Your model's answer looked unreliable, so a larger model on this computer read the same notes">⇡ Checked with ${esc(l.by || "a larger model")}</span>`;
  return `<span class="verify un tier" title="The trust link judged this answer likely wrong, so it was held back">◌ Held back a guess</span>`;
}
function draftNote(t) {
  const l = t.link;
  if (!l || !l.draft || l.action === "keep") return "";
  return `<details class="draft"><summary>${l.action === "escalate" ? "Your model's first answer" : "What it would have said"}</summary><div>${md(l.draft)}</div></details>`;
}
// Code blocks: each with its own copy button; while streaming, an unclosed block is shown as code already.
function streamMd(text) { return md((text.match(/```/g) || []).length % 2 ? text + "\n```" : text); }
function codeCopy(root) {
  $$("pre", root).forEach((pre) => {
    if ($(".copy-code", pre)) return;
    const b = document.createElement("button"); b.type = "button"; b.className = "copy-code"; b.textContent = "Copy";
    b.onclick = () => { navigator.clipboard?.writeText($("code", pre)?.textContent || pre.textContent); b.textContent = "Copied"; setTimeout(() => b.textContent = "Copy", 1500); };
    pre.appendChild(b);
  });
}
function finish(el, t) {
  const a = $(".answer", el); a.classList.remove("cursor"); a.innerHTML = md(t.answer); codeCopy(a);
  el.querySelectorAll(".tier-status").forEach((x) => x.remove());  // the badge says what happened
  const g = t.grounded;
  const gcol = g == null ? "" : g >= 0.6 ? "var(--good)" : g >= 0.3 ? "#e3b341" : "var(--warn)";
  const stored = t.saved_to_memory && !(t.sources || []).length && !t.abstained;  // a "remember that" turn
  const copyBtn = `<button class="act copy" title="Copy the answer">${ICON.copy}<span>Copy</span></button>`;
  $(".actions", el).innerHTML = (t.turn_id && stored ? copyBtn : t.turn_id ? `
    ${copyBtn}
    ${t.ask_to_teach ? "" : `<button class="act up ${t.feedback === 1 ? "on" : ""}" title="Good answer: save it to memory">${teachLabel(t.feedback === 1)}</button>`}
    <button class="act down ${t.feedback === -1 ? "on" : ""}" title="Not helpful" aria-label="Not helpful">${ICON.down}</button>` : "")
    + verifyBadge(t.verification) + tierBadge(t)
    + (g != null && !t.verification ? `<span class="ground" title="Share of the answer's words found in the memories it read"><span class="meter"><i style="width:${Math.round(100 * g)}%;background:${gcol}"></i></span>grounded ${Math.round(100 * g)}%</span>` : "")
    + (t.generation_ms ? `<span class="timing">${Math.round(t.retrieval_ms)} ms memory · ${t.first_token_ms ? (t.first_token_ms / 1000).toFixed(1) + " s to first word · " : ""}${(t.generation_ms / 1000).toFixed(1)} s answer</span>` : "");
  if (stored) a.insertAdjacentHTML("beforeend", `<div class="saved-note">✦ Stored in memory</div>`);
  a.insertAdjacentHTML("beforeend", draftNote(t));
  if (t.ask_to_teach) {
    $(".actions", el).insertAdjacentHTML("afterbegin", `<button class="act teach" title="Tell CAMR, and it will remember">✦ Teach me</button>`);
    $(".teach", el).onclick = () => { if (!S.rememberMode) $("#remember-toggle").click(); input.placeholder = "Tell me, e.g. “my passport number is …”"; input.focus(); };
  }
  const up = $(".up", el), down = $(".down", el), copy = $(".copy", el);
  if (copy) copy.onclick = () => { navigator.clipboard?.writeText(t.answer); toast("Copied"); };
  if (up) up.onclick = async () => { await api("/api/feedback", { method: "POST", body: { turn_id: t.turn_id, helpful: true } });
    up.classList.add("on"); up.innerHTML = teachLabel(true); down?.classList.remove("on");
    toast("Saved to memory: CAMR will reuse this answer"); refresh(); };
  if (down) down.onclick = async () => {
    const r = await api("/api/feedback", { method: "POST", body: { turn_id: t.turn_id, helpful: false } });
    down.classList.add("on");
    if (up) { up.classList.remove("on"); up.innerHTML = teachLabel(false); }
    toast(r.forgotten ? "Taken back: this answer is no longer in memory" : "Thanks, noted. Tip: correct it with “remember that …”");
    if (r.forgotten) refresh(); };
}

async function send(text) {
  text = text.trim(); if (!text || S.streaming) return;
  if (S.rememberMode && !S.about && !/^\s*remember/i.test(text)) text = "remember that " + text;
  const about = S.about; clearAbout();
  input.value = ""; autosize(); app.classList.remove("empty"); $("#hero").classList.add("hidden");
  addUser(text); const el = addAssistant(); thread.scrollTop = thread.scrollHeight;
  const ctrl = new AbortController(); S.streaming = ctrl; setSending(true);
  let answer = "", conv = S.current;
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, signal: ctrl.signal,
      body: JSON.stringify({ message: text, conversation_id: S.current, about }) });
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let i; while ((i = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, i); buf = buf.slice(i + 2);
        if (!line.startsWith("data: ")) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.type === "lookup") { conv = ev.conversation_id; showLookup(el); }
        else if (ev.type === "recall") { conv = ev.conversation_id; if (ev.small_talk) $(".recall", el)?.remove(); else renderRecall(el, ev.sources, ev.abstained, ev.retrieval_ms, ev.learned, ev.experts); }
        else if (ev.type === "skill") $(".answer", el).insertAdjacentHTML("beforebegin", `<div class="tier-status">◆ Using the “${esc(ev.skill)}” skill card</div>`);
        else if (ev.type === "escalate") { $(".answer", el).classList.add("cursor"); $(".answer", el).insertAdjacentHTML("beforebegin", `<div class="tier-status">⇡ Not sure of this one: checking with ${esc(ev.by)}…</div>`); }
        else if (ev.type === "token") { answer += ev.text; $(".answer", el).innerHTML = streamMd(answer); $(".answer", el).classList.add("cursor"); thread.scrollTop = thread.scrollHeight; }
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
$("#suggestions [data-action=learning]").onclick = () => openPanel("learning");
document.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); newChat(); } });

// ---------- teaching ----------
// ---------- files: read, learn, interview, highlight ----------
const ACCEPT = ".txt,.md,.csv,.pdf,.docx,.png,.jpg,.jpeg,.heic,.heif,.webp,.gif,.tif,.tiff,.bmp,.py,.ipynb,.js,.mjs,.ts,.tsx,.jsx,.java,.kt,.go,.rs,.c,.h,.cpp,.hpp,.cs,.rb,.php,.swift,.scala,.sql,.sh,.r,.lua,.dart,.vue,.svelte,.html,.css,.scss,.json,.yaml,.yml,.toml,.ini,.cfg";
async function teachFiles(files) {
  if (!files.length) return;
  if (S.current == null) {  // the interview happens in a chat
    S.current = (await api("/api/conversations", { method: "POST", body: {} })).id;
    app.classList.remove("empty"); $("#hero").classList.add("hidden"); thread.innerHTML = "";
  }
  for (const f of files) {
    addUser(`📎 ${f.name}`); const el = addAssistant();
    $(".recall summary b", el).textContent = `Reading ${f.name}…`; thread.scrollTop = thread.scrollHeight;
    const buf = new Uint8Array(await f.arrayBuffer()); let bin = "";
    for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    try {
      const r = await api("/api/teach", { method: "POST", body: { filename: f.name, data_base64: btoa(bin), conversation_id: S.current } });
      uploadCard(el, r);
    } catch (e) { $(".recall", el)?.remove(); $(".answer", el).classList.remove("cursor"); $(".answer", el).innerHTML = `<p class="muted">⚠ ${esc(f.name)}: ${esc(e.message)}</p>`; }
    thread.scrollTop = thread.scrollHeight;
  }
  await loadChats(); refresh();
}
function uploadCard(el, u) {
  $(".recall", el)?.remove(); const a = $(".answer", el); a.classList.remove("cursor");
  const pages = (u.pages || []).filter((p) => p.image);
  const kept = u.unchanged ? "Already in memory: this version was learned before" : u.notes ? `Kept ${u.notes} memor${u.notes === 1 ? "y" : "ies"} from it` : "";
  a.innerHTML = `<div class="upload-card">
    ${pages.length ? `<div class="thumbs n${Math.min(pages.length, 3)}">${pages.slice(0, 3).map((p) => `<button class="thumb" data-page="${p.index}" title="Open ${esc(u.name)}">
      <img src="/api/files/${u.file_id}/${p.image}" alt="${esc(u.name)}, page ${p.index + 1}"><span>${p.lines ? `${p.lines} lines read` : `page ${p.index + 1}`}</span></button>`).join("")}
      ${pages.length > 3 ? `<button class="thumb more" data-page="3">+${pages.length - 3} pages</button>` : ""}</div>` : ""}
    <div class="up-name">📎 ${esc(u.name)}</div>
    ${u.summary ? md(u.summary) : ""}
    ${u.problem ? `<p class="small warn-text">${esc(u.problem)}</p>` : ""}
    ${kept ? `<div class="saved-note">✦ ${kept}</div>` : ""}
    <label class="expert-pick">Expert <select aria-label="Which expert this file belongs to"><option value="">Shared memory (always open)</option></select>
      <input class="new-expert hidden" placeholder="e.g. code:acme" aria-label="New expert name" maxlength="40"></label>
    ${(u.chips || []).length ? `<div class="focus"><span class="muted small">What should I focus on?</span>${u.chips.map((c) => `<button class="chip" data-focus="${esc(c)}">${esc(c)}</button>`).join("")}</div>` : ""}
    ${(u.questions || []).length ? `<div class="asks">${u.questions.map((q) => `<button class="ask" data-q="${esc(q)}">↳ ${esc(q)}</button>`).join("")}</div>` : ""}
  </div>`;
  $$(".thumb", a).forEach((b) => b.onclick = () => openFile(u.file_id, +b.dataset.page));
  expertPicker($(".expert-pick", a), u);
  $$(".chip", a).forEach((b) => b.onclick = () => focusOn(u, b.dataset.focus, b));
  $$(".ask", a).forEach((b) => b.onclick = () => setAbout(u, b.dataset.q));
}
async function expertPicker(label, u) {
  const sel = $("select", label), inp = $(".new-expert", label);
  let ex = []; try { ex = await api("/api/experts"); } catch { /* experts are optional */ }
  const names = [...new Set([...ex.map((e) => e.name), ...(u.expert ? [u.expert] : [])])];
  sel.innerHTML = `<option value="">Shared memory (always open)</option>` + names.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("")
    + `<option value="__new">＋ New expert…</option>`;
  sel.value = u.expert || "";
  const save = async (name) => {
    try { const r = await api("/api/experts/assign", { method: "POST", body: { file_id: u.file_id, expert: name } });
      u.expert = r.expert; toast(r.expert ? `◆ ${u.name} now opens only with questions about ${r.expert}` : `${u.name} is back in shared memory`); }
    catch (e) { toast(e.message); sel.value = u.expert || ""; }
  };
  sel.onchange = () => { if (sel.value === "__new") { inp.classList.remove("hidden"); inp.focus(); } else { inp.classList.add("hidden"); save(sel.value); } };
  inp.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); if (inp.value.trim()) { save(inp.value.trim()); inp.classList.add("hidden"); expertPicker(label, u); } }
    if (e.key === "Escape") { inp.classList.add("hidden"); sel.value = u.expert || ""; } };
}
async function focusOn(u, what, btn) {
  btn.disabled = true;
  const el = addAssistant(); $(".recall", el)?.remove();
  $(".answer", el).innerHTML = `<p class="muted">Looking for ${esc(what.toLowerCase())} in ${esc(u.name)}…</p>`; thread.scrollTop = thread.scrollHeight;
  try {
    const r = await api(`/api/files/${u.file_id}/focus`, { method: "POST", body: { focus: what, conversation_id: S.current } });
    $(".answer", el).innerHTML = r.facts.length ? md(r.facts.map((f) => "- " + f).join("\n"))
      + `<div class="saved-note">✦ Kept ${r.facts.length} note${r.facts.length === 1 ? "" : "s"} on ${esc(what.toLowerCase())}</div>`
      : `<p class="muted">I couldn't find ${esc(what.toLowerCase())} in ${esc(u.name)}.</p>`;
  } catch (e) { $(".answer", el).innerHTML = `<p class="muted">⚠ ${esc(e.message)}</p>`; }
  $(".answer", el).classList.remove("cursor"); btn.disabled = false; refresh();
}
function setAbout(u, q) {
  S.about = { file_id: u.file_id, question: q, name: u.name };
  const bar = $("#about-bar");
  bar.innerHTML = `<span>↳ Answering about <b>${esc(u.name)}</b>: ${esc(q)}</span><button type="button" class="x" aria-label="Stop answering about this file">✕</button>`;
  bar.classList.remove("hidden"); $(".x", bar).onclick = clearAbout; input.focus();
}
function clearAbout() { S.about = null; $("#about-bar").classList.add("hidden"); }
async function openFile(fid, page = 0, marks = null) {
  let f; try { f = await api(`/api/files/${fid}`); } catch (e) { toast(e.message); return; }
  S.viewing = f; S.sel = null; $("#sel-bar").classList.add("hidden");
  $("#file-name").textContent = f.name;
  const hit = new Set((marks || []).map((m) => m.page + ":" + m.box.join(",")));
  const pct = (b) => `left:${100 * b[0]}%;top:${100 * b[1]}%;width:${100 * b[2]}%;height:${100 * b[3]}%`;
  $("#file-pages").innerHTML = f.pages.filter((p) => p.image).map((p) => `<div class="vpage" data-page="${p.index}">
      <img src="/api/files/${fid}/${p.image}" alt="${esc(f.name)}, page ${p.index + 1}" draggable="false">
      ${p.lines.map((l) => `<i class="ln${hit.has(p.index + ":" + l.box.join(",")) ? " hit" : ""}" style="${pct(l.box)}" title="${esc(l.text)}"></i>`).join("")}
      <div class="lasso hidden"></div></div>`).join("") || `<p class="muted">This file has no pages to show.</p>`;
  $("#file-hint").textContent = marks ? `Highlighted: the ${marks.length} line${marks.length === 1 ? "" : "s"} this memory came from. Drag over a part to teach or ask about it.`
    : "Boxes show what was read. Drag over a part of a page to teach or ask about just that.";
  $("#file-dlg").showModal();
  const first = $(".ln.hit", $("#file-pages")) || $(`.vpage[data-page="${page}"]`, $("#file-pages"));
  first?.scrollIntoView({ block: "center" });
  $$(".vpage", $("#file-pages")).forEach(lasso);
}
function lasso(pg) {
  const box = $(".lasso", pg); let start = null;
  const at = (e) => { const r = pg.getBoundingClientRect(); return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))]; };
  pg.onpointerdown = (e) => { start = at(e); pg.setPointerCapture(e.pointerId); box.classList.remove("hidden"); draw(start, start); };
  pg.onpointermove = (e) => { if (start) draw(start, at(e)); };
  pg.onpointerup = async (e) => {
    if (!start) return; const end = at(e); const b = [Math.min(start[0], end[0]), Math.min(start[1], end[1]), Math.abs(end[0] - start[0]), Math.abs(end[1] - start[1])]; start = null;
    if (b[2] < 0.02 || b[3] < 0.01) { box.classList.add("hidden"); return; }
    const r = await api(`/api/files/${S.viewing.file_id}/select`, { method: "POST", body: { page: +pg.dataset.page, box: b } });
    S.sel = { page: +pg.dataset.page, box: b, text: r.text };
    $("#sel-text").textContent = r.text || "No text in that part.";
    $("#sel-bar").classList.toggle("hidden", false); $("#sel-teach").disabled = $("#sel-ask").disabled = !r.text;
  };
  function draw(a, c) { box.style.cssText = `left:${100 * Math.min(a[0], c[0])}%;top:${100 * Math.min(a[1], c[1])}%;width:${100 * Math.abs(c[0] - a[0])}%;height:${100 * Math.abs(c[1] - a[1])}%`; }
}
$("#file-close").onclick = () => $("#file-dlg").close();
$("#sel-teach").onclick = async () => {
  const r = await api(`/api/files/${S.viewing.file_id}/select`, { method: "POST", body: { page: S.sel.page, box: S.sel.box, teach: true } });
  toast(r.notes ? "✦ Kept that part as its own memory" : "That part was already in memory"); refresh();
};
$("#sel-ask").onclick = () => {
  $("#file-dlg").close(); input.value = `About “${S.viewing.name}”: “${S.sel.text.replace(/\n/g, " ")}” — `; autosize(); input.focus();
};
document.addEventListener("click", async (e) => {
  const b = e.target.closest(".show-in-file"); if (!b) return;
  try { const h = await api(`/api/highlight/${b.dataset.note}`); openFile(h.file_id, h.boxes[0]?.page || 0, h.boxes); }
  catch { toast("This memory has no page to show"); }
});
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
$$("[data-panel=learning]").forEach((b) => b.onclick = () => { openPanel("learning"); closeMobile(); });
$$(".tab").forEach((t) => t.onclick = () => selectTab(t.dataset.tab));
function selectTab(name) {
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  for (const n of ["recall", "memory", "learning", "growth"]) $(`#panel-${n}`).classList.toggle("hidden", n !== name);
  if (name === "memory") loadMemory(); if (name === "growth") renderGrowth(S.state.stats); if (name === "learning") loadLearning();
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
    <p class="muted small">${st.helpful} helpful · ${st.not_helpful} not helpful · ${st.turns} questions. The model's weights never change: every gain here is memory.</p>`;
}

// ---------- learning panel ----------
const fmt = (n) => n >= 1e6 ? (n / 1e6).toFixed(1) + " M" : n >= 1e3 ? (n / 1e3).toFixed(1) + " k" : String(n);
async function loadLearning() {
  const L = await api("/api/learning"); S.learning = L;
  const w = L.weights, model = S.state.models.find((m) => m.name === S.state.settings.model);
  const jobs = L.jobs || {}, sl = jobs.sleep?.status === "running", hv = jobs.harvest?.status === "running";
  $("#learn-badge").classList.toggle("hidden", !sl);
  const rep = L.last_sleep?.report;
  const ad = rep?.adapter, ix = rep?.index, cur = rep?.curiosity;
  $("#panel-learning").innerHTML = `
    <div class="stat weights"><div class="k">External weights</div>
      <div class="wrow"><span>Model <b>${esc(model?.parameters || "?")}</b> parameters</span><span class="frozen">frozen</span></div>
      <div class="wrow"><span>Memory <b>${fmt(w.memory_parameters)}</b> numbers <span class="muted">(${w.notes.toLocaleString()} notes × ${w.dim})</span></span><span class="grows">grows</span></div>
      <div class="wrow"><span>Learned retrieval <b>${fmt(w.adapter_parameters)}</b>${w.index_clusters ? ` · index of <b>${w.index_clusters}</b> clusters` : ""}</span><span class="grows">${w.adapter_parameters ? "trained" : "after sleep"}</span></div>
      <p class="muted small">The model computes; memory holds what it knows. Memory lives on disk (${w.store_mb} MB) and only what a question needs is read.</p>
      ${L.device ? `<p class="small device-line">This device: <b>${(L.device.disk_free_mb / 1024).toFixed(1)} GB</b> free (keeping ${(L.device.reserve_disk_mb / 1024).toFixed(1)} GB) · room for about <b>${fmt(L.device.room_for_notes)}</b> more memories${L.device.pending_vectors ? ` · <b>${L.device.pending_vectors.toLocaleString()}</b> searchable by words now, by meaning after the next sleep` : ""}</p>` : ""}</div>
    <div class="stat-grid">
      <div class="stat"><div class="k">Looked up</div><div class="v">${L.lookups.total}</div><div class="muted small">${L.lookups.learned_from} taught it something</div></div>
      <div class="stat"><div class="k">Learned online</div><div class="v">${L.lookups.notes}</div><div class="muted small">memories, with links</div></div>
    </div>
    <div class="stat"><div class="k">Sleep</div>
      <p class="small">${sl ? "Sleeping now: tidying, re-indexing and learning to find things faster…" : rep ? `Last slept ${esc((L.last_sleep.at || "").replace("T", " ").slice(0, 16))} UTC:
        removed <b>${rep.tidy?.duplicates_removed ?? 0}</b> duplicates${cur?.learned?.length ? `, looked up <b>${cur.learned.length}</b> names it kept seeing (${cur.learned.map((x) => esc(x.title)).slice(0, 3).join(", ")})` : ""}${ix?.built ? `, indexed <b>${ix.notes.toLocaleString()}</b> notes in ${ix.clusters} clusters (${ix.index_ms} ms vs ${ix.exact_ms} ms per lookup)` : ""}${ad?.trained ? `, ${ad.kept ? `learned to find things better (recall@5 ${Math.round(100 * ad.recall_before["recall@5"])}% → ${Math.round(100 * ad.recall_after["recall@5"])}%)` : "tried to learn retrieval, kept the old way (no gain)"}` : ""}.`
        : "It hasn't slept yet. Sleep tidies memory, looks up names it keeps seeing, builds an index once memory passes 100,000 notes, and learns from answers you liked."}</p>
      <button class="ghost" id="sleep-btn" ${sl ? "disabled" : ""}>${sl ? "Sleeping…" : "◐ Sleep now"}</button></div>
    ${L.trust?.model ? `<div class="stat"><div class="k">Trust link · ${esc(L.trust.model)}</div>
      <p class="small">${L.trust.on ? `After each answer it decides: state it, hold back a likely-wrong guess${L.trust.escalate_to ? `, or ask <b>${esc(L.trust.escalate_to)}</b>` : ""}. Started from <b>${esc(L.trust.start || "untrained")}</b>; learned from <b>${L.trust.feedback}</b> of your thumbs.` : "Off: every answer is stated. Turn it on in Settings."}</p>
      ${L.trust.on ? `<p class="muted small">So far: ${L.trust.decisions.keep} stated · ${L.trust.decisions.decline} held back · ${L.trust.decisions.escalate} checked with a larger model${L.trust.escalate_to ? "" : " (choose a second-opinion model in Settings to allow this)"}</p>` : ""}</div>` : ""}
    <div class="stat"><div class="k">Experts</div>
      <p class="muted small">Closed parts of memory, one per subject. A question opens only the experts it is about, plus your shared memory, so one project's code or one course's notes never crowd another's. If they find nothing, the rest of memory gets one look.</p>
      ${(L.experts || []).map((e) => `<div class="pack-row"><div><b>${esc(e.name)}</b> <span class="muted small">${e.notes} memories${e.files ? ` · ${e.files} file${e.files === 1 ? "" : "s"}` : ""}</span><div class="muted small">${esc(e.titles.join(", "))}</div></div>
        <div class="row-actions"><button class="ghost sm" data-rename-expert="${esc(e.name)}">Rename</button><button class="ghost sm" data-close-expert="${esc(e.name)}" title="Its memories return to shared memory; nothing is forgotten">Dissolve</button></div></div>`).join("")
        || `<p class="muted small">No experts yet. Code files start one (code); put any file in an expert from its card in the chat.</p>`}</div>
    <div class="stat"><div class="k">Skill cards</div>
      <p class="muted small">Small add-ons for one model, trained on corrections of one skill. Memory attaches a card only when its corrections are what a question needs; the model's own weights never change, and a calculator does the arithmetic.</p>
      ${(L.cards || []).map((p) => `<div class="pack-row"><div><b>${esc(p.title)}</b> <span class="muted small">${p.skills.length} skills · for ${esc(p.base)}</span><div class="muted small">${esc(p.skills.join(", "))}${p.usable ? "" : ` · used only when ${esc(p.base)} answers`}</div></div>
        ${p.installed ? `<button class="ghost sm" data-uncard="${esc(p.name)}">Remove</button>` : `<button class="primary sm" data-card="${esc(p.name)}">Install</button>`}</div>`).join("") || `<p class="muted small">No card packs on this computer.</p>`}</div>
    <div class="stat"><div class="k">Knowledge packs</div>
      <p class="muted small">Ready-made memory: notes with their vectors already computed, so a pack plugs in without running a model.</p>
      ${L.packs.map((p) => `<div class="pack-row"><div><b>${esc(p.title)}</b> <span class="muted small">${p.notes} notes · ${esc(p.licence)}</span><div class="muted small">${esc(p.description)}</div></div>
        ${p.installed ? `<button class="ghost sm" data-unpack="${esc(p.name)}">Remove</button>` : `<button class="primary sm" data-pack="${esc(p.name)}">Install</button>`}</div>`).join("") || `<p class="muted small">No packs on this computer yet. Harvest one below.</p>`}
      <div class="harvest"><input id="harvest-topic" placeholder="Harvest a topic, e.g. Kenya" aria-label="Topic to harvest" ${hv ? "disabled" : ""}>
        <button class="ghost sm" id="harvest-btn" ${hv || !L.settings.learn_online ? "disabled" : ""}>${hv ? "Harvesting…" : "Harvest"}</button></div>
      ${jobs.harvest?.status === "done" ? `<p class="small ok">✓ Harvested “${esc(jobs.harvest.topic)}”: ${jobs.harvest.pages} articles, ${jobs.harvest.notes_added} new memories</p>`
        : jobs.harvest?.status === "error" ? `<p class="small warn">${esc(jobs.harvest.error)}</p>` : ""}
      ${L.settings.learn_online ? "" : `<p class="muted small">Turn on “Look things up online” in Settings to harvest.</p>`}</div>
    <div class="stat"><div class="k" style="margin-bottom:6px">Recently learned</div>
      ${L.feed.map((f) => `<div class="feed-item"><span class="kind ${f.kind}">${KIND[f.kind] || f.kind}</span>
        <span class="t">${f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.title || host(f.url))}</a>` : esc(f.title || "(untitled)")}</span>
        <span class="muted small">${esc((f.added || "").slice(0, 10))}</span></div>`).join("") || `<p class="muted small">Nothing yet.</p>`}</div>`;
  $("#sleep-btn").onclick = async () => { await api("/api/sleep", { method: "POST", body: {} }); toast("Sleeping: CAMR is consolidating its memory"); loadLearning(); };
  $$("#panel-learning [data-pack]").forEach((b) => b.onclick = async () => { b.disabled = true; const r = await api("/api/packs/install", { method: "POST", body: { name: b.dataset.pack } });
    toast(`✦ Installed ${r.title}: ${r.notes_added} memories in ${r.seconds} s${r.vectors_reused ? " (no model needed)" : ""}`); loadLearning(); refresh(); });
  $$("#panel-learning [data-rename-expert]").forEach((b) => b.onclick = async () => {
    const old = b.dataset.renameExpert, name = prompt(`Rename the expert “${old}” (an existing name merges them):`, old);
    if (!name || name === old) return;
    try { const r = await api("/api/experts/rename", { method: "POST", body: { old, new: name } }); toast(`◆ ${old} is now ${r.expert}`); } catch (e) { toast(e.message); }
    loadLearning(); });
  $$("#panel-learning [data-close-expert]").forEach((b) => b.onclick = async () => {
    if (!confirm(`Dissolve “${b.dataset.closeExpert}”? Its memories return to shared memory; nothing is forgotten.`)) return;
    const r = await api(`/api/experts/${encodeURIComponent(b.dataset.closeExpert)}`, { method: "DELETE" }); toast(`Dissolved: ${r.sources} sources back in shared memory`); loadLearning(); });
  $$("#panel-learning [data-card]").forEach((b) => b.onclick = async () => { b.disabled = true; b.textContent = "Installing…";
    try { const r = await api("/api/cards/install", { method: "POST", body: { name: b.dataset.card } }); toast(`◆ Installed ${r.cards} skill cards for ${r.base}`); }
    catch (e) { toast(e.message); } loadLearning(); refresh(); });
  $$("#panel-learning [data-uncard]").forEach((b) => b.onclick = async () => { const r = await api(`/api/cards/${b.dataset.uncard}`, { method: "DELETE" }); toast(`Removed ${r.cards} skill cards`); loadLearning(); refresh(); });
  $$("#panel-learning [data-unpack]").forEach((b) => b.onclick = async () => { const r = await api(`/api/packs/${b.dataset.unpack}`, { method: "DELETE" }); toast(`Removed ${r.removed} memories`); loadLearning(); refresh(); });
  $("#harvest-btn").onclick = async () => { const topic = $("#harvest-topic").value.trim(); if (!topic) return;
    try { await api("/api/packs/harvest", { method: "POST", body: { topic, pages: 15 } }); toast(`Harvesting “${topic}”…`); } catch (e) { toast(e.message); } loadLearning(); };
  clearTimeout(loadLearning.t);
  if ((sl || hv) && !$("#panel-learning").classList.contains("hidden")) loadLearning.t = setTimeout(() => { loadLearning(); refresh(); }, 2000);
}

// ---------- settings ----------
$("#open-settings").onclick = () => {
  const s = S.state.settings; $("#set-budget").value = s.token_budget; $("#set-turns").value = s.history_turns; $("#set-chat").checked = s.remember_chat;
  $("#set-online").checked = s.learn_online; $("#set-sleep").checked = s.sleep_when_idle; $("#set-verified").checked = !!s.verified_only;
  $("#set-trust").checked = s.trust_learning !== false; $("#set-experts").checked = s.route_experts !== false;
  $("#set-vision").innerHTML = `<option value="">None</option>` + S.state.models.filter((m) => !m.embedding)
    .map((m) => `<option value="${esc(m.name)}" ${m.name === s.vision_model ? "selected" : ""}>${esc(m.name)} (${esc(m.parameters)})</option>`).join("");
  $("#set-check").innerHTML = `<option value="">None</option>` + S.state.models.filter((m) => !m.embedding && m.name !== s.model)
    .map((m) => `<option value="${esc(m.name)}" ${m.name === s.check_model ? "selected" : ""}>${esc(m.name)} (${esc(m.parameters)})</option>`).join("");
  $("#budget-val").textContent = s.token_budget + " tokens"; $("#turns-val").textContent = s.history_turns;
  $("#about").textContent = `CAMR Personal ${S.state.version} · memory model ${s.embed_model} · abstains below similarity ${s.min_similarity} · data in ${S.state.home}`;
  $("#settings-dlg").showModal(); closeMobile();
};
$("#set-budget").oninput = (e) => $("#budget-val").textContent = e.target.value + " tokens";
$("#set-turns").oninput = (e) => $("#turns-val").textContent = e.target.value;
$("#export-text").onchange = (e) => $("#export-link").href = "/api/export?text=" + (e.target.checked ? 1 : 0);
$("#settings-save").onclick = async () => {
  await api("/api/settings", { method: "POST", body: { token_budget: +$("#set-budget").value, history_turns: +$("#set-turns").value, remember_chat: $("#set-chat").checked,
    learn_online: $("#set-online").checked, sleep_when_idle: $("#set-sleep").checked, verified_only: $("#set-verified").checked, check_model: $("#set-check").value,
    trust_learning: $("#set-trust").checked, vision_model: $("#set-vision").value, route_experts: $("#set-experts").checked } });
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
