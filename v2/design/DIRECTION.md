# The app's design: Instrument, with grafts

This is the final spec the app builders implement tonight (4 Nov 2026). It picks the **Instrument** direction
(`instrument/DIRECTION.md`) and grafts in the strongest ideas from **Phosphor** (`deck/DIRECTION.md`) and **Living**
(`living/DIRECTION.md`). The design lead decided it from Ibrahim's recorded picks while he slept. Three taste
questions are left for him at the end.

Where this file and the three proposals disagree, this file wins. Nothing here is a drawn mockup. The first render of
a real memory is the mockup.

## Scoring

Each direction was scored from 1 to 5 against his taste notes (`visual-taste-colour-means-something`,
`camr-brain-view`), the engine as it is in `v2/camr_engine/` tonight, and one night of building.

| Criterion | Instrument | Phosphor (deck) | Living |
| --- | --- | --- | --- |
| Fit with his taste | **5** | 4 | 3 |
| Shows memory moving between the SSD and RAM, and what an answer used | **5** | **5** | 4 |
| Buildable tonight as a static vanilla-JS app with vendored files | **4** | 3 | 2 |
| Distinctiveness | 4 | 3 | **5** |
| Coherence across all six screens | **5** | 4 | 4 |
| **Total** | **23** | 19 | 18 |

**Why:**
- **Instrument, fit 5:** it is the microscope he picked on 2 Nov, scored against everything on his boards:
  - one crisp specimen on true black, with a tight halo and never a wide bloom (he rejected murk);
  - five colours, each with one meaning;
  - white for selected, as in suite2p;
  - stacked trace rows with a tick per event;
  - only active parts glowing inside thin outlines;
  - "picked" and "used" as different marks.
- **Phosphor, fit 4:** the colour discipline is perfect, since colour appears only where memory is. But it is the
  densest in text: mono type everywhere, blocks, tables and a terminal frame. He rejects text-heavy layouts hard.
- **Living, fit 3:** on 2 Nov he chose the microscope over a living network, and this brings the organism back. It
  makes white mean "used", which takes white away from selection (his suite2p pick), and its tilted 3D glass planes
  risk the murk he rejected. It does give him green over red and a translucent body lit inside, which he loved.
- **Clarity, Instrument and Phosphor 5:** both draw the byte path to scale (SSD → bus → desk in RAM → the watched
  layers). Phosphor adds the strongest single idea: rooms drawn as tensors, not as a scatter of points.
- **Clarity, Living 4:** height as latency reads well, but a tilted, orbiting 3D view makes sizes and times harder to
  read exactly.
- **Buildable, Instrument 4:** it is a 2D stage, done in one small WebGL library (regl) with a four-pass halo.
- **Buildable, Phosphor 3:** three.js plus postprocessing, particles, a ⌘K palette, Warp-style blocks and sigma.
- **Buildable, Living 2:** a 3D terrarium with SDF blobs, Bézier ribbons in shaders, projected labels and camera
  moves.
- **Distinctiveness:** Living is the most original (slime-mould doors, height as latency). Instrument's lab-instrument
  metaphor is distinctive but scopes exist. Phosphor looks most like Warp, Zed and Linear.
- **Coherence, Instrument 5:** one stage component is reused in Chat, Memory and Swarm, one trace row everywhere, and
  one gauge in Models and the top strip.
- **Coherence, Phosphor and Living 4:** Phosphor's shell is coherent, but its hero idioms change on every screen.
  Living's Models and Bench drop the organism.

### What was taken from each

| From | Idea | Where it lands |
| --- | --- | --- |
| Phosphor | Tensors drawn as tensors: a room is a tile of layer rows by token columns, on the SSD and on the desk alike | The stage, the room sheet |
| Phosphor | RAM drawn to scale on a 24 GB ruler, with the weights beside the tiny camr, plus a magnified inset with its factor printed | The stage's RAM plate |
| Phosphor | Context meter on the composer: tokens in view against the whole history | Chat |
| Phosphor | Perfetto-style lanes for one answer's path, with a broken axis after the first word | Light path sheet |
| Phosphor | A bus line on every screen that flares when memory moves | Top strip |
| Phosphor | Measured or nothing ("—"), and the view pauses while a benchmark measures | Everywhere |
| Phosphor | Bench tabs, one per question in the plan, and a probe matrix; Claude always grey | Bench |
| Phosphor | A shared RAM bar showing which agent holds the RAM | Swarm |
| Living | A thick tensor beam beside a hairline thread of words: the 29,000× size gap is visible without a number | The stage |
| Living | A copy and its home: a room on the desk keeps an amber ring on its SSD tile, and nothing flies back on eviction | The stage |
| Living | Model anatomy: one mark per layer, filled for layers that keep KV and hollow for linear-attention layers | Models |
| Living | The reach as an aperture: everything outside the reaches being read dims | Chat, Memory |
| Living | Door thickness grows with use and never falls below a hairline | Vault mode |
| Living | In transit, colour is location: a read runs blue to amber across the bus | The stage, the bus line |
| Living | A real headless-browser screenshot for "the page that grows" | Bench |
| Living | The view costs under 2% of tok/s, capped at 60 fps | Frame loop |

### What was left out, and why

| Idea | Why not |
| --- | --- |
| Instrument's reach turret `CORE · ROOMS · VAULT` | The engine's reach is `session · project · agent · global` (`reach.py`), several read at once, one written |
| Instrument's four raster rows `L12 L16 L20 L24` | The answer event stores one look per word per node, averaged over the four watched layers. Four rows would claim a split that was never kept |
| Instrument's "swap between core and desk" slide | `swap.py` moves rooms between a hot shelf in RAM and the SSD; the core never swaps. The slide is kept, for RAM hits |
| Instrument's reticle | It carries no measurement |
| sigma, graphology, Observable Plot and d3 | One renderer is enough: the vault graph is drawn on the same stage at the same layout, and charts use uPlot plus plain SVG |
| Living's 3D planes, orbit and camera moves | Murk risk, the heaviest build, and the "living network" he passed over |
| Living's white for "used" and rose-red for the SSD | White stays selection, and red stays fault |
| Phosphor's ember RAM `#FF8A3D` | The amber `#FFB75E` separates better from fault red. This is taste question 1 |
| Phosphor's 220 particles per read | Decoration. One beam sized to its bytes says the same, to scale |
| Server-Sent Events | `EventSource` cannot send the `X-CAMR-Token` header the server checks. The page polls instead |

## The idea in two sentences

