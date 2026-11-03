# Instrument: a design direction for the memory-engine app

Lens: a precision scientific instrument. The memory is a specimen under a microscope, and the telemetry reads like a
lab bench or an observatory console. This file describes the look in words only. Nothing here is a drawn mockup,
because Ibrahim rejects code-drawn mockups. Every screen is specified closely enough to build, or to render from real
event data.

## The idea in two sentences

The memory sits on a black stage like a living specimen. Every light on it is a measured event: a room burst-read
from the SSD, tensors laid on the desk in RAM, or a moment the model's attention actually landed on. The app is the
instrument around that stage. It stays still and exact until something moves, then it glows in the one colour that
says what moved and where.

## What it takes from his picks

| He loved (boards 1–2, 2–3 Nov) | Where it shows up here |
| --- | --- |
| A crisp single structure glowing on black | The Memory stage: one specimen, true black, tight halos and no haze |
| Colour that means something (depth, region, channel) | Five channel colours, one meaning each, the same on every screen |
| Only the active groups glow inside thin outlines | Rooms are 1 px hairlines at rest and fill with light only when used |
| Thousands of dots inside area borders | Every moment is a dot inside its room's outline (the t-SNE layout in `engram/view/layout.py`) |
| A translucent body lit inside | At rest the whole memory stays visible at 22% intensity, and events light it from inside |
| Stacked traces on black, a tick per event, labelled rows A1–A8 | The instrument strip under every live view, and the Swarm's channel rows |
| Selected cells turn white (suite2p) | Pure white means one thing: you selected it, and its trace row turns white too |
| A glow sweeping through an outlined body over time | The model's gaze moving across the desk, word by word, as it writes |
| Line thickness = connection strength (FlyWire) | Vault links, and the threads from used moments to the words that used them |

| He rejected | The rule that prevents it |
| --- | --- |
| Murky or blurry footage | Glow is a sharp core plus one tight halo (2–6 px), never a wide bloom |
| Dense, cluttered tissue; a crowded purple-yellow cell map | Rest state is dim. Only events reach full brightness, and they fade |
| Brainbow (a random colour per cell) | Identity is never a colour. Agents, rooms and models are told apart by place and label |
| Round-1 directions that were sparse and flat (Atlas no, Recorder maybe, Sweep no) | The hero visual fills 60% or more of the screen, is drawn at full real density, and trace rows are filled glowing bands, not thin lines |

## Principles

1. **Every light is a real event.** Nothing moves unless bytes moved or attention landed. No ambient particles, no
   breathing gradients, no idle shimmer. When idle, the GPU loop stops: dark, still and cheap on battery.
2. **Colour is a channel.** There are five saturated colours, each with one stated meaning on every screen, plus white
   for selection. Anything that is neither a channel nor a selection is grey.
3. **Hue says where, brightness says how recently.** Hue gives the place or the act: SSD, RAM, vault, used, fault.
   Brightness gives recency and strength. A resting room is dim blue, a room read just now is bright blue, and a moment
   whose attention share was larger glows harder.
4. **The nearer to the word, the brighter.** The channel lightness order is the data path: used (L 0.92) > RAM (0.83)
   > SSD (0.73) > vault (0.62). The eye goes to the answer first and to the deep archive last.
5. **Picked is not used.** Tensors laid on the desk are amber rings. Moments that drew at least 0.10 of the desk's
   attention (`events.USED`) are filled green. The gap between the two is the story the app tells.
6. **Afterglow instead of animation.** As on a digital phosphor oscilloscope, each event flares and then decays.
   History reads as intensity on the specimen itself, so paths used often stay brighter. There are no averaged line
   charts of "activity".
7. **Big specimen, small readouts.** Each screen has one hero visual. Numbers sit in thin strips and readout
   clusters around it, like the traces under a microscope image.
8. **Measure, don't decorate.** Every visual has a unit and a scale, and you can hover any mark for its exact number
   (ms, MB, GB/s, share, tokens). Numerals are tabular, and a value says when it is an estimate rather than a
   measurement.
9. **Quiet chrome.** Navigation, panels and controls stay in greys with 1 px hairlines and no glow (as in Linear's
   refresh, which cut colour and noise from the chrome). There is no brand accent colour.
10. **Honest by construction.** A decline on a question that was never asked is shown calmly as a dash. A false memory
    is the only alarm. Only the watched layers can glow: layers 12, 16, 20 and 24 are marked, and the other 24
    never light, because nobody measured them.

## Colour tokens

These are defined in OKLCH, with sRGB hex as the fallback. They were checked on true black: every text-carrying
colour reaches at least 4.5:1, and the channels reach 5.2–17.4:1. They were also checked under simulated
deuteranopia, protanopia and tritanopia (Machado 2009, full severity). Every pair of channels stays at least 0.11
apart in OKLab. The closest pairs are RAM/used and SSD/vault under deuteranopia, so those pairs also always differ in
form (rules below).

### Channels: the only saturated colours

