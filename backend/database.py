"""SQLite persistence for analysis history."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")


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


def save_analysis(filename: str, role: str, report: dict) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO analyses (filename, role, overall, grade, created_at, report)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                filename,
                role,
                report["overall"],
                report["grade"],
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                json.dumps(report),
            ),
        )
        return cur.lastrowid


def list_history(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, filename, role, overall, grade, created_at"
            " FROM analyses ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
