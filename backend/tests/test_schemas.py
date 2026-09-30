"""
Regression test for a real bug: SQLite returns naive datetimes (no
timezone marker) even though every value stored is UTC. Serializing that
naive value as-is produces a JSON timestamp with no offset, which
JavaScript's Date then silently misinterprets as the browser's local
time instead of UTC — shifting displayed times (and sometimes dates) by
the browser's UTC offset. ConversationSummary must always attach an
explicit UTC marker so this can't happen.
"""
from datetime import datetime, timezone

from app.models.schemas import ConversationSummary


def test_naive_datetime_gets_explicit_utc_offset():
    naive = datetime(2026, 9, 28, 5, 43, 0)  # what SQLite hands back
    summary = ConversationSummary(conversation_id="abc", created_at=naive)
    serialized = summary.model_dump_json()
    assert "+00:00" in serialized or serialized.endswith('Z"')


def test_already_aware_datetime_is_left_correct():
    aware = datetime(2026, 9, 28, 5, 43, 0, tzinfo=timezone.utc)
    summary = ConversationSummary(conversation_id="abc", created_at=aware)
    serialized = summary.model_dump_json()
    assert "+00:00" in serialized or serialized.endswith('Z"')