The memory sits on a black stage like a specimen under a microscope. Every light on it is a measured event (a room
burst-read from the SSD, tensors laid on the desk in RAM, a moment the model's attention landed on), and it glows in
the one colour that says where that memory is, then fades like phosphor.

## Principles

1. **Every light is a real event.** Nothing moves unless bytes moved or attention landed. There are no ambient
   particles, breathing glows or idle shimmer. When idle, the frame loop stops.
2. **Colour is a channel.** Five saturated colours each carry one meaning on every screen. White means selected or
   focused. Everything else is grey.
3. **Hue says where, brightness says how recently, shape says what.** No colour is ever the only cue.
4. **Nearer the word, brighter.** The lightness order follows the data path: used > RAM > SSD > vault.
5. **Picked is not used.** Moments on the desk are amber rings. Moments that drew at least 0.10 of the desk's
   attention (`events.USED`) are filled green. The gap between the two is the story the app tells.
6. **Tensors are drawn as tensors.** Rooms are layer-by-token tiles, never a cloud of points. This is not a vector
   database, and the picture must say so.
7. **Afterglow, not animation.** An event flares and decays. History reads as intensity on the specimen itself.
8. **Measured or nothing.** Every number has a unit and comes from this Mac. An unmeasured value shows `—`. An
   estimate says `est.`.
9. **One big picture per screen.** The hero render takes at least 55% of the screen at full real density. Numbers sit
   in thin strips and readout clusters around it. Text is never the hero.
10. **Quiet chrome.** Navigation and panels are grey with 1 px hairlines and never glow. There is no brand colour.
11. **The view gets out of the way of the measurement.** It never takes more than 2% of tok/s, and it pauses while a
    benchmark measures.

## Colour

### Channels: the only saturated colours

The hex values are the exact sRGB conversions of the OKLCH values, and all are inside the sRGB gamut. They were
checked tonight:
- Contrast on black is 5.2–17.4:1.
- Under simulated deuteranopia, protanopia and tritanopia (Machado 2009, full severity), every pair stays at least
  0.106 apart in OKLab.
- The closest pairs are RAM/used and SSD/vault under deuteranopia, so those pairs always differ in form as well.

| Token | Hex | OKLCH | Means | Never means | Form rule |
| --- | --- | --- | --- | --- | --- |
| `--ssd` | `#28B8E5` | `0.73 0.13 225` | On the SSD: awake rooms at rest, SSD reads and writes, model files and bytes landing on disk | info, links, brand | Room tiles; reads are beams |
| `--ram` | `#FFB75E` | `0.83 0.134 70` | In RAM now: weights, the core, the hot shelf, the desk; picked for the desk | warning | Rings and tile fills; never a green fill |
| `--used` | `#9DFFB3` | `0.92 0.14 150` | Used in this answer: attention share ≥ 0.10 at the watched layers | success, OK, online | Always filled, always with a halo |
| `--vault` | `#9D63E3` | `0.62 0.19 302` | In the vault, as words: plain-text notes, asleep rooms, memory read as text (the 4 closest moments, Ollama, the 27B), your saved fixes | AI, magic, premium | Round dots and hairline threads |
| `--fault` | `#EE333E` | `0.62 0.22 24` | Something went wrong: a false memory, a failed check, a model that won't fit, a failed download | heat, RAM, hot rooms | Always with a `×` glyph |
| `--select` | `#FFFFFF` | — | You selected or focused this | anything else | White outline, white trace row, the focus ring |

**In transit** is the only gradient in the app. A read crossing the bus runs from `--ssd` at the SSD edge to `--ram`
at the RAM edge, because where it is changes as it travels.

### Steps: one hue, several brightnesses

A step is the channel multiplied by a factor over black, in sRGB. This is what CSS `color-mix(in srgb, X n%, black)`
gives, so the DOM and the shaders match.

| Step | Factor | `--ssd` | `--ram` | `--used` | `--vault` | `--fault` | Used for |
| --- | --- | --- | --- | --- | --- | --- | --- |
| far | 8% | `#030F12` | `#140F08` | `#0D140E` | `#0D0812` | `#130405` | Outside the reaches being read (the aperture is closed) |
| rest | 22% | `#092832` | `#382815` | `#233827` | `#231632` | `#340B0E` | Exists but is not involved now: the translucent body |
| resident | 35% | `#0E4050` | `#594021` | `#37593F` | `#37234F` | `#531216` | Held in RAM, untouched (weights, core, hot shelf at rest) |
| hold | 60% | `#186E89` | `#996E38` | `#5E996B` | `#5E3B88` | `#8F1F25` | Infinite persistence; used marks after an answer |
| event | 100% | channel | channel | channel | channel | channel | The event itself, decaying to its base step |

### Neutrals

| Token | Hex | Contrast on black | Use |
| --- | --- | --- | --- |
| `--void` | `#000000` | — | Every stage, trace row and chart background |
| `--bed` | `#030506` | — | The app background around stages |
| `--s1` | `#0A0D0F` | — | Panels, sheets, the top strip |
| `--s2` | `#111417` | — | Raised controls, hover, popovers |
| `--hair` | `#1B2024` | — | 1 px hairlines, plate outlines |
| `--hair-2` | `#292F33` | — | Strong hairlines, control borders |
| `--ink-4` | `#33393E` | 1.8:1 | Grid lines, minor ticks, ceilings. Never text |
| `--ink-3` | `#737C82` | 4.9:1 | Labels, units, axes |
| `--ink-2` | `#9EA6AB` | 8.5:1 | Secondary text, structural ticks (watched layers, the 24 GB line), model compute time, Claude |
| `--ink` | `#E8ECEF` | 17.7:1 | Primary text, readout values, the first-word tick |

White is reserved for selection. Structural marks that look near-white use `--ink` or `--ink-2`, never `--select`.

### Shader values

The palette uniform takes sRGB floats in 0–1:
- `ssd` = (0.1569, 0.7216, 0.8980);
- `ram` = (1.0, 0.7176, 0.3686);
- `used` = (0.6157, 1.0, 0.7020);
- `vault` = (0.6157, 0.3882, 0.8902);
- `fault` = (0.9333, 0.2000, 0.2431);
- `select` = (1, 1, 1);
- `ink2` = (0.6196, 0.6510, 0.6706);
- `ink4` = (0.2000, 0.2235, 0.2431).

Build the uniform from `tokens.css` at start (read the custom properties with `getComputedStyle`), so there is one
source of truth.

### Glow

- **DOM:** a 1 px line in the channel colour plus one `box-shadow: 0 0 6px` of the same colour at 45%. Nothing wider,
  never stacked. Only events and the current selection glow. Text never glows.
- **Stage:** marks are drawn additively on black. A quarter-resolution halo of the *lit part only* is blurred with a
  9-tap separable Gaussian (sigma 2 CSS px) and added back at 0.35. Mark edges stay sharp at full resolution.
  Resting structure gets no halo.

## Form vocabulary

Shape says what a thing is, and hue never changes it.

| Thing | Form | Size from |
| --- | --- | --- |
| Room (conscious memory, saved KV) | A rounded tile, radius 2 px: tokens run left to right, layers run top to bottom | Width ∝ tokens (512 at most); height fixed per plate |
| Moment | A cell: the room tile's column span for that moment's tokens, with 1 px gaps between moments | Its token count |
| Core (subconscious) | A tile of 28 layer rows by its tokens, in RAM | Its tokens (about 256) |
| Desk | A tile of 28 layer rows by every token on it: header, core, room, words, question | Its tokens |
| Hot room (`swap.py` RAM tier) | A small room tile on the hot shelf in RAM | Its bytes, against the 512 MiB budget |
| Vault note | A round dot | Fixed 2 px; in vault mode its radius grows with links pointing to it |
| Door | A straight hairline between notes | Width = 0.6 + 1.4 × log2(1 + weight) px, at most 4 px, never under 0.5 px |
| SSD read | A beam along room → bus → desk | 1 px per 2 MB, at least 1 px, at most 40 px |
| Words read in | A hairline thread | Its bytes on the same scale, so it always draws at the 0.5 px floor |
| Write (remember, wake) | A dashed line, right to left | 1 px |
| Picked | An amber ring, 1.5 px | — |
| Used | A green fill with a halo | Brightness ∝ share |
| Asleep room | A dashed `--ink-4` outline with no cells | — |
| Fault | A red `×` | — |
| Selected | A white outline, and its trace row turns white | — |

## Type

All three families are OFL-1.1 and vendored as woff2 from Fontsource 5.3.0 (latin and latin-ext only).

| Family (CSS name) | Job |
| --- | --- |
| **Martian Mono** (`'Martian Mono Variable'`, `wght` 100–800, `wdth` 75–112.5 in one file) | The instrument's voice: every number, unit, label, axis and readout |
| **Geist** (`'Geist Variable'`, `wght` 100–900) | Words people read: chat, notes, buttons, headings |
| **Geist Mono** (`'Geist Mono Variable'`, `wght` 100–900) | Code only: the editor, the terminal, tool-call receipts |

Fallbacks: `ui-monospace, Menlo, monospace` and `system-ui, -apple-system, sans-serif`.

| Role token | Family | Size / line | Settings | Use |
| --- | --- | --- | --- | --- |
| `--t-label` | Martian Mono | 10.5 / 14 | `wght` 500, `font-stretch` 87.5%, uppercase, tracking +0.08em, `--ink-3` | Row labels, plate labels, key caps. One to three words |
| `--t-readout` | Martian Mono | 12 / 16 | `wght` 400, stretch 100% | Strip readouts, tooltips, chips |
| `--t-cluster` | Martian Mono | 14 / 20 | `wght` 400 | Readout clusters on a stage |
| `--t-figure` | Martian Mono | 28 / 32 | `wght` 300 | Sheet figures |
| `--t-hero` | Martian Mono | 88 / 88 | `wght` 250, stretch 112.5%, tracking −0.01em | One headline number per screen at most |
| `--t-body` | Geist | 15 / 24 | 400 | Notes, panels, buttons |
| `--t-chat` | Geist | 16 / 26 | 400, max 68 characters per line | Answers and your messages |
| `--t-head` | Geist | 22 / 28 | 550, tracking −0.01em | Sheet titles only |
| `--t-code` | Geist Mono | 13 / 20 | 400 | Editor, receipts |
| `--t-term` | Geist Mono | 12.5 / 18 | 400 | Terminal |

Rules:
- `font-variant-numeric: tabular-nums` on all Martian Mono, so live numbers never jitter.
- A unit follows its value after a thin space (U+2009), in `--ink-3`: `57.3 MB`, `3.14 GB/s`, `0.07 s`.
- Sentence case everywhere, except `--t-label`.
- Glyphs that the vendored latin subsets lack (`●`, `○`, `▲`) are drawn as inline SVG, never typed.

## Spacing and shape

| Token | Value | Use |
| --- | --- | --- |
| `--sp-1` … `--sp-8` | 4, 8, 12, 16, 24, 32, 48, 64 px | The only spacings |
| `--r-mark` | 2 px | Tiles, keys, chips, marks |
| `--r-panel` | 6 px | Panels, sheets, the composer |
| `--r-pill` | 999 px | Toggles only |
| `--strip-h` | 44 px | The top strip |
| `--row-trace` | 28 px | A trace row |
| `--row-channel` | 44 px | A Swarm channel row |
| `--row-list` | 56 px | A Models row |
| `--row-module` | 40 px | A rack module |
| `--gutter-label` | 72 px | The label column of any trace strip |
| hairline | 1 px | All borders. Boxes are rare; prefer a hairline between regions |

The reference frame is 1512 × 982 points (the 14-inch MacBook Pro default). Everything works at 1280 × 800. At 900 px
and under, each screen stacks into one column: the hero first, then its strip, then its panels as sheets.

## Motion

Motion comes from events. The layout never moves.

Brightness of any lit mark at display time `now`, for an event at `t_event`:

```
b = base + (1 - base) * 2^(-(now - t_event) / half_life)
```

`base` is the mark's resting step (far, rest, resident or hold). Half-lives are in display time.

| Event (source) | Look | Half-life |
| --- | --- | --- |
| Choose (`seconds.choose`) | The chosen room tile's outline flares `--ssd` | 400 ms |
| SSD read (`tier: "ssd"`, `read_bytes`, `seconds.fetch`) | A beam's head travels at a constant rate from the room to the desk over the measured read time × timebase, then the whole beam decays | 400 ms after landing |
| RAM hit (`tier: "ram"`) | The hot-shelf tile flares amber and its copy slides into the desk: linear, 240 ms. This is the only sliding motion in the app. The bus stays dark | 400 ms |
| Asleep (`tier: "vault"`, `asleep`) | Violet threads from the room's notes in the vault drawer to the desk's words; no beam | 600 ms |
| Woken (`seconds.wake`) | A dashed blue write from RAM to the room's tile (its notes written again), which turns solid, then the read as above | 800 ms |
| Core (`seconds.core`, `core_tokens`) | The core tile flares from resident | 400 ms |
| Lay the desk (`seconds.desk`) | The desk's room span fills amber left to right in one stroke; the words span fills hatched amber | 400 ms |
| Words in (`closest`) | Violet hairlines from the 4 closest moments' cells to the desk's words span | 600 ms |
| Each written word (`looks[i]`) | Green on each node's spans in the four watched desk rows and on its home cell on the SSD plate, brightness = that word's look at the node ÷ the word's largest look | 1.2 s |
| Used (`used`, end of answer) | Used nodes settle to green fill at the hold step with a halo; picked-only nodes keep amber rings | 4 s back to rest |
| Desk cleared (answer done) | Desk spans drain in 200 ms (linear). Nothing travels back: the SSD copy never left | — |
| Remember (`remember`) | A dashed blue line from RAM to the room, and a new cell at the room's right end (rooms are append-only) | 800 ms |
| Evict from the hot shelf (state change) | The shelf tile drains in 200 ms | — |
| Sleep (`sleep`) | The room's cells drain and its outline turns dashed `--ink-4`; its notes in the drawer get violet rings | 800 ms |
| Wake (`wake`) | The outline turns solid and its cells refill blue | 800 ms |
| False memory (`verdict: "false_memory"`) | A red `×` on that answer's strip and receipts | Stays |

- **Timebase.** Reads take tens of milliseconds. A scope-style timebase sets playback to `REAL`, `×10 SLOW` or
  `×100 SLOW` (keys `[` and `]`). The setting is always printed in the stage's bottom-right corner, for example
  `TIMEBASE ×10 SLOW`, and a chip on any slowed beam reads `18 ms · shown ×10`. It never invents a duration. Trace
  strips always run in real time.
- **Word timing.** Word `i` plays at `wait_s + i × (total_s − wait_s) / words` from the answer's metrics record. When
  no record exists, words play at 20 per second, and the stage prints `words not timed`.
- **Persistence** (key `P`):
  - `VARIABLE` is the default, using the half-lives above.
  - `INFINITE`: every mark the session touched keeps a base of `0.22 + 0.38 × min(1, log2(1 + hits) / 4)`, a heat
    map of where this session pulled from, in the same hues.
  - `OFF`: marks are lit only while their event runs.
- **Data motion is linear.** Bytes move at a constant rate, because an easing curve would lie about speed.
- **UI motion:** 120 ms fades; sheets and hovers take 160 ms on `cubic-bezier(0.2, 0, 0, 1)`. There are no springs or
  bounces. Changing screen is a cut.
- **Reduced motion** (`prefers-reduced-motion`): beams don't travel and there is no afterglow. Events become instant
  fills that clear after 600 ms, plus their strip ticks.
- **Frame loop:** `requestAnimationFrame` runs only while a mark is within six half-lives of its event, a beam is in
  flight, or the user is panning. Then it stops. It is capped at 60 fps even on 120 Hz screens, because the GPU is
  shared with MLX. It also stops while the tab is hidden or a benchmark is measuring. DOM readouts update at most
  10 times a second.
- **Measuring mode:** while the server reports a measuring job, every stage shows `MEASURING · VIEW PAUSED` in
  `--t-label` and draws nothing.
- **Budget:** the lead measures tok/s with the Memory screen open and animating. Over 2% means turning off the halo
  first, then capping at 30 fps.

## The app frame

**Top strip** (44 px, `--s1`, a 1 px `--hair` below):
- **Left:** the working name `camr` in Martian Mono 13 px, `wght` 500, `--ink`.
- **Centre:** six screen keys, `MODELS CHAT CODE SWARM MEMORY BENCH`:
  - each is a 28 px key with a 1 px `--hair-2` border, radius 2, `--t-label`, and its number `1`–`6` in `--ink-4`
    before the word;
  - the current key has `--ink` text and a 2 px white underline (selection);
  - keys `1`–`6` switch screens when focus is not in a text field. ⌘1–⌘6 belong to the browser and are not used.
- **Right:** live meters, each a `--t-label` above a `--t-readout`:
  - `RAM`: a 64 px amber bar against 24 GB, with the pressure word `normal`, `tight` or `critical` (from
    `sysctl kern.memorystatus_vm_pressure_level`: 1, 2 or 4);
  - `SSD`: the last read, as `57.3 MB · 3.14 GB/s`, or `—`;
  - `MODEL`: the loaded reader;
  - `FIRST WORD`: the last time to the first word.
- **The bus line** is the strip's bottom hairline, and it is the one signature on every screen:
  - When any read moves bytes from the SSD to RAM, the whole line flares in place: a gradient from `--ssd` at the
    left to `--ram` at the right, half-life 400 ms, 1 px (2 px for reads over 32 MB).
  - A RAM hit flares amber only, and words read in flare violet.
  - It never travels, so it never claims a duration. It means "memory just moved", from any screen.

**Keyboard everywhere:**
- `1`–`6` switch screens.
- `Space` is RUN/STOP: it freezes the stages and queues events.
- `[` and `]` change the timebase, and `P` cycles persistence.
- `R` replays the selected answer, or the last one.
- `C` shows the measuring cursors.
- `Esc` clears the selection or closes a sheet.
- `/` focuses the composer.
- Focus is always a 2 px white outline, offset 2 px.

**Empty states:** a panel with no data shows its hairline outline and one line in `--ink-3` saying what would fill
it, for example `no answers yet · ask something in Chat`. There is never demo data. A fixture loaded for development
shows a `FIXTURE` badge in the top strip.

## Shared components

| Component | What it is | Built on |
| --- | --- | --- |
| **Stage** | The regl canvas holding plates, tiles, cells, dots, beams, threads, afterglow and halo. Modes: `live`, `compact`, `path`, `vault`, `well` | regl |
| **Trace strip** | Stacked 28 px rows on `--void` with a 72 px label gutter. Modes: `roll` (60 s window, now at the right) and `answer` (ms from the question, broken after the first word) | uPlot for bands, Canvas 2D for tick rasters |
| **Readout** | A `--t-label` above a value and unit. Sizes: strip, cluster, hero | DOM |
| **Toggle** | A hardware two-position switch (`MEMORY ON/OFF`, `LIVE/VAULT`), as a pill | DOM |
| **Reach picker** | Four reach segments, several read at once and one written (Chat section) | DOM + inline SVG |
| **Gauge** | A calibrated ruler bar with segments and a ghost-fit outline | DOM + SVG |
| **Path strip** | The 20 px data path under each answer | SVG |
| **Light path sheet** | One answer in full: a path stage plus lanes plus every metric | Stage + SVG |
| **Sheet** | A right-side panel, 360 px (420 px for notes), `--s1`, hairline at its left edge | DOM |
| **Module tile** | A 40 px rack unit with type, name and a status mark | DOM |
| **Cursor pair** | Two draggable lines on a trace strip, with Δt, bytes and mean GB/s between them | Canvas 2D |

## The live memory visual: the Stage

This is the heart of the app, so it is specified to build.

### Inputs

All of these exist in the engine tonight:
- **Moments and rooms:** `GET /api/brain` gives moments `{room, day, text}`, rooms `{id, members}` and `layout`. The
  layout is one `[x, y]` in 0–1 per moment, from `view/layout.py`, which caches it.
- **Room sizes:** each room's tokens are the sum of its members' tokens, and its bytes are tokens × `token_bytes`
  (112 KB per token on the 1.7B, so a full 512-token room is about 57.3 MB).
- **What is where:** `Tiers.state()` gives the hot-shelf rooms in RAM, the RAM budget and its use, the bytes awake on
  the SSD and the asleep rooms.
- **The event log** (`events.jsonl`):
  - `answer` and `agent`: `room`, `closest`, `nodes` (moment ids on the desk), `share`, `used`, `words`, `looks`
    (words × nodes), `wait_s`, `seconds` {choose, core, fetch, wake, desk}, `tier`, `asleep`, `read_bytes`,
    `core_tokens` and `reach`;
  - `remember`: `moment`, `room`, `tokens`, `new_room` and `slept`;
  - `sleep` and `wake`: `rooms`;
  - `verdict`, `tool`.
- **Metrics:** one record per answer in `metrics.jsonl`, with `first_word_s`, `total_s`, `retrieval_ms`, `gbps`,
  `read_share`, `context_tokens`, `history_tokens` and `peak_ram_bytes`.

Events are written when an answer finishes. So the stage plays each answer the moment its event arrives, at the chosen
timebase, labelled `just now` (or `replay · answer 41` for an older one). It never pretends to be inside a running
answer.

### Geometry (`live` mode)

The stage is the full width, with 16 px padding. It has three regions, left to right, matching the data path:

**1. SSD plate** (x 0–46% of the width). Label at top left: `SSD · 312 rooms · 17.8 GB · 9 asleep`.
- **Reach bands:** with more than one reach read, the plate splits into horizontal bands, one per reach, with 8 px
  gaps. A band's height is proportional to √(its bytes), at least 64 px. Each band is labelled at its top left (for
  example `GLOBAL · 212 rooms`). Reaches are told apart by place and label, never by colour.
