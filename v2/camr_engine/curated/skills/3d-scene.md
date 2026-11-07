---
name: 3d-scene
description: A three.js scene in motion.js from the vendored files: renderer, camera, lights, resize, a GLB model or the procedural rocket, the frame loop and clean-up
---
# A 3D scene with three.js

The page has `<canvas id="scene"></canvas>` and the import map that names `three` (see the loading HTML). Import from
the vendored files only:

```js
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { makeRocket, makePad, makeStars, disposeAll } from './vendor/camr-rocket.js';

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
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

const rocket = makeRocket(THREE, { accent: 0xff6a3d });   // always there, no file needed
scene.add(rocket, makePad(THREE), makeStars(THREE));

function render() { renderer.render(scene, camera); }
function place() {
  renderer.setSize(window.innerWidth, window.innerHeight, false);
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
}
place();
window.addEventListener('resize', () => { place(); render(); });

// a model file (optional): the page still works if it does not load
new GLTFLoader().load('vendor/models/space-kit/platform_large.glb', (gltf) => {
  scene.add(gltf.scene);
  render();
}, undefined, () => {});

if (calm) {
  render();                                  // once: a still picture
} else {
  renderer.setAnimationLoop((t) => {         // every frame
    rocket.rotation.y = t * 0.0004;          // or move it from a ScrollTrigger timeline (scroll-motion)
    render();
  });
}

window.addEventListener('pagehide', () => {
  renderer.setAnimationLoop(null);
  disposeAll(THREE, scene);
  renderer.dispose();
});
```

## Rules

- The canvas fills the screen behind the text: in the CSS, `#scene { position: fixed; inset: 0; width: 100%;
  height: 100%; z-index: 1; pointer-events: none; }`, and the content above it with `position: relative; z-index: 2`.
- Always light the scene (a hemisphere light and a directional light): MeshStandardMaterial is black without light.
- `makeRocket(THREE)` is about 4 units tall with its base at y = 0; `rocket.getObjectByName('flame').visible = true`
  shows its flame at lift-off.
- Models: `vendor/models/space-kit/` holds rocket_baseA, rocket_fuelA, rocket_sidesA, rocket_finsA, rocket_topA,
  platform_large and satelliteDish (.glb). Load with GLTFLoader and a relative path; never a URL.
- Keep it light: one renderer, at most a few thousand stars, no shadows. The page must keep 50 frames a second.
- Never call render from many places in one frame: the loop draws; outside it (calm, resize, a model loaded) call
  `render()` once.
