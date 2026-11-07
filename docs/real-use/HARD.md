# Hard briefs: launch-site front ends (7 November 2026)

Five briefs at the level of a real product launch page: a 3D scene, motion tied to the scroll, depth layers, and a calm
version for people who ask their system for reduced motion. Each is marked by rule in Chrome (Playwright), not by a
model's opinion: the lead's own page test runs the motion check when the brief asks for motion
(camr_engine.agentic.motion), and `v2/scripts/hard.py` runs a brief with a chosen model and collects the report.

The rules, with their thresholds (all measured in Playwright's Chrome at 1280 x 800, the page served from this Mac only
with every other host blocked):

| Rule | What is measured | Pass |
|---|---|---|
| canvas | the biggest canvas, read in a frame callback after the page draws (no preserveDrawingBuffer needed), 48 x 48 | at least 8 colours and a brightness spread of 4 or more (not one flat colour) |
| fps | requestAnimationFrame frames while the page is scrolled from top to bottom over 2 s | 50 or more a second |
| console | Chrome's errors from load to the end of the scroll, and in the reduced-motion load | none |
| layers | every element's transform at five scroll positions; how much each changes per 1000 px scrolled | 3 or more different speeds (within 12% is one speed) |
| reduced | the page loaded again with prefers-reduced-motion: reduce, watched for 1.5 s, then scrolled halfway | no transform changes over time or with the scroll, the canvas still, every heading, paragraph, item, link and button visible |
| strip | screenshots at 0, 25, 50, 75 and 100% of the scroll | 5 saved in the project's report/ folder |

Which rules a brief gets is also a rule: every motion brief gets fps, console, reduced and strip; a 3D brief (or a page
with a canvas) gets canvas; a brief that says parallax, layers or depth gets layers.

The runner answers the agent's questions from the "Told" list (as a person would in the app); anything not told is
left unanswered, and the page must not make it up.

## H1: Rocket company home page

> **Brief:** A rocket company's home page: a 3D rocket that turns and lifts off as you scroll, parallax layers of sky and stars, a live countdown to the next launch, motion on every section, and a calm version when reduced motion is on.

**Told:**
- The company is Halcyon Launch Systems; its line is "Orbit, on schedule."
- The next launch is Halcyon-7, on 14 March 2027 at 14:00 UTC, from Pad 2.
- Halcyon-7 carries three weather satellites to a 550 km sun-synchronous orbit, 8 min 40 s to orbit.
- The rocket is 32 m tall, two stages, nine first-stage engines, 1,200 kg to low orbit.

**Pass rules:**
- canvas, fps, console, layers, reduced, strip (all six)
- the countdown's numbers change from one second to the next (text, so it runs in the calm version too)
- every told fact on the page; nothing that was not told

## H2: Mission-control dashboard

> **Brief:** A mission-control dashboard web page for a satellite launch: an animated 3D trajectory from the pad to orbit that draws itself as you scroll, live telemetry numbers that tick, a stage timeline that lights up in order, and a calm version with reduced motion.

**Told:**
- The mission is Halcyon-7: lift-off, max-Q at 1 min 12 s, stage separation at 2 min 40 s, orbit at 8 min 40 s.
- The target orbit is 550 km; top speed 7.6 km/s.

**Pass rules:**
- canvas, fps, console, reduced, strip
- the four stage events in order on the timeline, with their told times

## H3: Product page with an exploded view

> **Brief:** A product page for a small satellite: a 3D model that comes apart into an exploded view in layers as you scroll and comes back together, a parallax depth of panels around it, and a calm version when reduced motion is on.

**Told:**
- The product is the Kestrel 6U cubesat: 10 x 22 x 34 cm, 9 kg, solar panels of 60 W.
- Its parts, outside in: solar wings, radio, battery pack, flight computer, payload bay.

**Pass rules:**
- canvas, fps, console, layers, reduced, strip
- the five parts named on the page, in the told order

## H4: Scroll-told story with pinned sections

> **Brief:** A scroll-told story page about the first launch from a new spaceport: each chapter is pinned while its pictures and words move in layers, the scroll drives the story, with a progress bar, and a calm version when reduced motion is on.

**Told:**
- The spaceport is Saltmarsh Spaceport; its first launch was on 2 June 2026.
- The chapters: the site, the build (14 months), the night before, lift-off, orbit.

**Pass rules:**
- fps, console, layers, reduced, strip
- five chapters, each pinned (its position does not move while its contents do, measured as the strip's middle frames)
- the progress bar's width grows with the scroll

## H5: Pricing page with physics-like motion

> **Brief:** A pricing page for launch slots with physics-like motion: the price cards spring into place and wobble when the plan toggle changes, a scroll-linked depth of floating shapes, and a calm mode when reduced motion is on.

**Told:**
- Rideshare slot: $1,200 per kg, at least 5 kg. Dedicated launch: $7.5 million. Custom orbit: ask us.
- Paying yearly takes 8% off the rideshare price.

**Pass rules:**
- fps, console, layers, reduced, strip
- the toggle changes the shown rideshare price between $1,200 and $1,104 per kg
- every told price on the page; nothing that was not told

## Verified so far

The rules were checked by hand-made pages before any model ran (no MLX or Ollama run while the GPU benchmark measures):
see the H1 reference page (`docs/real-use/hard/h1-reference`, must pass every rule) and a deliberately broken one
(`docs/real-use/hard/h1-broken`: a flat canvas, a console error, no reduced-motion handling), with their numbers in the
table below. Both were copied into scratch projects (`work/scratch-hard`) with the vendored kits and checked with
`scripts/hard.py check` (Playwright MCP 0.0.84, headless Chrome, 1280 x 800, a scroll of 2,305 px), on 7 November 2026.

| Rule | Reference page | Broken page |
|---|---|---|
| canvas | pass: 43 colours, brightness spread 30.5 | FAIL: 1 colour, spread 0 (only the clear colour is drawn) |
| fps | pass: 59.5 (120 frames in 2.02 s, slowest 33 ms) | pass: 60 (121 frames in 2.02 s, slowest 17 ms) |
| console | pass: no errors | FAIL: `ReferenceError: startTelemetry is not defined` |
| layers | pass: 9 speeds (the four sky layers, 26 to 156 px per 1000 px, and the reveals) | pass: 10 speeds |
| reduced | pass: nothing moved over 1.5 s or with the scroll, 21 of 21 texts visible, canvas still | FAIL: 4 elements move over time (the spinning badge, unfinished reveals), 11 move with the scroll (the layers), 2 of 21 texts hidden |
| strip | pass: 5 screenshots in report/ | pass: 5 screenshots in report/ |

The same pages also load in the app's own shut-in preview (WKWebView at camr-page://page/, checked with the preview's
own ShutIn, ProjectFiles and ProjectPage code): the module and its three.js imports run, `vendor/.../platform_large.glb`
is served as model/gltf-binary, a path climbing out or naming a dot-file gets 404, and `https://example.com` is blocked.

No model has built a hard brief yet: `scripts/hard.py run H1 --model ...` is ready, but MLX and Ollama wait until the
GPU benchmark is done.
