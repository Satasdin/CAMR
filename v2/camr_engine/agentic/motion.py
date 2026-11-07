"""Motion: hard front-end briefs (a 3D scene, scroll-driven motion, parallax layers, a calm reduced-motion version),
the files they are built with, and the rules that mark the result.

- Which briefs ask for motion (``MOTION_BRIEF``), and which checks they get (``wants``): a rule on the request's words.
- The vendored libraries (``vendor/``: three.js with its GLTF loader, GSAP with ScrollTrigger, a few CC0 models and a
  procedural rocket; sources and licences in vendor/VENDOR.md) are copied into a project's ``vendor/`` folder through
  the Workspace (``install``), so a page needs no network; ``LOADER`` is the exact HTML that loads them.
- The check runs in Playwright's Chrome (``chrome_motion``, called by plugins.browser_check): one script measures the
  page while it is scrolled from top to bottom (the biggest canvas's pixels, frames per second, every element's
  transform at five scroll positions), the console is read, five screenshots are taken down the page, then the page is
  loaded again with prefers-reduced-motion: reduce and watched standing still. ``score`` marks the numbers by rule;
  it is a pure function, so the rules are tested without a browser.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

VENDOR = Path(__file__).resolve().parent / "vendor"
KITS = {
    "three": ["three/three.module.js", "three/three.core.js", "three/LICENSE", "three/addons/loaders/GLTFLoader.js",
              "three/addons/utils/BufferGeometryUtils.js", "three/addons/utils/SkeletonUtils.js"],
    "rocket": ["camr-rocket.js", "models/rocket/rocket.glb", "models/rocket/SOURCE.md"],
    "models": [f"models/space-kit/{m}.glb" for m in ("rocket_baseA", "rocket_fuelA", "rocket_sidesA", "rocket_finsA",
                                                      "rocket_topA", "platform_large", "satelliteDish")]
              + ["models/space-kit/License.txt"],
    "gsap": ["gsap/gsap.min.js", "gsap/ScrollTrigger.min.js", "gsap/LICENSE.md"],
}

# a request that asks for motion gets a motion part and the motion check
MOTION_BRIEF = re.compile(
    r"\b(3-?d|three\.?js|webgl|gsap|animat\w*|motion|parallax|pinned|pinning|exploded|lifts? off|lift-?off|"
    r"physics(?:-like)?|scroll[- ]?(?:driven|linked|told|triggered|story|telling|animations?)|"
    r"as (?:you|people|they|the user|visitors?) scrolls?|on scroll|while scrolling|trajectory)\b", re.I)
THREE_D = re.compile(r"\b(3-?d|three\.?js|webgl|exploded|rocket|globe|planet)\b", re.I)
LAYERS = re.compile(r"\b(parallax|layers?|layered|depth)\b", re.I)

# the rules, by name, in the order they are reported
RULES = ("canvas", "fps", "console", "layers", "reduced", "clear", "strip")
MIN_FPS = 50.0
MIN_COLOURS = 8  # distinct colours (4 bits a channel) in a 48 x 48 sample of the canvas
MIN_SPREAD = 4.0  # standard deviation of the sample's brightness, 0 to 255
MIN_LAYERS = 3  # elements whose transforms change at different rates while scrolling
MOVED = 0.5  # px, %, or degrees: less than this is not a change
SAME_RATE = 0.12  # rates within 12% of each other are one layer
STRIP = 5  # screenshots down the page
CLASH_SPREAD = 28  # brightness spread of the canvas under a text with no panel behind it: over the model, not the sky


def asks_motion(request: str) -> bool:
    return bool(MOTION_BRIEF.search(request or ""))


def wants(request: str, page: str = "") -> set[str]:
    """The checks a page gets, by rule: every motion page is measured for frames, console, reduced motion and the
    strip; a 3D brief (or a page with a canvas) for its canvas; a brief with parallax or layers for its layers."""
    if not asks_motion(request) and not re.search(r"<canvas\b|vendor/three|gsap|ScrollTrigger", page or "", re.I):
        return set()
    out = {"fps", "console", "reduced", "strip"}
    if THREE_D.search(request or "") or re.search(r"<canvas\b|vendor/three|from\s+['\"]three['\"]", page or ""):
        out |= {"canvas", "clear"}
    if LAYERS.search(request or ""):
        out.add("layers")
    return out


def kits_for(request: str) -> list[str]:
    """The vendored kits a motion brief gets: GSAP always; three.js, the rocket and the models for a 3D one."""
    return (["three", "rocket", "models"] if THREE_D.search(request or "") else []) + ["gsap"]


def install(ws, kits: list[str]) -> list[str]:
    """Copy the kits' files into the project's vendor/ folder through the workspace (its path checks, atomic writes),
    with VENDOR.md for their sources and licences. A file already there at the same size is left alone."""
    copied = []
    for rel in ["VENDOR.md", *[f for k in kits for f in KITS[k]]]:
        data = (VENDOR / rel).read_bytes()
        dest = f"vendor/{rel}"
        try:
            if ws.path(dest).is_file() and ws.path(dest).stat().st_size == len(data):
                continue
        except Exception:  # noqa: BLE001 (Outside: put() says why)
            pass
        copied.append(ws.put(dest, data))
    return copied


def loader(kits: list[str], script: str = "motion.js") -> str:
    """The exact HTML that loads the kits and the page's motion script, for the builder to paste in."""
    lines = []
    if "three" in kits:
        lines.append('<script type="importmap">{"imports": {"three": "./vendor/three/three.module.js", '
                     '"three/addons/": "./vendor/three/addons/"}}</script>')
    if "gsap" in kits:
        lines += ['<script src="vendor/gsap/gsap.min.js"></script>',
                  '<script src="vendor/gsap/ScrollTrigger.min.js"></script>']
    lines.append(f'<script type="module" src="{script}"></script>')
    return "\n".join(lines)


