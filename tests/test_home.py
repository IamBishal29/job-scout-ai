from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from jobpilot import db
from jobpilot.models import Application, Job, Score, Status
from jobpilot.views import greeting, summarize, top_matches

APP = str(Path(__file__).parents[1] / "app.py")
JOBS = [
    Job(f"j:{n}", "t", f"Engineer {n}", f"Co {n}", "Remote", f"https://j/{n}") for n in range(8)
]
SCORES = {
    f"j:{n}": Score(f"j:{n}", s, f"reason {n}", "m", "cv")
    for n, s in enumerate(
        [95, 80, 76, 74, 60, 30, 88]  # j:7 is not scored
    )
}
STATUSES = {
    "j:0": Status.REJECTED,
    "j:1": Status.APPLIED,
    "j:2": Status.INTERVIEW,
    "j:3": Status.SAVED,
}


@pytest.mark.parametrize(("hour", "text"), [(6, "morning"), (13, "afternoon"), (21, "evening")])
def test_greeting(hour, text):
    assert greeting(hour) == f"Good {text}"


def test_summarize_counts():
    stats = summarize(len(JOBS), SCORES, STATUSES)
    assert (stats.jobs, stats.scored, stats.strong) == (8, 7, 4)  # 95, 80, 76, 88
    assert (stats.applications, stats.interviews) == (2, 1)  # applied + interview


def test_top_matches_skip_rejected_and_unscored():
    best = top_matches(JOBS, SCORES, STATUSES, n=3)
    assert [(j.id, s.score) for j, s in best] == [("j:6", 88), ("j:1", 80), ("j:2", 76)]


@pytest.fixture
def home(tmp_path, monkeypatch):
    for name in ("GEMINI_API_KEY", "SMTP_USER", "SMTP_APP_PASSWORD", "DIGEST_TO"):
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n'
        f'[llm]\ncv_path="{(tmp_path / "cv.md").as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("JOBPILOT_CONFIG", str(cfg))
    monkeypatch.setenv("JOBPILOT_ENV", str(tmp_path / ".env"))
    return tmp_path


def test_new_user_sees_checklist_and_first_step(home):
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Finish setting up" in text and "radio_button_unchecked" in text
    assert [m.value for m in at.metric] == ["0", "0", "0", "0"]
    assert any("Click **Fetch jobs** above" in i.value for i in at.info)


def test_user_with_data_sees_numbers_and_top_matches(home):
    conn = db.connect(home / "j.db")
    db.init_db(conn)
    db.insert_jobs(conn, JOBS)
    for score in SCORES.values():
        db.save_score(conn, score)
    for job_id, status in STATUSES.items():
        db.save_application(conn, Application(job_id, status))
    conn.close()

    at = AppTest.from_file(APP, default_timeout=30).run()
    assert [m.value for m in at.metric] == ["8", "7", "4", "2"]
    titles = [m.value for m in at.markdown if m.value.startswith("**Engineer")]
    assert titles[0].startswith("**Engineer 6**") and len(titles) == 5  # best first, top 5
    assert not any("Engineer 0" in t for t in titles)  # rejected job hidden
    assert "reason 6" in [c.value for c in at.caption]
