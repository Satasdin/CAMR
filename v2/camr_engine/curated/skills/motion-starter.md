---
name: motion-starter
description: A complete, tested motion.js for a 3D scroll page (rocket turning and lifting off, depth layers, reveals, a live countdown, a calm version): copy it whole, then change only the lines marked CHANGE
---
# motion.js: start from this file

This file passed every check (canvas, 60 frames a second, a clean console, 9 layer speeds, a calm version, no text
on the model, a ticking countdown). **Write it whole with write_file, then change only the lines marked CHANGE.**
It needs, in index.html: `<canvas id="scene">`, the `.layer` divs with `data-speed`, sections with class `panel`
or `hero` whose parts have class `reveal`, and (for a countdown) `<b id="cd-days">`, `cd-hours`, `cd-mins`,
`cd-secs`. Remove the countdown block only if the brief has no countdown.

```js
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { loadRocket, makePad, makeStars, disposeAll } from './vendor/camr-rocket.js';

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// -- the countdown: text only, so it runs in the calm version too
const launch = Date.parse('2027-03-14T14:00:00Z');  // CHANGE: the launch time from BRIEF.md, in UTC
const pad2 = (n) => String(n).padStart(2, '0');
const cd = {
  days: document.getElementById('cd-days'), hours: document.getElementById('cd-hours'),
  mins: document.getElementById('cd-mins'), secs: document.getElementById('cd-secs'),
};
function tick() {
  if (!cd.secs) return;  // no countdown on this page
  let s = Math.max(0, Math.floor((launch - Date.now()) / 1000));
  cd.days.textContent = pad2(Math.floor(s / 86400)); s %= 86400;
  cd.hours.textContent = pad2(Math.floor(s / 3600)); s %= 3600;
  cd.mins.textContent = pad2(Math.floor(s / 60));
  cd.secs.textContent = pad2(s % 60);
}
tick();
setInterval(tick, 1000);

// -- the 3D scene
const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 200);
camera.position.set(0, 2.2, 11);
camera.lookAt(0, 2, 0);
scene.add(new THREE.HemisphereLight(0xcfd8ff, 0x1a1020, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 2.2);
sun.position.set(4, 8, 6);
scene.add(sun);

const rig = new THREE.Group();  // the rocket and its pad, to the right of the text on a wide screen
scene.add(rig);
const rocket = loadRocket(THREE, GLTFLoader, { onLoad: () => { if (calm) render(); } });  // the detailed rocket
const pad = makePad(THREE);
const stars = makeStars(THREE, { count: 1200 });
rig.add(rocket, pad);
scene.add(stars);

// the Kenney launch platform under the procedural pad (CC0); the page still works if it does not load
new GLTFLoader().load('vendor/models/space-kit/platform_large.glb', (gltf) => {
  const deck = gltf.scene;
  deck.scale.setScalar(1.6);
  const box = new THREE.Box3().setFromObject(deck);  // the model's own origin is at a corner: centre it under the pad
  const mid = box.getCenter(new THREE.Vector3());
  deck.position.set(-mid.x, -0.56 - box.max.y, -mid.z);
  rig.add(deck);
  if (calm) render();
}, undefined, () => {});

function place() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  rig.position.x = w > 900 ? 2.6 : 0;
  rig.position.z = w > 900 ? 0 : -4;
}
function render() { renderer.render(scene, camera); }
place();
window.addEventListener('resize', () => { place(); render(); });

if (calm) {
  render();  // once, the final still: the rocket on its pad
} else {
  gsap.registerPlugin(ScrollTrigger);
  // the rocket turns as the page scrolls, then lifts off; scrub ties it to the scrollbar
  const flight = gsap.timeline({
    scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true },
    // look the flame up each time: the detailed rocket replaces the stand-in (and its flame) when it loads
    onUpdate: () => { rocket.getObjectByName('flame').visible = rocket.position.y > 0.05; },
  });
  // CHANGE: what the brief asks to happen as people scroll (here: one full turn, then lift-off at 60%)
  flight.to(rocket.rotation, { y: Math.PI * 2, ease: 'none', duration: 1 })
    .to(rocket.position, { y: 14, ease: 'power2.in', duration: 1.2 }, 0.6)
    .to(camera.position, { y: 6, ease: 'none', duration: 1.2 }, 0.6);

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

  // a slow idle turn of the stars, drawn every frame
  renderer.setAnimationLoop((t) => {
    stars.rotation.y = t * 0.00002;
    const flame = rocket.getObjectByName('flame');
    if (flame.visible) flame.scale.y = 0.85 + Math.sin(t * 0.03) * 0.15;
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

- Another object instead of the rocket: keep everything else and replace the `loadRocket(...)` line with a model
  from `vendor/models/` loaded by GLTFLoader, or a group of three.js shapes (`new THREE.Mesh(new
  THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0xcccccc }))`). Move the group, never its
  children.
- An exploded view: give each part a direction and move its `position` out and back in the `flight` timeline,
  e.g. `flight.to(part.position, { y: 2 }, 0)` for each part, then `.to(part.position, { y: 0 }, 1)`.
- A path that draws itself: a `THREE.Line` from the points, with `geometry.setDrawRange(0, n)` set from the
  timeline's progress in `onUpdate`.
- A pinned chapter: add `pin: true` to that section's ScrollTrigger (see scroll-motion).

## Mistakes seen in real builds

- Wrong: `const scene = ...` and later `scene = ...` again. A const cannot be given a new value: the script stops
  with a TypeError and nothing moves. Right: make each thing once and change its properties.
- Wrong: `const flame = rocket.getObjectByName('flame')` once at the start. The detailed rocket replaces the
  stand-in when it loads, so that flame is gone. Right: look it up where it is used, as above.
- Wrong: placeholder words ("Headline placeholder", "Company name", "TBA"). Right: the facts from BRIEF.md,
  copied exactly; if a fact is missing, leave that part out.
- Wrong: text straight on top of the 3D model. Right: text on a panel (a solid background), or beside the model.
- Wrong: `gsap.from(..., { opacity: 0 })` that also runs when reduced motion is on: the text stays invisible.
  Right: every gsap call inside `if (!calm)`, as above.
- Wrong: a URL from the internet for three.js, GSAP or a model. Right: only the files in `vendor/`.