| Token | OKLCH | Hex | Means | Never means | Form rule (so meaning survives colour blindness) |
| --- | --- | --- | --- | --- | --- |
| `--ssd` | `oklch(0.73 0.13 225)` | `#28B8E5` | On the SSD: saved tensor rooms at rest, SSD reads and writes, bytes landing on disk (downloads) | "info", links, brand | Capsule outlines; reads are beams |
| `--ram` | `oklch(0.83 0.134 70)` | `#FFB75E` | In RAM now: the always-on core and the desk; "picked for the desk"; a model's RAM footprint | warning | Rings and tiles; never filled green |
| `--used` | `oklch(0.92 0.14 150)` | `#9DFFB3` | Used in this answer: attention share at or above 0.10, at the watched layers | success, "OK", online | Always filled, always with a halo |
| `--vault` | `oklch(0.62 0.19 302)` | `#9D63E3` | In the vault: linked plain-text notes, the archive, words written during sleep | AI, magic, premium | Round dots joined by links; text glyph `Aa` |
| `--fault` | `oklch(0.62 0.22 24)` | `#EE333E` | Something went wrong: a false memory, a failed check, a model that won't fit, a failed download | RAM, heat, "hot" rooms | Always paired with a `×` glyph |
| `--select` | `#FFFFFF` | `#FFFFFF` | You selected this (one item, or a set you drew) | anything else | White outline plus white trace row |

### Intensity steps (one hue, many brightnesses)

| Step | Mix | Used for |
| --- | --- | --- |
| rest | channel at 22% over black | Rooms and moments that exist but are not involved now (the translucent body) |
| resident | channel at 35% | Tensors held in RAM that nothing is touching (the core when idle) |
| event | channel at 100%, decaying | A read, a lay, a write or a look, which fades with the half-lives under Motion |
| hold | channel at 60% | Persistence set to infinite: everything the session touched, graded by how often |

### Neutrals

| Token | OKLCH | Hex | Use |
| --- | --- | --- | --- |
| `--void` | `oklch(0 0 0)` | `#000000` | The stage, i.e. any surface that holds the specimen or a trace |
| `--bed` | `oklch(0.11 0.005 240)` | `#030506` | The app background around stages |
| `--s1` | `oklch(0.155 0.006 240)` | `#0A0D0F` | Panels and sheets |
| `--s2` | `oklch(0.19 0.008 240)` | `#111417` | Raised controls and hover |
| `--hair` | `oklch(0.24 0.010 240)` | `#1B2024` | 1 px hairlines and room outlines (before the channel tint) |
| `--hair-2` | `oklch(0.30 0.012 240)` | `#292F33` | Strong hairlines and the focused control |
| `--ink-4` | `oklch(0.34 0.012 240)` | `#33393E` | Grid lines and minor ticks (never text) |
| `--ink-3` | `oklch(0.58 0.014 240)` | `#737C82` | Labels, units, axes (4.9:1) |
| `--ink-2` | `oklch(0.72 0.012 240)` | `#9EA6AB` | Secondary text, model compute time, Claude yardstick marks (8.5:1) |
| `--ink` | `oklch(0.94 0.006 240)` | `#E8ECEF` | Primary text and readout values (17.6:1) |

```css
:root {
  color-scheme: dark;
  --void:#000; --bed:#030506; --s1:#0A0D0F; --s2:#111417; --hair:#1B2024; --hair-2:#292F33;
  --ink-4:#33393E; --ink-3:#737C82; --ink-2:#9EA6AB; --ink:#E8ECEF; --select:#FFFFFF;
  --ssd:oklch(0.73 0.13 225); --ram:oklch(0.83 0.134 70); --used:oklch(0.92 0.14 150);
  --vault:oklch(0.62 0.19 302); --fault:oklch(0.62 0.22 24);
  --rest:22%; --resident:35%; --hold:60%;
  /* e.g. a resting room outline: color-mix(in oklch, var(--ssd) var(--rest), transparent) */
}
```

The app has one theme, full dark. There is no light mode, because the stage only works on black. Printed figures for
the thesis can use clean white backgrounds, which he said are fine.

### Glow: how "crisp" is made

- **DOM:** a 1 px line in the channel colour, plus `box-shadow: 0 0 6px` of the same colour at 45%. Use nothing
  wider and never stack shadows.
- **WebGL stage:** draw marks additively (`ONE, ONE`) on black. Run one bloom pass at quarter resolution with a 9-tap
  separable Gaussian (sigma of about 2 px at 1×) and mix it back at 0.35. The core of each mark stays sharp at full
  resolution, and the halo is tight. Never use a wide fuzzy bloom.
- **Budget:** glow is used only for events and the current selection. Chrome, panels, text and buttons never glow.

## Type

All three families are OFL and vendored locally. Each has one job.

| Family | Role | Settings |
| --- | --- | --- |
| **Martian Mono** (variable, `wdth` 75–112.5, `wght` 100–800) | The instrument's voice: every number, unit, label, axis and readout | Labels: 10–11 px, `wdth` 87.5, `wght` 500, uppercase, tracking +0.08em, `--ink-3`. Readouts: 13–15 px, `wdth` 100, `wght` 400, `--ink`. Hero numerals: 64–96 px, `wdth` 112.5, `wght` 250 |
| **Geist** (variable, `wght` 100–900) | Words people read: chat, notes, docs, buttons | Body 15/24, chat 16/26, `wght` 400; headings 20–28 px, `wght` 550, tracking −0.01em |
| **Geist Mono** (variable) | Code only: the editor, the terminal, inline code | 13/20 in the editor, 12.5/18 in the terminal |

Rules:
- `font-variant-numeric: tabular-nums` on all Martian Mono text, so numbers never jitter while they update.
- A unit always follows its value after a thin space and is set in `--ink-3`, as in `57.3 MB`, `3.14 GB/s` or
  `0.07 s`.
- There are no all-caps sentences, only short uppercase labels of one to three words.
- Spacing grid is 4 px, with steps of 4, 8, 12, 16, 24, 32 and 48. Corner radius is 2 px for tiles and marks and 6 px
  for panels. Pill shapes are used only for toggles.

