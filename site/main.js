// CAMR landing page: tabs, copy buttons, the Long Haul chart, and the download link.
"use strict";

// --- tabs (arrow keys move between them)
document.querySelectorAll("[data-tabs]").forEach((box) => {
  const tabs = [...box.querySelectorAll('[role="tab"]')];
  const pick = (tab) => {
    for (const t of tabs) {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    }
  };
  tabs.forEach((t, i) => {
    t.tabIndex = t.getAttribute("aria-selected") === "true" ? 0 : -1;
    t.addEventListener("click", () => pick(t));
    t.addEventListener("keydown", (e) => {
      const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
      if (!step) return;
      const next = tabs[(i + step + tabs.length) % tabs.length];
      pick(next);
      next.focus();
    });
  });
});

// --- copy buttons on every code panel
document.querySelectorAll(".panel pre").forEach((pre) => {
  const b = document.createElement("button");
  b.className = "copy";
  b.type = "button";
  b.textContent = "copy";
  b.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(pre.innerText.trim());
      b.textContent = "copied";
    } catch {
      b.textContent = "select it";
    }
    setTimeout(() => (b.textContent = "copy"), 1600);
  });
  pre.parentElement.appendChild(b);
});

// --- the download: the button says so when the app is not built yet
const dl = document.getElementById("dl");
if (dl && location.protocol.startsWith("http")) {
  fetch(dl.getAttribute("href"), { method: "HEAD" })
    .then((r) => {
      if (!r.ok) throw new Error(String(r.status));
    })
    .catch(() => {
      dl.textContent = "CAMR.app.zip: coming soon";
      dl.classList.add("off");
      dl.removeAttribute("href");
    });
}

// --- the Long Haul: share of questions right as the history grows (MORNING.md, 4 November 2026)
const CUTS = ["64K", "256K", "1M", "2M", "3M", "4M"];
const ASKED = [34, 40, 69, 73, 73, 73];
const SERIES = [
  { name: "Qwen3 4B + CAMR", color: "var(--mem-mark)", right: [25, 26, 25, 29, 29, 29], end: "CAMR" },
  { name: "the same 4B, bare", color: "var(--model-mark)", right: [18, 14, 20, 11, 12, 13], end: "bare 4B" },
  { name: "Claude Sonnet 5.5 alone", color: "var(--claude-mark)", right: [28, 35, 43, 32, 13, 10], end: "Sonnet", dash: "6 5" },
];

const chart = document.getElementById("chart");
const tip = document.getElementById("tip");
const NS = "http://www.w3.org/2000/svg";

function el(name, attrs, parent) {
  const n = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}

function draw() {
  if (!chart) return;
  chart.textContent = "";
  const W = Math.max(300, chart.clientWidth);
  const narrow = W < 560;
  const H = narrow ? 300 : 400;
  const pad = { l: narrow ? 34 : 44, r: narrow ? 88 : 120, t: 18, b: 40 };
  const x = (i) => pad.l + (i * (W - pad.l - pad.r)) / (CUTS.length - 1);
  const y = (share) => pad.t + (1 - share) * (H - pad.t - pad.b);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H }, chart);

  const grid = el("g", { class: "grid" }, svg);
  for (const s of [0, 0.25, 0.5, 0.75, 1]) {
    el("line", { x1: pad.l, x2: W - pad.r, y1: y(s), y2: y(s) }, grid);
    el("text", { x: pad.l - 8, y: y(s) + 4, "text-anchor": "end" }, svg).textContent = `${s * 100}%`;
  }
  CUTS.forEach((c, i) => {
    el("text", { x: x(i), y: H - 14, "text-anchor": "middle" }, svg).textContent = c;
  });
  // Claude reads the newest 1M tokens: past this line the history no longer fits its window
  const wx = (x(2) + x(3)) / 2;
  el("line", { class: "window", x1: wx, x2: wx, y1: pad.t, y2: H - pad.b }, svg);
  el("text", { x: wx + 6, y: pad.t + 12 }, svg).textContent = narrow ? "past 1M" : "past Claude's 1M window";

  // the end labels, nudged apart where their lines end close together
  const ends = SERIES.map((s) => ({ s, y: y(s.right.at(-1) / ASKED.at(-1)) + 4 })).sort((a, b) => a.y - b.y);
  ends.forEach((e, k) => { if (k && e.y - ends[k - 1].y < 17) e.y = ends[k - 1].y + 17; });
  const endY = new Map(ends.map((e) => [e.s, e.y]));

  for (const s of SERIES) {
    const pts = s.right.map((r, i) => [x(i), y(r / ASKED[i])]);
    el("polyline", {
      points: pts.map((p) => p.join(",")).join(" "), fill: "none", stroke: s.color, "stroke-width": 2,
      "stroke-linejoin": "round", "stroke-linecap": "round", ...(s.dash ? { "stroke-dasharray": s.dash } : {}),
    }, svg);
    for (const [px, py] of pts) {
      el("circle", { cx: px, cy: py, r: 4.5, fill: s.color, stroke: "var(--panel)", "stroke-width": 2 }, svg);
    }
    const last = s.right.length - 1;
    const lbl = el("text", { x: pts[last][0] + 12, y: endY.get(s), class: s === SERIES[0] ? "lbl big" : "lbl" }, svg);
    lbl.textContent = `${s.right[last]} · ${s.end}`;
  }

  // hover: a crosshair on the nearest cut, and every series' count there
  const hover = el("line", { class: "hover-line", y1: pad.t, y2: H - pad.b, visibility: "hidden" }, svg);
  const hit = el("rect", { x: 0, y: 0, width: W, height: H, fill: "transparent" }, svg);
  const show = (clientX) => {
    const box = svg.getBoundingClientRect();
    const px = clientX - box.left;
    let i = Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (CUTS.length - 1));
    i = Math.max(0, Math.min(CUTS.length - 1, i));
    hover.setAttribute("x1", x(i));
    hover.setAttribute("x2", x(i));
    hover.setAttribute("visibility", "visible");
    tip.innerHTML = `<b>${CUTS[i]} tokens told · ${ASKED[i]} questions</b>` + SERIES.map((s) =>
      `<div><i style="background:${s.color}"></i>${s.name}<span>${s.right[i]}</span></div>`).join("");
    tip.hidden = false;
    const card = chart.parentElement.getBoundingClientRect();
    const left = box.left - card.left + x(i) + 14;
    tip.style.left = `${Math.min(left, card.width - tip.offsetWidth - 12)}px`;
    tip.style.top = `${box.top - card.top + pad.t + 8}px`;
  };
  hit.addEventListener("pointermove", (e) => show(e.clientX));
  hit.addEventListener("pointerdown", (e) => show(e.clientX));
  hit.addEventListener("pointerleave", () => {
    tip.hidden = true;
    hover.setAttribute("visibility", "hidden");
  });
}

draw();
let wait;
window.addEventListener("resize", () => {
  clearTimeout(wait);
  wait = setTimeout(draw, 120);
});