- **Room tiles:**
  - Each awake room is a tile with height `h0` and width `3.2 · h0 · tokens / 512` (at least `0.5 · h0`).
  - `h0` is solved so the tiles cover 40% of the band: `h0 = sqrt(0.4 · bandArea / Σ(3.2 · tokens / 512))`, clamped
    to 6–28 px. This gives density without clutter, against round 1's lesson that sparse and flat loses.
- **Placement:**
  - A tile's centre is the mean layout position of its moments, scaled into the band.
  - Then 60 passes of rectangle separation push overlapping tiles apart along their smaller overlap, half each, kept
    inside the band. Use a spatial hash with cells of twice the largest tile.
  - It is deterministic. Positions are kept for the session.
  - A new room (`new_room`) takes the free spot nearest its band's lower-left corner. A full re-layout happens only
    on reload.
- **Inside a tile:**
  - Moments are column spans (cells), in token order, with 1 px `--void` gaps when a span is at least 3 px.
  - **Level of detail:**
    - with a tile at least 14 px tall on screen, the tile shows its 28 layer rows (1 px gaps);
    - at 7–13 px, it shows 7 bands of 4 layers;
    - below 7 px, no rows.
  - When rows show, layers 12, 16, 20 and 24 are the only rows that can light green.
- **At rest:** the outline is `--ssd` rest and the cells are `--ssd` at 12% (between far and rest). The plate reads
  as a translucent body full of structure.
