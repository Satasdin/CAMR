// The stage's renderer: instanced unit quads drawn additively on black with WebGL, then the lit part only drawn again
// at quarter resolution, blurred (9-tap separable Gaussian, sigma 2 CSS px) and added back at 0.35 (DIRECTION.md,
// "Rendering"). Marks keep sharp edges: coverage is a smoothstep over one device pixel. Brightness decays in the
// shader from each instance's event time, so an event writes only the instances it touches. Without WebGL the same
// instances are drawn with Canvas 2D ('lighter', no halo).
//
// Three instance kinds, each a Float32Array with a fixed layout (see RECT, DOT and SEG below):
// - rects: tiles, cells, desk spans, the core block, hot tiles, rings and outlines;
// - dots: vault notes;
// - segs: beams, word threads, writes and doors.
// Colours come from the palette uniform, read from tokens.css at start (palette.js); there is none here.

// rect: x y w h | radius outline flags baseChan | base flareChan tEvent halfLife | peak tOn tOff drainMs |
//       revealMs dx dy moveMs
export const RECT = 20;
// dot: cx cy r flags | baseChan base flareChan tEvent | halfLife peak ringChan ringPeak
export const DOT = 12;
// seg: x0 y0 x1 y1 | width flags c0 c1 | base peak tStart tLand | tDecay halfLife dash spare
export const SEG = 16;

// rect flags (bits)
export const F = { PLATE: 1, DASHED: 2, HATCH: 4, ROWS: 8, WATCHED: 16, STEADY: 32, FORCE_ROWS: 64, TICKS: 128 };
// seg flags
export const S = { PLATE0: 1, PLATE1: 2, DASHED: 4 };
export const NEVER = 1e9;

const BIT = `float bit(float f, float k) { return mod(floor(f / pow(2.0, k) + 0.001), 2.0); }`;

const RECT_VS = `
precision highp float;
attribute vec2 q;
attribute vec4 a0, a1, a2, a3, a4;
uniform vec2 size; uniform vec3 view; uniform float now; uniform vec3 pal[12];
varying vec2 vLocal, vSize, vScreen; varying vec4 v1, v2, v3; varying float vReveal; varying vec3 vBase, vFlare;
${BIT}
void main() {
  vec4 r = a0;
  float mt = a4.w > 0.0 ? clamp((now - a3.y) / a4.w, 0.0, 1.0) : 1.0;
  r.xy += a4.yz * (1.0 - mt);
  if (bit(a1.z, 0.0) > 0.5) { r.xy = r.xy * view.x + view.yz; r.zw *= view.x; }
  vec2 p = r.xy - 1.0 + q * (r.zw + 2.0);
  vLocal = p - r.xy; vSize = r.zw; vScreen = p; v1 = a1; v2 = a2; v3 = a3; vReveal = a4.x;
  vBase = pal[int(a1.w + 0.5)]; vFlare = pal[int(a2.y + 0.5)];
  vec2 n = p / size * 2.0 - 1.0;
  gl_Position = vec4(n.x, -n.y, 0.0, 1.0);
}`;

