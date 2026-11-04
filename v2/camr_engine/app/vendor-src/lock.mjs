// The second half of build.sh: download section A (the direct files) from jsDelivr, copy every bundled package's
// licence, write the icons module, check every package was published at least two weeks before the build, and write
// LOCK.json with each file's package, version, licence, source URL and SHA-256.
//
//   node lock.mjs <build dir with node_modules and meta-*.json> <static/vendor>

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";

const [BUILD, OUT] = process.argv.slice(2);
if (!BUILD || !OUT) throw new Error("usage: node lock.mjs <build dir> <static/vendor>");
const CDN = "https://cdn.jsdelivr.net/npm/";
const CUTOFF = "2026-10-21T23:59:59Z"; // two weeks before the build night (4 Nov 2026)
const ICONS = ["play", "pause", "download", "x", "search", "chevron-right", "chevron-down", "rotate-ccw", "zoom-in",
  "zoom-out", "crosshair", "square-terminal", "file-code", "folder", "folder-open", "timer"];
const DIRECT = [
  { name: "uplot", version: "1.6.32", licence: "MIT", files: ["dist/uPlot.esm.js", "dist/uPlot.min.css"] },
  { name: "@xterm/xterm", version: "6.0.0", licence: "MIT", files: ["lib/xterm.mjs", "css/xterm.css"] },
  { name: "@xterm/addon-fit", version: "0.11.0", licence: "MIT", files: ["lib/addon-fit.mjs"] },
  { name: "@fontsource-variable/martian-mono", version: "5.3.0", licence: "OFL-1.1",
    files: ["files/martian-mono-latin-standard-normal.woff2", "files/martian-mono-latin-ext-standard-normal.woff2"] },
  { name: "@fontsource-variable/geist", version: "5.3.0", licence: "OFL-1.1",
    files: ["files/geist-latin-wght-normal.woff2", "files/geist-latin-ext-wght-normal.woff2"] },
  { name: "@fontsource-variable/geist-mono", version: "5.3.0", licence: "OFL-1.1",
    files: ["files/geist-mono-latin-wght-normal.woff2", "files/geist-mono-latin-ext-wght-normal.woff2"] },
  { name: "lucide-static", version: "1.58.0", licence: "ISC", files: ICONS.map((i) => `icons/${i}.svg`) },
];
const BUNDLES = ["ui", "regl", "codemirror", "markdown"];

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");
const save = (path, buf) => { mkdirSync(dirname(path), { recursive: true }); writeFileSync(path, buf); };

async function get(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return Buffer.from(await r.arrayBuffer());
}

const published = new Map(); // name -> its registry "time" map
async function publishedOn(name, version) {
  if (!published.has(name)) {
    const r = await fetch(`https://registry.npmjs.org/${name.replace("/", "%2F")}`);
    if (!r.ok) throw new Error(`registry ${name}: HTTP ${r.status}`);
    published.set(name, (await r.json()).time || {});
  }
  const at = published.get(name)[version];
  if (!at) throw new Error(`registry has no publish time for ${name}@${version}`);
  if (at > CUTOFF) throw new Error(`${name}@${version} was published ${at}, after ${CUTOFF}`);
  return at;
}

function licenceFile(dir) {
  const names = readdirSync(dir).filter((f) => /^(licen[cs]e|copying)(-[a-z0-9.]+)?(\.(md|txt))?$/i.test(f));
  return names.length ? join(dir, names[0]) : null;
}

const files = [];
function record(path, entry) {
  const buf = readFileSync(path);
  files.push({ path: relative(OUT, path), ...entry, bytes: buf.length, sha256: sha256(buf) });
}

// A. direct files, each with its package's licence beside it
for (const p of DIRECT) {
  const base = join(OUT, `${p.name}@${p.version}`);
  const at = await publishedOn(p.name, p.version);
  for (const f of [...p.files, "LICENSE"]) {
    const url = `${CDN}${p.name}@${p.version}/${f}`;
    save(join(base, f), await get(url));
    record(join(base, f), { package: p.name, version: p.version, licence: p.licence, published: at, source: url });
  }
}

// the icons, inlined as strings so a screen can put one in the DOM without a request
const icons = {};
for (const i of ICONS) {
  icons[i] = readFileSync(join(OUT, `lucide-static@1.58.0/icons/${i}.svg`), "utf8")
    .replace(/<!--[\s\S]*?-->/g, "").replace(/\s+/g, " ").trim();
}
save(join(OUT, "icons.js"), `// lucide-static@1.58.0 (ISC), inlined by vendor-src/lock.mjs\nexport const icons = ${JSON.stringify(icons, null, 1)};\n`);
record(join(OUT, "icons.js"), { package: "lucide-static", version: "1.58.0", licence: "ISC", source: "built by lock.mjs" });

// B. bundles: which packages each one holds (from esbuild's metafile), with their licences copied
const lock = JSON.parse(readFileSync(join(BUILD, "package-lock.json"), "utf8"));
const tree = Object.entries(lock.packages).filter(([k]) => k.startsWith("node_modules/"));
for (const [key, info] of tree) await publishedOn(key.slice("node_modules/".length), info.version);
const bundles = {};
for (const b of BUNDLES) {
  const meta = JSON.parse(readFileSync(join(BUILD, `meta-${b}.json`), "utf8"));
  const names = new Set();
  for (const input of Object.keys(meta.inputs)) {
    const m = input.match(/node_modules\/((?:@[^/]+\/)?[^/]+)\//);
    if (m) names.add(m[1]);
  }
  const packages = [];
  for (const name of [...names].sort()) {
    const info = lock.packages[`node_modules/${name}`];
    const dir = join(BUILD, "node_modules", name);
    const lic = licenceFile(dir);
    if (lic) save(join(OUT, "licenses", `${name}@${info.version}`, "LICENSE"), readFileSync(lic));
    packages.push({ name, version: info.version, licence: info.license || null,
      published: await publishedOn(name, info.version), source: info.resolved, integrity: info.integrity,
      licence_file: lic ? `licenses/${name}@${info.version}/LICENSE` : null });
  }
  bundles[`${b}.js`] = packages;
  record(join(OUT, `${b}.js`), { package: `bundle of ${packages.length} packages`, version: null,
    licence: [...new Set(packages.map((p) => p.licence))].join(" AND "), source: `vendor-src/entries/${b}.js` });
}

const esbuild = lock.packages["node_modules/esbuild"];
const out = { built: new Date().toISOString(), node: process.version, tool: `esbuild@${esbuild.version} (MIT)`,
  cutoff: CUTOFF, tree: tree.length, files, bundles };
writeFileSync(join(OUT, "LOCK.json"), JSON.stringify(out, null, 1) + "\n");
console.log(`LOCK.json: ${files.length} files, ${tree.length} packages in the tree, all published by ${CUTOFF}`);
if (!existsSync(join(OUT, "ui.js"))) throw new Error("bundles missing: run build.sh, not lock.mjs alone");
