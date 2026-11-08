"""The reranker (camr_engine.rerank): a small cross-encoder run in MLX, used to pick the bridge line of a second
search. Needs the cross-encoder's files in the local Hugging Face cache; skipped without them."""

import pytest

from camr_engine.bench.local import parse_settings
from camr_engine.finder import LineIndex

try:
    from camr_engine.rerank import RERANKER, _snapshot

    _snapshot(RERANKER)
    HAVE = True
except Exception:  # not cached here: nothing is downloaded by a test
    HAVE = False

needs_model = pytest.mark.skipif(not HAVE, reason="the cross-encoder is not in the local cache")

MOMENTS = [
    "[2025-10-06, day 11] User: Branch managers' call. Leftovers at Karen up 6%. The new phones arrive Friday.",
    "[2025-10-07, day 12] User: Kevin handles payroll from this week. Can you look at the cart drawer?",
    "[2025-10-08, day 13] User: Whoever handles payroll gets extension 214 on the new phones.",
    "[2025-10-09, day 14] User: Don't schedule Wanjiru Kamau on Tuesdays, that's their day off.",
]


@needs_model
def test_the_cross_encoder_matches_its_model_card():
    from camr_engine.rerank import shared

    got = shared().scores("How many people live in Berlin?",
                          ["Berlin has a population of 3,520,031 registered inhabitants in an area of 891.82 square "
                           "kilometers.", "Berlin is well known for its museums."])
    assert got[0] > 8 and abs(got[1] - (-4.32)) < 0.05


@needs_model
def test_moments_are_ordered_by_their_best_line():
    from camr_engine.rerank import shared

    ix = LineIndex(MOMENTS)
    ranked, best = shared().order(ix, "What day is Wanjiru Kamau off?", [0, 1, 2, 3])
    assert ranked[0] == 3 and "Tuesdays" in best[3][1]


@needs_model
def test_the_second_search_follows_the_bridge_to_the_answer():
    from camr_engine.rerank import second_search

    ix = LineIndex(MOMENTS)
    # the first search found who handles payroll; the extension is told only of "whoever handles payroll"
    assert second_search(ix, "Which extension does Kevin get?", [1], keep=1) == [2]


def test_hop_is_a_setting_for_both_readers():
    assert parse_settings("engine", "closest=6,hop=2") == {"closest": 6, "hop": 2}
    assert parse_settings("rag", "k=6,hop=2") == {"k": 6, "hop": 2}