const RECT_FS = `
precision highp float;
uniform float now, px, litOnly, reduced; uniform vec4 clip;
varying vec2 vLocal, vSize, vScreen; varying vec4 v1, v2, v3; varying float vReveal; varying vec3 vBase, vFlare;
${BIT}
void main() {
  float rad = min(v1.x, 0.5 * min(vSize.x, vSize.y)); float ol = v1.y; float flags = v1.z;
  vec2 hs = vSize * 0.5;
  vec2 d = abs(vLocal - hs) - (hs - rad);
  float sd = length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - rad;
  float cov = clamp(0.5 - sd / px, 0.0, 1.0);
  if (vSize.x < px || vSize.y < px) cov *= min(vSize.x, vSize.y) / px;
  if (ol > 0.0) {
    cov *= clamp(0.5 + (sd + ol) / px, 0.0, 1.0);
    if (bit(flags, 1.0) > 0.5) {
      float along = abs(d.x) > abs(d.y) ? vLocal.y : vLocal.x;
      if (mod(along, 6.0) >= 3.0) cov = 0.0;
    }
  } else if (bit(flags, 2.0) > 0.5) {
    if (mod(vLocal.x + vLocal.y, 3.0) >= 1.0) cov *= 0.0;
  }
  float rowLit = 1.0;
  if (ol == 0.0 && (bit(flags, 3.0) > 0.5 || bit(flags, 6.0) > 0.5)) {
    float h = vSize.y; float rows = 0.0; float gap = px;
    if (bit(flags, 6.0) > 0.5) { rows = 28.0; gap = 1.0; }
    else if (h >= 14.0 && h / 28.0 >= 2.0 * px) rows = 28.0;
    else if (h >= 7.0 && h / 7.0 >= 2.0 * px) rows = 7.0;
    if (rows > 0.0) {
      float rh = h / rows; float ri = floor(vLocal.y / rh);
      if (ri > 0.0 && vLocal.y - ri * rh < gap) cov = 0.0;
      if (bit(flags, 4.0) > 0.5) {
        if (rows > 7.5) rowLit = (ri == 12.0 || ri == 16.0 || ri == 20.0 || ri == 24.0) ? 1.0 : 0.0;
        else rowLit = ri >= 3.0 ? 1.0 : 0.0;
      }
    }
  }
  if (bit(flags, 7.0) > 0.5 && ol == 0.0) {   // one column every 4 px (the core's 8-token columns)
    if (mod(vLocal.x, 4.0) >= 3.0) cov = 0.0;
  }
  float vis = now >= v3.y ? 1.0 : 0.0;
  if (vReveal > 0.0 && vis > 0.0) {
    float prog = clamp((now - v3.y) / vReveal, 0.0, 1.0);
    if (vLocal.x > prog * vSize.x + 0.5) vis = 0.0;
  }
  if (now > v3.z) vis *= clamp(1.0 - (now - v3.z) / max(v3.w, 1.0), 0.0, 1.0);
  if (bit(flags, 0.0) > 0.5 && (vScreen.x < clip.x || vScreen.y < clip.y || vScreen.x > clip.z || vScreen.y > clip.w)) vis = 0.0;
  float fl = 0.0; float hl = v2.w; float dt = now - v2.z;
  if (bit(flags, 5.0) > 0.5) fl = v3.x;
  else if (hl > 0.0 && dt >= 0.0) fl = reduced > 0.5 ? (dt < 600.0 ? v3.x : 0.0) : v3.x * exp2(-dt / hl);
  fl *= rowLit;
  float base = v2.x;
  vec3 c = litOnly > 0.5 ? vFlare * max(0.0, fl - base) : max(vBase * base, vFlare * fl);
  gl_FragColor = vec4(c * cov * vis, 1.0);
}`;

const DOT_VS = `
precision highp float;
attribute vec2 q;
attribute vec4 a0, a1, a2;
uniform vec2 size; uniform vec3 view; uniform vec3 pal[12];
varying vec2 vLocal, vScreen; varying float vR, vPlate; varying vec4 v1, v2; varying vec3 vBase, vFlare, vRing;
${BIT}
void main() {
  vec2 c = a0.xy; float r = a0.z;
  vPlate = bit(a0.w, 0.0);
  if (vPlate > 0.5) { c = c * view.x + view.yz; }
  vec2 p = c + (q * 2.0 - 1.0) * (r + 1.5);
  vLocal = p - c; vR = r; vScreen = p; v1 = a1; v2 = a2;
  vBase = pal[int(a1.x + 0.5)]; vFlare = pal[int(a1.z + 0.5)]; vRing = pal[int(a2.z + 0.5)];
  vec2 n = p / size * 2.0 - 1.0;
  gl_Position = vec4(n.x, -n.y, 0.0, 1.0);
}`;

