// Models: what fits this Mac. The gauge block is the hero: RAM to scale (other apps, the loaded weights, the
// engram's own RAM, free) with the GPU's limit marked, the disk under it, and the free RAM as one big figure. Hover or
// arrow onto a model and its footprint projects onto both bars as an outline. The list below shows each model's
// anatomy (one mark per layer: filled keeps KV and can read tensor memory, hollow is linear attention), what it needs
// here, how fast it ran here (or est. from the models that did), and its verdict. Search reaches mlx-community on
// Hugging Face through the local server; downloads fill their disk bar as bytes land.

const CONTEXT_KEY = "engram.models.context";
const LABEL_W = 132; // room right of the gauge's end for its label and any overflow

export function mount(el, api) {
  const { html, render, signal, computed, useRef, useState, useLayoutEffect } = api.ui;
  const { Val, Glyph, Icon, Empty } = api.parts;
  const { fmt } = api;
  api.css("/static/screens/models.css");

  const board = signal(null);
  const boardError = signal(null);
  const jobs = signal({ downloads: [], runtime: null });
  const context = signal(readContext());
  const query = signal("");
  const sort = signal("downloads");
  const results = signal(null); // null: not asked yet
  const searchError = signal(null);
  const searching = signal(false);
  const infos = signal({});
  const ghost = signal(null);
  const notes = signal({}); // repo -> the last action's refusal
  const probing = signal(false);
  const searchRef = { current: null };

  function readContext() {
    try { return Number(localStorage.getItem(CONTEXT_KEY)) || 8192; } catch { return 8192; }
  }

  // -- data

  async function loadBoard() {
    try {
      board.value = await api.get("/api/models", { context: context.value });
      boardError.value = null;
      jobs.value = { downloads: board.value.downloads, runtime: board.value.runtime };
    } catch (e) {
      boardError.value = e.message;
    }
  }

  async function loadJobs() {
    try { jobs.value = await api.get("/api/models/jobs"); } catch { /* the next board load says why */ }
  }

  let searchSeq = 0;
  async function search() {
    const seq = ++searchSeq;
    searching.value = true;
    try {
      const got = await api.get("/api/models/search", { q: query.value, sort: sort.value, limit: 30 });
      if (seq !== searchSeq) return;
      results.value = got.results;
      searchError.value = null;
      await fillInfos(got.results.filter((r) => !r.local).map((r) => r.repo));
    } catch (e) {
      if (seq === searchSeq) searchError.value = e.message;
    } finally {
      if (seq === searchSeq) searching.value = false;
    }
  }

  async function fillInfos(repos, fresh = false) {
    const want = repos.filter((r) => fresh || !infos.value[`${r}@${context.value}`]);
    for (let i = 0; i < want.length; i += 12) {
      try {
        const got = await api.get("/api/models/info", { repos: want.slice(i, i + 12).join(","), context: context.value });
        const next = { ...infos.value };
        for (const [repo, row] of Object.entries(got.rows)) next[`${repo}@${context.value}`] = row;
        infos.value = next;
      } catch { /* those rows keep their quick estimate */ }
    }
  }

  async function act(path, repo, body = {}) {
    try {
      await api.post(`/api/models/${path}`, { repo, context: context.value, ...body });
      notes.value = { ...notes.value, [repo]: null };
    } catch (e) {
      notes.value = { ...notes.value, [repo]: e.message };
    }
    await loadJobs();
    await loadBoard();
  }

  async function probe() {
    probing.value = true;
    try { await api.post("/api/models/probe"); } catch (e) { boardError.value = e.message; }
    probing.value = false;
    await loadBoard();
  }

  // -- polling, only while the screen is on show: the board every 5 s, jobs every second while something moves

  let timer = null;
  let ticks = 0;
  let wasBusy = false;
  function busy() {
    const j = jobs.value;
    return (j.downloads || []).some((d) => d.state === "downloading") || j.runtime?.job?.state === "loading";
  }
  async function tick() {
    ticks++;
    const now = busy();
    if (now) await loadJobs();
    if (ticks % 5 === 0 || (wasBusy && !busy())) await loadBoard();
    wasBusy = busy();
    timer = setTimeout(tick, 1000);
  }

  let searchTimer = null;
  function searchSoon() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(search, 300);
  }

  // -- the gauge block

  function useWidth() {
    const ref = useRef(null);
    const [w, setW] = useState(0);
    useLayoutEffect(() => {
      const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)));
      ro.observe(ref.current);
      return () => ro.disconnect();
    }, []);
    return [ref, w];
  }

  function rowOf(id) {
    const b = board.value;
    if (!b) return null;
    return [...b.mlx, ...b.ollama.models].find((r) => r.id === id)
      || infos.value[`${id}@${context.value}`] || null;
  }

  function RamGauge() {
    const [ref, W] = useWidth();
    const b = board.value;
    const total = b?.hardware?.ram_bytes;
    const plot = Math.max(0, W - LABEL_W);
    const x = (bytes) => (total ? (Math.max(0, bytes) / total) * plot : 0);
    const H = 48;
    const now = b?.now || {};
    const ram = b?.ram || {};
    const process = now.process_bytes || 0;
    const weights = Math.min(ram.weights_bytes || 0, process || ram.weights_bytes || 0);
    const engram = ram.engram_bytes || 0;
    const other = Math.max(0, (now.used_bytes || 0) - process);
    const runtimeRest = Math.max(0, process - weights - engram);
    const segs = [["g-other", other], ["g-other", runtimeRest], ["g-weights", weights], ["g-engram", engram]];
    let at = 0;
    const rects = segs.map(([cls, bytes]) => {
      const r = html`<rect class=${cls} x=${x(at)} y="0" width=${Math.max(0, x(at + bytes) - x(at) - (bytes ? 1 : 0))} height=${H} />`;
      at += bytes;
      return r;
    });
    const used = at;
    const g = ghost.value;
    let ghostEls = null;
    if (g?.fit && total) {
      const picked = jobs.value.runtime?.picked?.repo;
      const replaces = picked && picked !== g.repo ? (rowOf(picked)?.weights_bytes || 0) : 0;
      const start = g.loaded ? used - (g.weights_bytes || 0) : used - replaces;
      const end = start + g.fit.need_bytes;
      const wont = g.fit.verdict === "wont_run";
      const inside = Math.min(end, total);
      ghostEls = html`
        <rect class=${wont ? "g-ghost wont" : "g-ghost"} x=${x(start) + 0.5} y="0.5" width=${Math.max(0, x(inside) - x(start) - 1)} height=${H - 1} />
        ${end > total ? html`<rect class="g-over" x=${x(total) + 0.5} y="0.5" width=${Math.min(W - x(total) - 1, x(end) - x(total))} height=${H - 1} />` : null}`;
    }
    const gib = 1024 ** 3;
    const ticks = [];
    if (total) {
      for (let gb = 0; gb * gib <= total + 1; gb++) {
        const major = gb % 4 === 0;
        ticks.push(html`<line class="g-tick" x1=${x(gb * gib) + 0.5} x2=${x(gb * gib) + 0.5} y1=${H} y2=${H + (major ? 6 : 3)} />`);
        const last = (gb + 1) * gib > total + 1;
        if (major || last) {
          ticks.push(html`<text class=${last ? "g-num end" : "g-num"} x=${x(gb * gib)} y=${H + 17}
            text-anchor=${gb === 0 ? "start" : "middle"}>${last ? `${gb} GB` : gb}</text>`);
        }
      }
    }
    const limit = b?.hardware?.gpu_limit_bytes;
    return html`<div class="m-gauge" ref=${ref}>
      ${W > 0 && total ? html`<svg width=${W} height=${H + 22} role="img" aria-label=${`RAM: ${fmt.text(fmt.ram(now.used_bytes))} used of ${fmt.text(fmt.ram(total))}`}>
        <defs><pattern id="m-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line class="g-hatch" x1="0" y1="0" x2="0" y2="4" /></pattern></defs>
        <rect class="g-free" x=${x(used) + 0.5} y="0.5" width=${Math.max(0, x(total) - x(used) - 1)} height=${H - 1} />
        ${rects}
        ${limit ? html`<line class="g-limit" x1=${x(limit) + 0.5} x2=${x(limit) + 0.5} y1="-2" y2=${H + 2} />` : null}
        <line class="g-end" x1=${x(total) + 0.5} x2=${x(total) + 0.5} y1="0" y2=${H + 6} />
        ${ghostEls}
        ${ticks}
        <text class=${now.pressure === "critical" ? "g-pressure fault" : "g-pressure"} x=${W} y=${H + 17} text-anchor="end">${now.pressure || "—"}</text>
        ${limit ? html`<text class="g-limit-label" x=${x(limit) - 6} y="13" text-anchor="end">GPU LIMIT ${fmt.text(fmt.ram(limit))}</text>` : null}
      </svg>` : null}
      <div class="m-legend t-readout">
        <span><i class="sw other"></i>other apps <${Val} v=${fmt.ram(other + runtimeRest)} /></span>
        <span><i class="sw weights"></i>weights <${Val} v=${weights ? fmt.ram(weights) : ["—", ""]} /></span>
        <span><i class="sw engram"></i>engram <${Val} v=${ram.engram_bytes == null ? ["—", ""] : fmt.ram(engram)} /></span>
        <span><i class="sw free"></i>free <${Val} v=${fmt.ram(now.free_bytes)} /></span>
        <span class="m-ghost-line">${ghostLine(g)}</span>
      </div>
    </div>`;
  }

  function ghostLine(g) {
    if (!g) return html`<span class="dim">hover a model to fit it</span>`;
    if (!g.fit) return html`<span class="dim">${g.name} · measuring its files…</span>`;
    const f = g.fit;
    const ctx = `at ${fmt.text(fmt.tok(f.context))}`;
    if (f.verdict === "wont_run") {
      return html`<span class="fault-text"><${Glyph} kind="cross" /> ${g.name} won't run · needs <${Val} v=${fmt.ram(f.need_bytes - f.limit_bytes)} /> past the GPU limit ${ctx}</span>`;
    }
    if (f.spare_bytes != null && f.spare_bytes < 0) {
      return html`<span class="fault-text"><${Glyph} kind="cross" /> ${g.name} needs <${Val} v=${fmt.ram(-f.spare_bytes)} /> more ${ctx} · close other apps</span>`;
    }
    return html`<span>${g.name} fits · <${Val} v=${fmt.ram(f.spare_bytes)} /> spare ${ctx}${f.tight ? " · tight" : ""}${f.source === "est." ? html` <span class="est">est.</span>` : null}</span>`;
  }

  function DiskRail() {
    const [ref, W] = useWidth();
    const b = board.value;
    const disk = b?.hardware?.disk || {};
    const total = disk.total_bytes;
    const plot = Math.max(0, W - LABEL_W);
    const x = (bytes) => (total ? (Math.max(0, bytes) / total) * plot : 0);
    const H = 12;
    const use = b?.disk_use || {};
    const models = use.models_bytes || 0, rooms = use.rooms_bytes || 0, vault = use.vault_bytes || 0;
    const usedAll = total && disk.free_bytes != null ? total - disk.free_bytes : 0;
    const other = Math.max(0, usedAll - models - rooms - vault);
    let at = 0;
    const rects = [["d-models", models], ["d-rooms", rooms], ["d-vault", vault], ["d-other", other]].map(([cls, bytes]) => {
      const r = html`<rect class=${cls} x=${x(at)} y="0" width=${Math.max(0, x(at + bytes) - x(at) - (bytes ? 1 : 0))} height=${H} />`;
      at += bytes;
      return r;
    });
    const g = ghost.value;
    const files = g && !g.local ? Math.max(0, (g.download_bytes || g.weights_bytes || 0) - (g.disk_bytes || 0)) : 0;
    return html`<div class="m-rail" ref=${ref}>
      ${W > 0 && total ? html`<svg width=${W} height=${H} role="img" aria-label=${`SSD: ${fmt.text(fmt.bytes(disk.free_bytes))} free`}>
        <rect class="g-free" x=${x(at) + 0.5} y="0.5" width=${Math.max(0, x(total) - x(at) - 1)} height=${H - 1} />
        ${rects}
        ${files ? html`<rect class=${at + files > total ? "g-ghost wont" : "g-ghost"} x=${x(at) + 0.5} y="0.5" width=${Math.max(1, x(at + files) - x(at) - 1)} height=${H - 1} />` : null}
        <line class="g-end" x1=${x(total) + 0.5} x2=${x(total) + 0.5} y1="0" y2=${H} />
      </svg>` : null}
      <div class="m-legend t-readout">
        <span class="t-label">SSD <${Val} v=${fmt.bytes(total)} /> · <${Val} v=${fmt.bytes(disk.free_bytes)} /> free</span>
        <span><i class="sw models"></i>model files <${Val} v=${fmt.bytes(models)} /></span>
        <span><i class="sw rooms"></i>rooms <${Val} v=${use.rooms_bytes == null ? ["—", ""] : fmt.bytes(rooms)} /></span>
        <span><i class="sw vault"></i>vault <${Val} v=${use.vault_bytes == null ? ["—", ""] : fmt.bytes(vault)} /></span>
        ${files ? html`<span class="m-ghost-line">${g.name} · <${Val} v=${fmt.bytes(files)} /> to download</span>` : null}
      </div>
    </div>`;
  }

  function Cluster() {
    const hw = board.value?.hardware || {};
    const p = hw.probe;
    const cpu = hw.cpu_cores || {};
    const item = (label, value) => html`<div class="readout"><span class="t-label">${label}</span><span class="t-cluster">${value}</span></div>`;
    return html`<div class="m-cluster">
      ${item("Chip", hw.chip || "—")}
      ${item("GPU", hw.gpu_cores ? html`<${Val} v=${[hw.gpu_cores, "cores"]} />` : "—")}
      ${item("CPU", cpu.performance ? html`${cpu.performance}P + ${cpu.efficiency}E` : "—")}
      ${item("Unified RAM", html`<${Val} v=${fmt.ram(hw.ram_bytes)} />`)}
      ${item("GPU limit", hw.gpu_limit_bytes ? html`<${Val} v=${fmt.ram(hw.gpu_limit_bytes)} />` : "—")}
      <div class="readout"><span class="t-label">SSD read</span><span class="t-cluster m-probe">
        ${p ? html`<${Val} v=${fmt.gbps(p.gbps)} /> <span class="dim t-readout">${fmt.text(fmt.bytes(p.bytes))} in ${fmt.text(fmt.ms(p.seconds * 1000))}</span>` : "—"}
        <button class="btn" onClick=${probe} disabled=${probing.value || !!api.measuring.value}
          title=${api.measuring.value ? "a benchmark is measuring" : "write 256 MB past the file cache and read it back in one burst"}>
          ${probing.value ? "probing" : "probe"}</button></span></div>
    </div>`;
  }

  function Top() {
    const b = board.value;
    const free = b?.now?.free_bytes;
    return html`<div class="m-top">
      <div class="m-hero">
        <span class="t-hero"><span class="v">${fmt.ram(free)[0]}</span></span>
        <span class="t-figure u">${fmt.ram(free)[1]} free</span>
      </div>
      <${Cluster} />
      <${RamGauge} />
      <${DiskRail} />
    </div>`;
  }

  // -- the list

  function Anatomy({ layers }) {
    if (!layers?.length) return html`<span class="dim t-readout">—</span>`;
    const n = layers.length;
    const step = 120 / n;
    const w = Math.max(0.75, Math.min(2, step - 0.5));
    const kv = layers.filter((k) => k === "kv").length;
    return html`<svg class="anatomy" width="120" height="20" role="img"
      aria-label=${`${n} layers: ${kv} keep keys and values, ${n - kv} do not`}>
      ${layers.map((k, i) => {
        const x = i * step + (step - w) / 2;
        if (k === "kv") return html`<rect class="a-kv" x=${x} y="1" width=${w} height="18" />`;
        if (k === "sliding") return html`<rect class="a-sliding" x=${x} y="10" width=${w} height="9" />`;
        if (k === "linear") return html`<g class="a-linear"><rect x=${x} y="1" width=${w} height="4" /><rect x=${x} y="15" width=${w} height="4" /></g>`;
        return html`<rect class="a-none" x=${x} y="17" width=${w} height="2" />`;
      })}
    </svg>`;
  }

  function Bar({ frac, cls, outline = false, fill = null }) {
    const f = Math.max(0, Math.min(1, frac || 0));
    return html`<span class="bar ${cls}">
      <i class=${outline ? "o" : "f"} style=${{ width: `${(f * 100).toFixed(2)}%` }}></i>
      ${fill != null ? html`<i class="f" style=${{ width: `${(Math.max(0, Math.min(1, fill)) * f * 100).toFixed(2)}%` }}></i>` : null}
    </span>`;
  }

  function quickRow(r) {
    const bits = r.bits || 16;
    const per = bits >= 16 ? bits / 8 : bits / 8 + 4 / 64;
    return { id: r.repo, repo: r.repo, name: r.repo.split("/").pop(), source: "hub", local: false, quick: true,
      params: r.params, quant: { label: r.bits ? `${r.bits}-bit` : "—" }, anatomy: null, memory_as: null, fit: null,
      measured: null, weights_bytes: r.params ? r.params * per : null, download_bytes: null, disk_bytes: 0 };
  }

  function Measured({ r }) {
    const m = r.measured;
    const f = r.fit;
    if (m) {
      return html`<span class="t-readout" title=${`measured on this Mac · ${m.record} · first word on a ${m.desk_tokens}-token desk`}>
        <${Val} v=${fmt.s(m.first_word_s)} /> · <${Val} v=${fmt.tps(m.decode_tps)} /></span>`;
    }
    if (f?.decode_tps) {
      return html`<span class="t-readout est" title="estimated from the models measured on this Mac">est. ${fmt.text(fmt.s(f.first_word_s))} · ${fmt.text(fmt.tps(f.decode_tps))}</span>`;
    }
    return html`<span class="t-readout dim">not measured</span>`;
  }

  function Verdict({ r }) {
    const f = r.fit;
    if (!f) return html`<span class="t-readout dim">—</span>`;
    if (f.verdict === "wont_run") return html`<span class="t-readout fault-text" title=${f.why}><${Glyph} kind="cross" /> won't run</span>`;
    if (f.verdict === "slow") return html`<span class="t-readout v-slow" title=${f.why}><${Icon} name="timer" /> slow</span>`;
    if (f.verdict === "fits") return html`<span class="t-readout v-fits">fits${f.tight ? html`<span class="dim"> · tight</span>` : null}</span>`;
    return html`<span class="t-readout dim">—</span>`;
  }

  function Action({ r }) {
    const d = (jobs.value.downloads || []).find((x) => x.repo === r.repo);
    const rt = jobs.value.runtime || {};
    const measuring = !!api.measuring.value;
    const why = measuring ? "a benchmark is measuring" : null;
    if (r.source === "ollama") return html`<span class="t-label">via ollama</span>`;
    if (rt.job?.repo === r.repo && rt.job.state === "loading") return html`<span class="t-label">loading</span>`;
    if (rt.memory?.repo === r.repo) return html`<span class="t-label">memory reader</span>`;
    if (r.role === "embedder" && r.loaded) return html`<span class="t-label">embedder</span>`;
    if (rt.picked?.repo === r.repo) {
      return html`<button class="btn" onClick=${() => act("unload", r.repo)}>unload</button>`;
    }
    if (d?.state === "downloading") {
      return html`<button class="btn" onClick=${() => act("pause", r.repo)} title="pause"><${Icon} name="pause" /> pause</button>`;
    }
    if (r.local && r.complete) {
      const wont = r.fit?.verdict === "wont_run";
      return html`<button class="btn" onClick=${() => act("load", r.repo)} disabled=${measuring || wont || rt.job?.state === "loading"}
        title=${why || (wont ? "it needs more RAM than the GPU may use here" : "load it into this server")}><${Icon} name="play" /> load</button>`;
    }
    const label = d?.state === "paused" || (r.disk_bytes > 0 && !r.complete) ? "resume" : d?.state === "failed" ? "retry" : "download";
    return html`<button class="btn" onClick=${() => act("download", r.repo)} disabled=${measuring} title=${why || "download into the Hugging Face cache"}>
      <${Icon} name="download" /> ${label}</button>`;
  }

  function Disk({ r, total }) {
    const d = (jobs.value.downloads || []).find((x) => x.repo === r.repo);
    const size = r.download_bytes || r.weights_bytes;
    if (d && (d.state === "downloading" || d.state === "paused" || d.state === "failed")) {
      const of = d.total || size;
      const frac = of ? d.bytes / of : 0;
      return html`<div class="cell-bar">
        <${Bar} frac=${of / total} cls="disk" outline=${true} fill=${frac} />
        ${d.state === "failed"
          ? html`<span class="t-readout fault-text" title=${d.error || ""}><${Glyph} kind="cross" /> ${(d.error || "failed").slice(0, 40)}</span>`
          : d.state === "paused" ? html`<span class="t-readout dim">paused · ${fmt.text(fmt.bytes(d.bytes))}</span>`
          : html`<span class="t-readout">${d.rate_bps ? html`<${Val} v=${[fmt.num(d.rate_bps / 1e6), "MB/s"]} /> · ${fmt.duration(d.eta_s)} left` : html`<${Val} v=${fmt.bytes(d.bytes)} />`}</span>`}
      </div>`;
    }
    const here = r.local ? r.disk_bytes || r.weights_bytes : 0;
    return html`<div class="cell-bar">
      <${Bar} frac=${(r.local ? here : size || 0) / total} cls="disk" outline=${!r.local} />
      <span class="t-readout"><${Val} v=${fmt.bytes(r.local ? here : size)} />${r.local ? null : html`<span class="dim"> to fetch</span>`}</span>
    </div>`;
  }

  function Row({ r, total }) {
    const f = r.fit;
    const note = notes.value[r.repo];
    const moe = r.active_params && r.params && r.active_params < r.params * 0.8;
    return html`<div class=${`m-row${r.loaded ? " loaded" : ""}${ghost.value?.id === r.id ? " ghosted" : ""}`} tabindex="0"
      data-id=${r.id} onMouseEnter=${() => { ghost.value = r; }} onMouseLeave=${() => { ghost.value = null; }}
      onFocus=${() => { ghost.value = r; }}>
      <div class="c-name">
        <span class="t-readout name" title=${r.repo}>${r.name}</span>
        <span class="t-label">${r.quant?.label || "—"}${r.role ? ` · ${r.role}` : ""}</span>
      </div>
      <div class="c-params"><span class="t-readout"><${Val} v=${fmt.params(r.params)} /></span>${moe ? html`<span class="t-label">${fmt.text(fmt.params(r.active_params))} active</span>` : null}</div>
      <div class="c-anat"><${Anatomy} layers=${r.anatomy?.layers} /></div>
      <div class=${`c-mem t-label ${r.memory_as || ""}`}>${r.memory_as || "—"}</div>
      <div class="cell-bar c-ram">
        <${Bar} frac=${f ? f.need_bytes / total : (r.weights_bytes || 0) / total} cls=${r.loaded ? "ram loaded" : "ram"} />
        <span class="t-readout">${f ? html`<${Val} v=${fmt.ram(f.need_bytes)} />${f.source === "est." ? html` <span class="est">est.</span>` : null}`
          : r.weights_bytes ? html`<span class="est">est. ${fmt.text(fmt.ram(r.weights_bytes))}</span>` : "—"}</span>
      </div>
      <div class="c-disk"><${Disk} r=${r} total=${total} /></div>
      <div class="c-meas"><${Measured} r=${r} /></div>
      <div class="c-verdict"><${Verdict} r=${r} /></div>
      <div class="c-act">${note ? html`<span class="t-readout fault-text" title=${note}><${Glyph} kind="cross" /> ${note.slice(0, 36)}</span>` : html`<${Action} r=${r} />`}</div>
    </div>`;
  }

  function Group({ label, rows, empty, total, busy }) {
    return html`<div class="m-group" role="rowgroup" aria-label=${label}>
      <div class="m-group-label t-label">${label}${busy ? html`<span class="dim"> · searching</span>` : null}</div>
      ${rows.length ? rows.map((r) => html`<${Row} key=${r.id} r=${r} total=${total} />`) : html`<div class="m-empty">${empty}</div>`}
    </div>`;
  }

  function List() {
    const b = board.value;
    const total = b?.hardware?.ram_bytes || 1;
    const ctx = context.value;
    const local = b?.mlx || [];
    const olla = b?.ollama || { running: false, models: [] };
    const hubRows = (results.value || []).filter((r) => !r.local).map((r) => infos.value[`${r.repo}@${ctx}`] || quickRow(r))
      .map((r) => (r.error ? { ...quickRow({ repo: r.repo }), note: r.error } : r));
    const sp = b?.speeds;
    return html`<div class="m-list">
      <div class="m-tools">
        <span class="t-label">Context</span>
        <div class="seg" role="group" aria-label="Context for the RAM estimate">
          ${(b?.contexts || [2048, 8192, 32768]).map((c) => html`<button aria-pressed=${String(c === ctx)}
            onClick=${() => setContext(c)}>${c / 1024}K</button>`)}
        </div>
        <span class="t-readout dim m-speeds" title=${sp?.records?.join(", ") || ""}>
          ${sp?.records?.length ? html`speeds from ${sp.records[sp.records.length - 1]}${sp.bandwidth_bps ? html` · est. from <${Val} v=${[fmt.num(sp.bandwidth_bps / 1e9), "GB/s"]} /> read per word` : null}` : "no speed records on this Mac yet"}
        </span>
        <span class="grow"></span>
        <select class="field" aria-label="Sort Hugging Face results" value=${sort.value}
          onChange=${(e) => { sort.value = e.target.value; searchSoon(); }}>
          <option value="downloads">most downloaded</option><option value="trending">trending</option>
          <option value="likes">most liked</option><option value="modified">newest</option>
        </select>
        <label class="m-search"><${Icon} name="search" />
          <input class="field" ref=${(el) => { searchRef.current = el; }} type="search" placeholder="search mlx-community   /"
            aria-label="Search mlx-community on Hugging Face" value=${query.value}
            onInput=${(e) => { query.value = e.target.value; searchSoon(); }} />
        </label>
      </div>
      <div class="m-head t-label" role="row">
        <span>Model</span><span>Params</span><span>Anatomy</span><span>Memory as</span>
        <span>RAM at ${ctx / 1024}K</span><span>Disk</span><span>On this Mac</span><span>Verdict</span><span></span>
      </div>
      ${boardError.value ? html`<div class="m-empty fault-text"><${Glyph} kind="cross" /> ${boardError.value}</div>` : null}
      <${Group} label="MLX · on this Mac" rows=${local} total=${total}
        empty=${b ? "no MLX models on this Mac yet · search Hugging Face below to download one" : "reading this Mac"} />
      <${Group} label="Ollama" rows=${olla.models} total=${total}
        empty=${olla.running ? "ollama has no models yet" : "ollama is not running · start it to list its models"} />
      <${Group} label=${`Hugging Face · mlx-community${query.value ? ` · “${query.value}”` : ""}`} rows=${hubRows} total=${total}
        busy=${searching.value}
        empty=${searchError.value ? html`<span class="fault-text"><${Glyph} kind="cross" /> ${searchError.value}</span>`
          : results.value === null ? "asking Hugging Face" : `no mlx-community model matches “${query.value}”`} />
    </div>`;
  }

  function setContext(c) {
    context.value = c;
    try { localStorage.setItem(CONTEXT_KEY, String(c)); } catch { /* private window */ }
    loadBoard();
    fillInfos((results.value || []).filter((r) => !r.local).map((r) => r.repo));
  }

  function Screen() {
    return html`<div class="models">
      ${api.measuring.value ? html`<div class="m-measuring t-label">measuring · ${api.measuring.value.job} · loading and probing wait</div>` : null}
      <${Top} />
      <${List} />
    </div>`;
  }

  render(html`<${Screen} />`, el);

  function rows() { return [...el.querySelectorAll(".m-row")]; }

  return {
    show() {
      loadBoard();
      if (results.value === null) search();
      clearTimeout(timer);
      timer = setTimeout(tick, 1000);
    },
    hide() {
      clearTimeout(timer);
      timer = null;
      ghost.value = null;
    },
    key(e, { typing }) {
      if (e.key === "/" && !typing) { searchRef.current?.focus(); return true; }
      if (e.key === "Escape" && ghost.value && !typing) { ghost.value = null; document.activeElement?.blur?.(); return true; }
      const list = rows();
      const at = list.indexOf(document.activeElement);
      if (e.key === "ArrowDown" && (at >= 0 || document.activeElement === searchRef.current)) {
        list[Math.min(list.length - 1, at + 1)]?.focus();
        return true;
      }
      if (e.key === "ArrowUp" && at >= 0) {
        (at === 0 ? searchRef.current : list[at - 1])?.focus();
        return true;
      }
      if (e.key === "Enter" && at >= 0) {
        list[at].querySelector(".c-act button:not(:disabled)")?.click();
        return true;
      }
      return false;
    },
  };
}