## Motion

Motion comes from events, and the layout itself never moves.

| Event | Look | Half-life of the afterglow |
| --- | --- | --- |
| SSD read (a room burst-read) | Blue beam from room to desk slot, then fades | 400 ms |
| Laying the desk | Amber tiles fill in one stroke as the bytes arrive | 400 ms |
| A word looks at a node (per-word looks from `events.py`) | Green flare on that node's tiles, on the watched layer rows only | 1.2 s (attention is the point, so it lingers) |
| Remember (moment joins a room) | Thin blue dashed line from desk to room: the only right-to-left beam | 800 ms |
| Evict (desk cleared) | Amber tiles drain to nothing. Nothing travels, because the room is still on the SSD | 200 ms drain |
| Swap between core and desk (`swap.py`) | Tiles slide between the two RAM blocks: the one real move inside RAM, linear, 240 ms | — |
| Vault write or fade during sleep | Violet dots brighten (write) or step down in brightness (5% per day fade, never removed) | 800 ms |

- **Timebase knob.** Real reads take tens of milliseconds, which is too fast to see. A scope-style timebase sets the
  playback: real time, ×10 slow or ×100 slow. The current setting is always printed in the corner, as in
  `TIMEBASE ×100 SLOW · 20 ms/div`. It is honest slow motion and never invents a duration.
- **Persistence modes** (key `P`), as on a digital phosphor scope:
  - VARIABLE (default): the half-lives above.
  - INFINITE: everything the session touched stays at the hold step, graded by hit count, which gives a heat map of
    where this conversation pulled from, in the same hues.
  - OFF: marks only, no afterglow.
- **UI motion:** 120 ms fades and 160 ms `cubic-bezier(0.2, 0, 0, 1)` for sheets and hovers. There are no springs,
  bounces or slides between screens: a tab change is a cut.
- **Data motion is linear.** Bytes move at a constant rate, because ease curves would lie about speed.
- **Reduced motion:** no beams and no afterglow. Events become instant fills plus a tick in the strip.
- **Frame loop:** the stage runs at display refresh (120 Hz ProMotion) only while something is decaying, then stops.
  DOM readouts update at 10 Hz at most.

## The app frame

- **Top strip** (44 px, `--bed`, hairline below):
  - Left: the working name `engram`, set in Martian Mono until the name is picked.
  - Centre: six screen keys styled as hardware keys, `MODELS CHAT CODE SWARM MEMORY BENCH`. The current key gets a
    white underline 2 px thick. Keys `1`–`6` switch screens.
  - Right: always-on live meters, each with a label above a value:
    - RAM: a thin amber bar against the 24 GB scale with a pressure word ("normal", "tight");
    - SSD: a blue spark of read GB/s over the last 30 s;
    - the loaded model;
    - the last time to first word.
- **No sidebar chrome.** Each screen owns the full width below the strip.
- **Keyboard, scope-style:** `Space` RUN/STOP (freezes the live views), `[` and `]` timebase, `P` persistence, `C`
  two measuring cursors, `Esc` clears the selection.
- **Reference frame** for the sizes below: 1512 × 982 points (the MacBook Pro default scaled resolution). Every
  layout also reflows to one column at 900 px and under.

## Screens

### Models: what fits this Mac

**Hero: the fit gauge** (top 30%). One wide horizontal bar is this Mac's unified memory, 24 GB, drawn as a calibrated
ruler with a minor tick every 1 GB and a labelled tick every 4 GB.
- Live contents, read from the system:
  - macOS and other apps in `--ink-4`;
  - the loaded model's weights in solid amber;
  - the engram core in amber at the resident step;
  - the desk flares amber when it fills.
- A white hairline marks 24 GB. A hatched grey zone marks what macOS keeps for itself.
- The memory pressure word sits at the right end in Martian Mono: "normal", "tight" or "swapping", taken from
  Activity Monitor's three states.

**Signature: the ghost fit.** Hover or select any model in the list, and its footprint is projected onto the gauge
as an amber outline, with no fill. The footprint is weights, plus KV for the chosen context, plus the engram core.
- If it fits, a readout says `fits · 6.2 GB spare`.
- If it crosses the hard line, the part past 24 GB turns into a red hatched outline with `× needs 3.1 GB more`.
- You see the answer before you download anything.

**The list** (below, 56 px rows, grouped by family):
- name and quant, in Martian Mono;
- parameters;
- RAM at load as an amber bar on the same scale as the gauge, so rows and gauge line up;
- disk size as a thin blue bar under it;
- memory form as a glyph: `tensors` for Qwen3 1.7B/4B/8B, `words` for Qwen 27B, whose linear-attention layers keep no
  KV;
- measured speed on this Mac (time to first word, decode tok/s), read from the dated records. A model that has never
  been run here shows `not measured`, never a guess.

**Downloading from Hugging Face:** the row's blue disk bar fills from the left as bytes land on the SSD, with
`412 MB/s · 1 m 40 s left` beside it and a pause key. A failed download leaves the bar where it stopped, with a red
`×` and the reason in words.

### Chat: the eyepiece

**Layout:**
- Left 62%: the conversation in a 720 px column.
- Right 38%: the eyepiece, a black field showing the specimen map of moments (the t-SNE layout), framed by a fine
  reticle (centre cross and edge ticks, `--ink-4`).
- Above the composer, three controls in a row: the memory switch, the reach turret and the model chip.