- **Asleep rooms:** a dashed `--ink-4` outline with no cells, at their place.
- **Outside the reach:** rooms in reaches not being read draw at the far step (the aperture is closed).

**2. The bus** (x 46–60%):
- **Scale:** a calibrated vertical scale from 0 to 8 GB/s on its left edge, with `--ink-4` ticks every 1 GB/s and
  `--t-label` numbers at 0, 2, 4, 6 and 8.
- **Reads** are beams:
  - Each beam is a polyline: from the room tile's right edge to the bus's left edge at height = the read's GB/s,
    straight across the bus at that height, then to the desk's room span.
  - Its thickness is bytes to scale (1 px per 2 MB, 1–40 px).
  - Its colour is `--ssd` on the SSD plate, a gradient across the bus, and `--ram` on the RAM plate.
  - A `--t-readout` chip rides the bus segment: `57.3 MB · 18 ms · 3.14 GB/s`, plus `· shown ×10` when slowed.
- **Words** (the 4 closest moments, or an asleep room's notes) are 0.5 px violet threads from their cells (or drawer
  dots) to the desk's words span. Beside a 28 px beam, the 29,000× gap is plain.
- **Writes** (remember, wake) are 1 px dashed blue lines running right to left.

**3. RAM plate** (x 60–100%), top to bottom:
- **RAM ruler** (20 px): 0–24 GB, calibrated, with a minor tick every 1 GB and a label every 4 GB. Its segments, in
  order:
  - other apps, `--ink-4`;
  - the model's weights, `--ram` resident;
  - the camr's RAM (core + hot shelf + desk), `--ram` at the event step;
  - free, hairline only.

  A 1 px `--ink-2` line marks 24 GB. Label: `RAM 24 GB · 1.71 GB this process · peak 1.83`.
- **Zoom bracket:** two `--ink-4` hairlines run from the camr's few-pixel span on the ruler down to the inset. The
  magnification is printed, for example `×412`, computed as the inset's px per GB ÷ the ruler's px per GB. The tiny
  real size is shown honestly, and the inset makes it readable.
- **Inset**, three blocks with 12 px between them, each with a `--t-label` and readout:
  - **Core:** 28 rows by one column per 8 tokens (32 columns for 256 tokens), rows 2 px with 1 px gaps, `--ram`
    resident. Label: `CORE 256 tok · 28.7 MB`. When the core is off, an empty hairline outline reads `CORE · off`.
  - **Hot shelf:** the rooms `swap.py` keeps in RAM, as small tiles from least recent (left) to most recent (right).
    Widths are bytes on a shelf scale where the full width is the RAM budget minus the core. A dashed white line at
    30% marks the budget: the allowance, which nothing crosses. Label: `HOT 4 rooms · 228 / 508 MB` (the
    512 MiB budget less the core).
  - **Desk:** 28 rows (row height 4 px, 1 px gap) by every token on the desk, left to right:
    - the header in `--ink-4`;
    - the core in `--ram` resident;
    - the room in `--ram`, one span per moment with 1 px gaps;
    - the words of the 4 closest moments, hatched `--ram` (45°, 1 px lines every 3 px), because they were re-read
      from words rather than saved tensors;
    - the question in `--ink-3`.

    Each moment span is at least 2 px wide; the desk scrolls horizontally if it must, which is rare. Rows 12, 16, 20
    and 24 carry a 4 px `--ink-2` tick and `L12`-style `--t-label` at the left. The legend under the desk reads
    `watched L12 L16 L20 L24 · mean of the four · 24 layers not watched`.
- **Readout cluster** at the plate's bottom right (`--t-cluster`):
  - `DESK 612 tok of 1.04M`;
  - `READ 57.3 MB · 3.14 GB/s · 18 ms · 12% of wait`;
  - `TIER ssd`;
  - `FIRST WORD 0.07 s · 1.9 s total`.

**Vault drawer** (64 px under the stage, full width, `--void`):
- One 2 px violet dot per note: x is the note's day (first day to today), y a stable hash of its id within 8–56 px.
- Brightness is the rest step × the note's strength relative to the strongest, never under 10% of rest. Faded notes
  dim but never vanish.
- Notes of asleep rooms carry a 1 px violet ring.
- Label: `VAULT · 3,118 notes · 41 MB`. Click it for vault mode.

**Stage corners:**
- `TIMEBASE REAL` at bottom right;
- `PERSISTENCE VARIABLE` at bottom left;
- `just now` or `replay · answer 41` at top centre while one plays.

### One answer, step by step

`f` is the timebase factor. `t0` is the display time the `answer` event arrived.

1. **Choose:** at `t0`, the chosen room's outline flares blue. The aperture applies.
2. **Core:** from `t0 + choose·f`, the core flares over `core·f`.
3. **Fetch, by tier:**
   - `ssd`: the beam's head travels linearly over `fetch·f`, and the bus line flares;
   - `ram`: the hot tile flares and its copy slides to the desk in 240 ms; the readout shows `RAM hit · 0 B from SSD`;
   - `vault` and asleep: violet threads only; with `wake`, the dashed write runs over `wake·f`, then the beam.
4. **Lay the desk:** the room span fills left to right over `max(desk·f, one frame)`. The words span fills hatched,
   and the violet threads from the closest moments flare. The home tile gets an amber ring, which it keeps while its
   copy is on the desk.
5. **Prefill:** the question span lights `--ink-3` until the first word at `wait_s·f` after `t0`. The WORDS strip
   gets its tall first-word tick.
6. **Decode:** word by word, at the word timing above (also × `f`), each node's spans on the four watched desk rows
   flare green at that word's relative look, and so does the node's home cell on the SSD plate. The chat's answer
   underlines the same word as it plays (in sync).
7. **Settle:** used nodes hold green with a halo, and picked-only nodes keep amber rings. The desk drains in 200 ms.
   The room appears on the hot shelf if the tiers state now lists it.

A false-memory verdict, when it arrives, adds a red `×` to that answer's path strip and receipt. The stage does not
redden: red never lights the specimen.

### Rendering (regl)

- **Canvas and context:**
  - One canvas per stage, sized to its CSS box × `devicePixelRatio`, capped at 2.
  - One regl context per canvas. Swarm draws its eight wells in one canvas with `viewport` and `scissor`, never eight
    contexts.
  - Extensions: `ANGLE_instanced_arrays` (required) and `OES_standard_derivatives` (optional, for edge antialiasing).
