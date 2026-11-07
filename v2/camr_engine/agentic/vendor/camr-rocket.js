// camr-rocket.js: a rocket, a launch pad and a star field made from three.js shapes, so a page always has a
// rocket even with no model file. Part of CAMR (MIT). Pass in THREE, so it works with any import of three.js:
//
//   import * as THREE from 'three';
//   import { makeRocket, makePad, makeStars } from './vendor/camr-rocket.js';
//   const rocket = makeRocket(THREE);            // a THREE.Group about 4 units tall, its base at y = 0
//   scene.add(rocket, makePad(THREE), makeStars(THREE));
//   rocket.getObjectByName('flame').visible = true;   // the engine's flame, hidden until lift-off
//
// Everything made here is disposed with disposeAll(THREE, rocket) when the page is done with it.
// For the detailed rocket from a model file, use loadRocket (below): same size, same 'flame', same group.

export function makeRocket(THREE, { body = 0xf2f2f2, accent = 0xd8452b, glass = 0x6fc3ff, scale = 1 } = {}) {
  const group = new THREE.Group();
  group.name = 'rocket';
  const metal = new THREE.MeshStandardMaterial({ color: body, metalness: 0.35, roughness: 0.4 });
  const paint = new THREE.MeshStandardMaterial({ color: accent, metalness: 0.2, roughness: 0.5 });

  // the body: a profile turned around the y axis (x is the radius, y the height)
  const profile = [
    [0.0, 0.0], [0.42, 0.0], [0.5, 0.25], [0.55, 0.9], [0.55, 2.4], [0.5, 2.9], [0.36, 3.35], [0.0, 3.5],
  ].map(([x, y]) => new THREE.Vector2(x, y));
  const hull = new THREE.Mesh(new THREE.LatheGeometry(profile, 48), metal);
  hull.name = 'body';
  group.add(hull);

  // the nose cone, in the accent colour
  const nose = new THREE.Mesh(new THREE.ConeGeometry(0.36, 0.7, 48), paint);
  nose.position.y = 3.55;
  nose.name = 'nose';
  group.add(nose);

  // a band and a round window
  const band = new THREE.Mesh(new THREE.CylinderGeometry(0.565, 0.565, 0.18, 48), paint);
  band.position.y = 1.0;
  group.add(band);
  const windowMat = new THREE.MeshStandardMaterial({ color: glass, emissive: glass, emissiveIntensity: 0.35 });
  const port = new THREE.Mesh(new THREE.CircleGeometry(0.16, 32), windowMat);
  port.position.set(0, 2.35, 0.552);
  group.add(port);

  // three fins, each a flat shape pushed out to a thin slab
  const fin = new THREE.Shape();
  fin.moveTo(0, 0);
  fin.lineTo(0.55, -0.15);
  fin.lineTo(0.55, 0.25);
  fin.lineTo(0, 1.0);
  fin.lineTo(0, 0);
  const finGeo = new THREE.ExtrudeGeometry(fin, { depth: 0.06, bevelEnabled: false });
  finGeo.translate(0, 0, -0.03);
  for (let i = 0; i < 3; i++) {
    const f = new THREE.Mesh(finGeo, paint);
    const a = (i / 3) * Math.PI * 2;
    f.position.set(Math.sin(a) * 0.48, 0.15, Math.cos(a) * 0.48);
    f.rotation.y = a - Math.PI / 2;
    group.add(f);
  }

  // the engine bell and its flame (hidden until lift-off)
  const bell = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.34, 0.3, 32, 1, true), metal);
  bell.position.y = -0.12;
  group.add(bell);
  const flameMat = new THREE.MeshBasicMaterial({ color: 0xffa23a, transparent: true, opacity: 0.9 });
  const flame = new THREE.Mesh(new THREE.ConeGeometry(0.3, 1.4, 24), flameMat);
  flame.rotation.x = Math.PI;
  flame.position.y = -0.95;
  flame.name = 'flame';
  flame.visible = false;
  group.add(flame);

  group.scale.setScalar(scale);
  return group;
}

// loadRocket: the detailed rocket (vendor/models/rocket/rocket.glb, a three-stage launcher with an escape tower,
// plain white and black, no markings). It returns a group at once, holding makeRocket's rocket, and puts the model
// in its place when the file has loaded, so the page can place, turn and lift the group straight away and is never
// left without a rocket. Same size as makeRocket (about 4 units tall, base at y = 0), with a 'flame' child too.
//
//   import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
//   const rocket = loadRocket(THREE, GLTFLoader, { onLoad: render });   // render once more when the model is in
//   scene.add(rocket);
export function loadRocket(THREE, GLTFLoader, { url = 'vendor/models/rocket/rocket.glb', height = 4, onLoad } = {}) {
  const group = new THREE.Group();
  group.name = 'rocket';
  const stand = makeRocket(THREE);
  stand.name = 'stand-in';
  group.add(stand);
  new GLTFLoader().load(url, (gltf) => {
    const model = gltf.scene;
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const s = height / size.y;
    model.scale.setScalar(s);
    const c = box.getCenter(new THREE.Vector3());
    model.position.set(-c.x * s, -box.min.y * s, -c.z * s);   // centred, its base on y = 0
    model.name = 'model';
    const width = Math.max(size.x, size.z) * s;
    const flameMat = new THREE.MeshBasicMaterial({ color: 0xffa23a, transparent: true, opacity: 0.9 });
    const flame = new THREE.Mesh(new THREE.ConeGeometry(width * 0.32, height * 0.4, 24), flameMat);
    flame.rotation.x = Math.PI;
    flame.position.y = -height * 0.2;
    flame.name = 'flame';
    flame.visible = stand.getObjectByName('flame').visible;   // a lift-off already under way keeps its flame
    group.remove(stand);
    disposeAll(THREE, stand);
    group.add(model, flame);
    if (onLoad) onLoad(group);
  }, undefined, () => {});   // no model: the stand-in stays
  return group;
}

export function makePad(THREE, { color = 0x3a3f4b, radius = 2.2 } = {}) {
  const pad = new THREE.Group();
  pad.name = 'pad';
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.85 });
  const deck = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius * 1.1, 0.3, 48), mat);
  deck.position.y = -0.4;
  pad.add(deck);
  const tower = new THREE.Mesh(new THREE.BoxGeometry(0.25, 4.2, 0.25), mat);
  tower.position.set(radius * 0.7, 1.75, 0);
  pad.add(tower);
  return pad;
}

export function makeStars(THREE, { count = 1500, radius = 60, size = 0.12, color = 0xffffff } = {}) {
  const positions = new Float32Array(count * 3);
  let seed = 7;  // the same sky every time: a small fixed random sequence
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < count; i++) {
    const u = rand() * 2 - 1, t = rand() * Math.PI * 2, r = radius * (0.6 + 0.4 * rand());
    const s = Math.sqrt(1 - u * u);
    positions.set([r * s * Math.cos(t), r * u, r * s * Math.sin(t)], i * 3);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const stars = new THREE.Points(geo, new THREE.PointsMaterial({ color, size, sizeAttenuation: true }));
  stars.name = 'stars';
  return stars;
}

export function disposeAll(THREE, root) {
  root.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
    for (const m of mats) m.dispose();
  });
}