def catalog(kits: list[str]) -> str:
    """The vendored files a project has, one line each, for the architect and the motion part."""
    about = {"three": "three.js 0.187 as an ES module: import * as THREE from 'three' (through the import map); "
                      "GLTFLoader from 'three/addons/loaders/GLTFLoader.js'",
             "rocket": "vendor/camr-rocket.js: loadRocket(THREE, GLTFLoader, {onLoad}) (the detailed rocket, "
                       "vendor/models/rocket/rocket.glb: a three-stage launcher, white and black, no markings; it "
                       "returns the group at once and puts the model in when it loads), makeRocket(THREE) (a simple "
                       "rocket from shapes), makePad(THREE), makeStars(THREE), disposeAll(THREE, group)",
             "models": "vendor/models/space-kit/*.glb (CC0, Kenney): rocket_baseA, rocket_fuelA, rocket_sidesA, "
                       "rocket_finsA, rocket_topA, platform_large (a launch pad), satelliteDish",
             "gsap": "GSAP 3.15 and ScrollTrigger as globals: vendor/gsap/gsap.min.js, vendor/gsap/ScrollTrigger.min.js"}
    return "\n".join(f"- {about[k]}" for k in kits if k in about)


# -- the check in Chrome ---------------------------------------------------------------------------------------------

