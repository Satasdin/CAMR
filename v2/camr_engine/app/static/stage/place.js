// Where each room sits on the SSD plate (DIRECTION.md, "Geometry"): one band per reach (height ∝ √bytes, at least
// 64 px, 8 px apart), tiles sized so they cover 40% of their band, each centred on its moments' mean layout position,
// then 60 passes of rectangle separation over a spatial hash. Deterministic. Positions are kept for the session as
// fractions of their band, so a resize keeps them; a new room takes the free spot nearest its band's lower-left. A band
// squeezed to nothing (a hidden screen measures 0 × 0) keeps no positions, and a kept position is always finite.

export const LABEL_H = 16; // a band's label row
const GAP = 8;
const MIN_BAND = 64;
const PASSES = 60;
const FULL = 512; // tokens in a full room

export function tileWidth(h0, tokens) {
  return Math.max(0.5 * h0, (3.2 * h0 * Math.min(tokens, 4 * FULL)) / FULL);
}

export function bands(reaches, plate) {
  const n = reaches.length;
  if (!n) return [];
  const H = plate.h - GAP * (n - 1);
  const raw = reaches.map((r) => Math.sqrt(Math.max(1, (r.history_tokens || 0) * (r.token_bytes || 1))));
  let heights;
  if (n === 1) heights = [plate.h];
  else if (MIN_BAND * n >= H) heights = reaches.map(() => H / n);
  else {
    heights = new Array(n).fill(0);
    let free = H;
    let open = reaches.map((_, i) => i);
    for (let pass = 0; pass < n; pass++) { // bands that would fall under the minimum take it; the rest share
      const sum = open.reduce((a, i) => a + raw[i], 0);
      const small = open.filter((i) => (free * raw[i]) / sum < MIN_BAND);
      if (!small.length) {
        for (const i of open) heights[i] = (free * raw[i]) / sum;
        break;
      }
      for (const i of small) { heights[i] = MIN_BAND; free -= MIN_BAND; }
      open = open.filter((i) => !small.includes(i));
      if (!open.length) break;
    }
  }
  let y = plate.y;
  return reaches.map((r, i) => {
    const b = { label: r.label, x: plate.x, y, w: plate.w, h: heights[i], reach: r };
    y += heights[i] + GAP;
    return b;
  });
}

const KEEP_MIN = 8; // a band's inner box narrower or shorter than this keeps no positions

function solveH0(band, rooms) {
  const area = Math.max(1, band.w) * Math.max(1, band.h - LABEL_H);
  const sum = rooms.reduce((a, r) => a + (3.2 * Math.max(1, Math.min(r.tokens, 4 * FULL))) / FULL, 0);
  if (!sum) return 12;
  const h0 = Math.max(6, Math.min(28, Math.sqrt((0.4 * area) / sum)));
  return Number.isFinite(h0) ? h0 : 12;
}

function keptAt(kept, id) { // a kept position, or null when there is none or it is not a pair of finite fractions
  const k = kept.get(id);
  return k && Number.isFinite(k[0]) && Number.isFinite(k[1]) ? k : null;
}

const unit = (v) => Math.max(0, Math.min(1, v));

// rooms: [{id, tokens, members: [moment ids]}]; layout: [[x, y]] per moment; kept: Map(id -> [fx, fy]) for this band
export function placeBand(band, rooms, layout, kept) {
  const h0 = solveH0(band, rooms);
  const inner = { x: band.x, y: band.y + LABEL_H, w: band.w, h: Math.max(h0, band.h - LABEL_H) };
  const tiles = rooms.map((r) => ({ id: r.id, w: tileWidth(h0, r.tokens), h: h0, x: 0, y: 0, room: r }));
  const fresh = [];
  for (const t of tiles) {
    const k = keptAt(kept, t.id);
    if (k) {
      t.x = inner.x + k[0] * inner.w - t.w / 2;
      t.y = inner.y + k[1] * inner.h - t.h / 2;
      continue;
    }
    const pts = t.room.members.map((m) => layout[m]).filter(Boolean);
    if (!pts.length) { fresh.push(t); continue; }
    const mx = pts.reduce((a, p) => a + p[0], 0) / pts.length;
    const my = pts.reduce((a, p) => a + p[1], 0) / pts.length;
    t.x = inner.x + t.w / 2 + mx * Math.max(0, inner.w - t.w) - t.w / 2;
    t.y = inner.y + t.h / 2 + my * Math.max(0, inner.h - t.h) - t.h / 2;
  }
  const placed = tiles.filter((t) => !fresh.includes(t));
  const anyKept = tiles.some((t) => keptAt(kept, t.id));
  if (!anyKept) separate(placed, inner);
  for (const t of fresh) freeSpot(t, placed, inner), placed.push(t);
  const keep = inner.w >= KEEP_MIN && inner.h >= KEEP_MIN;
  for (const t of tiles) {
    clamp(t, inner);
    const fx = (t.x + t.w / 2 - inner.x) / inner.w, fy = (t.y + t.h / 2 - inner.y) / inner.h;
    if (keep && Number.isFinite(fx) && Number.isFinite(fy)) kept.set(t.id, [unit(fx), unit(fy)]);
  }
  return { h0, inner, tiles };
}

