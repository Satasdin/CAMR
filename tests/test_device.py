"""Device governor and bulk ingestion: stop at the device's limits, resume without loss or duplicates."""

from __future__ import annotations

import json

from camr.device import DeviceProfile, Governor, Limits, plan, probe
from camr.memory.bulk import bulk_ingest, read_folder, read_jsonl
from camr.memory.note import Document
from test_learning import fresh_engine


def fake_probe(free_mb=50_000.0, avail_mb=8_000.0, load=0.1, cpus=4):
    return lambda path: DeviceProfile(ram_total_mb=16_000, ram_available_mb=avail_mb, cpu_count=cpus, load_1m=load,
                                      disk_total_mb=100_000, disk_free_mb=free_mb, path=str(path))


def docs(n, start=0):
    return (Document("bulk:t", f"d{i}", f"Paragraph {i} says that place {i} has {i * 7} inhabitants and a river.",
                     f"Place {i}") for i in range(start, start + n))


def test_probe_reads_the_real_machine(tmp_path):
    p = probe(tmp_path)
    assert p.ram_total_mb > 0 and p.cpu_count >= 1 and p.disk_free_mb > 0


def test_the_governor_names_the_limit_that_stops_work(tmp_path):
    store = tmp_path / "m.sqlite"
    store.write_bytes(b"x" * 3 * 1024 * 1024)
    assert Governor(store, Limits(reserve_disk_mb=1000), probe_fn=fake_probe(free_mb=900)).check().reason == "disk"
    assert Governor(store, Limits(reserve_disk_mb=1000), probe_fn=fake_probe(free_mb=1010)).check(20).reason == "disk"
    assert Governor(store, Limits(max_store_mb=2), probe_fn=fake_probe()).check().reason == "store size"
    assert Governor(store, Limits(reserve_ram_mb=1024), probe_fn=fake_probe(avail_mb=900)).check().reason == "memory"
    g = Governor(store, Limits(max_process_mb=100), probe_fn=fake_probe(), rss_fn=lambda: 150.0)
    assert g.check().reason == "process memory"
    assert Governor(store, Limits(), probe_fn=fake_probe()).check().ok


def test_background_work_waits_while_the_cpu_is_busy(tmp_path):
    loads = iter([3.9, 3.8, 0.2])
    g = Governor(tmp_path / "m.sqlite", Limits(max_load_per_core=0.9),
                 probe_fn=lambda p: fake_probe(load=next(loads))(p))
    slept = []
    assert g.wait_until_idle(step_s=5, sleep=slept.append) == 10 and slept == [5, 5]


def test_bulk_ingest_stops_at_the_store_cap_and_resumes_without_duplicates(tmp_path):
    engine = fresh_engine(tmp_path, "bulk")
    store_path = tmp_path / "bulk.sqlite"
    ckpt = tmp_path / "bulk.ckpt"
    size0 = Governor(store_path, Limits()).store_mb()
    cap = Governor(store_path, Limits(max_store_mb=size0 + 1.5, reserve_disk_mb=0), probe_fn=fake_probe())
    r1 = bulk_ingest(engine, docs(3000), governor=cap, batch_docs=100, checkpoint=ckpt)
    assert r1.stopped == "store size" and 0 < r1.documents < 3000 and not r1.finished
    assert json.loads(ckpt.read_text())["consumed"] == r1.documents
    roomy = Governor(store_path, Limits(reserve_disk_mb=0), probe_fn=fake_probe())
    r2 = bulk_ingest(engine, docs(3000), governor=roomy, batch_docs=500, checkpoint=ckpt)
    assert r2.finished and r2.resumed_from == r1.documents and r1.documents + r2.documents == 3000
    n_notes, n_sources = engine.store.conn.execute("SELECT count(*), count(DISTINCT source_id) FROM note").fetchone()
    assert n_notes == n_sources == 3000  # every paragraph once, none twice
    assert r2.bytes_per_note and r2.room_for_notes is not None


def test_bulk_ingest_without_a_checkpoint_still_never_duplicates(tmp_path):
    engine = fresh_engine(tmp_path, "b2")
    bulk_ingest(engine, docs(200), batch_docs=64)
    r = bulk_ingest(engine, docs(300), batch_docs=64)  # the first 200 are already stored
    assert r.skipped_existing == 200 and r.notes_added == 100