_HELPERS = r"""
  const frame = () => new Promise(r => requestAnimationFrame(r));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const root = document.scrollingElement || document.documentElement;
  const label = e => (e.tagName.toLowerCase() + (e.id ? '#' + e.id : '')
    + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '')).slice(0, 60);
  const els = [...document.body.querySelectorAll('*')]
    .filter(e => !['SCRIPT', 'STYLE', 'LINK', 'META', 'BR', 'TEMPLATE', 'NOSCRIPT'].includes(e.tagName)).slice(0, 1500);
  const sig = e => { const s = getComputedStyle(e); return [s.transform, s.translate, s.rotate, s.scale].join('|'); };
  const vec = e => { const t = getComputedStyle(e).transform;
    let m; try { m = new DOMMatrixReadOnly(t && t !== 'none' ? t : undefined); } catch (x) { return [0, 0, 100, 0]; }
    return [m.m41, m.m42, Math.hypot(m.m11, m.m12) * 100, Math.atan2(m.m12, m.m11) * 180 / Math.PI].map(v => Math.round(v * 100) / 100); };
  const canvases = [...document.querySelectorAll('canvas')].filter(c => c.width * c.height > 0)
    .sort((a, b) => b.width * b.height - a.width * a.height);
  const big = canvases[0] || null;
  const probe = document.createElement('canvas'); probe.width = probe.height = 48;
  const pctx = probe.getContext('2d', {willReadFrequently: true});
  // read in a frame callback after the page's own (and after scroll events): the WebGL buffer is not cleared yet
  const pixels = () => {
    try { pctx.clearRect(0, 0, 48, 48); pctx.drawImage(big, 0, 0, 48, 48); } catch (x) { return {error: String(x.message || x)}; }
    const d = pctx.getImageData(0, 0, 48, 48).data; let n = 0, sum = 0, sq = 0, h = 0; const seen = new Set();
    for (let i = 0; i < d.length; i += 4) { const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      sum += l; sq += l * l; n++; seen.add((d[i] >> 4) << 8 | (d[i + 1] >> 4) << 4 | (d[i + 2] >> 4)); h = (h * 31 + (d[i] >> 3) + (d[i + 1] >> 3) * 7 + (d[i + 2] >> 3) * 13) | 0; }
    const mean = sum / n;
    return {colours: seen.size, spread: Math.round(Math.sqrt(Math.max(0, sq / n - mean * mean)) * 10) / 10, hash: h};
  };
  // text drawn straight over the busy part of the 3D scene (the model, not the plain sky): no panel behind it, and
  // the canvas under its box varies a lot in brightness
  const panelled = e => { for (let x = e; x && x !== document.body; x = x.parentElement) {
      const c = getComputedStyle(x).backgroundColor.match(/[\d.]+/g);
      if (c && (c.length < 4 || parseFloat(c[3]) >= 0.55)) return true; } return false; };
  const clashes = () => {
    if (!big) return [];
    const r = big.getBoundingClientRect(); if (!r.width || !r.height) return [];
    const out = [];
    for (const e of document.body.querySelectorAll('h1, h2, h3, p, li, a, button')) {
      if (!e.innerText || !e.innerText.trim() || panelled(e)) continue;
      const b = e.getBoundingClientRect();
      if (b.width < 8 || b.height < 8 || b.bottom < 0 || b.top > innerHeight) continue;
      const x0 = Math.max(b.left, r.left), y0 = Math.max(b.top, r.top), x1 = Math.min(b.right, r.right), y1 = Math.min(b.bottom, r.bottom);
      if (x1 - x0 < 8 || y1 - y0 < 8) continue;
      const sx = big.width / r.width, sy = big.height / r.height;
      try { pctx.clearRect(0, 0, 48, 48);
        pctx.drawImage(big, (x0 - r.left) * sx, (y0 - r.top) * sy, (x1 - x0) * sx, (y1 - y0) * sy, 0, 0, 48, 48); }
      catch (x) { continue; }
      const d = pctx.getImageData(0, 0, 48, 48).data; let n = 0, sum = 0, sq = 0;
      for (let i = 0; i < d.length; i += 4) { const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]; sum += l; sq += l * l; n++; }
      const mean = sum / n, spread = Math.sqrt(Math.max(0, sq / n - mean * mean));
      if (spread >= CLASH_SPREAD) out.push({el: label(e), text: e.innerText.trim().slice(0, 40), spread: Math.round(spread)});
    }
    return out;
  };
"""