function clamp(t, r) {
  t.x = Math.max(r.x, Math.min(r.x + r.w - t.w, t.x));
  t.y = Math.max(r.y, Math.min(r.y + r.h - t.h, t.y));
}

function separate(tiles, inner) {
  if (tiles.length < 2) { tiles.forEach((t) => clamp(t, inner)); return; }
  const big = Math.max(...tiles.map((t) => Math.max(t.w, t.h)));
  const cell = Math.max(4, 2 * big);
  const pad = 1; // a hairline of black between tiles
  for (let pass = 0; pass < PASSES; pass++) {
    const grid = new Map();
    tiles.forEach((t, i) => {
      const x0 = Math.floor(t.x / cell), x1 = Math.floor((t.x + t.w) / cell);
      const y0 = Math.floor(t.y / cell), y1 = Math.floor((t.y + t.h) / cell);
      for (let gx = x0; gx <= x1; gx++) for (let gy = y0; gy <= y1; gy++) {
        const k = `${gx},${gy}`;
        if (!grid.has(k)) grid.set(k, []);
        grid.get(k).push(i);
      }
    });
    let moved = false;
    const seen = new Set();
    for (const list of grid.values()) {
      for (let a = 0; a < list.length; a++) for (let b = a + 1; b < list.length; b++) {
        const i = Math.min(list[a], list[b]), j = Math.max(list[a], list[b]);
        const key = i * 100003 + j;
        if (seen.has(key)) continue;
        seen.add(key);
        const p = tiles[i], q = tiles[j];
        const ox = Math.min(p.x + p.w, q.x + q.w) - Math.max(p.x, q.x) + pad;
        const oy = Math.min(p.y + p.h, q.y + q.h) - Math.max(p.y, q.y) + pad;
        if (ox <= 0 || oy <= 0) continue;
        moved = true;
        if (ox < oy) {
          const s = (p.x + p.w / 2 <= q.x + q.w / 2 ? -1 : 1) * ox / 2;
          p.x += s; q.x -= s;
        } else {
          const s = (p.y + p.h / 2 <= q.y + q.h / 2 ? -1 : 1) * oy / 2;
          p.y += s; q.y -= s;
        }
      }
    }
    tiles.forEach((t) => clamp(t, inner));
    if (!moved) break;
  }
}

function overlaps(t, others) {
  return others.some((o) => t.x < o.x + o.w + 1 && o.x < t.x + t.w + 1 && t.y < o.y + o.h + 1 && o.y < t.y + t.h + 1);
}

function freeSpot(t, others, inner) {
  const step = Math.max(2, t.h / 2);
  for (let y = inner.y + inner.h - t.h; y >= inner.y; y -= step) {
    for (let x = inner.x; x <= inner.x + inner.w - t.w; x += step) {
      t.x = x; t.y = y;
      if (!overlaps(t, others)) return;
    }
  }
  t.x = inner.x; t.y = inner.y + inner.h - t.h; // the band is full: sit at its lower-left
}

// a room's moments as column spans inside its tile, in token order; 1 px gaps once a span is at least 3 px
export function cells(tile, moments) {
  const total = moments.reduce((a, m) => a + m.tokens, 0) || 1;
  const out = [];
  let at = 0;
  for (const m of moments) {
    const x0 = tile.x + (tile.w * at) / total;
    const w = (tile.w * m.tokens) / total;
    const gap = w >= 3 ? 1 : 0;
    out.push({ id: m.id, x: x0, y: tile.y, w: Math.max(0.5, w - gap), h: tile.h });
    at += m.tokens;
  }
  return out;
}
