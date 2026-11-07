// The rocket, the depth layers, the reveals and the countdown. Calm when the person asks for reduced motion:
// the rocket stands on its pad, drawn once; nothing moves; every section is shown as it ends up.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { loadRocket, makePad, makeStars, disposeAll } from './vendor/camr-rocket.js';

const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// -- the countdown: text only, so it runs in the calm version too
const launch = Date.parse('2027-03-14T14:00:00Z');
const pad2 = (n) => String(n).padStart(2, '0');
const cd = {
  days: document.getElementById('cd-days'), hours: document.getElementById('cd-hours'),
  mins: document.getElementById('cd-mins'), secs: document.getElementById('cd-secs'),
};
function tick() {
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
  const flame = rocket.getObjectByName('flame');
  // the rocket turns as the page scrolls, then lifts off; scrub ties it to the scrollbar
  const flight = gsap.timeline({
    scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true },
    onUpdate: () => { flame.visible = rocket.position.y > 0.05; },
  });
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
    if (flame.visible) flame.scale.y = 0.85 + Math.sin(t * 0.03) * 0.15;
    render();
  });
}

window.addEventListener('pagehide', () => {
  renderer.setAnimationLoop(null);
  disposeAll(THREE, scene);
  renderer.dispose();
});