MEASURE = "async () => {" + _HELPERS.replace("CLASH_SPREAD", str(CLASH_SPREAD)) + r"""
  await sleep(800);  // the page's own start-up: modules, a model loading
  const max = Math.max(0, root.scrollHeight - innerHeight);
  const out = {max, width: innerWidth, height: innerHeight, canvas: big ? {width: big.width, height: big.height,
    samples: []} : null, frames: 0, seconds: 0, worst_ms: 0, moved: [], clashes: []};
  root.scrollTop = 0; await frame(); await frame();
  // frames per second while the page is scrolled from top to bottom over about two seconds
  const t0 = await frame(); let last = t0, n = 0;
  while (true) {
    const now = await frame(); const t = (now - t0) / 2000;
    out.worst_ms = Math.max(out.worst_ms, now - last); last = now; n++;
    if (t >= 1) break;
    root.scrollTop = max * t;
    if (big && n % 24 === 6) out.canvas.samples.push(pixels());
  }
  out.frames = n; out.seconds = Math.round((last - t0)) / 1000; out.worst_ms = Math.round(out.worst_ms);
  // every element's transform at five scroll positions, each settled for a moment
  const at = [];
  for (let k = 0; k < 5; k++) {
    root.scrollTop = max * k / 4; await frame(); await frame(); await sleep(180); await frame();
    if (big && out.canvas.samples.length < 8) out.canvas.samples.push(pixels());
    if (big) { await frame(); for (const c of clashes()) if (!out.clashes.some(o => o.el === c.el)) out.clashes.push({...c, at: k}); }
    at.push(els.map(vec));
  }
  els.forEach((e, i) => { const v = at.map(a => a[i]);
    if (v.some(x => x.some((c, j) => Math.abs(c - v[0][j]) > 0.5))) out.moved.push({el: label(e), at: v}); });
  out.moved = out.moved.slice(0, 60);
  root.scrollTop = 0; await frame();
  return JSON.stringify(out);
}"""

STILL = "async () => {" + _HELPERS.replace("CLASH_SPREAD", str(CLASH_SPREAD)) + r"""
  await sleep(800);
  const max = Math.max(0, root.scrollHeight - innerHeight);
  const snap = () => els.map(sig);
  const read = () => big ? frame().then(() => pixels()) : Promise.resolve(null);
  const a = snap(), pa = await read(); await sleep(1500); const b = snap(), pb = await read();
  const overTime = els.filter((e, i) => a[i] !== b[i]).map(label);
  root.scrollTop = max / 2; await frame(); await frame(); await sleep(400);
  const c = snap();
  const onScroll = els.filter((e, i) => b[i] !== c[i]).map(label);
  // what a person reads: every heading, paragraph, item, link and button with text must be there to see
  const seen = e => { if (e.closest('[aria-hidden="true"]')) return true;
    let o = 1; for (let x = e; x && x.nodeType === 1; x = x.parentElement) { const s = getComputedStyle(x);
      if (s.visibility === 'hidden' && x === e) return false; o *= parseFloat(s.opacity || '1'); }
    return o >= 0.2; };
  const texts = [...document.body.querySelectorAll('h1, h2, h3, h4, p, li, a, button, dd, td')]
    .filter(e => e.innerText && e.innerText.trim() && e.getClientRects().length);
  const hidden = texts.filter(e => !seen(e)).map(label);
  root.scrollTop = 0;
  return JSON.stringify({overTime: overTime.length, overTimeEls: overTime.slice(0, 8), onScroll: onScroll.length,
    onScrollEls: onScroll.slice(0, 8), texts: texts.length, hidden: hidden.length, hiddenEls: hidden.slice(0, 8),
    canvasChanged: !!(pa && pb && !pa.error && pa.hash !== pb.hash), max});
}"""

