"""SQLite persistence for analyses, interview sessions, the master profile
and the job application tracker."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")

# Columns added after v1.0. Each is applied with ALTER TABLE on startup so an
# existing radar.db keeps working without being deleted and recreated.
_MIGRATIONS = {
    "resume_text": "TEXT",   # extracted plain text, needed to rebuild the resume
    "questions": "TEXT",     # JSON: gap-fill questions generated for this resume
    "answers": "TEXT",       # JSON: the candidate's answers
    "rebuilt": "TEXT",       # the improved resume produced from those answers
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                filename   TEXT NOT NULL,
                role       TEXT,
                overall    INTEGER NOT NULL,
                grade      TEXT NOT NULL,
                created_at TEXT NOT NULL,
                report     TEXT NOT NULL
            )
            """
        )
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(analyses)")}
        for column, coltype in _MIGRATIONS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE analyses ADD COLUMN {column} {coltype}")

        # One master profile per install; the fixed id keeps it a singleton.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                data       TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                company     TEXT,
                title       TEXT,
                url         TEXT,
                job_type    TEXT,
                work_mode   TEXT,
                location    TEXT,
                stipend     TEXT,
                duration    TEXT,
                status      TEXT NOT NULL DEFAULT 'Saved',
                notes       TEXT,
                jd_text     TEXT,
                resume_text TEXT,
                match_score INTEGER,
                engine      TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
            """
        )


def save_analysis(filename: str, role: str, report: dict, resume_text: str = "") -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO analyses (filename, role, overall, grade, created_at, report, resume_text)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                filename,
                role,
                report["overall"],
                report["grade"],
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                json.dumps(report),
                resume_text,
            ),
        )
        return cur.lastrowid


def get_analysis(analysis_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:
        return None
    item = dict(row)
    for key in ("report", "questions", "answers"):
        if item.get(key):
            try:
                item[key] = json.loads(item[key])
            except (TypeError, ValueError):
                item[key] = None
    return item


def save_questions(analysis_id: int, questions: list[dict]) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE analyses SET questions = ? WHERE id = ?",
            (json.dumps(questions), analysis_id),
        )


def save_rebuild(analysis_id: int, answers: dict, rebuilt: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE analyses SET answers = ?, rebuilt = ? WHERE id = ?",
            (json.dumps(answers), rebuilt, analysis_id),
        )


# --------------------------------------------------------------------------
# Master profile
# --------------------------------------------------------------------------
def get_profile() -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT data FROM profile WHERE id = 1").fetchone()
    if not row:
        return None
    try:
        return json.loads(row["data"])
    except (TypeError, ValueError):
        return None


def save_profile(data: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO profile (id, data, updated_at) VALUES (1, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET data = excluded.data,"
            " updated_at = excluded.updated_at",
            (json.dumps(data), _now()),
        )


# --------------------------------------------------------------------------
# Application tracker
# --------------------------------------------------------------------------
APPLICATION_FIELDS = (
    "company", "title", "url", "job_type", "work_mode", "location",
    "stipend", "duration", "status", "notes", "jd_text", "resume_text",
    "match_score", "engine",
)

# Columns too large to ship in the list view; fetched per-application instead.
_HEAVY_FIELDS = ("jd_text", "resume_text")
_LIST_FIELDS = ["id"] + [f for f in APPLICATION_FIELDS if f not in _HEAVY_FIELDS] + [
    "created_at", "updated_at"
]


def create_application(data: dict) -> int:
    values = {f: data.get(f) for f in APPLICATION_FIELDS}
    values["status"] = values.get("status") or "Saved"
    now = _now()
    columns = ", ".join(APPLICATION_FIELDS) + ", created_at, updated_at"
    marks = ", ".join("?" for _ in range(len(APPLICATION_FIELDS) + 2))
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO applications ({columns}) VALUES ({marks})",
            tuple(values[f] for f in APPLICATION_FIELDS) + (now, now),
        )
        return cur.lastrowid


def update_application(app_id: int, data: dict) -> bool:
    fields = [f for f in APPLICATION_FIELDS if f in data]
    if not fields:
        return False
    assignments = ", ".join(f"{f} = ?" for f in fields) + ", updated_at = ?"
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE applications SET {assignments} WHERE id = ?",
            tuple(data[f] for f in fields) + (_now(), app_id),
        )
        return cur.rowcount > 0


def get_application(app_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    return dict(row) if row else None


def list_applications() -> list[dict]:
    columns = ", ".join(_LIST_FIELDS)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {columns}, (resume_text IS NOT NULL AND resume_text != '') AS has_resume"
            " FROM applications ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_application(app_id: int) -> bool:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM applications WHERE id = ?", (app_id,))
        return cur.rowcount > 0


def list_history(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, filename, role, overall, grade, created_at,"
            " (rebuilt IS NOT NULL) AS improved"
            " FROM analyses ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
