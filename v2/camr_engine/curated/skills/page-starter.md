---
name: page-starter
description: A complete, tested index.html and style.css for a 3D scroll page (canvas behind, depth layers, a hero with a live countdown, sections on panels beside the 3D model): copy them, then put in the brief's words
---
# index.html and style.css: start from these files

These two files passed every check with motion-starter's motion.js: the canvas sits behind, the layers move at
different speeds, every text is on a panel beside the model (never on it), and nothing hides in the calm version.
**Copy the file you are writing whole, then change only the words: every heading, sentence and number comes from
BRIEF.md, copied exactly.** Keep the ids (`scene`, `cd-days`, `cd-hours`, `cd-mins`, `cd-secs`) and the classes
(`layer`, `hero`, `panel`, `reveal`, `facts`, `countdown`): motion.js looks for them. Add or remove sections to
match the brief; give each one `class="panel"` and an id.

## index.html

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Halcyon Launch Systems</title>
  <link rel="stylesheet" href="style.css">
  <script type="importmap">{"imports": {"three": "./vendor/three/three.module.js", "three/addons/": "./vendor/three/addons/"}}</script>
</head>
<body>
  <div class="sky" aria-hidden="true">
    <div class="layer layer-glow" data-speed="0.15"></div>
    <div class="layer layer-far" data-speed="0.3"></div>
    <div class="layer layer-near" data-speed="0.6"></div>
    <div class="layer layer-haze" data-speed="0.9"></div>
  </div>
  <canvas id="scene" aria-label="A rocket on its launch pad, turning and lifting off as the page scrolls"></canvas>

  <header class="site-header">
    <a class="brand" href="#top">Halcyon</a>
    <nav><a href="#mission">Mission</a><a href="#vehicle">Vehicle</a><a href="#site">Launch site</a></nav>
  </header>

  <main id="top">
    <section class="hero" id="hero">
      <p class="kicker reveal">Halcyon Launch Systems</p>
      <h1 class="reveal">Orbit, on schedule.</h1>
      <p class="lede reveal">Reusable small-lift rockets for science and communications payloads.</p>
      <div class="countdown reveal" id="countdown" aria-live="polite">
        <span class="label">Next launch, Halcyon-7</span>
        <span class="clock"><b id="cd-days">00</b>d <b id="cd-hours">00</b>h <b id="cd-mins">00</b>m <b id="cd-secs">00</b>s</span>
        <span class="when">14 March 2027, 14:00 UTC, Pad 2</span>
      </div>
      <a class="btn reveal" href="#mission">See the mission</a>
    </section>

    <section class="panel" id="mission">
      <h2 class="reveal">The mission</h2>
      <p class="reveal">Halcyon-7 carries three weather satellites to a 550 km sun-synchronous orbit.</p>
      <ul class="facts reveal">
        <li><b>550 km</b> target orbit</li>
        <li><b>3</b> satellites</li>
        <li><b>8 min 40 s</b> to orbit</li>
      </ul>
    </section>

    <section class="panel" id="vehicle">
      <h2 class="reveal">The vehicle</h2>
      <p class="reveal">Two stages, one reusable booster, nine engines on the first stage.</p>
      <ul class="facts reveal">
        <li><b>32 m</b> tall</li>
        <li><b>1,200 kg</b> to low orbit</li>
        <li><b>9</b> engines</li>
      </ul>
    </section>

    <section class="panel" id="site">
      <h2 class="reveal">The launch site</h2>
      <p class="reveal">Pad 2, on the coast, with a clear range over open water to the east.</p>
    </section>
  </main>

  <footer class="site-footer"><p>Halcyon Launch Systems. </p></footer>

  <script src="vendor/gsap/gsap.min.js"></script>
  <script src="vendor/gsap/ScrollTrigger.min.js"></script>
  <script type="module" src="motion.js"></script>
</body>
</html>
```

## style.css

```css
:root {
  --ink: #f4f6fb;
  --dim: #aab3c5;
  --night: #050816;
  --accent: #ff6a3d;
  --panel: rgba(8, 12, 30, 0.72);
  --space: 1rem;
}

* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  background: var(--night);
  color: var(--ink);
  font: 16px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
  overflow-x: hidden;
}

