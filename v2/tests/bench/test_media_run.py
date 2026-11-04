"""The multimodal memory benchmark on fakes: the files and their questions, the script they are told in, the cached
describer, and the contenders (the engine ingesting files, bare reading their words, the file in the prompt). No
model is loaded; test_core's fake reader and embedder need MLX for their arrays."""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

from camr_engine import media
from camr_engine.bench import contender as cn
from camr_engine.bench import media_run
from camr_engine.bench.haul import files
from camr_engine.bench.haul.grade import grade
from camr_engine.bench.haul.script import calendar
from camr_engine.models import Reply

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # test_core's fakes

pytest.importorskip("mlx")
pytest.importorskip("reportlab")


@pytest.fixture(autouse=True)
def quiet_environment(monkeypatch):
    monkeypatch.setattr(cn, "environment", lambda: {"machine": "test"})


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """A media run built on a small fake Long Haul, with short videos so it builds quickly."""
    mp = pytest.MonkeyPatch()
    mp.setattr(files, "VIDEO_SECONDS", 3)
    mp.setattr(files, "VIDEO_FPS", 2)
    mp.setattr(files, "BOARD_SECONDS", 1)
    root = tmp_path_factory.mktemp("media")
    haul = root / "haul"
    haul.mkdir()
    events, total = [], 0
    for i in range(400):
        text = f"Noise number {i} about the menu site and the riders."
        total += 300
        events.append({"i": i, "day": 1 + i // 40, "kind": "chat", "role": "user", "text": text, "tokens": 300,
                       "cum_tokens": total})
    (haul / "script.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (haul / "probes.jsonl").write_text(json.dumps({"id": "fact-001", "events": [5, 6]}) + "\n")
    plan = media_run.build(1, haul, root / "m", noise_tokens=90_000)
    yield root / "m", plan
    mp.undo()


def describer(image, ask):
    return f"caption of {Path(image).stem}" if ask == media.CAPTION else f"text of {Path(image).stem}"


def test_every_file_has_its_planted_facts_and_the_never_said_questions_name_the_nearest_file():
    specs = files.specs(1, calendar())
    again = files.specs(1, calendar())
    assert [s.draw for s in specs] == [s.draw for s in again]  # fixed by the seed
    qs = [q for s in specs for q in s.questions]
    assert Counter(q["family"] for q in qs) == {"pdf": 8, "image": 9, "chart": 6, "video": 6, "never": 8}
    names = {s.name for s in specs if s.kind != "never"}
    assert len(names) == 21 and all(q["file"] in names for q in qs)
    assert len({q["ask"] for q in qs}) == len(qs) and len({q["id"] for q in qs}) == len(qs)
    for q in qs:
        if q["family"] == "never":
            assert grade(q, "I don't know.").verdict == "right" and grade(q, "It was 450.").verdict == "false_memory"
        else:
            right = grade(q, f"It was {q['answer']}.").verdict
            assert right == "right", (q["id"], q["answer"])
            assert grade(q, "I don't know.").verdict == "declined"


def test_the_files_go_among_the_noise_in_order_and_the_planted_events_are_left_out(built):
    folder, plan = built
    _, script = media_run.load(folder)
    told = [e for e in script if "file" in e]
    assert len(told) == len(plan["files"]) == 21
    assert all(media_run.FIRST_AT <= e["depth"] <= media_run.LAST_AT for e in told)
    noise = [e for e in script if "file" not in e]
    texts = {e["text"] for e in noise}
    assert "Noise number 5 about the menu site and the riders." not in texts  # it planted a probe
    assert sum(e["tokens"] for e in noise) == plan["noise_tokens"] <= 90_000
    assert all((folder / f["path"]).exists() for f in plan["files"])


def test_the_cached_describer_runs_the_vision_model_once_per_image_and_ask(tmp_path):
    from PIL import Image

    calls = []
    image = tmp_path / "a.png"
    Image.new("RGB", (8, 8), (1, 2, 3)).save(image)
    c = media_run.Cached(tmp_path / "cache.json", lambda i, a: calls.append(a) or f"words for {a}")
    assert c(image, "x") == c(image, "x") == "words for x" and calls == ["x"]
    again = media_run.Cached(tmp_path / "cache.json")  # the cache alone, no model
    assert again(image, "x") == "words for x"
    with pytest.raises(KeyError):
        again(image, "y")


def test_each_contender_reads_its_own_describer_s_words():
    assert media_run.words_for("engine:qwen2.5-vl-3b") == "mlx:qwen2.5-vl-3b"
    assert media_run.words_for("engine:qwen2.5-vl-3b+look") == "mlx:qwen2.5-vl-3b"
    assert media_run.words_for("engine:qwen3-4b") == media_run.DESCRIBER
    assert media_run.words_for("ollama:qwen2.5vl:3b") == "ollama:qwen2.5vl:3b"
    assert media_run.words_for("bare:qwen3-4b", "ollama:qwen2.5vl:3b") == "ollama:qwen2.5vl:3b"


def test_a_told_file_is_one_history_line_for_bare_and_its_moments_for_the_engine(built, tmp_path):
    from test_core import FakeEmbedder, FakeReader

    from camr_engine.bench.local import Bare
    from camr_engine.bench.longhaul import grader

    folder, plan = built
    cached = media_run.Cached(folder / "cache-test.json", describer)
    got = {"describer": "test", "seconds": 0.0, "calls": 0, "files": {}}
    for f in plan["files"]:
        pieces = media.read(folder / f["path"], describe=cached, folder=tmp_path / "frames" / f["name"])
        got["files"][f["name"]] = {"pieces": [{"text": p.text} for p in pieces]}
    events = media_run.told_events(folder, got, lambda text: len(text) // 4 + 1)
    tolds = [e["told"] for e in events if "told" in e]
    assert all(isinstance(t, media_run.Told) and str(t).startswith("User: File ") for t in tolds)
    menu = next(t for t in tolds if t.path.name == "catering-menu-2025.pdf")
    assert len(menu.pieces) == 3 and "page 3 of 3" in menu.pieces[2]
    cp = media_run.checkpoint(plan, events)
    assert cp["events"] == len(events) and len(cp["questions"]) == 37

    dates = lambda d: dt.date(2025, 9, 21) + dt.timedelta(days=d)  # noqa: E731
    eng = media_run.MediaEngine("fake", reader=FakeReader(), embedder=FakeEmbedder(), describe=cached,
                                dates=dates, room_tokens=4000, join=0.99, describer_name="test")
    rec = cn.run(eng, events, [cp], task="media", grader=grader, folder=tmp_path / "eng", text=media_run.text_of,
                 limit=6, records=tmp_path / "records", progress=lambda s: None)
    st = rec["checkpoints"][0]["status"]
    assert st["files"] == 21 and st["files_bytes"] > 0 and "failed" not in rec
    assert len(rec["checkpoints"][0]["answers"]) == 6 and rec["contender"]["describer"] == "test"
    assert rec["checkpoints"][0]["answers"][0]["metrics"]["disk_gb"] > 0
    assert Path(rec["path"]).name.endswith("-media-engine-fake.json")

    bare = Bare("fake", reader=FakeReader(), window=60_000)
    bare.name = "bare:fake"
    rec = cn.run(bare, events, [cp], task="media", grader=grader, folder=tmp_path / "bare", text=media_run.text_of,
                 limit=3, records=tmp_path / "records", progress=lambda s: None)
    assert any(line.startswith("User: File ") for line in bare.lines) and "failed" not in rec


def test_the_file_in_the_prompt_comes_with_its_own_question(built):
    folder, plan = built
    seen = []

    class Seer:
        repo = "fake-seer"

        def see(self, images, system, user, max_tokens=None):
            seen.append((images, system, user))
            return Reply("I don't know", 0.01, 10.0, 50, 4, [])

    paths = {f["name"]: folder / f["path"] for f in plan["files"]}
    c = media_run.FileInPrompt("fake", seer=Seer(), files={q["ask"]: paths[q["file"]] for q in plan["questions"]})
    by = {q["id"]: q for q in plan["questions"]}
    c.ask(by["pdf-menu-minimum"]["ask"], max_tokens=20, family="pdf")
    images, system, _ = seen[-1]
    assert images == [] and "Page 3 of 3" in system and "cater for" in system
    c.ask(by["image-notice-wifi"]["ask"], max_tokens=20, family="image")
    assert [Path(p).name for p in seen[-1][0]] == ["notice-wifi.jpg"]
    a = c.ask(by["video-eggs"]["ask"], max_tokens=20, family="video")
    assert 1 <= len(seen[-1][0]) <= media_run.MAX_FRAMES and "frames at 0:00" in seen[-1][2]
    assert a.extra["file"] == "video-stock-board.mp4" and a.metrics["context_tokens"] == 50
