"""The word finder (camr_engine.finder): lines scored by their words, a moment scoring as its best line, a second look
for a bridge, and the index growing with the memory."""

import numpy as np

from camr_engine.finder import LineIndex, best_lines, lines_of, words

MOMENTS = [
    "[2025-10-06, day 11] User: Branch managers' call, Monday 6 October\nPresent: Naliaka, Wafula\n"
    "- For the staging infrastructure experiments, use the `mnk-infra2` repo.\n- Leftovers at Karen up 6%.",
    "[2025-10-07, day 12] User: Kevin handles payroll from this week. Can you look at the cart drawer?",
    "[2025-10-08, day 13] User: Whoever handles payroll gets extension 214 on the new phones.",
    "[2025-10-09, day 14] User: Don't schedule Wanjiru Kamau on Tuesdays, that's their day off.",
    "[2025-10-24, day 24] User: Don't schedule Wanjiru Njoroge on Thursdays, that's their day off.",
]


def test_lines_drop_the_stamp_and_split_sentences():
    got = lines_of(MOMENTS[0])
    assert got[0].startswith("Branch managers' call")
    assert any("mnk-infra2" in line for line in got)
    assert all(not line.startswith("[2025") for line in got)


def test_words_skip_stop_words():
    assert words("What is the day off of Wanjiru Kamau?") == ["day", "off", "wanjiru", "kamau"]


def test_a_rare_name_finds_its_moment_not_its_lookalike():
    ix = LineIndex(MOMENTS)
    order = ix.order("What is Wanjiru Njoroge's day off?")
    assert int(order[0]) == 4
    assert int(ix.order("What is Wanjiru Kamau's day off?")[0]) == 3


def test_a_moment_scores_as_its_best_line():
    ix = LineIndex(MOMENTS)
    assert int(ix.order("Which repo holds the staging infrastructure experiments?")[0]) == 0


def test_the_second_look_reaches_the_bridge():
    ix = LineIndex(MOMENTS)
    with_hop = list(ix.order("Which extension will Kevin get on the new phones?", hop=True)[:2])
    assert set(int(m) for m in with_hop) == {1, 2}


def test_the_index_grows_with_the_memory():
    ix = LineIndex(MOMENTS[:2])
    assert ix.moments == 2
    for t in MOMENTS[2:]:
        ix.add(t)
    assert ix.moments == 5
    assert int(ix.order("Wanjiru Kamau Tuesdays")[0]) == 3


def test_dense_scores_join_the_ranking():
    ix = LineIndex(MOMENTS)
    dense = np.array([0, 0, 0, 0, 1.0], dtype=np.float32)
    assert len(ix.order("day off", dense)) == 5


def test_best_lines_keep_their_order():
    ix = LineIndex(MOMENTS)
    got = best_lines(ix, "staging repo", [0], per=2)
    assert any("mnk-infra2" in line for line in got[0])


def test_an_empty_index_orders_nothing():
    assert len(LineIndex().order("anything")) == 0


def test_a_page_request_looks_for_the_design_system():
    ix = LineIndex(MOMENTS + ["[2025-10-01, day 9] User: Design system for the site: main colour #0B5FFF, font Inter.",
                              "[2025-10-02, day 10] User: The catering menu has twelve dishes."])
    top = [int(m) for m in ix.order("Build the catering page.")[:2]]
    assert 5 in top


def test_the_fast_rankings_match_a_full_stable_sort():
    import numpy as np

    from camr_engine.finder import ranks, sparse_ranks, top

    rng = np.random.default_rng(1)
    for _ in range(50):
        x = rng.integers(0, 4, size=200).astype(np.float32) * (rng.random(200) < 0.3)  # mostly zero, many ties
        assert (sparse_ranks(x) == ranks(x)).all()
        full = np.argsort(-x, kind="stable")
        for n in (1, 5, 37, 200, 250):
            assert (top(x, n) == full[:n]).all()


def test_asking_for_the_head_gives_the_head_of_the_whole_order():
    import numpy as np

    from camr_engine.finder import LineIndex

    texts = [f"[2025-10-0{i % 9 + 1}, day {i}] User: order {i % 7} of salt from supplier {i % 5}." for i in range(300)]
    ix = LineIndex(texts)
    dense = np.random.default_rng(2).random(300).astype(np.float32)
    for q in ("Who supplies salt?", "order 3", "supplier 4 salt"):
        assert (ix.order(q, dense, head=40) == ix.order(q, dense)[:40]).all()