SCROLL_TO = "async () => { const r = document.scrollingElement || document.documentElement; " \
            "r.scrollTop = Math.max(0, r.scrollHeight - innerHeight) * %s; " \
            "await new Promise(x => requestAnimationFrame(() => requestAnimationFrame(x))); " \
            "await new Promise(x => setTimeout(x, 350)); return r.scrollTop; }"


def _value(link, fn: str) -> dict:
    from camr_engine.agentic.plugins import _result

    got = link.call("browser_evaluate", {"function": fn})
    try:
        out = json.loads(_result(got.get("text", "")))
        return out if isinstance(out, dict) else {"error": f"the check returned {str(out)[:200]}"}
    except ValueError:
        return {"error": f"the check could not be read: {str(got.get('text'))[:300]}"}


def console_errors(link) -> list[str]:
    """Chrome's error messages since the page was last loaded."""
    msgs = link.call("browser_console_messages", {"level": "error"})
    out = []
    for x in str(msgs.get("text", "")).splitlines():
        x = x.strip()
        if re.match(r"^-?\s*\[(ERROR|error)\]", x) or ("Error" in x and not x.startswith(("Total", "###"))):
            x = x.strip("- ").strip()
            if "favicon.ico" not in x and x not in out:
                out.append(x[:300])
    return out[:10]


def _saved(text: str, cwd=None) -> str | None:
    """Where Playwright says it saved a screenshot ("[Screenshot of viewport](./x.png)", relative to its folder)."""
    m = re.search(r"\]\(([^)\s]+\.png)\)", text or "") or re.search(r"(/[^\s)\]`'\"]+\.png)", text or "")
    if not m:
        return None
    p = Path(m.group(1))
    return str(p if p.is_absolute() else Path(cwd or Path.cwd()) / p)


def chrome_motion(link, url: str, want: set[str], width: int = 1280, height: int = 800) -> dict:
    """The page at ``url`` measured in Playwright's Chrome, then marked: {measured, still, console, strip, rules,
    failed}. ``strip`` lists where Playwright saved each screenshot (the caller copies them into the project)."""
    link.call("browser_resize", {"width": width, "height": height})
    nav = link.call("browser_navigate", {"url": url})
    if not nav.get("ok"):
        measured = {"error": f"Playwright could not open the page: {str(nav.get('text'))[:300]}"}
        return {"measured": measured, "rules": [], "failed": [measured["error"]], "console": [], "strip": []}
    measured = _value(link, MEASURE)
    console = console_errors(link)
    strip = []
    if "strip" in want:
        for k in range(STRIP):
            link.call("browser_evaluate", {"function": SCROLL_TO % (k / (STRIP - 1))})
            # into Playwright's own folder; keep_report copies them into the project's report folder
            got = link.call("browser_take_screenshot", {"type": "png", "filename": f".playwright-mcp/camr-motion-{k}.png"})
            path = _saved(str(got.get("text", "")), getattr(link, "cwd", None))
            if path:
                strip.append(path)
    still: dict = {}
    if "reduced" in want:
        link.call("browser_emulate_media", {"reducedMotion": "reduce"})
        try:
            link.call("browser_navigate", {"url": url})
            still = _value(link, STILL)
            console += [e for e in console_errors(link) if e not in console]
        finally:
            link.call("browser_emulate_media", {"reducedMotion": "no-preference"})
    rules = score({"measured": measured, "still": still, "console": console, "strip": strip}, want)
    return {"measured": measured, "still": still, "console": console, "strip": strip, "rules": rules,
            "failed": [f"motion check, {r['rule']}: {r['text']}" for r in rules if not r["ok"]]}


# -- marking, by rule ------------------------------------------------------------------------------------------------