**Memory switch:** a two-position hardware toggle labelled `MEMORY` with `ON` and `OFF`. When it is OFF:
- the eyepiece goes dark except for a centred `memory off` label in `--ink-3`;
- the turret greys out;
- each answer's data path shows only the model segment.

This makes the with/without comparison one flick.

**Reach turret:** a microscope nosepiece. Real objectives carry a coloured ring that tells you what each one does
(ISO 8578), and the turret uses the same idea. There are three detents, and each one adds a layer:
- `CORE` has an amber ring and is always included while memory is ON;
- `ROOMS` has a blue ring;
- `VAULT` has a violet ring.

Turning to a detent lights the rings it includes. The turret is the same control in Chat, Code personas and Swarm
agents.

**Each answer:**
- The text is in Geist 16/26.
- Words whose attention went mostly to a used moment carry a 1 px green underline at 40%. The data comes from the
  per-word looks in `events.py`.
- Hover a word, and the moment it looked at hardest flares in the eyepiece, with that moment's text in a small sheet.
- Under the text is the inline data path (next section).
- Picked moments show in the eyepiece as amber rings and used ones as green filled dots. Everything else in the
  memory rests at 22% blue.

### The data path of one answer

**Inline form** (one 20 px strip under every answer). A segmented time bar, drawn to scale from question to last
word. Each segment is coloured by where the time was spent:

| Segment | Colour |
| --- | --- |
| `choose` (picking the room) | `--ink-3` |
| `SSD read` | `--ssd` |
| `lay desk` | `--ram` |
| `prefill` | `--ink-2` |
| first word | a white tick |
| `decode` | a thin `--ink-2` line |

At the right end, in Martian Mono 11 px, sits `● 3 used ○ 5 picked · 57 MB · 3.1 GB/s · 0.07 s`. The dot is green
and the ring is amber. Click the strip to open the full light path.

**Full form: the light path** (a full-width sheet). It reads left to right like the optical path of a microscope.
There are six stations, each aligned to a shared time ruler at the bottom:

1. **Question:** the question text in `--ink`, 13 px.
2. **Choose:** the rooms the embedder ranked, as ticks on a 0–1 similarity scale, with the chosen room lit. If
   `choose` does not expose its scores, only the chosen room is shown, and nothing is invented.
3. **SSD:** the chosen room's capsule in blue, with `bytes · ms`. At 112 KB per token on the 1.7B, a full 512-token
   room is about 57 MB.
4. **Bus:** a beam whose thickness is to scale (1 px = 2 MB), labelled with GB/s and the read's share of the wait.
5. **Desk (RAM):** a horizontal strip of every token on the desk, widths to scale:
   - header in `--ink-4`;
   - the room's saved tensors as solid amber;
   - the 4 closest moments as hatched amber, because they were re-read from words rather than saved tensors;
   - the question in `--ink-3`.

   Under the strip are four thin raster rows labelled `L12 L16 L20 L24`, showing each node's attention share over
   the answer as green brightness. Nodes at or above 0.10 get a filled green marker, and nodes below stay amber rings.
6. **Answer:** the written words. From each used node, threads run to the words that looked at it hardest. Thread
   thickness is that word's share, as in the FlyWire connection graphs. Picked-only nodes have no threads.

**Time ruler:** `choose | read | lay | prefill → first word → decode`, with the session's p50 and p90 for each phase
as faint whiskers. Under it, the full set of answer metrics in one readout row:
- right or wrong;
- honest or false memory;
- time to first word and total time;
- prefill and decode tok/s;
- retrieval p50 and p90;
- bytes, GB/s and share of the wait;
- context tokens used against the history's total;
- peak RAM.

### Memory: the stage

The Memory screen has two modes, picked with a two-key switch at top left: `LIVE` and `VAULT`. A sleep state takes
over LIVE when the engine naps.

#### LIVE: tensors moving between the SSD and RAM

**Layout at 1512 × 982:**
- the stage takes the top 58% (about 570 px), true black, full width;
- a 64 px vault drawer sits under it;
- an instrument strip takes the remaining 260 px.

The stage has three regions, side by side:

1. **SSD plate** (left 46%). Every room on the SSD is drawn as a capsule outline, a 1 px hairline tinted blue at the
   rest step.
   - Each capsule's area is proportional to its tokens (512 at most), placed at the t-SNE position of its moments.
   - Inside each capsule, every moment is a 2 px dot, also at rest.
   - With a few thousand moments this is dense and alive at rest, the "thousands of dots inside area borders" he
     loved, and never an empty black field.
   - A label `SSD · 312 rooms · 17.8 GB` sits at the plate's top left in Martian Mono labels.
2. **The bus** (middle 14%). A horizontal channel with a calibrated vertical scale from 0 to 8 GB/s at its left edge.
   - Reads cross the bus left to right as beams. Thickness is bytes to scale, brightness decays with the afterglow,
     and the beam's height on the scale is the measured GB/s.
   - Writes (`remember`) cross right to left as dashed blue lines.
   - Read and write differ in direction and stroke, so colour is not needed to tell them apart.
3. **RAM plate** (right 40%). Two blocks stacked:
   - **Core** (subconscious, always on): a block of tensor tiles at the resident step of amber. It is held, but not an
     event.
   - **Desk** (conscious): a slot frame of 28 rows, one per layer of the 1.7B, with width proportional to token
     capacity.
     - When a room lands, its tiles fill amber in one stroke, as the burst arrives.
     - The 4 closest moments fill as hatched amber blocks at the right end.
     - Four rows, 12, 16, 20 and 24, carry a small white tick and label at the left edge: they are the watched layers.
   - A readout cluster sits at the top right:
     - `DESK 612 / 48,900 tok`;
     - `RAM 1.71 GB · peak 1.83`;
     - `READ 57.3 MB · 3.14 GB/s · 18 ms · 12% of wait`.

