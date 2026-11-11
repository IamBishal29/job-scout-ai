from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import open_page
from streamlit.testing.v1 import AppTest

from jobpilot import db
from jobpilot.models import Application, Job, Status
from jobpilot.views import BOARD, ago, board_columns

APP = str(Path(__file__).parents[1] / "app.py")
NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
JOBS = {n: Job(f"j:{n}", "t", f"Role {n}", f"Co {n}", "Remote", f"https://j/{n}") for n in range(6)}


def app(n: int, status: Status, days_ago: int, notes: str = "") -> Application:
    when = NOW - timedelta(days=days_ago)
    applied = when if status not in (Status.NEW, Status.SAVED) else None
    return Application(f"j:{n}", status, notes, applied_at=applied, updated_at=when)


TRACKED = [
    (app(0, Status.SAVED, 2), JOBS[0]),
    (app(1, Status.APPLIED, 5, "Recruiter: Ms Rahman\nsecond line"), JOBS[1]),
    (app(2, Status.APPLIED, 1), JOBS[2]),
    (app(3, Status.INTERVIEW, 0), JOBS[3]),
    (app(4, Status.REJECTED, 9), JOBS[4]),
    (app(5, Status.NEW, 0), JOBS[5]),  # not on the board
]


@pytest.mark.parametrize(("days", "text"), [(0, "today"), (1, "yesterday"), (6, "6 days ago")])
def test_ago(days, text):
    assert ago(NOW - timedelta(days=days), NOW) == text


def test_board_columns_group_and_sort_newest_first():
    columns = board_columns(TRACKED)
    assert list(columns) == [*BOARD, Status.REJECTED]
    assert [j.id for _, j in columns[Status.APPLIED]] == ["j:2", "j:1"]  # 1 day before 5 days
    assert [j.id for _, j in columns[Status.OFFER]] == []
    assert all(j.id != "j:5" for items in columns.values() for _, j in items)  # NEW excluded


@pytest.fixture
def setup(tmp_path, monkeypatch):
    for name in ("GEMINI_API_KEY", "SMTP_USER", "SMTP_APP_PASSWORD", "DIGEST_TO"):
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)
    conn = db.connect(tmp_path / "j.db")
    db.init_db(conn)
    db.insert_jobs(conn, JOBS.values())
    for application, _ in TRACKED:
        db.save_application(conn, application)
    conn.close()
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("JOBPILOT_CONFIG", str(cfg))
    monkeypatch.setenv("JOBPILOT_ENV", str(tmp_path / ".env"))
    return AppTest.from_file(APP, default_timeout=30).run()


def test_tracker_board_shows_columns_cards_and_rejected(setup):
    at = open_page(setup, "tracker")
    assert not at.exception
    text = [m.value for m in at.markdown]
    for header in ("**Saved** · 1", "**Applied** · 2", "**Interview** · 1", "**Offer** · 0"):
        assert header in text
    assert "Nothing here yet" in [c.value for c in at.caption]  # empty Offer column
    assert any("Recruiter: Ms Rahman" in c.value for c in at.caption)  # first line of notes
    assert not any("second line" in c.value for c in at.caption)
    assert at.expander[0].label == "Rejected (1)"
    assert any(c.value.startswith("4 active application") for c in at.caption)


def test_settings_sections_show_status_icons(setup):
    at = open_page(setup, "settings")
    headings = [h.value for h in at.subheader]
    assert headings == [
        ":orange[:material/error:] Gemini API key",
        ":orange[:material/error:] Your CV",
        ":orange[:material/error:] Gmail for the daily digest",
    ]
