"""Complex interactions in CAMR Personal with a real model: each scenario runs twice, without memory and
with CAMR, in fresh homes, and is captured as a side-by-side screenshot plus a JSON log of the real answers.

Needs Ollama running locally with the chat model and nomic-embed-text.

    python scripts/scenario_screens.py --model llama3.2:3b --out docs/figures/scenarios --log docs/results/scenarios.json
"""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

from camr.app.server import App, make_handler

ROOT = Path(__file__).resolve().parents[1]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

LAB_RULES = """# Chemistry lab safety rules (Science Complex, Lab 2)
1. Goggles and a buttoned lab coat must be worn at all times in the lab.
2. After a chemical splash to the eyes, rinse at the eyewash station for at least 15 minutes, holding the eyelids open.
3. Report every incident, however small, to the lab technician, Mr. Kamau, before you leave the lab.
4. Concentrated acids are poured only inside fume hood 3, and always acid into water.
5. Broken glass goes in the yellow sharps bin, never in the ordinary bin.
"""

SCENARIOS = [
    {"key": "bridge", "title": "Two notes joined by a name (entity bridging)",
     "notes": [("Project CAMR", "Project CAMR is supervised by Dr. Achieng Otieno. Supervisor meetings are every second "
                                "Tuesday at 10:00, and Chapter 5 is due on 20 October."),
               ("Dr. Achieng Otieno", "Dr. Achieng Otieno's office is Room 4.12 on the third floor of the Science "
                                      "Complex. She wants drafts sent by email as a PDF.")],
     "messages": ["Which room is my project supervisor's office in, and how does she want drafts sent?"],
     "expected": [["4.12"], ["pdf"]]},
    {"key": "arithmetic", "title": "Arithmetic over a remembered fact",
     "notes": [("Car service", "The car was serviced at 84,200 km on 20 September. The next oil change is due at "
                               "89,200 km.")],
     "messages": ["My odometer reads 86,950 km today. How many kilometres until the next oil change?"],
     "expected": [["2,250", "2250", "2 250"]]},
    {"key": "update", "title": "A fact that changes", "with_only": True,
     "notes": [("Dentist", "Dentist appointment on Thursday 9 October at 14:30 with Dr. Wanjiru at Upper Hill Dental.")],
     "messages": ["remember that the dentist appointment moved to Friday 10 October at 09:00",
                  "When is my dentist appointment now?"],
     "expected": [["friday"], ["09:00", "9:00", "9 am", "9am", "9.00"]]},
    {"key": "window", "title": "Remembering beyond the context window",
     "notes": [],
     "messages": ["I'm allergic to penicillin, please keep that in mind.", "What is 17 × 23?",
                  "Convert 5 miles to kilometres.", "What's the capital of Australia?", "Give me a synonym for quick.",
                  "What is 15% of 240?", "How many days are in a leap year?", "Which antibiotic am I allergic to?"],
     "expected": [["penicillin"]],
     "without": {"remember_chat": False}},
    {"key": "document", "title": "Answering from a taught document",
     "file": ("lab_safety.md", LAB_RULES),
     "notes": [],
     "messages": ["How long should I rinse my eyes after a chemical splash, and who do I report it to?"],
     "expected": [["15 minutes", "fifteen minutes"], ["kamau"]]},
]


def call(port, method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=900)
    c.request(method, path, body=json.dumps(body) if body is not None else None,
              headers={"Content-Type": "application/json", "Host": f"127.0.0.1:{port}"})
    r = c.getresponse()
    return json.loads(r.read().decode() or "{}")


def start(home: Path):
    app = App(home, "http://127.0.0.1:11434")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return app, httpd, httpd.server_address[1]