**Signature: the gaze.** While the model writes, each word flares green on the desk tiles of the nodes it looked at,
on the four watched rows only, brightness by share.
- Across an answer you see the model's attention sweep through the outlined desk, the "glow sweeping through an
  outlined body" he loved.
- The same nodes flare green back on the SSD plate at their home rooms, so you see which rooms really paid off.
- Rooms that were read but never used stay amber-ringed with no green. Picked is not used, and you can see it.
- Every frame comes from real per-word looks.

**Eviction and swap:**
- When the desk is cleared, its tiles drain in 200 ms and the RAM readout drops. Nothing flies back, because the SSD
  copy never left.
- When `swap.py` moves a room between the desk and the core, its tiles slide 240 ms between the two RAM blocks. This
  is the only sliding motion in the app, because it is the only real move.

**Selection:** click a room or a moment, and it turns white: its outline, its dots and its trace row in the strip.
- A right sheet (360 px, `--s1`) shows:
  - the moments' text and their dates;
  - the bytes on disk;
  - how many times the room has been read;
  - its last attention share.
- Draw a lasso to select a set, the Rastermap way.

**The vault drawer** (64 px under the stage): a thin strip of violet dots, one per note, ordered by date.
- It lights when notes are written in sleep, or read with the `VAULT` reach.
- Click it to switch to VAULT mode.

**The instrument strip** (260 px): stacked trace rows on `--void`, each 28 px.
- Each row has a left label gutter (72 px, Martian Mono labels) and a filled band with glow, not a thin line.
- There is a tick for each event, and the rows scroll right to left at the timebase (default 5 s/div).

| Row | Trace |
| --- | --- |
| `SSD R` | read GB/s, blue band, tick per burst |
| `SSD W` | write MB/s, blue dashed band |
| `RAM` | resident GB, amber band, peak marker |
| `DESK` | tokens on the desk against the history total (`--ink-4` ceiling line) |
| `L12` `L16` `L20` `L24` | a green tick raster, one tick per word where some node drew 0.10 or more at that layer |
| `TTFT` | one dot per answer on a 0–0.2 s scale, with the 0.07 s reference line |

At the right end of the strip:
- `RUN/STOP`;
- the timebase readout;
- two draggable measuring cursors that read Δt, bytes and mean GB/s between them, as on a real scope.

#### VAULT: the atlas

The full stage becomes the vault as a graph, Obsidian-like but crisp, rendered on the GPU with sigma.js.
- **Notes:** violet dots, sized by how many notes link to them.
- **Links:** lines whose thickness is link strength.
- **Topic clusters:** each has a thin translucent hull (a 1 px `--hair-2` outline), so only active regions glow inside
  thin outlines.
- **Rings:** notes that also exist as tensor rooms carry a thin blue ring. Notes in the current answer glow green, and
  notes on the desk carry an amber ring.
- **Reading pane:** click a note to open it in a 420 px right pane, with plain text, its links and backlinks, rendered
  as Markdown.
- **Growth scrub** along the bottom, like Obsidian's time-lapse but measured:
  - drag through the days to watch the vault grow;
  - brightness is each note's strength after the 5% per day fade, so old notes dim but never disappear.

#### Sleep state

When the engine naps on the charger, the LIVE stage dims to 30%. Distilling shows as real events:
- moments read from rooms appear as blue flares;
- quiz-checked notes are written to the vault as violet flares in the drawer;
- the fade steps down the brightness of old notes.

A quiet label at top left reads `SLEEPING · distilling 41 / 120`. Nothing else moves.

### Code: the workbench

**Layout:** a workspace in the Claude Code mould.
- Left 240 px: files.
- Centre: the editor (CodeMirror) with tabs.
- Bottom 30%: two panes. One is the agent transcript with the run trace; the other is a terminal (xterm.js).
- Right 300 px: **the rack**.

**The rack:** modules stacked like 1U rack units, a nod to Teenage Engineering's modular hardware. Each tile is 40 px
tall and shows:
- a type label (`MCP`, `PLUGIN`, `SKILL`, `PERSONA`) in Martian Mono labels;
- a name in Geist;
- a status dot: white when it is active this session, a hollow `--ink-3` ring when idle, and red `×` when failing.

Persona tiles also carry their reach as three tiny rings (amber, blue, violet), lit or not. A persona is a reach plus
its own rooms, so selecting one changes what memory the workspace reads.

**Signature: memory in the gutter.** A 3 px bar beside the line numbers shows which lines memory wrote:
- green where the line came from a used moment, such as a helper's exact name, unit or quirk;
- violet where it came from a vault note, such as a saved "your fix" note.

Hover the bar to see the moment or note it came from. When you edit the model's code and save, a violet tick lands
on the changed lines with `your fix · kept`. That fix will feed the next answer.

**The run trace** (above the transcript, 120 px), in the style of Perfetto's tracks:
- one row for the model, one per MCP server and one for the shell;
- each call is a bar in `--ink-2`, and memory reads inside a call show as blue, amber and green ticks on it;
- area-select a span to total its time, tokens and bytes.

### Swarm: the multi-well plate