- **Five instanced draw calls,** each a unit quad:

| Draw | Per-instance attributes | Shape in the fragment shader |
| --- | --- | --- |
| `tiles` | rect, radius, outline px, fill alpha, channel, base, t_event, half_life, rows LOD, dashed | Rounded-rect SDF; optional row stripes; dashed outline |
| `cells` | rect, row mask (28 bits as 2 floats, for watched-row-only flares), channel, base, t_event, peak, ring | Rect with an optional 1.5 px ring band |
| `dots` | centre, radius, channel, base, t_event, ring | Circle SDF |
| `beams` | p0, p1, thickness, colour at p0, colour at p1, t_start, t_land, t_event | Segment; the head reveals by `(now − t_start) / (t_land − t_start)` along the polyline's length |
| `lines` | p0, p1, width, channel, base, t_event, dashed | Segment SDF, dashes by arc length |

- **Shading:**
  - Edge coverage is `smoothstep` over one device pixel, so marks stay crisp.
  - Output = `palette[channel] × b × coverage`, with additive blending (`ONE, ONE`) on black.
- **Passes:**
  1. Draw everything into FBO `main` (full resolution, RGBA8, cleared to black).
  2. Draw everything again into FBO `glow` at quarter resolution with `u_litOnly = 1`, outputting
     `palette × max(0, b − base) × coverage`.
  3. Blur `glow` with a 9-tap separable Gaussian, horizontal then vertical. Sigma is 2 CSS px, which is
     `2 · dpr / 4` glow pixels.
  4. Composite to the screen: `main + 0.35 × glow`.
- **Updates:**
  - Instances live in typed arrays.
  - An event writes `t_event` and `peak` for the instances it touches, then calls `buffer.subdata` on just that
    range.
  - The gaze touches at most (desk nodes × 2) instances per word.
- **Budget:** at most 60,000 instances. A real memory of about 3,000 moments, 300 rooms and a 600-token desk is
  about 5,000.
- **Picking:** a CPU spatial grid (32 px cells) over tile and dot rectangles handles hover and click. There is no GPU
  picking.
- **Without WebGL:** Canvas 2D draws the same layout with `globalCompositeOperation = 'lighter'` and no halo, and the
  stage says `no WebGL · flat view`.

### Interaction

- **Hover a tile:** a tooltip (`--s2`, `--t-readout`) reads
  `room 41 · 12 moments · 498 tok · 55.8 MB · read 7× · last share 0.31`.
- **Click a tile:** it turns white (outline and its USED sub-row), and the 360 px room sheet opens. The sheet holds:
  - the room close-up: its full 28-row tensor tile at sheet width, the watched rows lit with the last answer's looks,
    and the other rows labelled `not watched`;
  - its moments, with day and words;
  - its bytes on disk, reads, last share and doors;
  - `open in vault`.
- **Zoom and pan:** the wheel or a pinch zooms the SSD plate from 1× to 16× around the cursor; drag pans;
  double-click resets. The level of detail follows the zoom.
- **Hover a desk span:** shows that moment's words and its share this answer.
- **Later (P3):** lasso a set.

### Trace strip (Memory: eight rows)

| Row | Source | Mark |
| --- | --- | --- |
| `SSD R` | `answer` with `tier: "ssd"` | A blue bar at the read: height = GB/s on 0–8, width = max(2 px, duration) |
| `SSD W` | `remember` (tokens × token bytes), `wake` | A dashed blue tick, height ∝ log(bytes) |
| `RAM` | `/api/sys` at 1 Hz: process resident bytes; metrics peak | A 1.5 px amber line over a 20% fill, with a peak mark |
| `HOT` | Tiers state: used against budget | An amber band, with a dashed white budget line |
| `DESK` | Metrics: `context_tokens` against `history_tokens` | An amber tick under an `--ink-4` ceiling, log scale |
| `USED` | `looks` | One 4 px sub-row per desk node (at most 16, by share). A green tick per word, brightness = the look. A node's label is a green dot if used, an amber ring if only picked |
| `WORDS` | `words` | An `--ink-2` tick per word, with a tall `--ink` tick at the first word |
| `TTFT` | Metrics `first_word_s` | One dot per answer on 0–0.2 s, with a dashed `--ink-4` line at 0.07 s |

Selecting an answer switches the strip to `answer` mode:
- x is ms from the question, with 55% of the width up to the first word and 45% for decode, and a `//` break mark;
- `C` shows two cursors, which read Δt, bytes and mean GB/s.

### Vault mode (`LIVE / VAULT` toggle, top left of the stage)

The same stage and positions, filled with notes instead of tiles:
- **Notes:** each note sits at its moment's layout position. Notes are violet dots, radius 2 + √(links to it) px,
  brightness by strength after the 5% daily fade.
- **Doors:** violet hairlines, width by weight (form table).
- **Overlays:**
  - a blue ring on a note whose room is awake on the SSD;
  - an amber ring on a note on the desk now;
  - a green fill on a note used in the last answer.
- **Open a note:** clicking one opens the 420 px note sheet. The note renders as Markdown with markdown-it
  (`html: false`), with its links and backlinks below.
- **Local graph:** a depth slider (1–3) shows only the notes near the selected one.
- **Growth scrub (P2):** drag along the bottom through the days, and the vault redraws as it stood on that day.
  Brightness is strength × 0.95^(days since last use).

### Sleep

`sleep` and `wake` events are drawn as above. While a distilling job reports progress, a `--t-label` at top left
reads `SLEEPING · distilling 41 / 120`, and nothing else moves.

On the first open after a sleep (P3), the night replays once, in 10 s, from its events. One line follows, built from
the counts, for example `+14 facts into the core · 3 rooms asleep · 0 destroyed`.

## An answer's data path

### The path strip (20 px under every answer)

A segmented bar, to scale. The first 60% of its width runs from the question to the first word, then a `//` break,
then decode in the last 40%.

| Segment | Mark |
| --- | --- |
| choose | `--ink-3` |
| core | `--ram` resident |
| fetch | `--ssd`, or a 2 px amber notch for a RAM hit |
| wake | `--vault` |
| desk | `--ram` |
| prefill | `--ink-2` |
| first word | a tall `--ink` tick |
| decode | a thin `--ink-2` line |

At the right, in `--t-readout`, sits `● 3 used ○ 9 picked · 57.3 MB · 3.14 GB/s · 0.07 s · 1.9 s` (example values). The
dot is a green SVG fill and the ring an amber SVG ring. With memory off, or for Claude, the strip is one grey model
segment.

Click the strip to open the light path.

### The light path sheet

The sheet rises over the screen to 72% of its height, `--s1`.

**Top 55%: the path stage** (Stage in `path` mode, left to right):
- the chosen room's tile, magnified with its 28 rows;
- the bus with the beam and its chip;
- the desk with its rows and the gaze;
- under the desk, the answer's words in one wrapped row of `--t-chat`.

From each used node's desk span, green threads run to the three words that looked at it hardest. A thread's width is
that word's look × 6 px. Picked-only nodes get no thread, so you can see they were fetched and ignored.

**Bottom 45%: lanes**, Perfetto-style, on one time ruler with the same break:

| Lane | Slices |
| --- | --- |
| `VAULT` | Words read in (thin), wake |
| `SSD` | The read: length = duration, labelled `57.3 MB · 18 ms` |
| `RAM` | The core (a constant thin bar), laying the desk |
| `MODEL` | Prefill, the first-word tick, decode with a tick per word |

- Faint whiskers show the session's p50 and p90 for each step (metrics `summary`).
- **Readout row:** right or wrong; honest or false memory; first word and total; prefill and decode tok/s; retrieval
  per step; bytes, GB/s and share of the wait; context tokens against history tokens; peak RAM and disk. A value
  that was not measured shows `—`.
- `Esc` closes the sheet.

## Screens

### 1. Models: what fits this Mac

**Gauge block** (top 30%, `--void`):
- **RAM gauge:** 48 px tall, the full content width, calibrated to 24 GB. Its segments:
  - other apps, `--ink-4`;
  - the loaded model's weights, solid `--ram`;
  - the camr (core + hot shelf + desk), `--ram` resident;
  - free, hairline only.

  A 1 px `--ink-2` line marks 24 GB, and the pressure word sits at the right end.
- **Disk rail:** 12 px, under it:
  - model files, `--ssd`;
  - rooms, `--ssd` resident;
  - vault, `--vault` resident;
  - free.

  Label: `SSD 1 TB · 612 GB free`.
- **Ghost fit:** hover or arrow onto any model, and its footprint projects onto both bars as outlines with no fill:
  - on the RAM gauge, weights + KV for the chosen context + the camr's RAM budget;
  - on the disk rail, its files.

  If it fits: `fits · 6.2 GB spare`. If it crosses 24 GB, the overflow is a red hatched outline past the end, with
  `× needs 3.1 GB more`.
