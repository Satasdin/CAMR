// The stage's palette, read from tokens.css at start (getComputedStyle), so the shaders and the DOM share one source
// of truth. Each channel has one meaning (DIRECTION.md, "Colour"); its steps are the channel times a factor over
// black, which is what color-mix(in srgb, X n%, black) gives in CSS.

export const CH = { ssd: 0, ram: 1, used: 2, vault: 3, fault: 4, select: 5, ink2: 6, ink4: 7, ink3: 8, ink: 9, hair: 10, void: 11 };
export const STEP = { far: 0.08, cell: 0.12, rest: 0.22, resident: 0.35, hold: 0.6, event: 1 };
// half-lives in display milliseconds (tokens.css --hl-*, and the motion table)
export const HL = { choose: 400, read: 400, ram: 400, words: 600, wake: 800, core: 400, desk: 400, gaze: 1200,
  used: 4000, write: 800, sleep: 800 };

const NAMES = { ssd: "--ssd", ram: "--ram", used: "--used", vault: "--vault", fault: "--fault", select: "--select",
  ink2: "--ink-2", ink4: "--ink-4", ink3: "--ink-3", ink: "--ink", hair: "--hair-2", void: "--void" };

function parse(text) {
  const t = (text || "").trim();
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(t);
  if (m) return [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255];
  const n = t.match(/[\d.]+/g); // a computed colour comes back as three numbers 0–255
  return n && n.length >= 3 ? [Number(n[0]) / 255, Number(n[1]) / 255, Number(n[2]) / 255] : [0, 0, 0];
}

export function palette(el = document.documentElement) {
  const cs = getComputedStyle(el);
  const list = [];
  const css = {};
  for (const [name, idx] of Object.entries(CH)) {
    const v = cs.getPropertyValue(NAMES[name]);
    list[idx] = parse(v);
    css[name] = `var(${NAMES[name]})`;
  }
  return { list, css };
}