**Hero: an 8-well plate** (top 55%). Microscopy plates hold many specimens side by side, and each agent is one well.
- The wells sit in a 2 × 4 grid. Each well is a miniature of the LIVE stage for that agent's own memory: its rooms as
  dots in outlines and its RAM block, with the same beams, gaze and afterglow.
- Wells are labelled `A1`–`A8` in Martian Mono, with the persona and model below.
- Agents are told apart by position and label only, never by colour. Inside every well the colours keep their one
  meaning.
- Click a well, and it expands to the full stage while the others shrink to a strip.

**Channel rows** (bottom 45%): one 44 px row per agent, `A1`–`A8`, aligned on one time axis.
- An amber band shows desk occupancy.
- Blue ticks above it mark SSD reads, green ticks mark used looks, and violet ticks mark vault reads.
- Messages between agents are thin `--ink-2` vertical connectors with small arrowheads at the moment sent, as with
  Perfetto flows.
- A selected agent's label and row turn white.

### Bench: the long exposure

**Hero: the headline** (top 30%). Martian Mono, 96 px, `wght` 250, with each figure's source record path in `--ink-3`
under it:
- `62–68 / 85` (Qwen 27B with memory);
- `0 / 85` beside it (without).

Under them sits the line "better, never heavier".

**Signature: the flat line** (35%). A big chart with memory size in tokens on x (log scale, 1K to 2M, cut lines at
64K, 256K, 1M and 2M labelled like exposure marks) and time to first word on y.
- Engram's line stays flat at 0.07 s in blue (tensors) with a tight glow.
- Baselines that read their whole history rise in `--ink-3`.
- A twin chart under it does the same for peak RAM (engram flat at 1.65–1.83 GB).
- Every point links to its dated JSON record.

**The Long Haul tape** (20%): 110 working days as one long ribbon, with the token count growing as an `--ink-4` area.
- Probes are arcs from the day they were planted to the day they were asked.
- A solid stroke means right and a dashed stroke means wrong, missed or stale.
- A red arc with `×` means a false memory.
- A short calm dash means a correct decline on something never told.
- A contender picker shows one contender's arcs at a time, so the tape never crowds.

**Small multiples** (below, scrolling): one panel per probe type (facts across the gap, changed facts, two-hop links,
corrected maths, the page that grows, code that must fit, look-alikes, never said).
- Each panel is a dot plot with one row per contender.
- Marks show the grade: filled means right, hollow means wrong, a dash means a correct decline, and a red `×` means a
  false memory.
- Contender colour follows the memory form, the same meanings as everywhere else:

| Contender | Mark |
| --- | --- |
| tensors (rooms) | `--ssd` |
| words (27B, Ollama, vault) | `--vault` |
| no memory | `--ink-3` |
| Claude yardstick | hollow `--ink-2`, with its tokens and $ at list price in the row's readout |

## Components (the parts every screen reuses)

| Component | What it is |
| --- | --- |
| **Readout** | A Martian Mono label above a value and unit. Comes in three sizes: strip (11/13), cluster (11/15) and hero (12/64–96) |
| **Trace row** | A labelled 28–44 px row on black with a filled band, an event tick raster and a white state when selected. Built on uPlot |
| **Stage** | The regl canvas: rooms, dots, tiles, beams, afterglow and bloom. One instance per stage or well |
| **Turret** | The reach control (CORE, ROOMS, VAULT) with coloured rings |
| **Toggle** | Hardware two-position switch (MEMORY ON/OFF, LIVE/VAULT) |
| **Gauge** | A calibrated ruler bar with a ghost-fit overlay (Models, RAM meter) |
| **Path strip** | The inline data path under an answer |
| **Module tile** | A 1U rack unit with type, name and status dot (Code) |
| **Cursor pair** | Two draggable measuring lines with a Δ readout (any trace) |
| **Timebase knob** | Real time, ×10 or ×100 slow, always printed on screen |

## Libraries: pinned, vendored, offline

Everything is copied into `v2/engram/app/static/vendor/<package>@<version>/` and served by the local server. A
`vendor/LOCK.json` records each file's source URL and npm `dist.integrity`. An import map in `index.html` maps bare
names (`preact`, `preact/hooks`) to the vendored files, so there is no build step for the app itself.

The current page loads IBM Plex from Google Fonts. This direction removes that, so the app makes no network request
other than to 127.0.0.1, plus Hugging Face only when you press download.

Every version below was released at least two weeks before 4 Nov 2026. The file paths were checked against the
published packages.

