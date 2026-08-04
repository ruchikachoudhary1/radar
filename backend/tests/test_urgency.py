"""
Tests for the follow-up rules.

These decide what the user chases and what they let go, so the boundaries
matter: day 6 should look calm and day 7 should not.
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import urgency  # noqa: E402

TODAY = date(2026, 8, 4)


def applied(days_ago: int) -> datetime:
    return datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time(), timezone.utc)


def due(days_ahead: int) -> str:
    return (TODAY + timedelta(days=days_ahead)).isoformat()


# --------------------------------------------------------------------------
# Outcomes that end the chase
# --------------------------------------------------------------------------
def test_an_offer_is_good_regardless_of_how_long_it_took():
    assert urgency.assess("Offer", applied_at=applied(90), today=TODAY)["level"] == "good"


def test_a_reply_stops_the_clock_even_while_still_waiting():
    result = urgency.assess("Applied", applied_at=applied(60), replied=True, today=TODAY)
    assert result["level"] == "good"
    assert result["label"] == "They replied"


def test_rejected_is_closed_not_urgent():
    assert urgency.assess("Rejected", applied_at=applied(60), today=TODAY)["level"] == "neutral"


# --------------------------------------------------------------------------
# Saved but not applied — the company's deadline is the only clock
# --------------------------------------------------------------------------
def test_saved_with_no_deadline_is_quiet():
    result = urgency.assess("Saved", today=TODAY)
    assert result == {"level": "neutral", "label": "Not applied yet"}


def test_a_distant_deadline_does_not_shout():
    assert urgency.assess("Saved", deadline=due(30), today=TODAY)["level"] == "neutral"


def test_a_deadline_within_three_days_warns():
    assert urgency.assess("Saved", deadline=due(3), today=TODAY)["level"] == "warn"


def test_a_deadline_today_is_urgent():
    result = urgency.assess("Saved", deadline=due(0), today=TODAY)
    assert result == {"level": "urgent", "label": "Closes today"}


def test_a_passed_deadline_is_urgent():
    result = urgency.assess("Saved", deadline=due(-1), today=TODAY)
    assert result == {"level": "urgent", "label": "Deadline passed"}


def test_deadline_is_ignored_once_the_application_is_in():
    """After applying, their closing date no longer tells you anything."""
    result = urgency.assess("Applied", applied_at=applied(1), deadline=due(-5), today=TODAY)
    assert result["level"] == "active"


# --------------------------------------------------------------------------
# Waiting to hear back — the boundaries
# --------------------------------------------------------------------------
@pytest.mark.parametrize("days,level", [
    (0, "active"),
    (1, "active"),
    (6, "active"),    # last calm day
    (7, "warn"),      # a week of silence
    (13, "warn"),
    (14, "urgent"),   # two weeks
    (60, "urgent"),
])
def test_silence_escalates_at_one_and_two_weeks(days, level):
    assert urgency.assess("Applied", applied_at=applied(days), today=TODAY)["level"] == level


def test_interviewing_uses_the_same_clock_as_applied():
    assert urgency.assess("Interviewing", applied_at=applied(20), today=TODAY)["level"] == "urgent"


def test_labels_read_naturally():
    assert urgency.assess("Applied", applied_at=applied(0), today=TODAY)["label"] == "Applied today"
    assert urgency.assess("Applied", applied_at=applied(1), today=TODAY)["label"] == "Applied 1 day ago"
    assert urgency.assess("Applied", applied_at=applied(3), today=TODAY)["label"] == "Applied 3 days ago"
    assert urgency.assess("Applied", applied_at=applied(9), today=TODAY)["label"] == "No reply for 9 days"


def test_applied_without_a_recorded_date_still_reads_sensibly():
    """Rows created before applied_at was stored must not crash or shout."""
    result = urgency.assess("Applied", applied_at=None, today=TODAY)
    assert result == {"level": "active", "label": "Waiting to hear back"}


# --------------------------------------------------------------------------
# Input handling
# --------------------------------------------------------------------------
def test_a_future_applied_date_does_not_produce_negative_days():
    assert urgency.assess("Applied", applied_at=applied(-5), today=TODAY)["level"] == "active"


@pytest.mark.parametrize("junk", ["", "not-a-date", "2026-13-45", None])
def test_unparseable_deadlines_are_ignored_rather_than_crashing(junk):
    assert urgency.assess("Saved", deadline=junk, today=TODAY)["level"] == "neutral"


def test_iso_strings_and_datetimes_are_both_accepted():
    as_string = urgency.assess("Applied", applied_at=applied(10).isoformat(), today=TODAY)
    as_datetime = urgency.assess("Applied", applied_at=applied(10), today=TODAY)
    assert as_string == as_datetime


def test_needs_follow_up_covers_exactly_warn_and_urgent():
    assert urgency.needs_follow_up("warn")
    assert urgency.needs_follow_up("urgent")
    assert not urgency.needs_follow_up("active")
    assert not urgency.needs_follow_up("good")
    assert not urgency.needs_follow_up("neutral")