- **Hero figure:** free RAM, for example `17.8 GB free`, in `--t-hero`.

**List** (below, 56 px rows, grouped: `MLX` and `OLLAMA`). The columns:
- name and quantisation, in `--t-readout`;
- parameters;
- **anatomy:** a 120 × 20 px glyph with one 2 px vertical mark per layer. A filled `--ink-2` mark is a layer that
  keeps KV (it can read tensor memory); a hollow one is a linear-attention layer (memory as words). Read it from
  `config.json`. The 27B's 48 hollow marks out of 64 explain at a glance why it reads words;
- memory as: `tensors` in `--ssd` or `words` in `--vault`;
- RAM at load, an amber bar on the gauge's scale;
- disk, a thin blue bar;
- measured on this Mac: first word and decode tok/s from the dated records, or `not measured`;
- verdict: `fits`, `tight` or `× won't fit`, as glyph and word.

**Hugging Face search:** a field at the top right of the list (`/` focuses it) searches MLX repositories through the
local server. The page itself never calls Hugging Face.
- **Downloading:** the row's blue disk bar fills as bytes land, with `412 MB/s · 1 m 40 s left` and a pause key. A
  failure leaves the bar where it stopped, with a red `×` and the reason.
- **Loading:** the RAM bar fills amber as the loader reports, or all at once if it reports nothing. There is never a
  fake progress bar.

### 2. Chat: the eyepiece

**Layout:**
- **Left 62%:** the conversation, in a 720 px column.
- **Right 38%: the eyepiece.** It is a Stage in `compact` mode, the same three regions at reduced labels, holding the
  memory being read. Under it is a 3-row trace strip (`SSD R`, `USED`, `WORDS`).

**Messages:**
- Yours are right-aligned on `--s2`, radius 6, in `--t-chat`.
- The engine's have no bubble: `--t-chat` text on `--bed`.
- Under each answer is its path strip.
- Words whose largest look went to a used node carry a 1 px `--used` underline at 40%.
- Hover a word, and its top node flares in the eyepiece, with that moment's text in a small popover.
- An errand answer is a receipt in `--t-code`: `book_ride(to="…", when="…")`. Argument values that leaned on memory
  are underlined green, and the result line follows.

**Composer** (bottom of the left column, `--s1`, 1 px `--hair-2`, radius 6, a `›` prompt in `--ink-3`):
- **Context meter:** the composer's top edge is a 2 px line. An amber segment is the tokens in view, and the `--ink-4`
  remainder is the model's window. At the right, in `--t-readout`:
  `in view 2,148 / window 32,768 · history 1.04M tok` (example values). As the history grows and the amber stays
  short, the claim shows itself.
- **Controls,** in a row above the input:
  - **`MEMORY` toggle:** ON or OFF. Off sends `on: false`. The eyepiece goes dark except a centred `memory off`
    (`--ink-3`), and answers get grey path strips.
  - **Reach picker:** four segments, `SESSION`, `PROJECT <name>`, `AGENT <name>` and `GLOBAL`.
    - Each carries a ring glyph (session innermost, global outermost) and a size line: the note count in `--vault`
      and the bytes on the SSD in `--ssd`.
    - Click a segment to read it or not. A read segment is white (text and ring); an unread one is `--ink-3`.
    - Shift-click sets the one reach written to, marked by a 2 px white underline. The default reads session and
      global, and writes to session (`reach.py`).
    - Unread reaches drop to the far step in every stage.
  - **Intent:** `TELL · ASK · ERRAND`, chosen automatically (ending in `?` means ASK) and changeable. TELL remembers,
    ASK answers, and ERRAND makes one tool call (`agent.act`).
  - **Model chip:** the reader in use.

### 3. Code: the workbench

**Layout:**
- **Left 240 px:** threads at the top, each ending in its last answer's path strip shrunk to 6 px; files below.
- **Centre:** the editor (CodeMirror 6, `--t-code`) with tabs.
- **Bottom 30% of the centre,** split in two:
  - the agent transcript: turns in `--t-body`, and each tool call a one-line receipt (`tool · argument · ms`) that
    unfolds to its output; diffs show through `unifiedMergeView`;
  - the terminal (xterm.js), which shows the agent's run output read-only. There is no shell typed from the page in
    this version.
- **Above the transcript:** the run trace (120 px, Perfetto tracks). There is one track for the model, one per tool,
  and one for the shell. Calls are `--ink-2` bars, and memory reads inside a call are blue, amber and green ticks.
- **Right 300 px: the rack.**

**The memory gutter** (the signature): a 3 px bar between the line numbers and the code.
- **Green:** the line was written while leaning on memory. Some word written in it had a look of at least 0.10 on a
  node; map the answer's `words` to lines by joining them.
- **Violet:** the line came from a vault note, such as a saved "your fix" note.
- **Hover the bar** to see the moment's words, its day and room, and that step's path strip.
- **Saving an edit** to the model's code puts a violet tick on the changed lines with `your fix · kept`. The fix
  feeds the next answer (the app already keeps these notes).

**The rack:** 40 px module tiles, each with:
- its type in `--t-label` (`TOOL`, `PERSONA`, and `MCP` or `SKILL` only where they exist);
- its name in `--t-body`;
- a status mark: a filled `--ink` dot when active this session, a hollow `--ink-3` ring when idle, a red `×` when
  failing.

Colour stays reserved for memory. A persona tile also shows its four reach rings, read or not. Choosing a persona
sets the reach.

### 4. Swarm: the multi-well plate

**Plate** (top 55%): eight wells in a 2 × 4 grid.
- Each well is a Stage in `well` mode: that agent's own memory (its agent reach), with the same tiles, beams, gaze and
  afterglow. All eight share one canvas.
- Wells are labelled `A1`–`A8` in `--t-label`, with the persona and model in `--t-readout` below.
- Agents are told apart by place and label, never by colour.
- Click a well, and it fills the plate while the others shrink to a 64 px strip.

**Shared RAM bar** (28 px under the plate): the hot-shelf budget over time, sliced into labelled segments (`A3`)
showing which agent's rooms sit in RAM. When the budget is full, the next arrival's blue read waits on its row until
a segment frees. That is contention, made visible.

**Channel rows** (the rest of the screen): one 44 px row per agent, on one time axis.
- An amber band shows desk occupancy.
- Above it are ticks: blue for SSD reads, green for used looks, violet for vault reads.
- Messages between agents are thin `--ink-2` vertical connectors with small arrowheads.
- A selected agent's label and row turn white.

With no swarm run, the wells show their outlines and `no swarm run yet`.

### 5. Memory: the stage

This is the full Stage (`live`):
- the top strip;
- a `LIVE / VAULT` toggle and the reach picker at the stage's top left;
- the stage, about 560 px;
- the vault drawer, 64 px;
- the trace strip, eight rows.

Room, desk and note sheets open on the right. Everything in "The live memory visual" above applies.

### 6. Bench: the evidence

**Headline** (top 28%):
- `62–68 / 85` beside `0 / 85` in `--t-hero`: Qwen 27B with memory against without;
- each figure's record path in `--t-readout` `--ink-3` under it;
- the line "better, never heavier" in `--t-body`.

**Tabs** (one per question in the plan): `Past the window`, `How far it grows`, `Which reach`, `Swarms` and `Sleep`.
Each tab has one full-width hero chart in the top 60% of its area. The run table sits below in `--t-readout`, and each
row opens its dated record with `↵`.

**Past the window:**
- **The flat line:** first word against history tokens. x is log scale from 1K to 2M, with cut lines at 64K, 256K, 1M
  and 2M. The camr's line is `--ssd` with a tight halo, staying flat at 0.07 s. Baselines that read their whole
  history rise in `--ink-3`.
- **Peak RAM:** a twin chart under it.
- **Score against history length:** each model's context window is a vertical `--hair-2` wall labelled at its foot.
  The memory lines keep going through the walls.
- **Contenders:**
  - tensors in `--ssd`;
  - words in `--vault`;
  - no memory in `--ink-3`;
  - Claude as a hollow, dashed `--ink-2` line.
- **Points:** every point links to its record. False memories hang under their point as red `×` marks, one each.

**Probe matrix** (under the tabs, every tab): the eight Long Haul probes (rows) against the contenders (columns).
- Each cell is a square whose brightness is the score, in the contender's memory hue (grey for none).
- Each cell also carries counts: `✓ right`, red `× wrong or false`, and `∅ honest declines`. The glyphs are inline
  SVG.

**Right column** (300 px), the yardstick: for each Claude model, its input, cached and output tokens and $ at list
price, from `records/bench/claude-ledger.jsonl`. A running total sits against the $60 cap as a thin `--ink-2` bar.

**The page that grows:** that probe's row shows the generated catering page as its real headless-browser screenshot.
It is the one real image of an output in the app.

**While a suite runs:** stages everywhere pause, the top strip reads `MEASURING`, and each new result lands as a dot
that flares and decays.

## What the views read

The app builders own `v2/camr_engine/app/`, so these are theirs to add to the server. Nothing below changes `notes.py`,
`rooms.py`, `memory.py` or `events.py`.

