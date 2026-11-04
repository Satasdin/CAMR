#!/usr/bin/env node
// camr-memory: the CAMR engine from npm. The engine is Python (it runs its models with MLX), so this installs it the
// first time, with the same install.sh as `curl | sh` (into ~/.camr/engine), then runs its `camr` command.
//
//   npx camr-memory                          camr serve: the OpenAI-compatible endpoint with memory, port 11436
//   npx camr-memory serve --backend lmstudio
//   npx camr-memory doctor | app | ollama | bench
//   npx camr-memory install                  install or update the engine, then stop
//
// CAMR_HOME (default ~/.camr) and CAMR_SOURCE are passed on to install.sh.
"use strict";

const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const home = process.env.CAMR_HOME || path.join(os.homedir(), ".camr");
const camr = path.join(home, "engine", "bin", "camr");
// the packed copy (npm pack copies ../install.sh in), else the repository's own when run from a clone
const installer = [path.join(__dirname, "..", "install.sh"), path.join(__dirname, "..", "..", "install.sh")]
  .find((f) => fs.existsSync(f));

function install() {
  console.error(`camr-memory: installing the CAMR engine into ${path.join(home, "engine")}`);
  if (!installer) throw new Error("install.sh is missing from this package");
  const r = spawnSync("sh", [installer], { stdio: "inherit", env: process.env });
  if (r.error) throw r.error;
  return r.status === 0;
}

let args = process.argv.slice(2);
if (args[0] === "install") {
  process.exit(install() ? 0 : 1);
}
if (!fs.existsSync(camr) && !install()) {
  console.error("camr-memory: the install failed; see the lines above");
  process.exit(1);
}
if (args.length === 0) args = ["serve"];

const child = spawn(camr, args, { stdio: "inherit", env: process.env });
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => child.kill(sig)); // the engine keeps its last exchanges before it stops
}
child.on("error", (e) => {
  console.error(`camr-memory: could not start ${camr}: ${e.message}`);
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
