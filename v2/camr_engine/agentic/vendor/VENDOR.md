# Vendored files

Libraries and models a page may use with no network at page time. The engine copies the ones a plan needs into a
project's `vendor/` folder (camr_engine.agentic.motion.install, through the Workspace); the preview and the local page
server serve them from there and block every network address. Downloaded on 7 November 2026; nothing here is changed
from the source except the choice of files.

| Kit | Files (in this folder) | Source | Version | Size | Licence |
|---|---|---|---|---|---|
| three | `three/three.module.js`, `three/three.core.js` (the module imports the core) | npm `three` tarball (`npm pack three`), `build/` | 0.187.0 | 658,900 + 1,474,799 B | MIT (`three/LICENSE`) |
| three | `three/addons/loaders/GLTFLoader.js`, `three/addons/utils/BufferGeometryUtils.js`, `three/addons/utils/SkeletonUtils.js` (the loader's two imports) | same tarball, `examples/jsm/` | 0.187.0 | 119,861 + 39,153 + 11,535 B | MIT |
| gsap | `gsap/gsap.min.js`, `gsap/ScrollTrigger.min.js` (UMD builds: `window.gsap`, `window.ScrollTrigger`) | npm `gsap` tarball (`npm pack gsap`), `dist/` | 3.15.1 | 73,357 + 44,683 B | GreenSock Standard "no charge" licence, https://gsap.com/standard-license (`gsap/LICENSE.md`) |
| models | `models/space-kit/rocket_baseA.glb`, `rocket_fuelA.glb`, `rocket_sidesA.glb`, `rocket_finsA.glb`, `rocket_topA.glb` (a rocket in five stacking parts), `platform_large.glb` (a launch pad), `satelliteDish.glb` | Kenney "Space Kit" 2.0, https://kenney.nl/assets/space-kit (`kenney_space-kit.zip`, `Models/GLTF format/`) | 2.0 (27 Aug 2020) | 87,368 B for the seven | CC0 1.0 (`models/space-kit/License.txt`) |
| rocket model | `models/rocket/rocket.glb` (a three-stage launcher with its escape tower), `models/rocket/SOURCE.md` | NASA 3D Resources "Saturn V" (https://science.nasa.gov/3d-resources/saturn-v/), its four textures (the "USA" lettering and flags) taken out by `v2/scripts/vendor_model.py` | 14 Apr 2025 | 831,500 B | NASA 3D Resources: free and without copyright; credit NASA/Michael D. Carbajal; no NASA insignia (`models/rocket/SOURCE.md`) |
| rocket | `camr-rocket.js`: `makeRocket`, `makePad`, `makeStars`, `disposeAll` from three.js shapes (LatheGeometry body, cone, fins), so a page always has a rocket even without a model | written for CAMR | 1 | about 5 KB | MIT, as CAMR |

Downloaded archives (SHA-256): `three-0.187.0.tgz` ff540832ded0cfe919764d24a3d88f3e2a05f23303f876423e4f893841e90728,
`gsap-3.15.1.tgz` c70a3bcf656015f32b4f6456e686034564c90d64280db535cfbd84de4497d988, `kenney_space-kit.zip`
d5d7cdf2635ed5a43a9187deaf409b6f47484e402321128341d3c3698e9ef4d9.

## How a page loads them

```html
<script type="importmap">
{ "imports": { "three": "./vendor/three/three.module.js", "three/addons/": "./vendor/three/addons/" } }
</script>
<script src="vendor/gsap/gsap.min.js"></script>
<script src="vendor/gsap/ScrollTrigger.min.js"></script>
<script type="module" src="motion.js"></script>
```

In `motion.js`: `import * as THREE from 'three';`, `import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';`,
`import { loadRocket } from './vendor/camr-rocket.js';` (then `loadRocket(THREE, GLTFLoader, { onLoad: render })`),, and `gsap` and `ScrollTrigger` as globals.

Total on disk: about 3.2 MB, of which three.js is 2.3 MB and the rocket model 0.8 MB.
