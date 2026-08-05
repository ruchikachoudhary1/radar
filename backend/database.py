"""
Data access for analyses, the master profile and the application tracker.

Every function takes the session and the owning user, and every query filters
on user_id. Scoping here rather than in the route handlers means a forgotten
check in one endpoint cannot leak another account's resumes — the only way to
read a row is through a function that already constrains by owner.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

import urgency
from db import init_db  # re-exported: main.py calls database.init_db() on startup
from models import Analysis, Application, Preference, Profile, User

__all__ = [
    "init_db",
    "save_analysis", "get_analysis", "save_questions", "save_rebuild", "list_history",
    "get_profile", "save_profile",
    "get_preferences", "save_preferences", "stamp_feed_refresh",
    "create_application", "get_application", "list_applications",
    "update_application", "delete_application", "summarise",
    "APPLICATION_FIELDS",
]

APPLICATION_FIELDS = (
    "company", "title", "url", "job_type", "work_mode", "location",
    "stipend", "duration", "status", "notes", "jd_text", "resume_text",
    "match_score", "engine", "replied", "deadline", "cover_letter",
)

# Large columns are omitted from the list view and fetched per-application.
_LIST_FIELDS = (
    "id", "company", "title", "url", "job_type", "work_mode", "location",
    "stipend", "duration", "status", "notes", "match_score", "engine",
    "replied", "deadline",
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


# --------------------------------------------------------------------------
# Analyses
# --------------------------------------------------------------------------
def save_analysis(
    db: Session, user: User, filename: str, role: str, report: dict, resume_text: str = ""
) -> int:
    row = Analysis(
        user_id=user.id,
        filename=filename,
        role=role or "",
        overall=report["overall"],
        grade=report["grade"],
        report=report,
        resume_text=resume_text,
    )
    db.add(row)
    db.commit()
    return row.id


def _analysis(db: Session, user: User, analysis_id: int) -> Analysis | None:
    return db.scalar(
        select(Analysis).where(Analysis.id == analysis_id, Analysis.user_id == user.id)
    )


def get_analysis(db: Session, user: User, analysis_id: int) -> dict | None:
    row = _analysis(db, user, analysis_id)
    if not row:
        return None
    return {
        "id": row.id,
        "filename": row.filename,
        "role": row.role,
        "overall": row.overall,
        "grade": row.grade,
        "report": row.report,
        "resume_text": row.resume_text or "",
        "questions": row.questions,
        "answers": row.answers,
        "rebuilt": row.rebuilt,
        "created_at": _iso(row.created_at),
    }


def save_questions(db: Session, user: User, analysis_id: int, questions: list[dict]) -> None:
    row = _analysis(db, user, analysis_id)
    if row:
        row.questions = questions
        db.commit()


def save_rebuild(db: Session, user: User, analysis_id: int, answers: dict, rebuilt: str) -> None:
    row = _analysis(db, user, analysis_id)
    if row:
        row.answers = answers
        row.rebuilt = rebuilt
        db.commit()


def list_history(db: Session, user: User, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.user_id == user.id)
        .order_by(Analysis.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "role": r.role,
            "overall": r.overall,
            "grade": r.grade,
            "created_at": _iso(r.created_at),
            "improved": bool(r.rebuilt),
        }
        for r in rows
    ]


# --------------------------------------------------------------------------
# Master profile
# --------------------------------------------------------------------------
DEFAULT_PREFERENCES = {
    "roles": [],
    "locations": [],
    "companies": [],
    "internships_only": False,
    "remote_only": False,
}


def get_preferences(db: Session, user: User) -> dict:
    row = db.scalar(select(Preference).where(Preference.user_id == user.id))
    prefs = dict(DEFAULT_PREFERENCES)
    if row:
        prefs.update(row.data or {})
        prefs["refreshed_at"] = _iso(row.refreshed_at)
    else:
        prefs["refreshed_at"] = None
    return prefs


def save_preferences(db: Session, user: User, data: dict) -> dict:
    row = db.scalar(select(Preference).where(Preference.user_id == user.id))
    clean = {k: data.get(k, v) for k, v in DEFAULT_PREFERENCES.items()}
    if row:
        row.data = clean
    else:
        db.add(Preference(user_id=user.id, data=clean))
    db.commit()
    return get_preferences(db, user)


def stamp_feed_refresh(db: Session, user: User) -> None:
    row = db.scalar(select(Preference).where(Preference.user_id == user.id))
    if not row:
        row = Preference(user_id=user.id, data=dict(DEFAULT_PREFERENCES))
        db.add(row)
    row.refreshed_at = datetime.now(timezone.utc)
    db.commit()


def get_profile(db: Session, user: User) -> dict | None:
    row = db.scalar(select(Profile).where(Profile.user_id == user.id))
    return row.data if row else None


def save_profile(db: Session, user: User, data: dict) -> None:
    row = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if row:
        row.data = data
    else:
        db.add(Profile(user_id=user.id, data=data))
    db.commit()


# --------------------------------------------------------------------------
# Application tracker
# --------------------------------------------------------------------------
def _as_dict(row: Application, fields: tuple[str, ...]) -> dict:
    out = {f: getattr(row, f) for f in fields}
    out["created_at"] = _iso(row.created_at)
    out["updated_at"] = _iso(row.updated_at)
    out["applied_at"] = _iso(row.applied_at)
    # Computed server-side so the pipeline colouring has one definition, and
    # so the rule that decides what the user chases can be tested.
    out["urgency"] = urgency.assess(
        status=row.status,
        applied_at=row.applied_at,
        deadline=row.deadline or "",
        replied=bool(row.replied),
    )
    return out


def create_application(db: Session, user: User, data: dict) -> int:
    values = {f: data[f] for f in APPLICATION_FIELDS if data.get(f) is not None}
    values.setdefault("status", "Saved")
    row = Application(user_id=user.id, **values)
    if row.status == "Applied":
        row.applied_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()
    return row.id


def get_application(db: Session, user: User, app_id: int) -> dict | None:
    row = db.scalar(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not row:
        return None
    return _as_dict(row, APPLICATION_FIELDS + ("id",))


def list_applications(db: Session, user: User) -> list[dict]:
    rows = db.scalars(
        select(Application)
        .where(Application.user_id == user.id)
        .order_by(Application.updated_at.desc(), Application.id.desc())
    ).all()
    out = []
    for row in rows:
        item = _as_dict(row, _LIST_FIELDS)
        item["has_resume"] = bool(row.resume_text)
        item["has_letter"] = bool(row.cover_letter)
        out.append(item)
    return out


def summarise(db: Session, user: User) -> dict:
    """
    The dashboard's numbers, computed in one pass over the user's rows.

    Counts come from the same urgency rule the cards use, so the dashboard can
    never disagree with the pipeline about what needs chasing.
    """
    apps = list_applications(db, user)
    analyses = list_history(db, user, limit=200)

    by_status: dict[str, int] = {}
    by_level: dict[str, int] = {}
    for app in apps:
        by_status[app["status"]] = by_status.get(app["status"], 0) + 1
        level = (app.get("urgency") or {}).get("level", "neutral")
        by_level[level] = by_level.get(level, 0) + 1

    chase = [a for a in apps if urgency.needs_follow_up((a.get("urgency") or {}).get("level", ""))]
    # Most pressing first, then the longest-waiting.
    chase.sort(key=lambda a: (a["urgency"]["level"] != "urgent", a.get("applied_at") or ""))

    scores = [a["overall"] for a in analyses]
    return {
        "totals": {
            "applications": len(apps),
            "analyses": len(analyses),
            "needs_follow_up": len(chase),
            "replied": sum(1 for a in apps if a.get("replied")),
            "with_resume": sum(1 for a in apps if a.get("has_resume")),
        },
        "by_status": by_status,
        "by_level": by_level,
        "follow_ups": chase[:6],
        "recent_applications": apps[:5],
        "recent_analyses": analyses[:5],
        "best_score": max(scores) if scores else None,
        "latest_score": scores[0] if scores else None,
    }


def update_application(db: Session, user: User, app_id: int, data: dict) -> bool:
    row = db.scalar(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not row:
        return False
    for field in APPLICATION_FIELDS:
        if field in data:
            setattr(row, field, data[field])
    # Stamp the moment of applying once, so "silent for N days" counts from the
    # application rather than from the last time any field was edited.
    if data.get("status") == "Applied" and row.applied_at is None:
        row.applied_at = datetime.now(timezone.utc)
    db.commit()
    return True


def delete_application(db: Session, user: User, app_id: int) -> bool:
    row = db.scalar(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True
