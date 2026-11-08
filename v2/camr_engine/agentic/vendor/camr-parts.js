// camr-parts.js: a model made of named parts that comes apart in layers and goes back together, for a product page
// with an exploded view (a satellite, a speaker, a phone...). Part of CAMR (MIT). Pass in THREE:
//
//   import * as THREE from 'three';
//   import { makeParts, explodeParts, makeStars, disposeAll } from './vendor/camr-parts.js';
//   const model = makeParts(THREE, ['solar wings', 'radio', 'battery pack', 'flight computer', 'payload bay']);
//   scene.add(model);
//   explodeParts(model, 0);     // 0: together, as one body
//   explodeParts(model, 1);     // 1: every part apart, in layers
//
// Parts whose name has wing, panel, solar or array become two flat panels on the sides that open outwards; every
// other part is a layer of the body, in the order given (the first on top), and the layers move apart up and down.
// The model is about 3.4 units tall, centred on (0, 0, 0). Each part is a group named as given (model.getObjectByName).

export { makeStars, disposeAll } from './camr-rocket.js';

const PALETTE = [0xd9d4c7, 0x3d7bd9, 0xe0a33a, 0x5aa36b, 0xb5523b, 0x8c7ae6, 0x5fb3b3, 0xc9c9d1];

export function makeParts(THREE, names, { size = [2.2, 2.2, 3.4], gap = 0.95, colours = PALETTE } = {}) {
  const [w, d, h] = size;
  const group = new THREE.Group();
  group.name = 'parts';
  const layers = names.filter((n) => !/wing|panel|solar|array/i.test(n));
  const wings = names.filter((n) => /wing|panel|solar|array/i.test(n));
  const edge = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.35 });
  const slab = h / Math.max(layers.length, 1);

  layers.forEach((name, k) => {
    const part = new THREE.Group();
    part.name = name;
    const colour = colours[k % colours.length];
    const mat = new THREE.MeshStandardMaterial({ color: colour, metalness: 0.45, roughness: 0.45 });
    const geo = new THREE.BoxGeometry(w, slab - 0.06, d);
    const mesh = new THREE.Mesh(geo, mat);
    part.add(mesh, new THREE.LineSegments(new THREE.EdgesGeometry(geo), edge));
    const y = h / 2 - slab * (k + 0.5);
    part.userData.home = new THREE.Vector3(0, y, 0);
    part.userData.out = new THREE.Vector3(0, (layers.length - 1) / 2 - k, 0).multiplyScalar(gap);
    part.position.copy(part.userData.home);
    group.add(part);
  });

  wings.forEach((name, k) => {
    const part = new THREE.Group();
    part.name = name;
    const mat = new THREE.MeshStandardMaterial({ color: 0x1f3a7a, metalness: 0.6, roughness: 0.3,
      emissive: 0x0a1a40, emissiveIntensity: 0.4 });
    const pw = w * 1.35, ph = h * 0.82;
    const geo = new THREE.BoxGeometry(pw, ph, 0.05);
    for (const side of [-1, 1]) {
      const panel = new THREE.Group();
      panel.add(new THREE.Mesh(geo, mat), new THREE.LineSegments(new THREE.EdgesGeometry(geo), edge));
      const cells = [];  // the solar cells: a grid of lines on the panel
      for (let i = 1; i < 4; i++) cells.push(-pw / 2 + (pw * i) / 4, -ph / 2, 0.03, -pw / 2 + (pw * i) / 4, ph / 2, 0.03);
      for (let j = 1; j < 6; j++) cells.push(-pw / 2, -ph / 2 + (ph * j) / 6, 0.03, pw / 2, -ph / 2 + (ph * j) / 6, 0.03);
      const grid = new THREE.BufferGeometry();
      grid.setAttribute('position', new THREE.Float32BufferAttribute(cells, 3));
      panel.add(new THREE.LineSegments(grid, edge));
      panel.position.x = side * (w / 2 + pw / 2 + 0.06 + k * 0.1);
      part.add(panel);
    }
    part.userData.home = new THREE.Vector3(0, 0, 0);
    part.userData.out = new THREE.Vector3(0, 0, -0.6 - k * 0.3);
    part.userData.spread = 1.1;  // the panels also open outwards, each side its own way
    group.add(part);
  });
  return group;
}

// t from 0 (together) to 1 (apart). Call it from a GSAP timeline's onUpdate, then render.
export function explodeParts(group, t) {
  for (const part of group.children) {
    const { home, out, spread } = part.userData;
    if (!home) continue;
    part.position.copy(home).addScaledVector(out, t);
    if (spread) part.children.forEach((panel) => {
      const side = Math.sign(panel.position.x) || 1;
      panel.userData.x ??= panel.position.x;
      panel.position.x = panel.userData.x + side * spread * t;
    });
  }
}
