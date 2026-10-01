"""CAMR Personal: the Streamlit front end for camr.app.assistant.

    camr app            # opens http://localhost:8502
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import streamlit as st

from camr import ui_theme
from camr.app.assistant import DEFAULT_HOME, DEFAULT_HOST, KINDS, Assistant, Turn, installed_models


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--home", default=str(DEFAULT_HOME))
    p.add_argument("--host", default=DEFAULT_HOST)
    return p.parse_args(sys.argv[1:])


ARGS = _args()
st.set_page_config(page_title="CAMR Personal", page_icon="◉", layout="wide")
ui_theme.apply(st)


@st.cache_resource(show_spinner="Loading the embedder (first run downloads ~130 MB)…")
def _assistant(home: str, host: str) -> Assistant:
    a = Assistant(home, host=host)
    a.engine.recall("warm up", touch=False)  # first embedding is slow; pay it at start-up
    return a


def _models(host: str) -> list[dict] | None:
    try:
        return installed_models(host)
    except Exception:  # Ollama not running or not installed
        return None


A = _assistant(ARGS.home, ARGS.host)
models = _models(ARGS.host)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    ui_theme.brand(st, "memory that grows · model that stays small")
    st.write("")
    page = st.radio("Navigate", ["Chat", "Teach", "Memory", "Growth", "Settings"], label_visibility="collapsed")
    st.write("")
    if models:
        names = [m["name"] for m in models]
        current = A.model if A.model in names else names[0]
        label = {m["name"]: f"{m['name']}  ·  {m['parameters']}  ·  {m['size_gb']} GB" for m in models}
        choice = st.selectbox("Model (from your Ollama)", names, index=names.index(current), format_func=label.get)
        if choice != A.model:
            A.save_settings(model=choice)
    s = A.stats()
    st.metric("Notes in memory", f"{s['notes']:,}", help=f"{s['store_mb']} MB on disk")
    st.caption("Everything stays on this computer: `" + str(A.home) + "`")

# ------------------------------------------------------------------ onboarding
if models is None or not models:
    st.markdown('<div class="camr-hero">Bring a model.<br><span>CAMR brings the memory.</span></div>',
                unsafe_allow_html=True)
    st.write("")
    st.markdown(f"""<div class="camr-card">
