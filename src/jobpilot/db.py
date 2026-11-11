"""SQLite access for jobs and applications. Functions take a connection (easy to test)."""

import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from jobpilot.models import Application, Job, Score, Status

DEFAULT_DB_PATH = Path("data") / "jobpilot.db"

# Schema history. Each entry runs once, in order; PRAGMA user_version remembers the last one.
# Never edit an old migration: add a new one. (v1 uses IF NOT EXISTS because databases
# created before migrations existed already have the jobs table but user_version 0.)
MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id          TEXT PRIMARY KEY,
        source      TEXT NOT NULL,
        title       TEXT NOT NULL,
        company     TEXT NOT NULL,
        location    TEXT NOT NULL,
        url         TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        posted_at   TEXT,
        fetched_at  TEXT NOT NULL,
        dedupe_key  TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_jobs_posted_at ON jobs (posted_at);
    CREATE UNIQUE INDEX IF NOT EXISTS ux_jobs_dedupe_key ON jobs (dedupe_key);
    """,
    """
    CREATE TABLE applications (
        job_id     TEXT PRIMARY KEY REFERENCES jobs (id),
        status     TEXT NOT NULL
                   CHECK (status IN ('new','saved','applied','interview','offer','rejected')),
        notes      TEXT NOT NULL DEFAULT '',
        applied_at TEXT,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX ix_applications_status ON applications (status);
    """,
    """
    CREATE TABLE scores (
        job_id    TEXT PRIMARY KEY REFERENCES jobs (id),
        score     INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
        reason    TEXT NOT NULL,
        model     TEXT NOT NULL,
        cv_hash   TEXT NOT NULL,
        scored_at TEXT NOT NULL
    );
    """,
)

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
    "dedupe_key",
)


def connect(path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open (and create if needed) the database file."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def init_db(conn: sqlite3.Connection) -> None:
    """Bring the database up to the latest schema. Safe to call on every start."""
    for version, sql in enumerate(MIGRATIONS, start=1):
        if version > schema_version(conn):
            # one transaction per migration: the tables and the version bump succeed together
            conn.executescript(f"BEGIN; {sql}; PRAGMA user_version = {version}; COMMIT;")


def insert_jobs(conn: sqlite3.Connection, jobs: Iterable[Job]) -> int:
    """Insert jobs, skipping any whose id OR dedupe_key is already stored.

    Returns how many were new, so running the same fetch twice inserts 0 the second time.
    """
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
        job.dedupe_key,
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


def get_application(conn: sqlite3.Connection, job_id: str) -> Application:
    """The tracking row for a job, or a fresh NEW application if there is none yet."""
    row = conn.execute("SELECT * FROM applications WHERE job_id = ?", (job_id,)).fetchone()
    return _app_from_row(row) if row else Application(job_id)


def save_application(conn: sqlite3.Connection, app: Application) -> None:
    """Insert or update (upsert) the tracking row for app.job_id."""
    with conn:
        conn.execute(
            """
            INSERT INTO applications (job_id, status, notes, applied_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (job_id) DO UPDATE SET
                status = excluded.status, notes = excluded.notes,
                applied_at = excluded.applied_at, updated_at = excluded.updated_at
            """,
            (
                app.job_id,
                app.status.value,
                app.notes,
                app.applied_at.isoformat() if app.applied_at else None,
                app.updated_at.isoformat(),
            ),
        )


def application_statuses(conn: sqlite3.Connection) -> dict[str, Status]:
    """job_id -> status for every tracked job (for the Status column)."""
    return {r[0]: Status(r[1]) for r in conn.execute("SELECT job_id, status FROM applications")}


def list_applications(conn: sqlite3.Connection) -> list[tuple[Application, Job]]:
    """All tracked jobs (status other than NEW), most recently updated first."""
    rows = conn.execute(
        """
        SELECT a.job_id, a.status, a.notes, a.applied_at, a.updated_at, j.*
        FROM applications a JOIN jobs j ON j.id = a.job_id
        WHERE a.status != 'new'
        ORDER BY a.updated_at DESC
        """
    )
    return [(_app_from_row(r), _from_row(r)) for r in rows]


def _app_from_row(row: sqlite3.Row) -> Application:
    applied = row["applied_at"]
    return Application(
        job_id=row["job_id"],
        status=Status(row["status"]),
        notes=row["notes"],
        applied_at=datetime.fromisoformat(applied) if applied else None,
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def unscored_jobs(conn: sqlite3.Connection, limit: int | None = None) -> list[Job]:
    """Jobs with no score yet, newest first. Scored jobs are never sent to the LLM again."""
    sql = """
        SELECT j.* FROM jobs j LEFT JOIN scores s ON s.job_id = j.id
        WHERE s.job_id IS NULL
        ORDER BY j.posted_at IS NULL, j.posted_at DESC, j.fetched_at DESC
    """
    params: tuple[int, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    return [_from_row(row) for row in conn.execute(sql, params)]


def save_score(conn: sqlite3.Connection, score: Score) -> None:
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO scores (job_id, score, reason, model, cv_hash, scored_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                score.job_id,
                score.score,
                score.reason,
                score.model,
                score.cv_hash,
                score.scored_at.isoformat(),
            ),
        )


def get_scores(conn: sqlite3.Connection) -> dict[str, Score]:
    """job_id -> Score for every scored job."""
    return {
        r["job_id"]: Score(
            r["job_id"],
            r["score"],
            r["reason"],
            r["model"],
            r["cv_hash"],
            datetime.fromisoformat(r["scored_at"]),
        )
        for r in conn.execute("SELECT * FROM scores")
    }