def test_readers_stream_jsonl_and_folders(tmp_path):
    (tmp_path / "c.jsonl").write_text("\n".join(json.dumps({"id": i, "title": f"T{i}", "text": f"text {i}"})
                                                for i in range(5)) + "\n\n")
    got = list(read_jsonl(tmp_path / "c.jsonl"))
    assert [d.doc_id for d in got] == ["0", "1", "2", "3", "4"] and got[0].title == "T0"
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "kenya_trip.md").write_text("First paragraph.\n\nSecond\nparagraph.\n")
    got = list(read_folder(tmp_path / "notes"))
    assert [(d.doc_id, d.text, d.title) for d in got] == [("kenya_trip.md#0", "First paragraph.", "kenya trip"),
                                                          ("kenya_trip.md#1", "Second paragraph.", "kenya trip")]


def test_the_read_plan_adapts_to_the_device():
    fast = DeviceProfile(16_000, 12_000, 8, 0.1, 100_000, 50_000, "/", search_ms={"100000": 12.0},
                         gen_tokens_per_s=60.0, prefill_tokens_per_s=900.0)
    slow = DeviceProfile(4_000, 1_500, 2, 0.1, 100_000, 3_000, "/", search_ms={"100000": 90.0},
                         gen_tokens_per_s=8.0, prefill_tokens_per_s=120.0)
    a = plan(fast, notes=20_000, dim=384)
    b = plan(slow, notes=20_000, dim=384, limits=Limits(latency_target_ms=2500, reserve_ram_mb=768))
    assert a.search == "exact" and a.token_budget == 512
    assert b.token_budget < a.token_budget and b.expected_ms <= 2500 + 1e-6 or b.token_budget == 64
    assert plan(fast, notes=250_000, dim=384).search == "exact"  # in RAM, exact is as fast at equal recall
    assert plan(fast, notes=1_500_000, dim=384).search == "index"
    assert plan(slow, notes=80_000, dim=768).search == "index"  # 234 MB of vectors would crowd its RAM
    assert b.max_notes_on_disk < a.max_notes_on_disk


# ---------------------------------------------------------------- deferred vectors
def test_deferred_ingest_is_searchable_at_once_and_vectors_follow(tmp_path):
    from camr.memory.bulk import drain

    lazy, eager = fresh_engine(tmp_path, "lazy"), fresh_engine(tmp_path, "eager")
    r = bulk_ingest(lazy, docs(400), batch_docs=100, defer_embedding=True)
    bulk_ingest(eager, docs(400), batch_docs=100)
    assert r.notes_added == 400 and r.pending_vectors == 400 and r.embed_seconds == 0
    hits = lazy.store.keyword("How many inhabitants does place 123 have?", 5, lazy.note_type)
    assert hits and "place 123 " in lazy.store.get_notes([hits[0][0]])[hits[0][0]].text
    q = "Paragraph 123 says that place 123 has how many inhabitants?"
    got = lazy.recall(q, touch=False)  # the keyword hits it reaches get their vectors now
    assert "861 inhabitants" in got.context
    assert lazy.store.pending_count() < 400
    assert drain(lazy).remaining == 0 and lazy.store.pending_count() == 0
    a, b = lazy.recall(q, touch=False), eager.recall(q, touch=False)
    assert [c.note.text for c in a.candidates[:5]] == [c.note.text for c in b.candidates[:5]]


def test_the_keyword_index_follows_deletions(tmp_path):
    engine = fresh_engine(tmp_path, "fts")
    engine.ingest([Document("web", "u1", "The okapi lives in the Ituri rainforest.", "Okapi")])
    assert engine.store.keyword("okapi rainforest", 3, engine.note_type)
    sid = engine.store.conn.execute("SELECT source_id FROM source").fetchone()[0]
    engine.store.delete_source(sid)
    assert engine.store.keyword("okapi rainforest", 3, engine.note_type) == []


def test_draining_waits_for_a_busy_cpu_and_stops_at_limits(tmp_path):
    from camr.memory.bulk import drain

    engine = fresh_engine(tmp_path, "drain")
    bulk_ingest(engine, docs(300), batch_docs=100, defer_embedding=True)
    cap = Governor(tmp_path / "drain.sqlite", Limits(reserve_disk_mb=1000), probe_fn=fake_probe(free_mb=1000.1))
    rep = drain(engine, governor=cap, batch=64)
    assert rep.stopped == "disk" and rep.embedded == 0 and rep.remaining == 300
    rep = drain(engine, batch=64, max_seconds=0.0)
    assert rep.stopped == "time"
    assert drain(engine, batch=64).remaining == 0


def test_the_index_switches_on_sooner_on_a_device_with_little_spare_ram():
    from camr.device import index_threshold

    roomy = DeviceProfile(64_000, 48_000, 16, 0.1, 1e6, 5e5, "/")
    tight = DeviceProfile(4_000, 1_200, 2, 0.1, 1e5, 2e3, "/")
    assert index_threshold(roomy, 384) == 1_000_000
    assert 20_000 <= index_threshold(tight, 768) < 100_000
