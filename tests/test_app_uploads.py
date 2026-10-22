"""Uploads in CAMR Personal (camr/app/reader.py): photos, screenshots, scans and Word files are read, learned, and
followed by an interview (summary, what to focus on, questions); a note shows the lines it came from, and a box drawn
on a page can be learned on its own."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from camr.app import reader
from camr.app.assistant import Assistant
from camr.memory.embedder import HashingEmbedder

RECEIPT_LINES = [("NAIVAS SUPERMARKET", [0.1, 0.05, 0.6, 0.04]), ("12 Oct 2026", [0.1, 0.12, 0.3, 0.03]),
                 ("Milk 2L 240.00", [0.1, 0.30, 0.6, 0.03]), ("Bread 65.00", [0.1, 0.35, 0.6, 0.03]),
                 ("TOTAL KSh 2,340.00", [0.1, 0.80, 0.6, 0.04])]


class _Resp:
    def __init__(self, lines=None, body=None):
        self.lines, self.body, self.status_code = lines or [], body, 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield from self.lines

    def json(self):
        return self.body


class FakeOllama:
    """A chat model, a vision model and the replies the upload interview asks for."""

    def __init__(self):
        self.bodies: list[dict] = []

    def get(self, url, timeout=None):
        return _Resp(body={"models": [{"name": "tiny:1b", "size": 1e9, "details": {"parameter_size": "1B"}},
                                      {"name": "qwen2.5vl:3b", "size": 3e9, "details": {"parameter_size": "3B"}}]})

    def post(self, url, json=None, stream=False, timeout=None):
        self.bodies.append(json)
        prompt = json.get("prompt", "")
        if json.get("images"):
            text = "This is a receipt from Naivas supermarket.\n- Total KSh 2,340 on 12 Oct 2026"
        elif "Reply in exactly this form" in prompt:
            text = "Summary: A Naivas receipt from 12 Oct 2026.\nQuestion: What was this shopping for?"
        elif "From the file below, list" in prompt:
            text = "- The Naivas receipt total was KSh 2,340.\n- none"
        else:
            notes = prompt.split("### Notes from memory\n", 1)[-1].split("\n\n###", 1)[0]
            text = notes.splitlines()[0] if notes else "ok"
        if not json.get("stream"):
            return _Resp(body={"response": text, "done": True, "prompt_eval_count": 10, "eval_count": 5})
        lines = [__import__("json").dumps({"response": w + " ", "done": False}).encode() for w in text.split(" ")]
        lines.append(__import__("json").dumps({"response": "", "done": True, "prompt_eval_count": 42}).encode())
        return _Resp(lines=lines)


def fake_see(exe, path, folder, max_pages=40):
    (folder / "page-0.jpg").write_bytes(b"\xff\xd8 jpeg")
    lines = [{"text": t, "conf": 1.0, "box": b} for t, b in RECEIPT_LINES]
    return [reader.Page(0, "page-0.jpg", 800, 1200, lines)], 1


@pytest.fixture
def assistant(tmp_path, monkeypatch):
    monkeypatch.setattr(reader, "see_binary", lambda home: tmp_path / "camr-see")
    monkeypatch.setattr(reader, "see", fake_see)
    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.3)
    a.save_settings(trust_learning=False)
    yield a
    a.close()


def docx(paragraphs: list[str], head: str = "") -> bytes:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'{head}<w:document xmlns:w="{w}"><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


def test_a_photo_is_read_described_learned_and_followed_by_questions(assistant):
    conv = assistant.new_conversation()
    out = assistant.learn_upload("receipt.jpg", b"\xff\xd8 a photo", conversation_id=conv)
    assert out["kind"] == "image" and out["notes"] >= 2 and out["pages"][0]["lines"] == len(RECEIPT_LINES)
    assert out["seen"].startswith("This is a receipt")  # the vision model, told the recognised text
    vision = next(b for b in assistant._http.bodies if b.get("images"))
    assert vision["model"] == "qwen2.5vl:3b" and "TOTAL KSh 2,340.00" in vision["prompt"]
    assert out["summary"] == "A Naivas receipt from 12 Oct 2026." and out["questions"] == ["What was this shopping for?"]
    assert {"Dates & deadlines", "Numbers & totals", "Key points"} <= set(out["chips"])
    turn = assistant.transcript(conv)[-1]
    assert turn["upload"]["file_id"] == out["file_id"] and turn["question"] == "📎 receipt.jpg"
    again = assistant.learn_upload("receipt.jpg", b"\xff\xd8 a photo")
    assert again["unchanged"] and again["notes"] == 0


def test_an_answer_to_a_question_about_the_file_is_kept_with_it(assistant):
    out = assistant.learn_upload("receipt.jpg", b"\xff\xd8 a photo")
    conv = assistant.new_conversation()
    about = {"file_id": out["file_id"], "question": out["questions"][0]}
    turn = list(assistant.events("Groceries for my mum's birthday party", conv, about=about))[-1]["turn"]
    assert turn["saved_to_memory"] and "receipt.jpg" in turn["answer"]
    told = assistant.store.conn.execute("SELECT doc_id FROM source WHERE doc_id LIKE 'file-receipt.jpg#told-%'"
                                        ).fetchall()
    assert len(told) == 1
    answer = assistant.ask("What was the Naivas shopping for?")
    assert any("birthday" in s.text for s in answer.sources)


def test_focus_learns_short_notes_of_what_was_asked_for(assistant):
    out = assistant.learn_upload("receipt.jpg", b"\xff\xd8 a photo")
    res = assistant.focus(out["file_id"], "Numbers & totals")
    assert res["facts"] == ["The Naivas receipt total was KSh 2,340."] and res["notes"] == 1


def test_a_note_shows_the_lines_it_came_from_and_a_box_can_be_learned(assistant):
    out = assistant.learn_upload("receipt.jpg", b"\xff\xd8 a photo")
    note = assistant.store.conn.execute(
        "SELECT n.note_id FROM note n JOIN source s USING(source_id) WHERE s.doc_id='file-receipt.jpg'").fetchone()[0]
    hl = assistant.highlight(note)
    assert hl["file_id"] == out["file_id"] and {b["text"] for b in hl["boxes"]} >= {"TOTAL KSh 2,340.00"}
    part = assistant.select(out["file_id"], 0, [0.0, 0.25, 1.0, 0.15], teach=True)  # the two item lines
    assert part["text"] == "Milk 2L 240.00\nBread 65.00" and part["notes"] == 1
    info = assistant.file_info(out["file_id"])
    assert info["pages"][0]["lines"][0]["text"] == "NAIVAS SUPERMARKET"


def test_forgetting_a_file_forgets_what_was_learned_about_it_and_its_pages(assistant):
    out = assistant.learn_upload("receipt.jpg", b"\xff\xd8 a photo")
    assistant.focus(out["file_id"], "Numbers & totals")
    main = assistant.store.conn.execute("SELECT source_id FROM source WHERE doc_id='file-receipt.jpg'").fetchone()[0]
    assistant.forget(main)
    left = assistant.store.conn.execute("SELECT COUNT(*) FROM source WHERE doc_id LIKE 'file-receipt.jpg%'").fetchone()
    assert left[0] == 0 and not (assistant.home / "files" / out["file_id"]).exists()


def test_a_word_file_is_read_and_one_declaring_a_dtd_is_refused(assistant):
    out = assistant.learn_upload("plan.docx", docx(["The launch is on 4 November.", "Budget: KSh 120,000."]))
    assert out["kind"] == "docx" and out["notes"] >= 1
    with pytest.raises(ValueError):
        assistant.learn_upload("evil.docx", docx(["x"], head='<!DOCTYPE d [<!ENTITY a "aaaa">]>'))


def test_without_text_recognition_an_image_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(reader, "see_binary", lambda home: None)
    a = Assistant(tmp_path / "h", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.3)
    out = a.learn_upload("photo.png", b"\x89PNG fake")
    assert out["kind"] == "image" and "Mac" in out["problem"]
    a.close()


def test_unsupported_files_are_refused(assistant):
    with pytest.raises(ValueError):
        assistant.learn_upload("song.mp3", b"ID3")


def test_highlighting_matches_whole_lines_only():
    r = reader.Reading("f", "r.jpg", "image", "", [reader.Page(0, "p.jpg", 1, 1, [
        {"text": "TOTAL KSh 2,340.00", "box": [0, 0, 1, 1]}, {"text": "TOTAL", "box": [0, 0, 1, 1]},
        {"text": "KSh", "box": [0, 0, 1, 1]}])])
    found = reader.lines_in(r, "The total: TOTAL KSh 2,340.00 paid in cash")
    assert [b["text"] for b in found] == ["TOTAL KSh 2,340.00", "TOTAL"]  # three letters are too few to show
    assert json.loads(json.dumps(reader.focus_chips("Meeting with Amina Wanjiru and Otieno Ouma on 3 Nov")))[-1] == \
        "Key points"


def test_an_item_and_its_price_are_read_as_one_row_but_columns_of_text_are_not():
    def ln(text, x, y):
        return {"text": text, "box": [x, y, 0.3, 0.03], "conf": 1.0}
    receipt = [ln("Fresh Milk 2L", 0.1, 0.30), ln("Bread 600g", 0.1, 0.35), ln("240.00", 0.7, 0.301),
               ln("65.00", 0.7, 0.352)]
    assert reader.row_text(receipt) == "Fresh Milk 2L  240.00\nBread 600g  65.00"
    article = [ln("The first column of an article runs on", 0.05, y) for y in (0.1, 0.15, 0.2)] + \
              [ln("while the second column says something else", 0.55, y) for y in (0.1, 0.15, 0.2)]
    assert reader.row_text(article).splitlines()[1] == "The first column of an article runs on"
