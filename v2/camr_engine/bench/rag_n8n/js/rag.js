// The pure functions the two n8n workflows' Code nodes run: cutting events into chunks (ingest), and choosing the
// chunks that fit the memory budget and writing the prompt around them (ask).
//
// build.py puts this file, followed by a few lines of glue, into each Code node, so the workflow a person opens in
// the n8n editor holds the whole logic. camr_engine/bench/rag_n8n/pipeline.py is the same logic in Python; the tests
// run both on the same input (this file with node) and require the same output.
//
// String lengths here are UTF-16 code units and Python's are code points: they differ only for characters outside
// the Basic Multilingual Plane (emoji), which only moves where an over-long event is cut.

const CHARS_PER_TOKEN = 3.5; // the Long Haul's text: 3.49 characters a Qwen3 token (used only when no count is given)
const PART_STRIDE = 64; // a point's id is event index * 64 + part, so an event may be cut into at most 64 parts

function estimateTokens(text) {
  return Math.max(1, Math.ceil(text.length / CHARS_PER_TOKEN));
}

function head(e) {
  // The date stamp every line carries, as CAMR dates its moments: "[2025-09-22, day 1] ".
  const day = e.day === undefined || e.day === null ? '' : `, day ${e.day}`;
  return `[${e.date}${day}] `;
}

function splitText(text, maxChars) {
  // Pieces of at most maxChars characters, cut at the last newline, else at the last space, else anywhere.
  const out = [];
  let rest = text;
  while (rest.length > maxChars) {
    let cut = rest.lastIndexOf('\n', maxChars);
    if (cut < maxChars / 2) cut = rest.lastIndexOf(' ', maxChars);
    if (cut < maxChars / 2) cut = maxChars;
    out.push(rest.slice(0, cut));
    rest = rest.slice(cut).replace(/^[\n ]+/, '');
  }
  if (rest.length) out.push(rest);
  return out;
}

function pieces(e, limit) {
  // One event as dated lines of at most `limit` tokens: the whole event, or, when it is longer, its parts, each
  // with the date stamp. `e.tokens` is the dated line's token count (with its newline) when the caller knows it.
  const h = head(e);
  const full = h + e.text;
  const n = typeof e.tokens === 'number' && e.tokens > 0 ? e.tokens : estimateTokens(full);
  if (n <= limit) return [{ text: full, tokens: n, part: 0 }];
  const perChar = n / full.length;
  const maxChars = Math.max(1, Math.floor(limit / perChar) - h.length);
  return splitText(e.text, maxChars).map((p, j) => ({
    text: h + p,
    tokens: Math.min(limit, Math.ceil((h.length + p.length) * perChar)),
    part: j,
  }));
}

function chunkEvents(events, limit) {
  // Consecutive events packed into chunks of at most `limit` tokens, in order; an event never straddles two chunks
  // unless it is longer than a chunk on its own. Each chunk keeps its dates, days and event indices.
  const chunks = [];
  let cur = null;
  for (const e of events) {
    for (const p of pieces(e, limit)) {
      if (cur && cur.tokens + p.tokens > limit) {
        chunks.push(cur);
        cur = null;
      }
      if (!cur) {
        cur = {
          id: e.i * PART_STRIDE + p.part, lines: [], tokens: 0, event_ids: [],
          date_from: e.date, date_to: e.date,
          day_from: e.day === undefined ? null : e.day, day_to: e.day === undefined ? null : e.day,
        };
      }
      cur.lines.push(p.text);
      cur.tokens += p.tokens;
      if (cur.event_ids[cur.event_ids.length - 1] !== e.i) cur.event_ids.push(e.i);
      cur.date_to = e.date;
      cur.day_to = e.day === undefined ? null : e.day;
    }
  }
  if (cur) chunks.push(cur);
  return chunks.map((c) => ({
    id: c.id, text: c.lines.join('\n'), tokens: c.tokens, event_ids: c.event_ids,
    date_from: c.date_from, date_to: c.date_to, day_from: c.day_from, day_to: c.day_to,
  }));
}

function selectChunks(hits, k, budget, order) {
  // The first `k` hits (closest first) that fit `budget` tokens together: a hit past the budget is skipped, and a
  // shorter one further down may still fit. Then put in date order (the history's order), or kept closest first.
  const picked = [];
  let total = 0;
  for (const h of hits.slice(0, k)) {
    const n = h.payload.tokens;
    if (total + n > budget) continue;
    picked.push(h);
    total += n;
  }
  if (order === 'date') picked.sort((a, b) => a.id - b.id);
  return { picked, tokens: total };
}

function notesText(picked) {
  return picked.map((h) => h.payload.text + '\n').join('');
}

function systemPrompt(intro, notes, today, then) {
  // CAMR's prompt with the notes as words: the instructions, the notes, today's date, the family's line.
  const date = today ? `\nToday is ${today}.` : '';
  return `${intro}\n\nNotes:\n${notes}End of notes.${date}` + (then ? `\n\n${then}` : '');
}