const DOT_FS = `
precision highp float;
uniform float now, px, litOnly, reduced; uniform vec4 clip;
varying vec2 vLocal, vScreen; varying float vR, vPlate; varying vec4 v1, v2; varying vec3 vBase, vFlare, vRing;
void main() {
  float d = length(vLocal);
  float fill = clamp(0.5 - (d - vR) / px, 0.0, 1.0);
  float ring = clamp(0.5 - (d - vR - 1.0) / px, 0.0, 1.0) * clamp(0.5 + (d - vR) / px, 0.0, 1.0);
  float fl = 0.0; float dt = now - v1.w; float hl = v2.x;
  if (hl < 0.0) fl = v2.y;
  else if (hl > 0.0 && dt >= 0.0) fl = reduced > 0.5 ? (dt < 600.0 ? v2.y : 0.0) : v2.y * exp2(-dt / hl);
  float base = v1.y;
  vec3 c = litOnly > 0.5 ? vFlare * max(0.0, fl - base) * fill : max(vBase * base, vFlare * fl) * fill;
  c += vRing * v2.w * ring * (litOnly > 0.5 ? 0.0 : 1.0);
  if (vPlate > 0.5 && (vScreen.x < clip.x || vScreen.y < clip.y || vScreen.x > clip.z || vScreen.y > clip.w)) c *= 0.0;
  gl_FragColor = vec4(c, 1.0);
}`;

const SEG_VS = `
precision highp float;
attribute vec2 q;
attribute vec4 a0, a1, a2, a3;
uniform vec2 size; uniform vec3 view; uniform vec3 pal[12];
varying vec2 vP; varying vec4 vEnds; varying vec4 v1, v2, v3; varying vec3 vC0, vC1;
${BIT}
void main() {
  vec2 p0 = a0.xy, p1 = a0.zw;
  if (bit(a1.y, 0.0) > 0.5) p0 = p0 * view.x + view.yz;
  if (bit(a1.y, 1.0) > 0.5) p1 = p1 * view.x + view.yz;
  vec2 dir = p1 - p0; float len = max(length(dir), 0.001); dir /= len;
  vec2 nrm = vec2(-dir.y, dir.x);
  float hw = max(a1.x, 1.0) * 0.5 + 1.0;
  vec2 p = p0 + dir * ((q.x * (len + 2.0 * hw)) - hw) + nrm * ((q.y * 2.0 - 1.0) * hw);
  vP = p; vEnds = vec4(p0, p1); v1 = a1; v2 = a2; v3 = a3;
  vC0 = pal[int(a1.z + 0.5)]; vC1 = pal[int(a1.w + 0.5)];
  vec2 n = p / size * 2.0 - 1.0;
  gl_Position = vec4(n.x, -n.y, 0.0, 1.0);
}`;

const SEG_FS = `
precision highp float;
uniform float now, px, litOnly, reduced;
varying vec2 vP; varying vec4 vEnds; varying vec4 v1, v2, v3; varying vec3 vC0, vC1;
${BIT}
void main() {
  vec2 p0 = vEnds.xy, p1 = vEnds.zw; vec2 dir = p1 - p0; float len = max(length(dir), 0.001);
  float t = dot(vP - p0, dir) / (len * len);
  vec2 closest = p0 + dir * clamp(t, 0.0, 1.0);
  float dist = length(vP - closest);
  float w = v1.x; float hw = max(w, px) * 0.5;
  float cov = clamp(0.5 - (dist - hw) / px, 0.0, 1.0) * min(1.0, w / px);
  if (bit(v1.y, 2.0) > 0.5 && mod(t * len, 6.0) >= 3.0) cov = 0.0;
  float span = v2.w - v2.z;
  float head = span > 0.0 ? clamp((now - v2.z) / span, 0.0, 1.0) : (now >= v2.z ? 1.0 : 0.0);
  if (now < v2.z || t > head) cov = 0.0;
  if (reduced > 0.5) cov = (now >= v2.z && now < v3.x + 600.0) ? clamp(0.5 - (dist - hw) / px, 0.0, 1.0) * min(1.0, w / px) : 0.0;
  float b = v2.y;
  float dt = now - v3.x;
  if (reduced < 0.5 && dt > 0.0) b = v3.y > 0.0 ? v2.y * exp2(-dt / v3.y) : 0.0;
  vec3 col = mix(vC0, vC1, clamp(t, 0.0, 1.0));
  vec3 c = litOnly > 0.5 ? col * max(0.0, b - v2.x) : col * max(b, v2.x);
  gl_FragColor = vec4(c * cov, 1.0);
}`;

