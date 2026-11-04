# Screens: the contract

The app is one page. The shell (`/static/shell.js`) draws the top strip, owns the keyboard and the polling, and shows
one screen at a time. Each screen is one ES module here, `screens/<id>.js`, for the five ids `models`, `chat`, `code`,
`memory` and `bench` (keys `1`–`5`). The design is `v2/design/DIRECTION.md`: read it before building.

## The module

```js
// screens/chat.js
export function mount(el, api) {
  const { html, render, signal } = api.ui;      // preact, htm and signals from /static/vendor/ui.js
  api.css("/static/screens/chat.css");           // your own stylesheet, loaded once
  render(html`<${Chat} />`, el);
  return {
    show() { /* start polling and frame loops */ },
    hide() { /* stop them: a hidden screen does no work */ },
    key(e, { typing }) { return false; },          // true when you handled the key
  };
}
```

- **`mount(el, api)`** runs once, on the first visit. `el` is the screen's own empty `<section>`, filling the area
  under the strip (`position: absolute; inset: 0; overflow: auto`). It may be `async`.
- It returns a **handle**, every part optional:
  - `show()` runs right after mount and on every later visit;
  - `hide()` runs when another screen is chosen. Stop timers, `requestAnimationFrame` loops and polls here;
  - `key(e, { typing })` gets every keydown first while the screen is on show. Return `true` to take it (the shell
    then calls `preventDefault`). `typing` is true when focus is in a text field.
- A screen that throws while loading shows a red `×` and the error in its section; the others carry on.

## `api`

| Name | What it is |
| --- | --- |
| `api.get(path, params)` | GET a JSON route with the launch token; `params` become the query. Throws `api.ApiError` (`status`, `message`) |
| `api.post(path, body)` | POST JSON with the token. While any POST is in flight the logs are polled 4 times a second |
| `api.on(name, fn)` | Subscribe; returns the unsubscribe function. Names: `event` (each new `events.jsonl` line, with its number `i`), `metric` (each new `metrics.jsonl` record), `replay` (`R`), `cursors` (`C`), `escape` (`Esc`), `focus` (`/` when no screen took it), `run` (Space: `true` running, `false` stopped) |
| `api.emit(name, data)` | Send to the same listeners (screens may talk to each other this way) |
| `api.state` | Signal: `/api/state` every 2 s (`moments`, `rooms`, `measuring`, `model`, `fixture`, `tiers` and `reaches` when the app has them, `route_errors`) |
| `api.sys` | Signal: `/api/sys` every second (`total_bytes`, `used_bytes`, `process_bytes`, `pressure`, `disk`) |
| `api.lastAnswer`, `api.lastMetric`, `api.lastRead` | Signals: the latest answer or agent event, metrics record, and SSD read `{bytes, gbps, at}` |
| `api.measuring` | Signal: the measuring job or `null`. While set, every stage shows `MEASURING · VIEW PAUSED` and draws nothing |
| `api.running` | Signal: `false` after Space (RUN/STOP): freeze stages and queue events |
| `api.timebase` | Signal: `1`, `10` or `100` (`[` and `]`). Print it as `TIMEBASE REAL` or `TIMEBASE ×10 SLOW` |
| `api.persistence` | Signal: `variable`, `infinite` or `off` (`P`) |
| `api.reducedMotion` | Signal: `prefers-reduced-motion`. No travel and no afterglow: instant fills that clear after 600 ms |
| `api.fixture` | Signal: true when the server shows a recorded memory read-only |
| `api.current`, `api.goto(id)` | The screen on show, and switching screens |
| `api.frame()` | Call once per drawn frame; `?debug=1` prints frames per second in the strip (it must read 0 at rest) |
| `api.css(href)` | Load a stylesheet from `/static/` once |
| `api.fmt` | Numbers with units: `bytes(n)` (decimal, for files and disks), `ram(n)` (binary, as macOS counts RAM), `gbps`, `s`, `ms`, `tps`, `tok`, `params`, `int`, `duration`; each gives `[value, unit]`, or `["—", ""]` when unmeasured. `fmt.text(pair)` joins them with a thin space |
| `api.parts` | `Val` (a value and its unit in `--ink-3`), `Readout` (a `--t-label` over a value), `Glyph` (`dot`, `ring`, `tri`, `cross`, `check`, `empty`, drawn as SVG), `Icon` (lucide by name), `Empty` (the hairline empty state) |
| `api.ui` | Everything `/static/vendor/ui.js` exports: `h`, `html`, `render`, `Fragment`, the hooks, `signal`, `computed`, `effect`, `batch`, `useSignal`, `useComputed`, `useSignalEffect` |
| `api.icons` | The inlined lucide SVG strings |

The bus line (the strip's bottom hairline) flares by itself from new `answer` and `agent` events: the SSD-to-RAM
gradient for a read (2 px over 32 MB), amber for a RAM hit, violet for words. Screens do not draw it.

## Rules every screen keeps

- **Colour:** no colour literal outside `/static/tokens.css`. Use the custom properties (`var(--ssd)`) in CSS, and read
  them with `getComputedStyle` for shaders. Five channels, each with one meaning; white only for selection and focus.
- **Measured or nothing:** every number has a unit or reads `—`; an estimate says `est.`. No demo data: an empty panel
  is its hairline outline and one `--ink-3` line saying what would fill it (`api.parts.Empty`).
- **Type:** `t-label`, `t-readout`, `t-cluster`, `t-figure`, `t-hero` (Martian Mono, tabular), `t-body`, `t-chat`,
  `t-head` (Geist), `t-code`, `t-term` (Geist Mono) are classes in `app.css`.
- **Motion:** only events move; frame loops stop at rest, while hidden, and while measuring; cap at 60 fps.
- **Layout:** works at 1512 × 982 and 1280 × 800, and stacks into one column at 900 px and under.
- **Imports:** only from `/static/` (the page may load nothing from beyond 127.0.0.1; the CSP enforces it).
  Vendored: `/static/vendor/ui.js`, `regl.js`, `codemirror.js`, `markdown.js` (use `html: false`), `uplot@1.6.32/`,
  `@xterm/xterm@6.0.0/`, `@xterm/addon-fit@0.11.0/`, `icons.js`.

## Server routes

A screen's routes live in `camr_engine/app/routes/<id>.py` and are found at start:

```python
from camr_engine.app.web import Refused, Request, Routes, part

def register(routes: Routes) -> None:
    @routes.get("/api/chat/thread")
    def thread(req: Request) -> dict:
        n = req.int("n", 20, lo=1, hi=200)          # query or body; bad input is a 400
        if req.app.memory is None:
            raise Refused(409, "no memory open")   # sent as {"error": ...}
        return {"turns": []}
```

- Paths live under `/api/`; registering one path twice is an error at start, so two screens never collide.
- The server has already checked the host, the origin, `application/json` on POSTs and the launch token.
- `req.app` is the app (`camr_engine.app.server.App`, or `Fixture` for a recorded memory, or a stand-in in tests): check
  with `getattr` before using what it may not have. `part(req.app, name, make)` keeps shared state on it.
- Routes that exist: `shell.py` (`/api/state`, `/api/sys`, `/api/events`, `/api/metrics`, `/api/metrics/summary`),
  `chat.py` (`/api/chat`, `/api/errand`), `memory.py` (`/api/brain`), `sim.py` (`/api/life`, `/api/quiz`,
  `/api/sim/*`), `models.py` (`/api/models*`). Extend the file for your screen.
- Tests live in `v2/tests/test_app_*.py`; they never load a model (pass fakes) and never reach the network.
