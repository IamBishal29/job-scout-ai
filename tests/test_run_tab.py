from pathlib import Path

import pytest
from conftest import open_page
from streamlit.testing.v1 import AppTest

from jobpilot import actions, db, llm, mailer
from jobpilot.config import load_config
from jobpilot.llm import FakeLlmClient
from jobpilot.models import Job, Score
from jobpilot.pipeline import SourceResult

APP = str(Path(__file__).parents[1] / "app.py")
JOB = Job("a:1", "t", "Senior .NET Developer", "Acme", "Remote", "https://a/1", "C# role")
CV = " ".join(["Senior .NET developer with C# and Azure experience."] * 5)


class FakeSMTP:
    sent: list = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg["Subject"])


@pytest.fixture
def setup(tmp_path, monkeypatch):
    """Temp DB with one job, temp config/.env; secrets registered so they're restored."""
    for name in ("GEMINI_API_KEY", "SMTP_USER", "SMTP_APP_PASSWORD", "DIGEST_TO"):
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)
    conn = db.connect(tmp_path / "j.db")
    db.init_db(conn)
    db.insert_jobs(conn, [JOB])
    conn.close()
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n'
        f'[llm]\ncv_path="{(tmp_path / "cv.md").as_posix()}"\nrequests_per_minute=6000\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("JOBPILOT_CONFIG", str(cfg))
    monkeypatch.setenv("JOBPILOT_ENV", str(tmp_path / ".env"))
    monkeypatch.setattr(
        llm, "make_llm_client", lambda c: FakeLlmClient(['{"score": 91, "reason": "Great."}'])
    )
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    FakeSMTP.sent = []
    return load_config(cfg), tmp_path


def click(at: AppTest, label: str) -> AppTest:
    [button] = [b for b in at.button if b.label == label]
    return button.click().run()


def test_actions_need_cv_and_key(setup):
    config, _ = setup
    assert actions.readiness(config) == actions.Readiness(gemini=False, cv=False, gmail=False)
    with pytest.raises(actions.ActionError, match="CV not found"):
        actions.score_jobs(config, 5)


def test_score_reports_progress_and_digest_send_marks_jobs(setup, monkeypatch):
    config, tmp = setup
    (tmp / "cv.md").write_text(CV, encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    calls = []
    run = actions.score_jobs(config, 5, on_progress=lambda d, t: calls.append((d, t)))
    assert (run.scored, calls) == (1, [(0, 1)])

    assert actions.preview_digest(config).job_ids == ("a:1",)
    for name, value in {
        "SMTP_USER": "me@gmail.com",
        "SMTP_APP_PASSWORD": "p",
        "DIGEST_TO": "me@gmail.com",
    }.items():
        monkeypatch.setenv(name, value)
    assert actions.send_digest(config).job_ids == ("a:1",)
    assert actions.preview_digest(config) is None  # marked: never emailed twice


def test_run_tab_disables_buttons_until_ready(setup):
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert [b.disabled for b in at.button if b.label == "Score jobs"] == [True]
    assert [b.disabled for b in at.button if b.label == "Send digest"] == [True]
    hints = " ".join(c.value for c in at.caption)
    assert "Add your Gemini key and CV in Settings" in hints and "Gmail settings" in hints


def test_run_tab_fetch_score_preview_send(setup, monkeypatch):
    _, tmp = setup
    (tmp / "cv.md").write_text(CV, encoding="utf-8")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(
        actions, "run_fetch", lambda conn, cfg, client: [SourceResult("remotive", 5, 2, 2)]
    )
    at = AppTest.from_file(APP, default_timeout=30).run()

    at = click(at, "Fetch jobs")
    assert any("2 new job(s) from 1 source(s)." in s.value for s in at.success)

    at = click(at, "Score jobs")
    assert any("Scored 1 job(s)." in s.value for s in at.success)
    jobs_page = " ".join(m.value for m in open_page(at, "jobs").markdown)
    assert "91 · strong" in jobs_page  # the Jobs page card shows the new score badge
    at = open_page(at, "home")

    at = click(at, "Preview digest")
    assert any("1 new match" in e.label for e in at.expander)  # preview shown in the page
    assert FakeSMTP.sent == []  # preview sends nothing

    for name, value in {
        "SMTP_USER": "me@gmail.com",
        "SMTP_APP_PASSWORD": "abcdefghijklmnop",
        "DIGEST_TO": "me@gmail.com",
    }.items():
        monkeypatch.setenv(name, value)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at = click(at, "Send digest")
    assert any("Sent: JobPilot" in s.value for s in at.success) and len(FakeSMTP.sent) == 1


def test_scores_below_min_are_not_in_the_digest(setup):
    config, tmp = setup
    conn = db.connect(tmp / "j.db")
    db.save_score(conn, Score("a:1", 50, "ok", "m", "cv"))
    conn.close()
    assert actions.preview_digest(config) is None  # 50 is below the default min_score 60
