---
name: page-starter-parts
description: A complete, tested index.html and style.css for a 3D product page (canvas behind, depth layers, the product's name and facts, its parts listed in order, sections on panels beside the model): copy them, then put in the brief's words
---
# index.html and style.css: start from these files

These two files passed every check with motion-starter-parts's motion.js: the canvas sits behind, the layers move at
different speeds, every text is on a panel beside the model (never on it), and nothing hides in the calm version.
**Copy the file you are writing whole, then change only the words: every heading, sentence and number comes from
BRIEF.md, copied exactly.** Keep the id `scene` and the classes (`layer`, `hero`, `panel`, `reveal`, `facts`,
`parts`): motion.js looks for them. Add or remove sections to match the brief; give each one `class="panel"` and
an id, and make every `href="#..."` name one of them.

## index.html

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Kestrel 6U cubesat</title>
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
  <canvas id="scene" aria-label="The Kestrel 6U cubesat, coming apart into its parts and going back together as the page scrolls"></canvas>

  <header class="site-header">
    <a class="brand" href="#top">Kestrel 6U</a>
    <nav><a href="#specs">Size and power</a><a href="#parts">Parts</a></nav>
  </header>

  <main id="top">
    <section class="hero" id="hero">
      <p class="kicker reveal">Cubesat</p>
      <h1 class="reveal">Kestrel 6U</h1>
      <p class="lede reveal">10 x 22 x 34 cm, 9 kg, solar panels of 60 W.</p>
      <a class="btn reveal" href="#parts">See its parts</a>
    </section>

    <section class="panel" id="specs">
      <h2 class="reveal">Size and power</h2>
      <ul class="facts reveal">
        <li><b>10 x 22 x 34 cm</b> size</li>
        <li><b>9 kg</b> mass</li>
        <li><b>60 W</b> solar panels</li>
      </ul>
    </section>

    <section class="panel" id="parts">
      <h2 class="reveal">Its parts, outside in</h2>
      <ol class="parts reveal">
        <li>Solar wings</li>
        <li>Radio</li>
        <li>Battery pack</li>
        <li>Flight computer</li>
        <li>Payload bay</li>
      </ol>
    </section>

    <section class="panel" id="together">
      <h2 class="reveal">Back together</h2>
      <p class="reveal">Kestrel 6U: 10 x 22 x 34 cm, 9 kg.</p>
    </section>
  </main>

  <footer class="site-footer"><p>Kestrel 6U cubesat. A reference page for CAMR's hard briefs.</p></footer>

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
  --accent: #4fb3ff;
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
.layer-haze { top: 40vh; background: linear-gradient(to top, rgba(79, 179, 255, 0.14), transparent 60%); }
@keyframes twinkle { from { opacity: 0.55; } to { opacity: 1; } }

#scene { position: fixed; inset: 0; width: 100%; height: 100%; z-index: 1; display: block; pointer-events: none; }

.site-header {
  position: fixed; top: 0; left: 0; right: 0; z-index: 3;
  display: flex; justify-content: space-between; align-items: center;
  padding: calc(var(--space) * 0.75) calc(var(--space) * 1.5);
  background: rgba(5, 8, 22, 0.92);
}
.brand { color: var(--ink); font-weight: 700; letter-spacing: 0.08em; text-decoration: none; text-transform: uppercase; }
.site-header nav { display: flex; gap: var(--space); }
.site-header nav a { color: var(--dim); text-decoration: none; font-size: 0.9rem; }

main { position: relative; z-index: 2; }
.hero { min-height: 100vh; display: flex; flex-direction: column; justify-content: center; padding: 6rem 1.5rem 3rem; max-width: 36rem; }
.kicker { color: var(--accent); text-transform: uppercase; letter-spacing: 0.12em; font-size: 0.8rem; margin: 0; }
h1 { font-size: clamp(2.4rem, 7vw, 4.5rem); line-height: 1.05; margin: 0.4rem 0; }
.lede { color: var(--dim); font-size: 1.15rem; }


.btn { align-self: flex-start; background: var(--accent); color: #fff; padding: 0.7rem 1.3rem; border-radius: 999px; text-decoration: none; font-weight: 600; }

.panel { min-height: 90vh; padding: 4rem 1.5rem; max-width: 34rem; margin-right: auto; margin-left: 0; display: flex; flex-direction: column; justify-content: center; }
.panel h2 { font-size: 2rem; margin: 0 0 0.5rem; align-self: flex-start; background: var(--panel); padding: 0.4rem 1rem; border-radius: 10px; }
.panel p { color: var(--dim); background: var(--panel); padding: 0.75rem 1rem; border-radius: 10px; }
.facts { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
.facts li { background: var(--panel); border-radius: 10px; padding: 0.75rem; color: var(--dim); font-size: 0.85rem; }
.facts b { display: block; color: var(--ink); font-size: 1.2rem; }
.parts { list-style: none; counter-reset: part; padding: 0; display: grid; gap: 0.6rem; }
.parts li { counter-increment: part; background: var(--panel); border-radius: 10px; padding: 0.7rem 1rem; }
.parts li::before { content: counter(part); display: inline-block; width: 1.6rem; color: var(--accent); font-weight: 700; }

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
```

## Mistakes seen in real builds

- Wrong: a rocket, a countdown or a launch date on a page whose brief has none (copied from the rocket's starter).
  Right: only what BRIEF.md asks for; this page has no countdown.
- Wrong: the brief's own request as the headline ("A 3D model that comes apart into an exploded view..."). The
  request says what to build; the page shows the product. Right: the product's name as the headline, its facts below.
- Wrong: the headline twice (once in the hero, once more in another box). Right: one `<h1>`.
- Wrong: `const scene = ...` and later `scene = ...` again: the script stops with a TypeError. Right: make each
  thing once and change its properties.
- Wrong: panels in the middle of the screen, over the model. Right: panels on the left (`margin-right: auto;
  margin-left: 0`), the model on the right, as here.
- Wrong: placeholder words ("Product name", "Feature one", "TBA"). Right: the facts from BRIEF.md, copied exactly.
- Wrong: `gsap.from(..., { opacity: 0 })` that also runs with reduced motion on. Right: every gsap call inside `if (!calm)`.
- Wrong: a URL from the internet for three.js, GSAP or a model. Right: only the files in `vendor/`.
