"""SQLite access for jobs. Functions take a connection so tests can use a temp DB."""

import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from jobpilot.models import Job

DEFAULT_DB_PATH = Path("data") / "jobpilot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    location    TEXT NOT NULL,
    url         TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    posted_at   TEXT,
    fetched_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_jobs_posted_at ON jobs (posted_at);
"""

_COLUMNS = (
    "id",
    "source",
    "title",
    "company",
    "location",
    "url",
    "description",
    "posted_at",
    "fetched_at",
)


def connect(path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (and create if needed) the database file."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist. Safe to call on every start."""
    conn.executescript(_SCHEMA)


def insert_jobs(conn: sqlite3.Connection, jobs: Iterable[Job]) -> int:
    """Insert jobs, skipping ids already stored. Returns how many were new."""
    sql = (
        f"INSERT OR IGNORE INTO jobs ({', '.join(_COLUMNS)}) "
        f"VALUES ({', '.join('?' * len(_COLUMNS))})"
    )
    with conn:  # one transaction: commit on success, rollback on error
        before = conn.total_changes
        conn.executemany(sql, (_to_row(job) for job in jobs))
        return conn.total_changes - before


def list_jobs(conn: sqlite3.Connection, limit: int | None = None) -> list[Job]:
    """Return jobs, newest first (jobs without posted_at go last)."""
    sql = "SELECT * FROM jobs ORDER BY posted_at IS NULL, posted_at DESC, fetched_at DESC"
    params: tuple[int, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    return [_from_row(row) for row in conn.execute(sql, params)]


def _to_row(job: Job) -> tuple:
    return (
        job.id,
        job.source,
        job.title,
        job.company,
        job.location,
        job.url,
        job.description,
        job.posted_at.isoformat() if job.posted_at else None,
        job.fetched_at.isoformat(),
    )


def _from_row(row: sqlite3.Row) -> Job:
    posted = row["posted_at"]
    return Job(
        id=row["id"],
        source=row["source"],
        title=row["title"],
        company=row["company"],
        location=row["location"],
        url=row["url"],
        description=row["description"],
        posted_at=datetime.fromisoformat(posted) if posted else None,
        fetched_at=datetime.fromisoformat(row["fetched_at"]),
    )