def run_variant(browser, sc: dict, with_memory: bool, model: str, out: Path) -> dict:
    home = Path(tempfile.mkdtemp(prefix=f"camr-{sc['key']}-"))
    app, httpd, port = start(home)
    for _ in range(120):
        st = call(port, "GET", "/api/state")
        if st.get("ready"):
            break
        time.sleep(1)
    call(port, "POST", "/api/settings", {"model": model, **({} if with_memory else sc.get("without", {}))})
    if with_memory:
        for title, text in sc["notes"]:
            call(port, "POST", "/api/teach", {"title": title, "text": text})
        if sc.get("file"):
            name, text = sc["file"]
            call(port, "POST", "/api/teach", {"filename": name, "data_base64": base64.b64encode(text.encode()).decode()})
    app.assistant.warm()
    page = browser.new_page(viewport={"width": 1180, "height": 2200}, device_scale_factor=1)
    page.add_init_script("try { localStorage.setItem('camr-theme', 'dark') } catch (e) {}")
    page.goto(f"http://127.0.0.1:{port}")
    page.wait_for_selector("#input")
    msgs = sc["messages"] if with_memory or sc["key"] != "update" else sc["messages"][1:]
    for i, m in enumerate(msgs, start=1):
        page.fill("#input", m)
        page.keyboard.press("Enter")
        page.wait_for_function(f"() => document.querySelectorAll('.msg.assistant .actions').length >= {i}"
                               " && !document.querySelector('.answer.cursor')", timeout=900000)
    page.evaluate("document.querySelectorAll('details.recall').forEach(d => d.open = true)")
    page.wait_for_timeout(400)
    thread = page.locator("#thread")
    last = page.locator(".msg").last.bounding_box()
    box = thread.bounding_box()
    shot = out / f"{sc['key']}_{'with' if with_memory else 'without'}.png"
    page.screenshot(path=str(shot), clip={"x": box["x"], "y": box["y"], "width": box["width"],
                                          "height": min(last["y"] + last["height"] + 24 - box["y"], 2150)})
    conv = call(port, "GET", "/api/conversations")
    cid = conv[0]["id"] if isinstance(conv, list) else conv["conversations"][0]["id"]
    turns = call(port, "GET", f"/api/conversations/{cid}")
    turns = turns.get("turns", turns) if isinstance(turns, dict) else turns
    log = [{"question": t["question"], "answer": t["answer"], "abstained": t.get("abstained"),
            "grounded": t.get("grounded"), "sources": [s.get("title") or s.get("kind") for s in t.get("sources", [])],
            "retrieval_ms": t.get("retrieval_ms"), "generation_ms": t.get("generation_ms")} for t in turns]
    page.close()
    httpd.shutdown()
    app.assistant.close()
    return {"screenshot": str(shot.relative_to(ROOT)), "turns": log}


def side_by_side(left: Path | None, right: Path, out: Path, labels=("Without memory", "With CAMR memory")) -> None:
    ims = [Image.open(p) for p in ([left] if left else []) + [right]]
    h = max(i.height for i in ims)
    head = 46
    w = sum(i.width for i in ims) + 16 * (len(ims) - 1)
    canvas = Image.new("RGB", (w, h + head), (11, 14, 20))
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, 22)
    x = 0
    for lab, im, col in zip(labels if left else labels[1:], ims, ((235, 104, 52), (27, 175, 122))):
        d.text((x + 18, 10), lab, fill=col, font=font)
        canvas.paste(im, (x, head))
        x += im.width + 16
    canvas.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--out", default=str(ROOT / "docs/figures/scenarios"))
    ap.add_argument("--log", default=str(ROOT / "docs/results/scenarios.json"))
    ap.add_argument("--only", help="comma-separated scenario keys")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log_path = Path(a.log)
    log = json.loads(log_path.read_text()) if log_path.exists() else {}
    log["model"] = a.model
    keys = set(a.only.split(",")) if a.only else None
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for sc in SCENARIOS:
            if keys and sc["key"] not in keys:
                continue
            entry = {"title": sc["title"], "notes": sc["notes"], "file": sc.get("file", [None])[0],
                     "expected": sc["expected"]}
            if not sc.get("with_only"):
                entry["without"] = run_variant(browser, sc, False, a.model, out)
            entry["with"] = run_variant(browser, sc, True, a.model, out)
            side_by_side(out / f"{sc['key']}_without.png" if not sc.get("with_only") else None,
                         out / f"{sc['key']}_with.png", out / f"{sc['key']}.png")
            for v in ("without", "with"):
                if v in entry:  # every expected element (any of its spellings) must appear in the final answer
                    final = entry[v]["turns"][-1]["answer"].lower()
                    entry[v]["correct"] = all(any(x in final for x in alts) for alts in sc["expected"])
            log.setdefault("scenarios", {})[sc["key"]] = entry
            log_path.write_text(json.dumps(log, indent=2, ensure_ascii=False))
            print(sc["key"], "without:", [t["answer"][:80] for t in entry.get("without", {}).get("turns", [])][-1:],
                  "| with:", [t["answer"][:80] for t in entry["with"]["turns"]][-1:], flush=True)
        browser.close()


if __name__ == "__main__":
    main()
