"""Files into memory (camr_engine.media), with fakes: a describer that names what it was shown, and test_core's fake
reader and embedder (MLX for their arrays). No model is loaded."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from camr_engine import media

pytest.importorskip("mlx")
pytest.importorskip("PIL")

DAY, DATE = 12, dt.date(2025, 10, 7)


def memory(path: Path):
    from test_core import make

    return make(path, vault=True)


class Describer:
    """Says what it was asked about which image, so a test can read it back."""

    def __init__(self):
        self.calls = []

    def __call__(self, image, ask):
        self.calls.append((Path(image).name, ask))
        return f"a photo of {Path(image).stem}" if ask == media.CAPTION else f"WRITTEN ON {Path(image).stem}"


def pdf(path: Path, pages: list[str]) -> Path:
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    for text in pages:
        c.drawString(72, 720, text)
        c.showPage()
    c.save()
    return path


def png(path: Path, colour=(200, 40, 40)) -> Path:
    from PIL import Image

    Image.new("RGB", (64, 48), colour).save(path)
    return path


def test_a_pdf_is_one_moment_a_page_and_the_file_is_kept_with_where_each_came_from(tmp_path):
    m = memory(tmp_path / "mem")
    f = pdf(tmp_path / "menu.pdf", ["Pilau is 450 shillings.", "Chapati is 30 shillings."])
    kept = media.ingest(f, m, day=DAY, date=DATE)
    assert kept == ["File menu.pdf, a PDF, page 1 of 2:\nPilau is 450 shillings.",
                    "File menu.pdf, a PDF, page 2 of 2:\nChapati is 30 shillings."]
    src = media.sources(m)
    assert [(s["file"], s["page"], s["pages"]) for s in src.values()] == [("menu.pdf", 1, 2), ("menu.pdf", 2, 2)]
    copy = Path(src[0]["copy_path"])
    assert copy.parent == m.vault.path / "files" and copy.read_bytes() == f.read_bytes()
    assert media.files_bytes(m) >= f.stat().st_size
    note = m.vault.read(m.vault.moment_id(0))
    assert {"file", "pdf"} <= set(note.tags) and note.day == DAY and note.date == DATE.isoformat()
    m.close()


def test_an_image_is_captioned_and_read_and_the_moment_is_stamped(tmp_path):
    m = memory(tmp_path / "mem")
    d = Describer()
    kept = media.ingest(png(tmp_path / "receipt.png"), m, describe=d, day=DAY, date=DATE,
                        stamp=lambda w: f"[{DATE}] User: {w}")
    assert kept == [f"[{DATE}] User: File receipt.png, an image. a photo of receipt\nWritten in it:\nWRITTEN ON "
                    "receipt"]
    assert sorted(a for _, a in d.calls) == sorted([media.CAPTION, media.READ_TEXT])
    s = media.sources(m)[0]
    assert s["kind"] == "image" and Path(s["image_path"]).exists() and s["image_path"] == s["copy_path"]
    m.close()


def test_an_image_with_nothing_written_is_its_caption_alone():
    got = media.image_words("x.png", Path("x.png"), lambda image, ask: "No text." if ask == media.READ_TEXT else
                            "A plain red square.")
    assert got == "File x.png, an image. A plain red square."


def test_a_video_is_read_frame_by_frame_and_a_still_board_once(tmp_path):
    import imageio.v2 as imageio
    import numpy as np
    from PIL import Image, ImageDraw

    path = tmp_path / "board.mp4"
    w = imageio.get_writer(str(path), fps=2, codec="libx264", macro_block_size=16, ffmpeg_log_level="error")
    for i in range(8):  # two boards of 2 s each: the second has a new line written on it
        im = Image.new("RGB", (320, 176), (240, 240, 236))
        ImageDraw.Draw(im).rectangle((20, 20, 300, 60) if i < 4 else (20, 90, 300, 150), fill=(20, 40, 140))
        w.append_data(np.asarray(im))
    w.close()
    shots = media.frames(path, every_s=1.0)
    assert [round(t) for t, _ in shots] == [0, 2]
    m = memory(tmp_path / "mem")
    kept = media.ingest(path, m, describe=Describer(), day=DAY)
    assert len(kept) == 2 and "a video, the frame at 0:00" in kept[0]
    src = media.sources(m)
    assert all(Path(s["image_path"]).exists() for s in src.values()) and [s["at_s"] for s in src.values()][0] == 0.0
    m.close()


def test_what_the_memory_cannot_read_is_refused(tmp_path):
    m = memory(tmp_path / "mem")
    with pytest.raises(ValueError):
        media.ingest(png(tmp_path / "a.png"), m, day=1)  # an image needs a describer
    (tmp_path / "a.docx").write_text("x")
    with pytest.raises(ValueError):
        media.ingest(tmp_path / "a.docx", m, day=1)
    assert media.clock(65) == "1:05" and media.clock(3725) == "1:02:05"
    m.close()


def test_a_look_shows_the_reader_the_image_when_the_closest_moment_came_from_one(tmp_path):
    from camr_engine.models import Reply

    m = memory(tmp_path / "mem")
    media.ingest(png(tmp_path / "wifi.png"), m, describe=lambda i, a: "wifi password notice", day=DAY, date=DATE)
    media.ingest(pdf(tmp_path / "menu.pdf", ["Pilau costs 450 shillings."]), m, day=DAY, date=DATE)
    seen = []

    class Seer:
        def see(self, images, system, user, max_tokens=None):
            seen.append(SimpleNamespace(images=images, system=system, user=user))
            return Reply("chapati21", 0.01, 10.0, 99, 3, [])

    got = media.look(m, "What is the wifi password notice?", DATE, seer=Seer())
    assert got.text == "chapati21" and got.image == "wifi.png"
    assert Path(seen[0].images[0]).parent == m.vault.path / "files" and "Notes:" in seen[0].system
    assert "wifi password notice" in seen[0].system and seen[0].user.endswith("What is the wifi password notice?")
    assert media.look(m, "How much does pilau cost?", DATE, seer=Seer()) is None  # a PDF: nothing to look at
    m.close()


def test_the_sources_log_survives_a_bad_line(tmp_path):
    m = memory(tmp_path / "mem")
    media.ingest(pdf(tmp_path / "a.pdf", ["One page."]), m, day=1)
    with open(media.files_folder(m) / media.SOURCES, "a") as f:
        f.write("not json\n")
    assert list(media.sources(m)) == [0]
    assert json.loads((media.files_folder(m) / media.SOURCES).read_text().splitlines()[0])["moment"] == 0
    m.close()
