"""SQLite persistence for analysis history and interview sessions."""
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


def list_history(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, filename, role, overall, grade, created_at,"
            " (rebuilt IS NOT NULL) AS improved"
            " FROM analyses ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
