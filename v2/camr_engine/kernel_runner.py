"""The notebook's side of the line: run by the kernel's own Python (``~/.camr/kernels/py``), never the engine's, and
imports nothing from camr_engine.

It starts one IPython kernel (jupyter_client, over Unix sockets in its temp folder, so it needs no network) with the
project folder as its working directory, then reads one JSON request per line on stdin and answers one JSON line on
stdout:

- ``{"op": "run", "code": ..., "timeout": 60}`` -> ``{"status": "ok" | "error" | "timeout" | "stopped",
  "count": n, "outputs": [nbformat outputs]}``
- ``{"op": "restart"}`` -> ``{"status": "ok"}``; ``{"op": "quit"}`` ends it.

SIGUSR1 interrupts the cell running now (the app's Stop). A cell that outlives its time limit is interrupted; one that
ignores the interrupt is ended by restarting the kernel.
"""

from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import sys
import time

KEEP = ("text/plain", "text/html", "text/markdown", "text/latex", "image/png", "image/jpeg", "image/svg+xml")
STREAM_CHARS = 100_000  # of one cell's printed text
IMAGES = 8  # images one cell keeps
IMAGE_CHARS = 3_000_000  # of one image, as base64
GRACE_S = 5.0  # after an interrupt, before the kernel is restarted

_interrupt = False


def _on_usr1(signum, frame):  # noqa: ARG001
    global _interrupt
    _interrupt = True


def main() -> int:
    cwd, tmp = sys.argv[1], sys.argv[2]
    proto = os.fdopen(os.dup(1), "w", buffering=1)  # the answers; anything else printed goes to stderr
    os.dup2(2, 1)
    signal.signal(signal.SIGUSR1, _on_usr1)
    from jupyter_client.manager import KernelManager

    km = KernelManager(kernel_name="python3", transport="ipc", ip=os.path.join(tmp, "k"),
                       connection_file=os.path.join(tmp, "kernel.json"))
    log = open(os.path.join(tmp, "kernel.log"), "ab")  # noqa: SIM115 (open for the kernel's life)

    def start():
        km.start_kernel(cwd=cwd, env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=log)
        kc = km.client()
        kc.start_channels()
        kc.wait_for_ready(timeout=60)
        return kc

    def say(obj):
        proto.write(json.dumps(obj) + "\n")
        proto.flush()

    try:
        kc = start()
    except Exception as e:  # noqa: BLE001 (said to the engine)
        say({"ready": False, "error": f"{type(e).__name__}: {e}"[:2000]})
        return 1
    say({"ready": True, "pid": km.provisioner.pid if km.provisioner else None})

    def restart():
        nonlocal kc
        try:
            kc.stop_channels()
        except Exception:  # noqa: BLE001
            pass
        km.restart_kernel(now=True)
        kc = km.client()
        kc.start_channels()
        kc.wait_for_ready(timeout=60)

    def run(code: str, timeout: float, grace: float = GRACE_S) -> dict:
        global _interrupt
        _interrupt = False
        msg_id = kc.execute(code, store_history=True, allow_stdin=False, stop_on_error=False)
        outputs: list[dict] = []
        count, status = None, "ok"
        deadline = time.monotonic() + timeout
        timed_out = stopped = False
        images = 0
        while True:
            now = time.monotonic()
            if _interrupt and not stopped:
                _interrupt, stopped = False, True
                km.interrupt_kernel()
                deadline = min(deadline, now + grace)
            elif now >= deadline:
                if timed_out or stopped:  # it ignored the interrupt: the kernel goes, and its variables with it
                    restart()
                    outputs.append({"output_type": "error", "ename": "KernelRestarted",
                                    "evalue": "the cell did not stop when interrupted, so the kernel was restarted",
                                    "traceback": []})
                    break
                timed_out = True
                km.interrupt_kernel()
                deadline = now + grace
            try:
                msg = kc.get_iopub_msg(timeout=0.2)
            except queue.Empty:
                continue
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            kind, c = msg["msg_type"], msg["content"]
            if kind == "status" and c.get("execution_state") == "idle":
                break
            if kind == "execute_input":
                count = c.get("execution_count")
            elif kind == "stream":
                text = c.get("text", "")
                if outputs and outputs[-1]["output_type"] == "stream" and outputs[-1]["name"] == c.get("name"):
                    outputs[-1]["text"] += text
                else:
                    outputs.append({"output_type": "stream", "name": c.get("name", "stdout"), "text": text})
                total = sum(len(o.get("text", "")) for o in outputs if o["output_type"] == "stream")
                if total > STREAM_CHARS:
                    o = outputs[-1]
                    o["text"] = o["text"][:max(0, len(o["text"]) - (total - STREAM_CHARS))]
                    if not o["text"].endswith("[more output left out]\n"):
                        o["text"] += "\n[more output left out]\n"
            elif kind in ("execute_result", "display_data"):
                data = {k: v for k, v in c.get("data", {}).items() if k in KEEP}
                pics = [k for k in data if k.startswith("image/")]
                if pics:
                    images += 1
                    if images > IMAGES or any(len(str(data[k])) > IMAGE_CHARS for k in pics):
                        data = {k: v for k, v in data.items() if not k.startswith("image/")}
                        data.setdefault("text/plain", "[an image was left out: too many or too large]")
                if not data:
                    continue
                out = {"output_type": kind, "data": data, "metadata": c.get("metadata", {})}
                if kind == "execute_result":
                    out["execution_count"] = c.get("execution_count")
                outputs.append(out)
            elif kind == "error":
                outputs.append({"output_type": "error", "ename": c.get("ename", "Error"),
                                "evalue": c.get("evalue", ""), "traceback": c.get("traceback", [])[-40:]})
                status = "error"
            elif kind == "clear_output":
                outputs = []
        if timed_out:  # the interrupt's own KeyboardInterrupt says less than this
            status = "timeout"
            outputs = [o for o in outputs if not (o["output_type"] == "error" and o["ename"] == "KeyboardInterrupt")]
            outputs.append({"output_type": "error", "ename": "TimeoutError",
                            "evalue": f"the cell ran longer than {timeout:g} s and was stopped", "traceback": []})
        elif stopped:
            status = "stopped"
        return {"status": status, "count": count, "outputs": outputs}

    for line in sys.stdin:
        try:
            req = json.loads(line)
        except ValueError:
            say({"status": "error", "error": "not JSON"})
            continue
        op = req.get("op")
        try:
            if op == "run":
                say(run(str(req.get("code", "")), float(req.get("timeout", 60)), float(req.get("grace", GRACE_S))))
            elif op == "restart":
                restart()
                say({"status": "ok"})
            elif op == "quit":
                break
            else:
                say({"status": "error", "error": f"no op {op!r}"})
        except Exception as e:  # noqa: BLE001 (said to the engine)
            say({"status": "error", "error": f"{type(e).__name__}: {e}"[:2000], "outputs": []})
    try:
        kc.stop_channels()
        km.shutdown_kernel(now=True)
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
