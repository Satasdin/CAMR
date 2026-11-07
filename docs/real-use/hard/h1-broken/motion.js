// BROKEN on purpose (the motion check must catch it): the 3D scene draws nothing but its clear colour, a function
// that does not exist is called (a console error), and reduced motion is ignored.
import * as THREE from 'three';

const launch = Date.parse('2027-03-14T14:00:00Z');
const pad2 = (n) => String(n).padStart(2, '0');
function tick() {
  let s = Math.max(0, Math.floor((launch - Date.now()) / 1000));
  document.getElementById('cd-days').textContent = pad2(Math.floor(s / 86400)); s %= 86400;
  document.getElementById('cd-hours').textContent = pad2(Math.floor(s / 3600)); s %= 3600;
  document.getElementById('cd-mins').textContent = pad2(Math.floor(s / 60));
  document.getElementById('cd-secs').textContent = pad2(s % 60);
}
tick();
setInterval(tick, 1000);

const canvas = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas });
renderer.setClearColor(0x0b1030, 1);  // flat: the rocket was never added to the scene
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, innerWidth / innerHeight, 0.1, 100);
renderer.setSize(innerWidth, innerHeight, false);

gsap.registerPlugin(ScrollTrigger);
document.querySelectorAll('.layer').forEach((layer) => {
  gsap.to(layer, { y: -Number(layer.dataset.speed) * innerHeight * 0.5, ease: 'none',
    scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true } });
});
document.querySelectorAll('.panel, .hero').forEach((section) => {
  gsap.from(section.querySelectorAll('.reveal'), { y: 40, opacity: 0, duration: 0.7, stagger: 0.08,
    scrollTrigger: { trigger: section, start: 'top 80%', toggleActions: 'play none none reverse' } });
});
renderer.setAnimationLoop(() => renderer.render(scene, camera));

startTelemetry();  // never defined: a ReferenceError in the console
