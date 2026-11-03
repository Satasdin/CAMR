# Design decision, 4 Nov 2026 (overnight)

**Picked: Instrument**, with grafts from Phosphor and Living. The full spec the builders follow is `DIRECTION.md` in
this folder. The three proposals stay in `instrument/`, `deck/` and `living/`.

| | Taste | SSD ↔ RAM, used | Buildable tonight | Distinct | Coherent | Total |
| --- | --- | --- | --- | --- | --- | --- |
| Instrument | 5 | 5 | 4 | 4 | 5 | **23** |
| Phosphor (deck) | 4 | 5 | 3 | 3 | 4 | 19 |
| Living | 3 | 4 | 2 | 5 | 4 | 18 |

**Why Instrument:**
- It is the microscope you chose on 2 Nov, and it covers your board picks:
  - crisp glow on true black, with no wide bloom;
  - one meaning per colour;
  - white for selected, as in suite2p;
  - stacked trace rows with a tick per event;
  - "picked" (amber ring) shown apart from "used" (green fill).
- It is also the one that can be built well in a night: a flat stage in a small WebGL library, with one renderer for
  everything.

**What was grafted in:**
- **From Phosphor:** rooms drawn as tensors (layer rows by token columns), so the picture says "not a vector
  database". Also the RAM ruler to scale beside the model's weights, the context meter in Chat, the per-answer lanes,
  and a bus line on every screen that flares when memory moves.
- **From Living:** the thick tensor beam beside a hairline thread of words, so the 29,000× size gap shows without a
  number. Also the copy keeping a ring on its home room, the model-anatomy glyph (why the 27B reads words), and the
  reach as an aperture that dims everything not being read.

**Left out:**
- Living's 3D tilted planes: they risk murk, and you had passed over the "living network" idea.
- Phosphor's mono-heavy, text-dense frame.

**Look at this first in the morning:**
1. Open the app on a real memory (a loaded life, such as farmer seed 0) and go to **Memory** (key `5`). Ask one
   question in **Chat** (key `2`) and watch the eyepiece:
   - a blue beam crosses from the SSD;
   - the desk fills amber;
   - green lands only on what the answer used.

   This render of your own memory is the mockup. Judge it, not this file. Press `]` for `×10` slow motion.
2. Then click the thin bar under the answer: the **light path** shows every metric for that one answer.
3. Answer the three taste questions at the end of `DIRECTION.md`:
   - amber or ember for RAM;
   - a flat or a layered stage;
   - Martian Mono or IBM Plex for numbers.

   Each is a small change.

**Notes:**
- `~/Desktop/inspiration-bank` is not on this Mac, so all three proposals worked from your two board notes.
- There is no stock photography. The big pictures are live renders of real data. The one real image is the
  headless-browser screenshot of the generated catering page in Bench.
