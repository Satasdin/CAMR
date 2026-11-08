---
name: motion-starter-parts
description: A complete, tested motion.js for a 3D product page whose model comes apart into its parts as you scroll and goes back together (an exploded view), with depth layers, reveals and a calm version: copy it whole, then change only the lines marked CHANGE
---
# motion.js: start from this file

This file passed every check (canvas, 60 frames a second, a clean console, 8 layer speeds, a calm version, no text
on the model). **Write it whole with write_file, then change only the lines marked CHANGE.** It needs, in
index.html: `<canvas id="scene">`, the `.layer` divs with `data-speed`, and sections with class `panel` or `hero`
whose parts have class `reveal`. The model is made by `makeParts` from vendor/camr-parts.js out of the part names
you give it: parts named wing, panel, solar or array become side panels; the others are layers of the body, the
first on top. It has no countdown: add none unless the brief asks for one.

```js
// The satellite, the depth layers and the reveals. The model comes apart into its layers as the page scrolls and
// goes back together by the end. Calm when the person asks for reduced motion: the parts stand apart, drawn once;
// nothing moves; every section is shown as it ends up.
import * as THREE from 'three';
import { makeParts, explodeParts, makeStars, disposeAll } from './vendor/camr-parts.js';

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// -- the 3D scene
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 200);
camera.position.set(0, 0.6, 12);
camera.lookAt(0, 0, 0);
scene.add(new THREE.HemisphereLight(0xcfd8ff, 0x1a1020, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 2.4);
sun.position.set(5, 6, 8);
scene.add(sun);

const rig = new THREE.Group();  // the model, to the right of the text on a wide screen
scene.add(rig);
// the parts, outside in, as BRIEF.md names them
const model = makeParts(THREE, ['solar wings', 'radio', 'battery pack', 'flight computer', 'payload bay']);  // CHANGE: the brief's parts, in its order
model.rotation.set(0.25, -0.6, 0);
rig.add(model);
const stars = makeStars(THREE, { count: 1200 });
scene.add(stars);

function place() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  rig.position.x = w > 900 ? 3.2 : 0;
  rig.position.z = w > 900 ? 0 : -5;
}
function render() { renderer.render(scene, camera); }
place();
window.addEventListener('resize', () => { place(); render(); });

if (calm) {
  explodeParts(model, 1);  // the still: every part apart, so each one can be seen
  render();
} else {
  gsap.registerPlugin(ScrollTrigger);
  // the model turns all the way down the page, comes apart by the middle and goes back together by the end;
  // scrub ties it to the scrollbar, so scrolling back plays it backwards
  const state = { t: 0 };
  const view = gsap.timeline({
    scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true },
    onUpdate: () => explodeParts(model, state.t),
  });
  // CHANGE: what the brief asks to happen as people scroll (here: one turn, apart by the middle, together at the end)
  view.to(model.rotation, { y: Math.PI * 2 - 0.6, ease: 'none', duration: 2 }, 0)
    .to(state, { t: 1, ease: 'power1.inOut', duration: 0.9 }, 0.1)
    .to(state, { t: 0, ease: 'power1.inOut', duration: 0.9 }, 1.1);

  // the depth layers: each moves at its own speed
  document.querySelectorAll('.layer').forEach((layer) => {
    const speed = Number(layer.dataset.speed);
    gsap.to(layer, {
      y: () => -speed * window.innerHeight * 0.5, ease: 'none',
      scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true, invalidateOnRefresh: true },
    });
  });

  // every section's parts slide in as they reach the screen
  document.querySelectorAll('.panel, .hero').forEach((section) => {
    gsap.from(section.querySelectorAll('.reveal'), {
      y: 40, opacity: 0, duration: 0.7, stagger: 0.08, ease: 'power2.out',
      scrollTrigger: { trigger: section, start: 'top 80%', toggleActions: 'play none none reverse' },
    });
  });

  // a slow drift of the stars, drawn every frame
  renderer.setAnimationLoop((t) => {
    stars.rotation.y = t * 0.00002;
    render();
  });
}

window.addEventListener('pagehide', () => {
  renderer.setAnimationLoop(null);
  disposeAll(THREE, scene);
  renderer.dispose();
});
```

## To make it fit another brief

- Other parts: change only the names in `makeParts(...)`, in the order the brief gives them.
- Apart and staying apart: remove the second `.to(state, ...)` line.
- A product that is one piece: give `makeParts` one name; the turn and the layers still work.

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