<b>1.</b> Install <a href="https://ollama.com/download">Ollama</a> and start it.<br>
<b>2.</b> Pull a small model, e.g. <code>ollama pull qwen2.5:1.5b</code> (the size that matched a frontier cloud
model on long-tail facts in our benchmarks) or <code>llama3.2:3b</code>.<br>
<b>3.</b> Reload this page. CAMR looks for Ollama at <code>{ARGS.host}</code>.
</div>""", unsafe_allow_html=True)
    st.stop()


AVATAR = {"user": "🙂", "assistant": "✦"}


def chips(t: dict) -> str:
    out = []
    for s in t.get("sources", []):
        name = s["title"] or KINDS.get(s["kind"], s["kind"])
        out.append(f'<span class="camr-chip"><b>{KINDS.get(s["kind"], s["kind"])}</b> · {name[:40]}'
                   f' · {s["similarity"]:.2f}{" · bridged" if s["via_bridge"] else ""}</span>')
    meta = []
    if t.get("abstained"):
        meta.append('<span class="camr-chip camr-pill-warn">no relevant memory: answered from the model alone</span>')
    elif t.get("grounded") is not None:
        cls = "camr-pill-good" if t["grounded"] >= 0.5 else "camr-pill-warn"
        meta.append(f'<span class="camr-chip {cls}">grounded {100 * t["grounded"]:.0f}%</span>')
    if t.get("retrieval_ms"):
        meta.append(f'<span class="camr-chip">memory {t["retrieval_ms"]:.0f} ms · answer {t["generation_ms"] / 1000:.1f} s</span>')
    if t.get("saved_to_memory"):
        meta.append('<span class="camr-chip camr-pill-good">remembered</span>')
    return "".join(out + meta)


# ------------------------------------------------------------------ chat
if page == "Chat":
    st.markdown("### Ask anything you've taught it")
    st.caption("Tip: start a message with **remember that …** to store a fact instantly. "
               "👍 on a good answer saves it to memory, so the model gets better without retraining.")
    if "msgs" not in st.session_state:
        st.session_state.msgs = []
    for i, m in enumerate(st.session_state.msgs):
        with st.chat_message(m["role"], avatar=AVATAR[m["role"]]):
            st.markdown(m["content"])
            if m["role"] == "assistant" and m.get("turn"):
                st.markdown(chips(m["turn"]), unsafe_allow_html=True)
                tid = m["turn"].get("turn_id")
                if tid and not m.get("rated"):
                    b1, b2, _ = st.columns([1, 1, 10])
                    if b1.button("👍", key=f"up{tid}", help="Helpful: save this answer to memory"):
                        A.feedback(tid, True); m["rated"] = "up"; st.rerun()
                    if b2.button("👎", key=f"down{tid}", help="Not helpful"):
                        A.feedback(tid, False); m["rated"] = "down"; st.rerun()
                elif m.get("rated"):
                    st.caption("Saved to memory. Thanks!" if m["rated"] == "up" else "Thanks, noted.")

    if q := st.chat_input("Message your memory…"):
        st.session_state.msgs.append({"role": "user", "content": q})
        with st.chat_message("user", avatar=AVATAR["user"]):
            st.markdown(q)
        with st.chat_message("assistant", avatar=AVATAR["assistant"]):
            box, parts, turn = st.empty(), [], None
            try:
                for item in A.ask_stream(q):
                    if isinstance(item, Turn):
                        turn = item
                    else:
                        parts.append(item)
                        box.markdown("".join(parts) + "▌")
            except Exception as exc:  # runtime down, model missing…
                box.error(f"The model could not answer: {exc}")
            if turn:
                box.markdown(turn.answer)
                st.markdown(chips(turn.as_dict()), unsafe_allow_html=True)
                st.session_state.msgs.append({"role": "assistant", "content": turn.answer, "turn": turn.as_dict()})
                st.rerun()

# ------------------------------------------------------------------ teach
elif page == "Teach":
    st.markdown("### Teach it")
    st.caption("Notes and files become memory. Nothing is uploaded anywhere: they are embedded on this computer "
               "and stored in one file.")
    with st.form("note", clear_on_submit=True):
        title = st.text_input("Title (optional)", placeholder="e.g. Car, Project X, Mum's birthday")
        text = st.text_area("Note", height=160, placeholder="Paste anything: facts, meeting notes, recipes, "
                                                             "documentation…")
        if st.form_submit_button("Save to memory", type="primary"):
            n = A.teach(text, title=title)
            st.success(f"Saved: {n} note(s).") if n else st.info("Nothing new to save (empty or already in memory).")
    files = st.file_uploader("Or add files (.txt, .md, .pdf)", type=["txt", "md", "pdf"], accept_multiple_files=True)
    if files and st.button("Add files to memory", type="primary"):
        for f in files:
            try:
                st.write(f"**{f.name}**: {A.teach_file(f.name, f.getvalue())} note(s)")
            except RuntimeError as exc:
                st.warning(f"{f.name}: {exc}")

# ------------------------------------------------------------------ memory
elif page == "Memory":
    st.markdown("### What it knows")
    c1, c2 = st.columns([3, 1])
    search = c1.text_input("Search", placeholder="Search your memory…", label_visibility="collapsed")
    kind = c2.selectbox("Kind", ["all"] + list(KINDS), format_func=lambda k: "All kinds" if k == "all" else KINDS[k],
                        label_visibility="collapsed")
    rows = A.sources(None if kind == "all" else kind, search)
    st.caption(f"{len(rows)} item(s)")
    for r in rows:
        with st.container():
            st.markdown(f'<div class="camr-card"><span class="camr-chip"><b>{KINDS.get(r["kind"], r["kind"])}</b></span>'
                        f' <b>{r["title"] or ""}</b> <span class="camr-muted">· {r["added"][:16]} · {r["notes"]} note(s)</span>'
                        f'<div style="margin-top:8px">{r["text"][:400]}{"…" if len(r["text"]) > 400 else ""}</div></div>',
                        unsafe_allow_html=True)
            if st.button("Forget", key=f"forget{r['source_id']}"):
                A.forget(r["source_id"]); st.rerun()

# ------------------------------------------------------------------ growth
elif page == "Growth":
    st.markdown("### How it is growing")
    s = A.stats()
    c = st.columns(4)
    c[0].metric("Notes in memory", f"{s['notes']:,}")
    c[1].metric("Questions asked", s["turns"])
    c[2].metric("Answered from memory", "—" if s["answered_with_memory"] is None else f"{100 * s['answered_with_memory']:.0f}%")
    c[3].metric("Memory lookup (median)", "—" if s["median_retrieval_ms"] is None else f"{s['median_retrieval_ms']:.0f} ms")
    if len(s["sources_per_day"]) == 1:
        st.markdown(f'<div class="camr-card">Day one: <b>{s["sources_per_day"][0][1]}</b> items in memory. '
                    'Come back tomorrow to see the curve.</div>', unsafe_allow_html=True)
    elif s["sources_per_day"]:
        import pandas as pd

        df = pd.DataFrame(s["sources_per_day"], columns=["day", "added"]).set_index("day")
        df["total items"] = df["added"].cumsum()
        st.markdown("**Memory over time**")
        st.area_chart(df[["total items"]], color=ui_theme.ACCENT)
    if s["notes_by_kind"]:
        st.markdown("**Where its knowledge comes from**")
        st.bar_chart({KINDS.get(k, k): v for k, v in s["notes_by_kind"].items()}, color=ui_theme.GOOD, horizontal=True)
    st.caption(f"👍 {s['helpful']} · 👎 {s['not_helpful']} · the model's weights never change: every gain here is memory.")

# ------------------------------------------------------------------ settings
else:
    st.markdown("### Settings")
    budget = st.slider("Memory read per question (tokens)", 64, 1024, A.token_budget, 64,
                       help="Measured: ~128 is best for single facts on tiny models; ~512 for multi-step questions.")
    turns = st.slider("Recent turns kept verbatim", 0, 12, A.history_turns,
                      help="Older turns are not lost: what you said is stored as memory and recalled when relevant.")
    chat = st.toggle("Remember what I say in chat", A.remember_chat)
    if st.button("Save settings", type="primary"):
        A.save_settings(token_budget=budget, history_turns=turns, remember_chat=chat)
        st.success("Saved.")
    st.divider()
    st.markdown("### Share feedback with the CAMR project")
    st.caption("Optional and manual. The export contains usage metrics only (counts, timings, 👍/👎), never your "
               "notes or messages unless you tick the box. Attach it to "
               "a GitHub issue.")
    with_text = st.checkbox("Include my questions and answers (only if you are comfortable sharing them)")
    st.download_button("Download feedback file", json.dumps(A.export_feedback(with_text), indent=2),
                       file_name="camr-feedback.json", mime="application/json")
