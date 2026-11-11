import sqlite3
from datetime import UTC, datetime

import pytest

from jobpilot import db
from jobpilot.models import ALLOWED, Application, Job, Status
from jobpilot.tracker import InvalidTransition, change_status, next_statuses, update_notes

T1 = datetime(2026, 11, 1, tzinfo=UTC)
T2 = datetime(2026, 11, 5, tzinfo=UTC)
JOB = Job("a:1", "remoteok", "Senior .NET Developer", "Acme", "Remote", "https://a/1")


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "jobs.db")
    db.init_db(c)
    db.insert_jobs(c, [JOB])
    yield c
    c.close()


# --- state machine -------------------------------------------------------------------


def test_every_status_has_rules_and_cannot_jump_to_offer_from_new():
    assert set(ALLOWED) == set(Status)
    with pytest.raises(InvalidTransition, match="new to offer"):
        change_status(Application("a:1"), Status.OFFER)


def test_happy_path_sets_applied_at_once():
    app = change_status(Application("a:1"), Status.SAVED, T1)
    app = change_status(app, Status.APPLIED, T1)
    app = change_status(app, Status.INTERVIEW, T2)
    assert (app.status, app.applied_at, app.updated_at) == (Status.INTERVIEW, T1, T2)


def test_step_back_and_same_status_are_allowed():
    applied = change_status(Application("a:1"), Status.APPLIED, T1)
    assert change_status(applied, Status.SAVED, T2).status == Status.SAVED
    assert change_status(applied, Status.APPLIED, T2) is applied  # no-op


def test_next_statuses_lists_current_first():
    assert next_statuses(Status.APPLIED) == [
        Status.APPLIED,
        Status.SAVED,
        Status.INTERVIEW,
        Status.REJECTED,
    ]


def test_update_notes_trims_and_skips_unchanged():
    app = Application("a:1", notes="call Tue", updated_at=T1)
    assert update_notes(app, " call Tue ") is app
    assert update_notes(app, "call Wed", T2).updated_at == T2


# --- repository + migrations ---------------------------------------------------------


def test_untracked_job_is_new_and_save_round_trips(conn):
    assert db.get_application(conn, "a:1").status == Status.NEW
    app = Application("a:1", Status.APPLIED, "sent CV", applied_at=T1, updated_at=T2)
    db.save_application(conn, app)
    db.save_application(conn, app)  # upsert: still one row
    assert db.get_application(conn, "a:1") == app
    assert db.application_statuses(conn) == {"a:1": Status.APPLIED}
    assert db.list_applications(conn) == [(app, JOB)]


def test_new_status_rows_are_not_listed_in_tracker(conn):
    db.save_application(conn, Application("a:1", Status.NEW, "maybe later"))
    assert db.list_applications(conn) == []


def test_database_rejects_unknown_status(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO applications (job_id, status, updated_at) VALUES ('a:1', 'ghosted', 'x')"
        )


def test_migrations_upgrade_an_old_database_without_losing_jobs(tmp_path):
    c = db.connect(tmp_path / "old.db")
    c.executescript(db.MIGRATIONS[0])  # a DB created before migrations: version 0
    db.insert_jobs(c, [JOB])
    assert db.schema_version(c) == 0

    db.init_db(c)
    db.init_db(c)  # second run is a no-op
    assert db.schema_version(c) == len(db.MIGRATIONS)
    assert [j.id for j in db.list_jobs(c)] == ["a:1"]
    c.close()
