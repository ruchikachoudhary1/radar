"""
Database connection.

One environment variable decides where data lives:

    DATABASE_URL unset            -> SQLite file at backend/data/radar.db (local dev)
    DATABASE_URL=postgresql://... -> that PostgreSQL server (production)

Nothing else in the codebase knows the difference, which is the point: the same
code and the same tests run against both.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from models import Base

DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "data", "radar.db")


def _normalise(url: str) -> str:
    """
    Make a hosted provider's URL usable by SQLAlchemy + psycopg 3.

    Neon, Render and Heroku all hand out `postgres://` or `postgresql://`, but
    SQLAlchemy needs the driver named explicitly or it reaches for psycopg2,
    which is not installed.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def _build_engine():
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return create_engine(
            _normalise(url),
            pool_pre_ping=True,   # hosted Postgres drops idle connections
            pool_recycle=300,
        )
    os.makedirs(os.path.dirname(DEFAULT_SQLITE_PATH), exist_ok=True)
    return create_engine(
        f"sqlite:///{DEFAULT_SQLITE_PATH}",
        connect_args={"check_same_thread": False},
    )


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def is_postgres() -> bool:
    return engine.dialect.name == "postgresql"


# Columns added after the pre-auth schema. SQLAlchemy's create_all() only
# creates missing *tables*, so an existing radar.db keeps its old shape unless
# the new columns are added explicitly.
_LEGACY_COLUMNS = {
    "analyses": {
        "user_id": "INTEGER",
        "resume_text": "TEXT",
        "questions": "TEXT",
        "answers": "TEXT",
        "rebuilt": "TEXT",
    },
    "applications": {
        "user_id": "INTEGER",
        "applied_at": "TIMESTAMP",
        "replied": "BOOLEAN DEFAULT 0",
        "deadline": "VARCHAR(10)",
        "cover_letter": "TEXT",
    },
}


def _migrate_legacy_columns() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _LEGACY_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for column, coltype in columns.items():
                if column not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))


def init_db() -> None:
    Base.metadata.create_all(engine)
    _migrate_legacy_columns()


def get_session() -> Session:
    return SessionLocal()
