import smtplib
import subprocess
import sys

import pytest

from jobpilot import __main__ as cli
from jobpilot import db, mailer
from jobpilot.digest import Digest
from jobpilot.mailer import MailError, build_message, send_message
from jobpilot.models import Job, Score

DIGEST = Digest("JobPilot: 1 new match", "<p>Hi</p>", "Hi", ("a:1",))
SECRET = "abcd efgh ijkl mnop"


class FakeSMTP:
    """Records the SMTP conversation instead of talking to Gmail."""

    calls: list = []
    fail_with: Exception | None = None

    def __init__(self, host, port, timeout):
        FakeSMTP.calls = [("connect", host, port)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, user, password):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("login", user))

    def send_message(self, msg):
        self.calls.append(("send", msg["To"], msg["Subject"]))


@pytest.fixture(autouse=True)
def reset_fake():
    FakeSMTP.calls, FakeSMTP.fail_with = [], None


def test_message_has_text_and_html_parts():
    msg = build_message(DIGEST, "me@gmail.com", "me@example.com")
    assert (msg["From"], msg["To"], msg["Subject"]) == (
        "me@gmail.com",
        "me@example.com",
        "JobPilot: 1 new match",
    )
    assert [p.get_content_type() for p in msg.iter_parts()] == ["text/plain", "text/html"]


def test_send_uses_tls_before_login():
    send_message(
        build_message(DIGEST, "me@gmail.com", "you@x.com"), "me@gmail.com", SECRET, FakeSMTP
    )
    assert FakeSMTP.calls == [
        ("connect", "smtp.gmail.com", 587),
        ("starttls",),
        ("login", "me@gmail.com"),
        ("send", "you@x.com", "JobPilot: 1 new match"),
    ]


def test_bad_login_gives_helpful_error_without_password():
    FakeSMTP.fail_with = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    with pytest.raises(MailError, match="app password") as err:
        send_message(build_message(DIGEST, "me", "you"), "me", SECRET, FakeSMTP)
    assert SECRET not in str(err.value)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "j.db")
    db.init_db(conn)
    db.insert_jobs(conn, [Job("a:1", "t", ".NET Dev", "Acme", "Remote", "https://a/1")])
    db.save_score(conn, Score("a:1", 90, "Great fit.", "m", "cv"))
    conn.close()
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n',
        encoding="utf-8",
    )
    for name, value in {
        "SMTP_USER": "me@gmail.com",
        "SMTP_APP_PASSWORD": SECRET,
        "DIGEST_TO": "me@example.com",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    return cfg, tmp_path / "j.db"


def digested(db_path) -> list:
    conn = db.connect(db_path)
    rows = [r[0] for r in conn.execute("SELECT job_id FROM digested_jobs")]
    conn.close()
    return rows


def test_dry_run_prints_and_changes_nothing(setup, capsys):
    cfg, db_path = setup
    assert cli.main(["--config", str(cfg), "digest", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and ".NET Dev" in out
    assert FakeSMTP.calls == [] and digested(db_path) == []


def test_send_marks_jobs_and_second_run_has_nothing(setup, capsys):
    cfg, db_path = setup
    assert cli.main(["--config", str(cfg), "digest"]) == 0
    assert ("send", "me@example.com", FakeSMTP.calls[-1][2]) == FakeSMTP.calls[-1]
    assert digested(db_path) == ["a:1"]
    assert cli.main(["--config", str(cfg), "digest"]) == 0
    assert "Nothing new" in capsys.readouterr().out


def test_failed_send_marks_nothing(setup, capsys):
    cfg, db_path = setup
    FakeSMTP.fail_with = smtplib.SMTPAuthenticationError(535, b"no")
    assert cli.main(["--config", str(cfg), "digest"]) == 1
    assert "Digest not sent" in capsys.readouterr().err
    assert digested(db_path) == []  # next run retries the same jobs


def test_cli_runs_as_a_real_process(setup):
    cfg, _ = setup
    result = subprocess.run(
        [sys.executable, "-m", "jobpilot", "--config", str(cfg), "digest", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "DRY RUN" in result.stdout


def test_build_message_handles_unicode_subject():
    msg = build_message(Digest("JobPilot – 2 matches", "<p>é</p>", "é", ()), "a", "b")
    assert msg["Subject"] == "JobPilot – 2 matches"