| Endpoint (GET, with the `X-CAMR-Token` header) | Gives |
| --- | --- |
| `/api/state` | Today's state, plus `tiers` (`Tiers.state()`), the loaded model, the measuring flag, and each reach's note count and bytes |
| `/api/brain` | Exists: moments, rooms, layout, answers |
| `/api/events?after=N` | `{next, events: [...]}`: new lines of `events.jsonl` after line N, at most 500 |
| `/api/metrics?after=N` | The same, for `metrics.jsonl` |
| `/api/sys` | Total and used RAM, this process's resident bytes, the pressure level, and free disk (from `sysctl`, `vm_stat` and `os.statvfs`; no new packages) |
| `/api/vault` | Notes: id, day, strength, room, asleep, links |
| `/api/models` | Models: config-derived anatomy, sizes, footprints and measured speeds |
| `/api/bench` | The index of dated bench records and the Claude ledger |

- **Polling:** the page polls `/api/events` and `/api/metrics` 4 times a second while a request is pending, and once
  a second otherwise. It stops while the tab is hidden. It does not use `EventSource`: it cannot send the token
  header, and putting the token in a URL would leak it into logs.
- **Token:** the server puts the launch token in `<meta name="camr-token" content="__CAMR_TOKEN__">`. `data.js`
  reads it, so no inline script is needed.
- **One proposal for the lead (optional):** an `evict` event `{rooms, bytes}` from `Tiers._fit`, with no change to
  behaviour. Until it exists, evictions are seen by diffing `tiers.ram.rooms` between polls.

**Static files and CSP** (the server serves only `/` today):
- Serve `/static/<path>` from `app/static/`.
- Refuse any path that resolves outside it.
- Set types: `.js` and `.mjs` → `text/javascript`, `.css`, `.woff2` → `font/woff2`, `.svg` → `image/svg+xml`,
  `.json`, `.png`.
- Every page response carries:
  `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; worker-src 'self' blob:; base-uri 'none'; frame-ancestors 'none'`.
  Inline styles are allowed because CodeMirror and xterm inject style elements. Scripts stay strict.
- Add tests for the static route (outside paths refused, the Host check still applied).

**For checking in a browser without loading a model:** ask the lead for a recorded memory folder (rooms,
`events.jsonl`, `metrics.jsonl`, `layout.json`) from a run tonight. Until then, use a fixture made with the test
fakes, shown under the `FIXTURE` badge.

## Libraries: pinned, vendored, offline

Everything is copied into `v2/camr_engine/app/static/vendor/` and served by the local server. At runtime the app makes no
request beyond 127.0.0.1. The current page's Google Fonts link goes.
- **Versions:** every version below was checked against the npm registry tonight and was published on or before
  21 Oct 2026, at least two weeks ago. That includes all 40 packages in the bundle tree.
- **Bundles:** the four bundles were built tonight with these exact pins to confirm they work.
- **LOCK:** `vendor/LOCK.json` records each file's package, version, licence, source URL and SHA-256. Each package's
  `LICENSE` is copied beside its files.

### A. Direct files (download as they are)

Base URL: `https://cdn.jsdelivr.net/npm/`. The vendor path is `vendor/<package>@<version>/<file>`.

| Package | Licence | Files | URLs |
| --- | --- | --- | --- |
| `uplot@1.6.32` | MIT | `dist/uPlot.esm.js` (145 KB), `dist/uPlot.min.css` | `https://cdn.jsdelivr.net/npm/uplot@1.6.32/dist/uPlot.esm.js`, `https://cdn.jsdelivr.net/npm/uplot@1.6.32/dist/uPlot.min.css` |
| `@xterm/xterm@6.0.0` | MIT | `lib/xterm.mjs` (345 KB, no imports), `css/xterm.css` | `https://cdn.jsdelivr.net/npm/@xterm/xterm@6.0.0/lib/xterm.mjs`, `https://cdn.jsdelivr.net/npm/@xterm/xterm@6.0.0/css/xterm.css` |
| `@xterm/addon-fit@0.11.0` | MIT | `lib/addon-fit.mjs` | `https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.11.0/lib/addon-fit.mjs` |
| `@fontsource-variable/martian-mono@5.3.0` | OFL-1.1 | `files/martian-mono-latin-standard-normal.woff2` (38 KB), `files/martian-mono-latin-ext-standard-normal.woff2` | `https://cdn.jsdelivr.net/npm/@fontsource-variable/martian-mono@5.3.0/files/martian-mono-latin-standard-normal.woff2`, `https://cdn.jsdelivr.net/npm/@fontsource-variable/martian-mono@5.3.0/files/martian-mono-latin-ext-standard-normal.woff2` |
| `@fontsource-variable/geist@5.3.0` | OFL-1.1 | `files/geist-latin-wght-normal.woff2` (29 KB), `files/geist-latin-ext-wght-normal.woff2` | `https://cdn.jsdelivr.net/npm/@fontsource-variable/geist@5.3.0/files/geist-latin-wght-normal.woff2`, `https://cdn.jsdelivr.net/npm/@fontsource-variable/geist@5.3.0/files/geist-latin-ext-wght-normal.woff2` |
| `@fontsource-variable/geist-mono@5.3.0` | OFL-1.1 | `files/geist-mono-latin-wght-normal.woff2` (23 KB), `files/geist-mono-latin-ext-wght-normal.woff2` | `https://cdn.jsdelivr.net/npm/@fontsource-variable/geist-mono@5.3.0/files/geist-mono-latin-wght-normal.woff2`, `https://cdn.jsdelivr.net/npm/@fontsource-variable/geist-mono@5.3.0/files/geist-mono-latin-ext-wght-normal.woff2` |
| `lucide-static@1.58.0` | ISC | `icons/<name>.svg` for `play pause download x search chevron-right chevron-down rotate-ccw zoom-in zoom-out crosshair square-terminal file-code folder folder-open timer`, inlined | `https://cdn.jsdelivr.net/npm/lucide-static@1.58.0/icons/play.svg` and so on |

The licences sit at `https://cdn.jsdelivr.net/npm/<package>@<version>/LICENSE`.

### B. Bundles (built once with esbuild, output committed, `node_modules` never committed)

These live in `v2/camr_engine/app/vendor-src/`, with `package.json` and `entries/` as below, plus `build.sh`. The output
goes to `static/vendor/`.

| Output | From | Size (built tonight) |
| --- | --- | --- |
| `vendor/ui.js` | `preact@10.29.8`, `htm@3.1.1`, `@preact/signals@2.11.3`, `@preact/signals-core@1.14.4` | 24 KB |
| `vendor/regl.js` | `regl@2.1.1` | 120 KB |
| `vendor/codemirror.js` | `codemirror@6.0.2` and the pinned `@codemirror/*` and `@lezer/*` below | 670 KB |
| `vendor/markdown.js` | `markdown-it@14.3.2` (used with `html: false`, which escapes raw HTML and refuses `javascript:` links, checked tonight) | 146 KB |

The tool is `esbuild@0.28.2` (MIT), for development only.

Reference URLs (npm tarballs follow `https://registry.npmjs.org/<name>/-/<basename>-<version>.tgz`):
- `https://registry.npmjs.org/preact/-/preact-10.29.8.tgz`
- `https://registry.npmjs.org/regl/-/regl-2.1.1.tgz`
- `https://registry.npmjs.org/markdown-it/-/markdown-it-14.3.2.tgz`
- `https://registry.npmjs.org/codemirror/-/codemirror-6.0.2.tgz`
- `https://cdn.jsdelivr.net/npm/preact@10.29.8/dist/preact.module.js`
- `https://cdn.jsdelivr.net/npm/regl@2.1.1/dist/regl.min.js`
- `https://cdn.jsdelivr.net/npm/markdown-it@14.3.2/dist/markdown-it.min.js`

`vendor-src/package.json`:

```json
{
  "private": true,
  "description": "Pinned sources for camr's vendored browser files. Built once with build.sh; node_modules is never committed.",
  "dependencies": {
    "preact": "10.29.8",
    "htm": "3.1.1",
    "@preact/signals": "2.11.3",
    "@preact/signals-core": "1.14.4",
    "regl": "2.1.1",
    "markdown-it": "14.3.2",
    "codemirror": "6.0.2",
    "@codemirror/view": "6.43.14",
    "@codemirror/state": "6.7.6",
    "@codemirror/language": "6.13.1",
    "@codemirror/commands": "6.11.1",
    "@codemirror/autocomplete": "6.20.4",
    "@codemirror/lint": "6.9.7",
    "@codemirror/search": "6.7.2",
    "@codemirror/lang-python": "6.2.1",
    "@codemirror/lang-javascript": "6.2.5",
    "@codemirror/lang-html": "6.4.12",
    "@codemirror/lang-css": "6.3.1",
    "@codemirror/lang-markdown": "6.5.2",
    "@codemirror/merge": "6.12.2",
    "@lezer/highlight": "1.2.5",
    "@lezer/common": "1.5.3",
    "@lezer/lr": "1.4.11",
    "esbuild": "0.28.2"
  },
  "overrides": {
    "preact": "10.29.8",
    "@preact/signals-core": "1.14.4",
    "@codemirror/view": "6.43.14",
    "@codemirror/state": "6.7.6",
    "@codemirror/language": "6.13.1",
    "@codemirror/autocomplete": "6.20.4",
    "@lezer/common": "1.5.3",
    "@lezer/lr": "1.4.11"
  }
}
```