def rates(moved: list[dict], scrolled: float) -> list[tuple[str, float]]:
    """For each element that moved, how much its transform changed per 1000 px scrolled (translation in px, scale in
    %, rotation in degrees, all added up along the five positions)."""
    out = []
    for m in moved or []:
        v = m.get("at") or []
        total = sum(abs(b[j] - a[j]) for a, b in zip(v, v[1:]) for j in range(min(len(a), len(b))))
        if total > MOVED:
            out.append((str(m.get("el", "?")), round(total * 1000 / max(scrolled, 1.0), 2)))
    return out


def layers(moved: list[dict], scrolled: float) -> tuple[int, list[tuple[str, float]]]:
    """How many different rates the moving elements change at: rates within SAME_RATE of each other are one layer."""
    got = sorted(rates(moved, scrolled), key=lambda x: x[1])
    groups: list[list[tuple[str, float]]] = []
    for name, r in got:
        if groups and r <= groups[-1][0][1] * (1 + SAME_RATE) + 0.5:
            groups[-1].append((name, r))
        else:
            groups.append([(name, r)])
    return len(groups), [g[0] for g in groups]


def score(result: dict, want: set[str]) -> list[dict]:
    """Each wanted rule marked from the numbers: {rule, ok, value, text}. Pure: no browser."""
    m, still = result.get("measured") or {}, result.get("still") or {}
    out = []

    def mark(rule, ok, value, text):
        out.append({"rule": rule, "ok": bool(ok), "value": value, "text": text})

    broken = m.get("error")
    for rule in RULES:
        if rule not in want:
            continue
        if broken and rule != "console":
            mark(rule, False, None, f"the page could not be measured ({broken})")
            continue
        if rule == "canvas":
            c = m.get("canvas")
            samples = [s for s in (c or {}).get("samples", []) if isinstance(s, dict) and "colours" in s]
            if not c:
                mark(rule, False, None, "there is no canvas: the 3D scene is not on the page")
            elif not samples:
                errs = [s.get("error") for s in c.get("samples", []) if isinstance(s, dict) and s.get("error")]
                mark(rule, False, None, "the canvas could not be read" + (f": {errs[0]}" if errs else ""))
            else:
                best = max(samples, key=lambda s: (s["colours"], s["spread"]))
                ok = best["colours"] >= MIN_COLOURS and best["spread"] >= MIN_SPREAD
                mark(rule, ok, {"colours": best["colours"], "spread": best["spread"]},
                     f"the canvas draws {best['colours']} colour{'s' if best['colours'] != 1 else ''}, brightness spread "
                     f"{best['spread']}" + (
                         "" if ok else f": one flat colour, nothing is drawn (wanted at least {MIN_COLOURS} colours "
                                       f"and a spread of {MIN_SPREAD:g})"))
        elif rule == "fps":
            secs = float(m.get("seconds") or 0)
            fps = round(m.get("frames", 0) / secs, 1) if secs > 0 else 0.0
            ok = fps >= MIN_FPS
            mark(rule, ok, {"fps": fps, "worst_ms": m.get("worst_ms")},
                 f"{fps:g} frames a second while scrolling (slowest frame {m.get('worst_ms')} ms)" + (
                     "" if ok else f": below {MIN_FPS:g}; draw less each frame, and render only while something moves"))
        elif rule == "console":
            errs = result.get("console") or []
            mark(rule, not errs, len(errs), "the console is clean from load to the end of the scroll" if not errs else
                 f"{len(errs)} error{'s' if len(errs) != 1 else ''} in the console: " + " | ".join(errs[:3]))
        elif rule == "layers":
            if not m.get("max"):
                mark(rule, False, 0, "the page does not scroll, so no layer can move at its own speed")
                continue
            n, firsts = layers(m.get("moved") or [], float(m.get("max") or 0))
            ok = n >= MIN_LAYERS
            shown = ", ".join(f"{name} {r:g}" for name, r in firsts[:5])
            mark(rule, ok, n, f"{n} layer{'s' if n != 1 else ''} move at different speeds while scrolling"
                 + (f" ({shown} per 1000 px)" if shown else "")
                 + ("" if ok else f": wanted at least {MIN_LAYERS}, each with its own transform speed"))
        elif rule == "reduced":
            if not still or still.get("error"):
                mark(rule, False, None, "the page could not be checked with reduced motion"
                     + (f" ({still.get('error')})" if still.get("error") else ""))
                continue
            problems = []
            if still.get("overTime"):
                problems.append(f"{still['overTime']} element(s) still move over time ({', '.join(still['overTimeEls'][:3])})")
            if still.get("canvasChanged"):
                problems.append("the canvas keeps animating")
            if still.get("onScroll"):
                problems.append(f"{still['onScroll']} element(s) move with the scroll ({', '.join(still['onScrollEls'][:3])})")
            if still.get("hidden"):
                problems.append(f"{still['hidden']} of {still.get('texts')} texts are hidden "
                                f"({', '.join(still['hiddenEls'][:3])}): show the final state")
            if not still.get("texts"):
                problems.append("no text is visible")
            mark(rule, not problems, {k: still.get(k) for k in ("overTime", "onScroll", "hidden", "texts", "canvasChanged")},
                 "with reduced motion nothing moves and every text shows" if not problems else
                 "with prefers-reduced-motion: reduce, " + "; ".join(problems))
        elif rule == "clear":
            clash = m.get("clashes") or []
            shown = "; ".join(f"\u201c{c.get('text')}\u201d ({c.get('el')})" for c in clash[:3])
            mark(rule, not clash, len(clash), "no text sits on the 3D model without a panel behind it" if not clash else
                 f"{len(clash)} text(s) sit straight on the busy part of the 3D scene: {shown}; move them beside the "
                 f"model, or give them a solid panel")
        elif rule == "strip":
            n = len(result.get("strip") or [])
            mark(rule, n >= STRIP, n, f"{n} of {STRIP} screenshots down the page were saved")
    return out


