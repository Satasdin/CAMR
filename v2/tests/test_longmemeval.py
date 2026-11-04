"""LongMemEval items become dated notes, oldest session first."""

from __future__ import annotations

import datetime as dt
import json

from camr_engine.ruler.longmemeval import load

ITEM = {"question_id": "abc_abs", "question_type": "knowledge-update", "question": "Where do I work now?",
        "answer": "Nairobi", "question_date": "2023/05/30 (Tue) 10:00",
        "haystack_dates": ["2023/05/20 (Sat) 02:21", "2023/05/01 (Mon) 09:00"],
        "haystack_session_ids": ["s2", "s1"],
        "haystack_sessions": [[{"role": "user", "content": "I moved to Nairobi."}, {"role": "assistant", "content": " "}],
                              [{"role": "user", "content": "I work in Kisumu."}]]}


def test_sessions_become_dated_notes_oldest_first(tmp_path):
    p = tmp_path / "lme.json"
    p.write_text(json.dumps([ITEM]))
    (item,) = load(path=p)
    assert item.asked == dt.date(2023, 5, 30) and item.should_decline
    assert [d for d, _ in item.sessions] == [dt.date(2023, 5, 1), dt.date(2023, 5, 20)]
    assert item.sessions[1][1] == ["[2023-05-20] user: I moved to Nairobi."]  # empty turns dropped