The `@lezer/common` and `@lezer/lr` pins matter: left free, npm resolves 1.5.5 and 1.4.12, published on 30 Oct, which
is less than two weeks ago.

`entries/ui.js`:

```js
export { h, render, Fragment, createContext } from "preact";
export { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback, useContext } from "preact/hooks";
export { signal, computed, effect, batch, useSignal, useComputed, useSignalEffect } from "@preact/signals";
import htm from "htm";
import { h } from "preact";
export const html = htm.bind(h);
```

`entries/regl.js`:

```js
import createREGL from "regl";
export default createREGL;
```

`entries/markdown.js`:

```js
export { default } from "markdown-it";
```

`entries/codemirror.js`:

```js
export { EditorView, basicSetup, minimalSetup } from "codemirror";
export { EditorState, StateField, StateEffect, RangeSet, RangeSetBuilder, Compartment } from "@codemirror/state";
export { gutter, GutterMarker, lineNumbers, Decoration, keymap } from "@codemirror/view";
export { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
export { tags } from "@lezer/highlight";
export { python } from "@codemirror/lang-python";
export { javascript } from "@codemirror/lang-javascript";
export { html } from "@codemirror/lang-html";
export { css } from "@codemirror/lang-css";
export { markdown } from "@codemirror/lang-markdown";
export { MergeView, unifiedMergeView } from "@codemirror/merge";
```

`build.sh`, the core of it:

```sh
cd "$(dirname "$0")" && npm install --no-audit --no-fund
for e in ui regl codemirror markdown; do
  ./node_modules/.bin/esbuild "entries/$e.js" --bundle --format=esm --minify --legal-comments=eof \
    --outfile="../static/vendor/$e.js"
done
# then: download section A into ../static/vendor/, copy each LICENSE, write ../static/vendor/LOCK.json with SHA-256
```

### Not used, on purpose

- three.js and postprocessing: the stage is 2D by design.
- sigma, graphology, ForceAtlas2: the vault graph uses the stage and the engine's layout.
- Observable Plot and d3: uPlot plus plain SVG.
- marked and DOMPurify: markdown-it with `html: false` does both jobs.
- fuzzysort, any CSS framework, any animation library, any CDN at runtime.
- A ⌘K palette is P3. If it is built, plain substring matching is enough.

### Static layout for the builders

```
v2/camr_engine/app/static/
  index.html        fonts, tokens.css, base.css, <meta camr-token>, <script type="module" src="/static/app/main.js">
  app/tokens.css    the token block below
  app/base.css      reset, type roles, component styles
  app/main.js       router (screens 1–6), top strip, bus line, keyboard
  app/data.js       API client, token, polling, the event bus as signals
  app/stage/        stage.js (regl, passes, loop), shaders.js, place.js (tile placement), replay.js (event → marks)
  app/parts/        readout, trace, toggle, reach, gauge, pathstrip, lightpath, sheet, module, cursors
  app/screens/      models.js, chat.js, code.js, swarm.js, memory.js, bench.js
  vendor/           section A files, section B bundles, LOCK.json
v2/camr_engine/app/vendor-src/   package.json, package-lock.json, entries/, build.sh (not served)
```

### `tokens.css`

```css
@font-face { font-family: 'Martian Mono Variable'; font-style: normal; font-display: swap;
  font-weight: 100 800; font-stretch: 75% 112.5%;
  src: url(/static/vendor/@fontsource-variable/martian-mono@5.3.0/files/martian-mono-latin-standard-normal.woff2) format('woff2-variations');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD; }
/* …and the same for latin-ext, Geist and Geist Mono, copying unicode-range from each package's CSS */

:root {
  color-scheme: dark;
  /* neutrals */
  --void:#000000; --bed:#030506; --s1:#0A0D0F; --s2:#111417; --hair:#1B2024; --hair-2:#292F33;
  --ink-4:#33393E; --ink-3:#737C82; --ink-2:#9EA6AB; --ink:#E8ECEF; --select:#FFFFFF;
  /* channels: one meaning each */
  --ssd:#28B8E5; --ram:#FFB75E; --used:#9DFFB3; --vault:#9D63E3; --fault:#EE333E;
  /* steps */
  --ssd-far:#030F12;  --ssd-rest:#092832;  --ssd-resident:#0E4050;  --ssd-hold:#186E89;
  --ram-far:#140F08;  --ram-rest:#382815;  --ram-resident:#594021;  --ram-hold:#996E38;
  --used-far:#0D140E; --used-rest:#233827; --used-resident:#37593F; --used-hold:#5E996B;
  --vault-far:#0D0812; --vault-rest:#231632; --vault-resident:#37234F; --vault-hold:#5E3B88;
  --fault-far:#130405; --fault-rest:#340B0E; --fault-resident:#531216; --fault-hold:#8F1F25;
  --transit: linear-gradient(90deg, var(--ssd), var(--ram));
  /* glow: events and selection only */
  --glow-ssd: 0 0 6px rgb(40 184 229 / .45);  --glow-ram: 0 0 6px rgb(255 183 94 / .45);
  --glow-used: 0 0 6px rgb(157 255 179 / .45); --glow-vault: 0 0 6px rgb(157 99 227 / .45);
  --glow-fault: 0 0 6px rgb(238 51 62 / .45);  --glow-select: 0 0 6px rgb(255 255 255 / .45);
  /* type */
  --f-mono:'Martian Mono Variable', ui-monospace, Menlo, monospace;
  --f-text:'Geist Variable', system-ui, -apple-system, sans-serif;
  --f-code:'Geist Mono Variable', ui-monospace, Menlo, monospace;
  /* space and shape */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-5:24px; --sp-6:32px; --sp-7:48px; --sp-8:64px;
  --r-mark:2px; --r-panel:6px; --r-pill:999px;
  --strip-h:44px; --row-trace:28px; --row-channel:44px; --row-list:56px; --row-module:40px; --gutter-label:72px;
  /* motion */
  --ui-fast:120ms; --ui:160ms; --ease:cubic-bezier(0.2, 0, 0, 1);
  --hl-read:400ms; --hl-words:600ms; --hl-gaze:1200ms; --hl-write:800ms; --hl-used:4000ms;
}
html, body { background: var(--bed); color: var(--ink); }
```

The only colour literals in the app live in `tokens.css`. Everything else, shaders included, reads these properties.

## Build order

| Priority | What | Done when |
| --- | --- | --- |
| P0 | Static serving and CSP; vendor build; `tokens.css` and fonts; the frame (top strip, bus line, keys) | The page loads with no request beyond 127.0.0.1 |
| P0 | `data.js`: token, polling, events | Events arrive as signals |
| P0 | The Memory stage: plates, tiles, the RAM ruler and inset, beams, the gaze, picked against used, all three tiers, trace strip | A recorded answer replays correctly at `REAL` and `×10` |
| P0 | Chat: messages, composer, memory toggle, reach picker, context meter, path strip, eyepiece | Ask, watch the eyepiece, see used against picked |
| P1 | The light path sheet | Every metric listed in BUILD_PLAN shows, or `—` |
| P1 | Models: gauge, disk rail, ghost fit, list with anatomy | Hovering a 27B shows whether it fits |
| P1 | Bench: headline, the flat line, probe matrix, yardstick column | Points open their records |
| P2 | Vault mode; sleep and wake visuals; persistence modes; cursors | — |
| P2 | Code: editor, memory gutter, rack, transcript, run trace, read-only terminal | A recalled helper name shows a green gutter mark |
| P2 | Swarm: plate, shared RAM bar, channel rows | — |
| P3 | Growth scrub, the "last night" replay, lasso, ⌘K palette, Long Haul tape, small multiples | — |

**Checks before calling a screen done:**
- No idle frames: a debug counter at `?debug=1` shows 0 fps at rest.
- No colour literal outside `tokens.css`: grep for `#` and `rgb(` in `app/`.
- Every number has a unit or `—`.
- Keyboard works with visible focus.
- Reduced motion works.
- Layouts hold at 1512 × 982 and 1280 × 800, and stack at 900 px.
- `pytest` stays green.

## Taste questions for Ibrahim

Only taste is left for him. Each default below is what gets built tonight.

1. **The colour of RAM.** Warm amber `#FFB75E` (built) or ember orange `#FF8A3D`, which is closer to the green-on-red
   look he loved but nearer the fault red. It is one token to change.
2. **Flat or layered.** A flat stage with the SSD on the left and RAM on the right (built), or Living's stacked glass
   planes with RAM above the SSD, seen at a tilt.
3. **The numbers' typeface.** Martian Mono (built) or IBM Plex Mono, which the current app and the thesis figures
   use.
