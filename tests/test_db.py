from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from jobpilot.db import connect, init_db, insert_jobs, list_jobs
from jobpilot.models import Job


def make_job(n: int, posted_day: int | None = 1) -> Job:
    return Job(
        id=f"test:{n}",
        source="test",
        title=f"Senior .NET Developer {n}",
        company="Acme",
        location="Remote",
        url=f"https://example.com/jobs/{n}",
        description="C#, ASP.NET Core",
        posted_at=datetime(2026, 11, posted_day, tzinfo=UTC) if posted_day else None,
        fetched_at=datetime(2026, 11, 11, 9, 0, tzinfo=UTC),
    )


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "sub" / "test.db")
    init_db(c)
    yield c
    c.close()


def test_job_is_immutable():
    with pytest.raises(FrozenInstanceError):
        make_job(1).title = "changed"


def test_init_db_is_idempotent(conn):
    init_db(conn)  # second call must not fail
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "jobs" in tables


def test_insert_and_list_round_trip(conn):
    job = make_job(1)
    assert insert_jobs(conn, [job]) == 1
    assert list_jobs(conn) == [job]


def test_insert_skips_existing_ids(conn):
    insert_jobs(conn, [make_job(1), make_job(2)])
    assert insert_jobs(conn, [make_job(2), make_job(3)]) == 1
    assert len(list_jobs(conn)) == 3


def test_list_orders_newest_first_and_respects_limit(conn):
    insert_jobs(conn, [make_job(1, posted_day=1), make_job(2, posted_day=None), make_job(3, 5)])
    assert [j.id for j in list_jobs(conn)] == ["test:3", "test:1", "test:2"]
    assert [j.id for j in list_jobs(conn, limit=1)] == ["test:3"]


def test_data_persists_across_connections(tmp_path):
    path = tmp_path / "jobs.db"
    with connect(path) as c:
        init_db(c)
        insert_jobs(c, [make_job(1)])
    c.close()
    c2 = connect(path)
    assert [j.id for j in list_jobs(c2)] == ["test:1"]
    c2.close()