| Package | Version | License | Job | Files to vendor |
| --- | --- | --- | --- | --- |
| preact | 10.29.8 | MIT | UI components without a build | `dist/preact.module.js`, `hooks/dist/hooks.module.js` |
| htm | 3.1.1 | Apache-2.0 | JSX-like templates in plain JS | `dist/htm.module.js` |
| @preact/signals | 2.11.3 | MIT | Telemetry state that updates at 10 Hz without re-rendering the tree | `dist/signals.module.js` |
| @preact/signals-core | 1.14.4 | MIT | Dependency of the above | `dist/signals-core.module.js` |
| regl | 2.1.1 | MIT | WebGL for the stage: instanced dots and tiles, beams, ping-pong half-float afterglow buffers, bloom | `dist/regl.min.js` |
| uplot | 1.6.32 | MIT | Trace rows and strip charts. Canvas 2D; its README measures 3,600 streaming points at 60 fps for about 10% CPU | `dist/uPlot.esm.js`, `dist/uPlot.min.css` |
| sigma | 3.0.3 | MIT | GPU graph for the vault atlas | bundled into `vendor/graph.js` (below) |
| graphology | 0.26.0 | MIT | Graph data structure for sigma | `vendor/graph.js` |
| graphology-layout-forceatlas2 | 0.10.1 | MIT | Vault layout, run in a web worker | `vendor/graph.js` |
| @observablehq/plot | 0.6.17 | ISC | Bench figures: dot plots and small multiples | `dist/plot.umd.min.js` |
| d3 | 7.9.0 | ISC | Scales and formats; required by Plot | `dist/d3.min.js` |
| codemirror | 6.0.2 | MIT | Editor in Code | bundled into `vendor/editor.js` |
| @codemirror/view / state / language / commands | 6.43.14 / 6.7.6 / 6.13.1 / 6.11.1 | MIT | Editor core, pinned together | `vendor/editor.js` |
| @codemirror/lang-python / lang-javascript / lang-markdown | 6.2.1 / 6.2.5 / 6.5.2 | MIT | Languages the Long Haul uses | `vendor/editor.js` |
| @xterm/xterm | 6.0.0 | MIT | Terminal in Code | `lib/xterm.mjs`, `css/xterm.css` |
| @xterm/addon-fit | 0.11.0 | MIT | Terminal sizing | `lib/addon-fit.mjs` |
| marked | 18.1.1 | MIT | Markdown for chat and vault notes | `lib/marked.esm.js` |
| dompurify | 3.4.17 | MPL-2.0 or Apache-2.0 | Sanitises model output before it becomes HTML (model text is untrusted) | `dist/purify.es.mjs` |
| @fontsource-variable/martian-mono | 5.3.0 | OFL-1.1 | Readout type, with both axes | `standard.css` plus its latin and latin-ext `standard` woff2 files |
| @fontsource-variable/geist | 5.3.0 | OFL-1.1 | Text type | `wght.css` plus latin and latin-ext woff2 files |
| @fontsource-variable/geist-mono | 5.3.0 | OFL-1.1 | Code type | `wght.css` plus latin and latin-ext woff2 files |
| lucide-static | 1.58.0 | ISC | The few icons, about 15 SVGs copied by name, inlined | `icons/<name>.svg` |

**Build-time only, not shipped:** esbuild 0.28.2 (MIT). It makes the two vendor bundles, `graph.js` (sigma,
graphology, ForceAtlas2 and their small dependencies) and `editor.js` (CodeMirror), from the pinned packages. The
bundles are written once into `vendor/`, so the app runs without Node.

**Deliberately not used:**
- a CSS framework (the tokens above are the system);
- an animation library (CSS, Web Animations and the regl loop are enough);
- three.js (the stage is 2D by design; if a 3D translucent shell is ever wanted, pin three 0.186.1);
- any CDN at runtime.

**CSP for the page:** `default-src 'self'; img-src 'self' data:; connect-src 'self' https://huggingface.co
https://*.hf.co; worker-src 'self' blob:`.

### What the visuals need from the engine (for the lead)

These are proposals only. Nothing here changes `notes.py`, `rooms.py`, `memory.py` or `events.py`.

- **Already there:**
  - `answer` events with the desk nodes, the per-word looks and the used nodes (`events.py`);
  - `remember` events;
  - room sizes and vectors (`rooms.py` `index.json` and `vectors.npy`);
  - moment positions (`view/layout.py`).
- **To add, as new event types written by the new layers, with defaults that keep today's behaviour:**
  - `read` {room, bytes, ms};
  - `lay` {room, tokens, ms};
  - `evict` {room, bytes};
  - `swap` {room, from, to, bytes};
  - `vault` {note, op: write | read | fade, strength};
  - one `metrics` record per answer carrying the metrics listed in BUILD_PLAN.
- **Transport:** a tail of `events.jsonl` served by the local app, as Server-Sent Events. If the JSON-only check
  rules SSE out, use 10 Hz polling of a JSON endpoint instead. The stage only needs events, never tensors.

## What makes it unlike anything else

- **It shows where an answer physically came from.** Local LLM apps (Ollama, LM Studio and the chat front ends) show
  a chat and a model list, and RAG apps list "sources". This one draws the byte path, measured: SSD room → bus → desk
  in RAM → the watched attention layers → the very words.