/* the depth layers, back to front; each is taller than the screen so moving it never shows an edge */
.sky { position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none; }
.layer { position: absolute; left: 0; right: 0; top: -20vh; height: 160vh; will-change: transform; }
.layer-glow { background: radial-gradient(ellipse at 50% 80%, #1b2a6b 0%, #0b1030 45%, var(--night) 75%); }
.layer-far {
  background-image: radial-gradient(1px 1px at 20px 30px, #fff 50%, transparent 51%),
    radial-gradient(1px 1px at 120px 80px, #cfd8ff 50%, transparent 51%),
    radial-gradient(1px 1px at 70px 150px, #fff 50%, transparent 51%);
  background-size: 180px 180px;
  opacity: 0.6;
}
.layer-near {
  background-image: radial-gradient(2px 2px at 40px 60px, #fff 50%, transparent 51%),
    radial-gradient(1.5px 1.5px at 200px 140px, #ffe9c2 50%, transparent 51%);
  background-size: 260px 260px;
  animation: twinkle 4s ease-in-out infinite alternate;
}
.layer-haze { top: 40vh; background: linear-gradient(to top, rgba(255, 106, 61, 0.18), transparent 60%); }
@keyframes twinkle { from { opacity: 0.55; } to { opacity: 1; } }

#scene { position: fixed; inset: 0; width: 100%; height: 100%; z-index: 1; display: block; pointer-events: none; }

.site-header {
  position: fixed; top: 0; left: 0; right: 0; z-index: 3;
  display: flex; justify-content: space-between; align-items: center;
  padding: calc(var(--space) * 0.75) calc(var(--space) * 1.5);
  background: linear-gradient(to bottom, rgba(5, 8, 22, 0.9), transparent);
}
.brand { color: var(--ink); font-weight: 700; letter-spacing: 0.08em; text-decoration: none; text-transform: uppercase; }
.site-header nav { display: flex; gap: var(--space); }
.site-header nav a { color: var(--dim); text-decoration: none; font-size: 0.9rem; }

main { position: relative; z-index: 2; }
.hero { min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 6rem 1.5rem 3rem; max-width: 36rem; }
.kicker { color: var(--accent); text-transform: uppercase; letter-spacing: 0.12em; font-size: 0.8rem; margin: 0; }
h1 { font-size: clamp(2.4rem, 7vw, 4.5rem); line-height: 1.05; margin: 0.4rem 0; }
.lede { color: var(--dim); font-size: 1.15rem; }

.countdown { margin: 1.5rem 0; padding: 1rem 1.25rem; background: var(--panel); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 12px; }
.countdown .label { display: block; color: var(--dim); font-size: 0.85rem; }
.countdown .clock { font-variant-numeric: tabular-nums; font-size: 1.6rem; }
.countdown b { color: var(--ink); }

.btn { align-self: flex-start; background: var(--accent); color: #fff; padding: 0.7rem 1.3rem; border-radius: 999px; text-decoration: none; font-weight: 600; }

.panel { min-height: 90vh; padding: 4rem 1.5rem; max-width: 34rem; margin-right: auto; margin-left: 0; display: flex; flex-direction: column; justify-content: center; }
.panel h2 { font-size: 2rem; margin: 0 0 0.5rem; align-self: flex-start; background: var(--panel); padding: 0.4rem 1rem; border-radius: 10px; }
.panel p { color: var(--dim); background: var(--panel); padding: 0.75rem 1rem; border-radius: 10px; }
.facts { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
.facts li { background: var(--panel); border-radius: 10px; padding: 0.75rem; color: var(--dim); font-size: 0.85rem; }
.facts b { display: block; color: var(--ink); font-size: 1.2rem; }

.site-footer { position: relative; z-index: 2; padding: 3rem 1.5rem; color: var(--dim); font-size: 0.85rem; }

@media (max-width: 640px) {
  .panel { margin-right: 0; }
  .facts { grid-template-columns: 1fr; }
  .site-header nav { display: none; }
}

/* the calm version: nothing moves, everything is where it ends up */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}

.countdown .when { display: block; margin-top: 0.35rem; font-size: 0.85rem; opacity: 0.8; }
```

## Mistakes seen in real builds

- Wrong: "Headline placeholder", "Company name", "Section title", "Lorem ipsum". Right: the brief's own words.
- Wrong: a countdown written as fixed text ("126 days"). Right: the `cd-...` spans, which motion.js fills every second.
- Wrong: sections on the same side as the 3D model without a background. Right: the panels as above.
- Wrong: links to sections that do not exist. Right: every `href="#..."` names a section id on the page.