REPORT_DIR = "report"


def keep_report(ws, motion: dict, page: str = "index.html") -> dict:
    """The strip copied into the project's report folder (report/motion-0.png ...) and the numbers written beside it
    (report/motion.json), through the workspace. Returns what was written, as REPORT.md reads it."""
    from camr_engine.agentic.workspace import Outside

    shots = []
    for k, src in enumerate(motion.get("strip") or []):
        try:
            data = Path(src).read_bytes()
            if data[:8] == b"\x89PNG\r\n\x1a\n":  # a screenshot, and nothing else, is copied in
                shots.append(ws.put(f"{REPORT_DIR}/motion-{k}.png", data))
        except (OSError, Outside):
            continue
    kept = {"page": page, "rules": motion.get("rules", []), "measured": _short(motion.get("measured") or {}),
            "still": motion.get("still") or {}, "console": motion.get("console") or [], "strip": shots}
    try:
        ws.write(f"{REPORT_DIR}/motion.json", json.dumps(kept, indent=1))
    except (OSError, Outside):
        pass
    return kept


def _short(measured: dict) -> dict:
    """The measurements without each moving element's five positions (the rates say it)."""
    out = {k: v for k, v in measured.items() if k != "moved"}
    if "moved" in measured:
        n, firsts = layers(measured["moved"], float(measured.get("max") or 0))
        out["layers"] = n
        out["rates"] = rates(measured["moved"], float(measured.get("max") or 0))[:20]
    return out


def read_report(ws) -> dict | None:
    """report/motion.json, when a motion check wrote one."""
    try:
        return json.loads(ws.text(f"{REPORT_DIR}/motion.json")[1])
    except Exception:  # noqa: BLE001 (none, or unreadable: no section)
        return None


def summary(motion: dict) -> list[str]:
    """One line per rule, for REPORT.md."""
    return [f"- {'pass' if r['ok'] else 'FAIL'}: {r['rule']}: {r['text']}" for r in motion.get("rules", [])]