- **Picked and used are different marks.** Retrieval UIs show what was fetched. This shows what the model actually
  looked at, at a stated threshold (0.10 of the desk's attention), on the layers that were measured and no others.
- **History is afterglow on the specimen**, borrowed from digital phosphor oscilloscopes, rather than a dashboard of
  averaged line charts. Paths used often stay bright, and infinite persistence turns a whole session into a heat map
  without adding a colour.
- **One colour language across six screens.** Blue means on the SSD in Models, Chat, Memory, Swarm and Bench alike.
  Brightness follows nearness to the word.
- **Honest slow motion.** A scope timebase lets you watch an 18 ms read at ×100 slow, and the screen always says it
  is slowed down.
- **Instrument controls for a memory**: a nosepiece turret for reach, scope cursors to measure bytes between two
  moments, and a multi-well plate for a swarm. These are real lab metaphors that carry function, not ornament.

## How to open the design round with him

His global rules say a design round opens with a board of real references he can mark love, maybe or no, and that
mockups are rendered only from real photos or high-fidelity renders. For this direction:
1. **Board:** real screenshots and photos from the references below. The most important are a digital phosphor scope
   screen in persistence mode, Open Ephys stacked traces, Neuroglancer and FlyWire Codex on black, OP-1 field screens,
   the Activity Monitor memory pressure graph, the Instruments and Perfetto timelines, and a multi-well plate under a
   fluorescence microscope.
2. **Then render the Memory stage from real data.** Use a real `events.jsonl` and real rooms (for example the farmer
   life, seed 0), at full density with the glow pipeline above. The round-1 lesson was that sparse, flat drawings lose
   to glowing real references, so the stage must be rendered, not drawn.

Note: the inspiration bank at `~/Desktop/inspiration-bank` is not on this Mac. No folder of that name exists under
the home directory, so it could not be skimmed. His loved and rejected picks above come from the memory notes about
boards 1 and 2 and the round-1 directions.

## References

His own boards (from the memory notes):
- Brain view board 2, picks in its db at `boards/brain-view-2`: https://claude.ai/artifact/1TnhhUGodwsLuEKXqrTyt8
- Directions round 1 (Atlas no, Recorder maybe, Sweep no): https://claude.ai/artifact/5VUmJC5P4QTAaQm9Axx4XV

Instruments and consoles:
- Teenage Engineering OP-1 field: reworked high-resolution colour screen, "all graphics reworked, screen by screen":
  https://teenage.engineering/products/op-1
- OP-1 field guide (four colour-coded encoders: blue, ochre, gray, orange):
  https://teenage.engineering/_img/676030a8ef599a28c8bc97cf_original.pdf
- OP-1 manual: a screen element's colour names the encoder that changes it (colour as a binding, not decoration):
  https://manuals.online/teenage-engineering/synthesizer/op-1/user-manual/u0yr
- OP-1 field launch notes (new palette, flush glass screen): https://www.thisispaper.com/mag/op-1-field-teenage-engineering
- Apple Activity Monitor, memory pressure green, yellow and red: https://support.apple.com/kb/PH19650
- Apple Instruments help (timeline pane, flags on the timeline):
  https://developer.apple.com/library/archive/documentation/AnalysisTools/Conceptual/instruments_help-collection/Chapter/Chapter.html
- Instruments VM Tracker beside Allocations (memory regions as tracks):
  https://useyourloaf.com/blog/tracking-background-memory-usage-of-ios-4-apps/
- Grafana visualizations (state timeline, heatmap): https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/
- Grafana state timeline (rows per entity, colour from value mappings):
  https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/state-timeline/
- Linear, "How we redesigned the Linear UI" (LCH themes from three variables, less colour in the chrome):
  https://linear.app/now/how-we-redesigned-the-linear-ui
- Vercel Geist design system: https://vercel.com/geist
- Geist colours (10-step scales by role): https://vercel.com/geist/colors
- Geist font: https://vercel.com/geist/font
- Vercel tracing (one request's path as spans): https://vercel.com/docs/tracing
- Perfetto UI (tracks, pinned tracks, area selection): https://perfetto.dev/docs/visualization/perfetto-ui
- Splunk APM waterfall (span bars on one time axis):
  https://splunk.github.io/observability-workshop/en/splunk4rookies/observability-cloud-short/4-apm/6-apm-waterfall/
- NASA Open MCT, a web mission-control telemetry framework: https://nasa.github.io/openmct/about-open-mct

Oscilloscope phosphor and persistence:
- Digital scopes offer an analog display mode (intensity grading):
  https://www.electronicdesign.com/technologies/industrial/displays/article/21779275/digital-scopes-offer-analog-display-mode
- Digital phosphor oscilloscope combines analog and digital strengths:
  https://www.controleng.com/digital-phosphor-oscilloscope-combines-analog-digital-strengths
- PicoScope display options (variable and infinite persistence, colour grading):
  https://www.picotech.com/library/knowledge-bases/picosample-knowledge-base/display-options-in-picosample
- P31 phosphor, yellowish green at about 531 nm (Sylvania SE3AP31 datasheet): https://lampes-et-tubes.info/cr/cr152.php?l=e
- SDR++ waterfall display: https://www.rtl-sdr.com/sdr-version-1-0-0-released/

Telescope and observatory software:
- N.I.N.A. imaging tab (dockable panels, live image with histogram, HFR history):
  https://nighttime-imaging.eu/docs/master/site/tabs/imaging
- Stellarium review (night mode that filters the screen to red):
  https://www.digitalcameraworld.com/uk/reviews/stellarium-review

Microscopy and neuroscience viewers:
- Open Ephys LFP Viewer (stacked channels, labels, colour by group, TTL overlays):
  https://open-ephys.github.io/gui-docs/User-Manual/Plugins/LFP-Viewer.html
- Rastermap (sorted raster, drawn regions, traces below): https://github.com/MouseLand/rastermap
- suite2p (cell masks, selected cells and their traces): https://github.com/MouseLand/suite2p
- Neuroglancer (WebGL volumetric viewer, cross sections plus 3D): https://github.com/google/neuroglancer
- FlyWire Codex: https://codex.flywire.ai/
- FlyWire whole-brain connectome paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC11446842
- ISO 8578, colour-coded rings on microscope objectives: https://www.iso.org/standard/50988.html
- Obsidian graph view (global and local graphs, groups, time-lapse): https://obsidian.md/help/plugins/graph

Libraries:
- uPlot (size, streaming benchmark): https://github.com/leeoniya/uPlot
- sigma.js (WebGL graphs on graphology): https://www.sigmajs.org/
- Versions, dates and licences were read from the npm registry (`https://registry.npmjs.org/<package>`), and the file
  paths from jsDelivr's package listings (`https://data.jsdelivr.com/v1/packages/npm/<package>@<version>`).
