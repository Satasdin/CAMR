// CAMR landing page: tabs, copy buttons, the CAMR / RAG loop in the showcase, and the download link.
"use strict";

// --- tabs: click, or arrow keys to move between them (Up/Down too, for the vertical list)
document.querySelectorAll("[data-tabs]").forEach((box) => {
  const list = box.querySelector('[role="tablist"]');
  const tabs = [...list.querySelectorAll('[role="tab"]')];
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
      const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
      if (!step) return;
      e.preventDefault();
      const next = tabs[(i + step + tabs.length) % tabs.length];
      pick(next);
      next.focus();
    });
  });
});

// --- copy buttons on every code block
document.querySelectorAll(".install .panel, .panel.code").forEach((panel) => {
  const pre = panel.querySelector("pre");
  if (!pre) return;
  const b = document.createElement("button");
  b.className = "copy";
  b.type = "button";
  b.textContent = "Copy";
  b.setAttribute("aria-label", "Copy the code");
  b.addEventListener("click", async () => {
    const text = [...pre.querySelectorAll("code")].map((c) => {
      const clone = c.cloneNode(true);
      clone.querySelectorAll(".pr").forEach((n) => n.remove());
      return clone.textContent;
    }).join("\n").trim();
    try {
      await navigator.clipboard.writeText(text);
      b.textContent = "Copied";
      b.classList.add("done");
    } catch {
      const r = document.createRange();
      r.selectNodeContents(pre);
      const s = getSelection();
      s.removeAllRanges();
      s.addRange(r);
      b.textContent = "Selected";
    }
    setTimeout(() => { b.textContent = "Copy"; b.classList.remove("done"); }, 1600);
  });
  panel.appendChild(b);
});

// --- showcase: the real CAMR and RAG captures of the tensor view, cross-faded on a loop
const sw = document.querySelector("[data-show]");
if (sw) {
  const frame = sw.nextElementSibling;
  const modes = [...sw.querySelectorAll("[data-mode]")];
  const play = sw.querySelector("[data-play]");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let timer = null;
  const show = (mode) => {
    modes.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
    frame.querySelectorAll("img[data-mode]").forEach((img) => img.classList.toggle("on", img.dataset.mode === mode));
    frame.querySelectorAll("[data-cap]").forEach((c) => (c.hidden = c.dataset.cap !== mode));
  };
  const setPlaying = (on) => {
    clearInterval(timer);
    timer = null;
    play.setAttribute("aria-pressed", String(on));
    play.setAttribute("aria-label", on ? "Pause the loop" : "Play the loop");
    play.textContent = on ? "❚❚" : "▶";
    if (on) {
      timer = setInterval(() => {
        const cur = modes.find((b) => b.getAttribute("aria-pressed") === "true").dataset.mode;
        show(cur === "camr" ? "rag" : "camr");
      }, 4200);
    }
  };
  modes.forEach((b) => b.addEventListener("click", () => { setPlaying(false); show(b.dataset.mode); }));
  play.addEventListener("click", () => setPlaying(!timer));
  // load the second capture right away so the first fade is clean
  frame.querySelectorAll("img[loading=lazy]").forEach((img) => (img.loading = "eager"));
  setPlaying(!reduce);
}

// --- the download: when served over http and the app is not built yet, say so instead of a dead link
if (location.protocol.startsWith("http")) {
  document.querySelectorAll("[data-dl]").forEach((dl) => {
    fetch(dl.getAttribute("href"), { method: "HEAD" })
      .then((r) => { if (!r.ok) throw new Error(String(r.status)); })
      .catch(() => {
        dl.lastChild.textContent = " CAMR.app.zip: build it with apps/mac/build.sh";
        dl.classList.add("off");
        dl.removeAttribute("href");
        dl.setAttribute("aria-disabled", "true");
      });
  });
}