const FULL_VS = `
precision highp float;
attribute vec2 q; varying vec2 uv;
void main() { uv = q; gl_Position = vec4(q * 2.0 - 1.0, 0.0, 1.0); }`;

const BLUR_FS = `
precision highp float;
uniform sampler2D src; uniform vec2 step; uniform float w[5]; varying vec2 uv;
void main() {
  vec3 c = texture2D(src, uv).rgb * w[0];
  for (int i = 1; i < 5; i++) {
    c += texture2D(src, uv + step * float(i)).rgb * w[i];
    c += texture2D(src, uv - step * float(i)).rgb * w[i];
  }
  gl_FragColor = vec4(c, 1.0);
}`;

const ADD_FS = `
precision highp float;
uniform sampler2D src; uniform float gain; varying vec2 uv;
void main() { gl_FragColor = vec4(texture2D(src, uv).rgb * gain, 1.0); }`;

const KINDS = ["rects", "dyn", "segs", "beams", "dots"];
const PROGRAM_OF = { rects: "rect", dyn: "rect", segs: "seg", beams: "seg", dots: "dot" };

function compile(gl, vs, fs) {
  const make = (type, src) => {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh) || "shader did not compile");
    return sh;
  };
  const p = gl.createProgram();
  gl.attachShader(p, make(gl.VERTEX_SHADER, vs));
  gl.attachShader(p, make(gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) || "program did not link");
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  const uniforms = {};
  for (let i = 0; i < n; i++) {
    const u = gl.getActiveUniform(p, i);
    const name = u.name.replace(/\[0\]$/, "");
    uniforms[name] = gl.getUniformLocation(p, u.name);
  }
  const attribs = {};
  for (const a of ["q", "a0", "a1", "a2", "a3", "a4"]) attribs[a] = gl.getAttribLocation(p, a);
  return { p, uniforms, attribs };
}

// Plain WebGL 1 with ANGLE_instanced_arrays. (regl is vendored, but it builds its draw commands with new Function,
// which the page's script-src 'self' policy refuses; this does the same few calls by hand.)
export class Renderer {
  constructor(canvas, palette) {
    this.canvas = canvas;
    this.palette = palette;
    this.flat = false;
    this.counts = { rects: 0, dyn: 0, dots: 0, segs: 0, beams: 0 };
    this.arrays = { rects: null, dyn: null, dots: null, segs: null, beams: null };
    let gl = null, ext = null;
    try {
      const probe = document.createElement("canvas").getContext("webgl");
      if (probe && probe.getExtension("ANGLE_instanced_arrays")) {
        gl = canvas.getContext("webgl", { antialias: false, alpha: false, premultipliedAlpha: false, preserveDrawingBuffer: false, depth: false, stencil: false });
        ext = gl && gl.getExtension("ANGLE_instanced_arrays");
      }
      probe?.getExtension("WEBGL_lose_context")?.loseContext();
    } catch { gl = null; }
    if (!gl || !ext) {
      this.flat = true;
      this.ctx = canvas.getContext("2d");
      return;
    }
    this.gl = gl;
    this.ext = ext;
    try {
      this.init();
    } catch (e) {
      console.error(e);
      this.gl = null;
      this.flat = true;
      const fresh = canvas.cloneNode(false); // a canvas that held WebGL cannot give a 2D context
      canvas.replaceWith(fresh);
      this.canvas = fresh;
      this.ctx = fresh.getContext("2d");
      return;
    }
    canvas.addEventListener("webglcontextlost", (ev) => { ev.preventDefault(); this.lost = true; });
    canvas.addEventListener("webglcontextrestored", () => {
      this.lost = false;
      this.init();
      for (const k of KINDS) this.caps[k] = 0;
      for (const k of KINDS) if (this.arrays[k]) this.set(k, this.arrays[k], this.counts[k]);
      if (this.w) this.resize(this.w, this.h, this.dpr);
    });
  }

