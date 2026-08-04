"""
How urgent is this application, and what should it say?

The rule lives here rather than in the React component for one reason: this is
the logic that decides what the user chases and what they let go, and logic
that matters should be testable. The frontend receives a level and a label and
only chooses a colour.

Levels, in the order they escalate:

    good     the company came back, or an offer landed — nothing to do
    neutral  saved but not applied, or closed out
    active   applied recently, still inside a reasonable wait
    warn     silent past a week, or a deadline coming up
    urgent   silent past two weeks, or the deadline has gone
"""
from __future__ import annotations

from datetime import date, datetime, timezone

# A week is when a follow-up starts being reasonable; two weeks is when
# silence usually means no. Both are judgement calls, not science, which is
# why they are named constants and not scattered through the code.
QUIET_DAYS = 7
STALE_DAYS = 14
# Far enough ahead to still act on, close enough to be worth flagging.
DEADLINE_SOON_DAYS = 3

WAITING_STATUSES = ("Applied", "Interviewing")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _as_date(value) -> date | None:
    """Accept a date, a datetime, or an ISO string, and give back a date."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def assess(
    status: str,
    applied_at=None,
    deadline: str = "",
    replied: bool = False,
    today: date | None = None,
) -> dict:
    """Return {'level': str, 'label': str} for one application."""
    today = today or datetime.now(timezone.utc).date()
    status = status or "Saved"

    if status == "Offer":
        return {"level": "good", "label": "Offer received"}
    if replied:
        return {"level": "good", "label": "They replied"}
    if status == "Rejected":
        return {"level": "neutral", "label": "Closed"}

    due = _as_date(deadline)

    # Not sent yet: the only clock that matters is the company's closing date.
    if status not in WAITING_STATUSES:
        if due:
            days = (due - today).days
            if days < 0:
                return {"level": "urgent", "label": "Deadline passed"}
            if days == 0:
                return {"level": "urgent", "label": "Closes today"}
            if days <= DEADLINE_SOON_DAYS:
                return {"level": "warn", "label": f"Closes in {_plural(days, 'day')}"}
            return {"level": "neutral", "label": f"Closes in {_plural(days, 'day')}"}
        return {"level": "neutral", "label": "Not applied yet"}

    # Applied or interviewing: the clock is how long they have been quiet.
    since = _as_date(applied_at)
    if not since:
        # Applied, but from before the date was being recorded.
        return {"level": "active", "label": "Waiting to hear back"}

    days = max((today - since).days, 0)
    if days == 0:
        return {"level": "active", "label": "Applied today"}
    if days < QUIET_DAYS:
        return {"level": "active", "label": f"Applied {_plural(days, 'day')} ago"}
    if days < STALE_DAYS:
        return {"level": "warn", "label": f"No reply for {_plural(days, 'day')}"}
    return {"level": "urgent", "label": f"No reply for {_plural(days, 'day')}"}


def needs_follow_up(level: str) -> bool:
    """The two levels the dashboard counts as needing action."""
    return level in ("warn", "urgent")