  init() {
    const gl = this.gl;
    this.programs = {
      rect: compile(gl, RECT_VS, RECT_FS), dot: compile(gl, DOT_VS, DOT_FS), seg: compile(gl, SEG_VS, SEG_FS),
      blur: compile(gl, FULL_VS, BLUR_FS), add: compile(gl, FULL_VS, ADD_FS),
    };
    this.quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1]), gl.STATIC_DRAW);
    this.buffers = {};
    this.caps = {};
    for (const k of KINDS) { this.buffers[k] = gl.createBuffer(); this.caps[k] = 0; }
    this.targets = [this.target(4, 4), this.target(4, 4)];
  }

  target(w, h) {
    const gl = this.gl;
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, w, h, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) {
      gl.texParameteri(gl.TEXTURE_2D, k, v);
    }
    const fbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return { tex, fbo, w, h };
  }

  set(kind, array, count) {
    this.arrays[kind] = array;
    this.counts[kind] = count;
    if (this.flat || this.lost) return;
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[kind]);
    if (array.length > this.caps[kind]) {
      gl.bufferData(gl.ARRAY_BUFFER, array, gl.DYNAMIC_DRAW);
      this.caps[kind] = array.length;
    } else if (count) {
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, array.subarray(0, count * this.width(kind)));
    }
  }

  update(kind, from, to, count = this.counts[kind]) { // instances [from, to) changed; count is how many there are now
    this.counts[kind] = count;
    if (this.flat || this.lost || to <= from) return;
    const n = this.width(kind);
    if (to * n > this.caps[kind]) { this.set(kind, this.arrays[kind], this.counts[kind]); return; }
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[kind]);
    gl.bufferSubData(gl.ARRAY_BUFFER, from * n * 4, this.arrays[kind].subarray(from * n, to * n));
  }

  width(kind) { return kind === "dots" ? DOT : kind === "segs" || kind === "beams" ? SEG : RECT; }

  resize(w, h, dpr) {
    this.w = w; this.h = h; this.dpr = dpr;
    const W = Math.max(1, Math.round(w * dpr)), H = Math.max(1, Math.round(h * dpr));
    if (this.canvas.width !== W || this.canvas.height !== H) { this.canvas.width = W; this.canvas.height = H; }
    if (this.flat || this.lost) return;
    const gw = Math.max(1, Math.round(W / 4)), gh = Math.max(1, Math.round(H / 4));
    const gl = this.gl;
    for (const t of this.targets) {
      gl.bindTexture(gl.TEXTURE_2D, t.tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gw, gh, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
      t.w = gw; t.h = gh;
    }
    const sigma = Math.max(0.5, (2 * dpr) / 4); // 2 CSS px, in quarter-resolution pixels
    const ws = [0, 1, 2, 3, 4].map((i) => Math.exp(-(i * i) / (2 * sigma * sigma)));
    const sum = ws[0] + 2 * (ws[1] + ws[2] + ws[3] + ws[4]);
    this.weights = ws.map((x) => x / sum);
  }

  bindQuad(prog) {
    const gl = this.gl;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.enableVertexAttribArray(prog.attribs.q);
    gl.vertexAttribPointer(prog.attribs.q, 2, gl.FLOAT, false, 0, 0);
    this.ext.vertexAttribDivisorANGLE(prog.attribs.q, 0);
  }

  instances(kind, uniforms) {
    const gl = this.gl, ext = this.ext;
    const prog = this.programs[PROGRAM_OF[kind]];
    gl.useProgram(prog.p);
    this.bindQuad(prog);
    const n = this.width(kind);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffers[kind]);
    const used = [];
    for (let k = 0; k < Math.ceil(n / 4); k++) {
      const loc = prog.attribs[`a${k}`];
      if (loc < 0) continue;
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, n * 4, k * 16);
      ext.vertexAttribDivisorANGLE(loc, 1);
      used.push(loc);
    }
    const u = prog.uniforms;
    gl.uniform2f(u.size, this.w, this.h);
    gl.uniform3f(u.view, ...uniforms.view);
    gl.uniform1f(u.now, uniforms.now);
    gl.uniform1f(u.px, 1 / this.dpr);
    gl.uniform1f(u.litOnly, uniforms.litOnly);
    gl.uniform1f(u.reduced, uniforms.reduced);
    if (u.clip) gl.uniform4f(u.clip, ...uniforms.clip);
    gl.uniform3fv(u.pal, this.palFlat);
    ext.drawArraysInstancedANGLE(gl.TRIANGLES, 0, 6, this.counts[kind]);
    for (const loc of used) { ext.vertexAttribDivisorANGLE(loc, 0); gl.disableVertexAttribArray(loc); }
  }

  full(name, target, set) {
    const gl = this.gl;
    const prog = this.programs[name];
    gl.useProgram(prog.p);
    this.bindQuad(prog);
    set(prog.uniforms);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
  }

  draw({ now, view = [1, 0, 0], clip = [0, 0, 1e6, 1e6], reduced = false, halo = true, blank = false }) {
    if (this.flat) return this.drawFlat({ now, view, clip, reduced, blank });
    if (this.lost) return;
    const gl = this.gl;
    const W = this.canvas.width, H = this.canvas.height;
    if (!this.palFlat) this.palFlat = new Float32Array(Array.from({ length: 12 }, (_, i) => this.palette.list[i] || [0, 0, 0]).flat());
    gl.disable(gl.DEPTH_TEST);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, W, H);
    gl.clearColor(0, 0, 0, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    if (blank) return;
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE);
    const pass = (litOnly) => {
      for (const kind of KINDS) if (this.counts[kind]) this.instances(kind, { now, view, clip, litOnly, reduced: reduced ? 1 : 0 });
    };
    pass(0);
    if (!halo) return;
    const [glow, tmp] = this.targets;
    gl.bindFramebuffer(gl.FRAMEBUFFER, glow.fbo);
    gl.viewport(0, 0, glow.w, glow.h);
    gl.clear(gl.COLOR_BUFFER_BIT);
    pass(1);
    gl.disable(gl.BLEND);
    const w = this.weights;
    const blur = (src, dst, step) => {
      gl.bindFramebuffer(gl.FRAMEBUFFER, dst.fbo);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, src.tex);
      this.full("blur", dst, (u) => { gl.uniform1i(u.src, 0); gl.uniform2f(u.step, ...step); gl.uniform1fv(u.w, w); });
    };
    blur(glow, tmp, [1 / glow.w, 0]);
    blur(tmp, glow, [0, 1 / glow.h]);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, W, H);
    gl.enable(gl.BLEND);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, glow.tex);
    this.full("add", null, (u) => { gl.uniform1i(u.src, 0); gl.uniform1f(u.gain, 0.35); });
  }

  // -- Canvas 2D: the same instances, the same brightness, no halo

  drawFlat({ now, view, clip, reduced, blank }) {
    const c = this.ctx, d = this.dpr;
    const pal = this.palette.list;
    const shade = (k, b) => {
      const p = pal[Math.round(k)] || [0, 0, 0];
      const f = Math.max(0, Math.min(1, b));
      return `color(srgb ${(p[0] * f).toFixed(4)} ${(p[1] * f).toFixed(4)} ${(p[2] * f).toFixed(4)})`;
    };
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.globalCompositeOperation = "source-over";
    c.fillStyle = shade(11, 1); // --void
    c.fillRect(0, 0, this.canvas.width, this.canvas.height);
    if (blank) return;
    c.setTransform(d, 0, 0, d, 0, 0);
    c.globalCompositeOperation = "lighter";
    const decay = (t, hl, peak) => (hl < 0 ? peak : hl > 0 && now >= t ? (reduced ? (now - t < 600 ? peak : 0) : peak * 2 ** (-(now - t) / hl)) : 0);
    const inClip = (x, y) => x >= clip[0] && y >= clip[1] && x <= clip[2] && y <= clip[3];
    for (const kind of ["rects", "dyn"]) {
      const a = this.arrays[kind];
      for (let i = 0; i < this.counts[kind]; i++) {
        const o = i * RECT;
        let [x, y, w, h] = [a[o], a[o + 1], a[o + 2], a[o + 3]];
        const flags = a[o + 6];
        if (now < a[o + 13]) continue;
        const mt = a[o + 19] > 0 ? Math.min(1, Math.max(0, (now - a[o + 13]) / a[o + 19])) : 1;
        x += a[o + 17] * (1 - mt); y += a[o + 18] * (1 - mt);
        if (flags & F.PLATE) { x = x * view[0] + view[1]; y = y * view[0] + view[2]; w *= view[0]; h *= view[0]; if (!inClip(x, y)) continue; }
        let vis = now > a[o + 14] ? Math.max(0, 1 - (now - a[o + 14]) / Math.max(1, a[o + 15])) : 1;
        if (a[o + 16] > 0) w *= Math.min(1, Math.max(0, (now - a[o + 13]) / a[o + 16]));
        const fl = flags & F.STEADY ? a[o + 12] : decay(a[o + 10], a[o + 11], a[o + 12]);
        const useFlare = fl > a[o + 8];
        const col = shade(useFlare ? a[o + 9] : a[o + 7], (useFlare ? fl : a[o + 8]) * vis);
        if (a[o + 5] > 0) { c.strokeStyle = col; c.lineWidth = a[o + 5]; c.strokeRect(x + a[o + 5] / 2, y + a[o + 5] / 2, w - a[o + 5], h - a[o + 5]); }
        else { c.fillStyle = col; c.fillRect(x, y, w, h); }
      }
    }
    for (const kind of ["segs", "beams"]) {
    const s = this.arrays[kind];
    for (let i = 0; i < this.counts[kind]; i++) {
      const o = i * SEG;
      if (now < s[o + 10]) continue;
      let [x0, y0, x1, y1] = [s[o], s[o + 1], s[o + 2], s[o + 3]];
      const fl = s[o + 5];
      if (fl & S.PLATE0) { x0 = x0 * view[0] + view[1]; y0 = y0 * view[0] + view[2]; }
      if (fl & S.PLATE1) { x1 = x1 * view[0] + view[1]; y1 = y1 * view[0] + view[2]; }
      const span = s[o + 11] - s[o + 10];
      const head = span > 0 ? Math.min(1, (now - s[o + 10]) / span) : 1;
      const b = now > s[o + 12] ? (s[o + 13] > 0 ? s[o + 9] * 2 ** (-(now - s[o + 12]) / s[o + 13]) : 0) : s[o + 9];
      c.strokeStyle = shade(s[o + 7], Math.max(b, s[o + 8]));
      c.lineWidth = Math.max(0.5, s[o + 4]);
      c.setLineDash(fl & S.DASHED ? [3, 3] : []);
      c.beginPath(); c.moveTo(x0, y0); c.lineTo(x0 + (x1 - x0) * head, y0 + (y1 - y0) * head); c.stroke();
    }
    }
    c.setLineDash([]);
    const p = this.arrays.dots;
    for (let i = 0; i < this.counts.dots; i++) {
      const o = i * DOT;
      let [x, y] = [p[o], p[o + 1]];
      if (p[o + 3] & 1) { x = x * view[0] + view[1]; y = y * view[0] + view[2]; if (!inClip(x, y)) continue; }
      const fl = decay(p[o + 7], p[o + 8], p[o + 9]);
      c.fillStyle = shade(fl > p[o + 5] ? p[o + 6] : p[o + 4], Math.max(fl, p[o + 5]));
      c.beginPath(); c.arc(x, y, p[o + 2], 0, Math.PI * 2); c.fill();
      if (p[o + 11] > 0) { c.strokeStyle = shade(p[o + 10], p[o + 11]); c.lineWidth = 1; c.stroke(); }
    }
  }

  destroy() {
    this.gl?.getExtension("WEBGL_lose_context")?.loseContext();
  }
}
