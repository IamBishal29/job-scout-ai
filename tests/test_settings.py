import os
from pathlib import Path

import pytest
from conftest import open_page
from streamlit.testing.v1 import AppTest

from jobpilot import llm, mailer
from jobpilot.env_store import save_secrets, secret_status
from jobpilot.llm import FakeLlmClient

APP = str(Path(__file__).parents[1] / "app.py")
KEY = "AIzaSyTEST-key-1234567890abcd"


@pytest.fixture
def clean_env(monkeypatch):
    """Register vars with monkeypatch so whatever save_secrets writes is undone afterwards."""
    for name in ("GEMINI_API_KEY", "OTHER", "SMTP_USER", "SMTP_APP_PASSWORD", "DIGEST_TO"):
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)
    return monkeypatch


def test_updates_existing_key_and_keeps_other_lines(tmp_path, clean_env):
    env = tmp_path / ".env"
    env.write_text("# my settings\nOTHER=1\nGEMINI_API_KEY=old\n", encoding="utf-8")
    save_secrets({"GEMINI_API_KEY": KEY}, env)
    assert env.read_text(encoding="utf-8") == f"# my settings\nOTHER=1\nGEMINI_API_KEY={KEY}\n"
    assert os.environ["GEMINI_API_KEY"] == KEY  # usable immediately, no restart


def test_appends_new_key_and_quotes_values_with_spaces(tmp_path, clean_env):
    env = tmp_path / ".env"
    save_secrets({"OTHER": 'abcd efgh "x"'}, env)
    assert env.read_text(encoding="utf-8") == 'OTHER="abcd efgh \\"x\\""\n'
    from dotenv import dotenv_values

    assert dotenv_values(env)["OTHER"] == 'abcd efgh "x"'  # round-trips through python-dotenv


@pytest.mark.parametrize(
    ("values", "message"),
    [({"GEMINI_API_KEY": "a\nEVIL=1"}, "single line"), ({"bad-name": "x"}, "invalid")],
)
def test_rejects_injection_and_bad_names(tmp_path, clean_env, values, message):
    with pytest.raises(ValueError, match=message):
        save_secrets(values, tmp_path / ".env")
    assert not (tmp_path / ".env").exists()


def test_status_never_reveals_the_secret(clean_env):
    assert secret_status("GEMINI_API_KEY") is None
    clean_env.setenv("GEMINI_API_KEY", KEY)
    assert secret_status("GEMINI_API_KEY") == "set (ends with abcd)"
    assert KEY[:-4] not in secret_status("GEMINI_API_KEY")


@pytest.fixture
def app(tmp_path, clean_env):
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n',
        encoding="utf-8",
    )
    clean_env.setenv("JOBPILOT_CONFIG", str(cfg))
    clean_env.setenv("JOBPILOT_ENV", str(tmp_path / ".env"))
    clean_env.setattr(llm, "make_llm_client", lambda c: FakeLlmClient(["JobPilot OK"]))
    return open_page(
        AppTest.from_file(APP, default_timeout=30).run(), "settings"
    ), tmp_path / ".env"


def test_settings_tab_reachable_on_first_run_and_saves_key(app):
    at, env = app
    assert "Status: **not set**" in [m.value for m in at.markdown]

    [box] = [t for t in at.text_input if t.label == "New API key"]
    box.input(KEY)
    [save] = [b for b in at.button if b.label == "Save key"]
    save.click().run()

    assert f"GEMINI_API_KEY={KEY}" in env.read_text(encoding="utf-8")
    assert "Saved." in at.success[0].value
    shown = " ".join(m.value for m in at.markdown)
    assert "ends with abcd" in shown and KEY not in shown  # never displayed back

    [test] = [b for b in at.button if b.label == "Test key"]
    test.click().run()
    assert "It works." in at.success[-1].value


PASSWORD = "abcd efgh ijkl mnop"


@pytest.mark.parametrize(
    ("user", "password", "to", "expected"),
    [
        ("me@gmail.com", PASSWORD, "me@gmail.com", []),
        ("me@gmail.com", None, "you@example.com", []),  # None = keep the saved password
        ("me", PASSWORD, "me@gmail.com", ["Gmail address"]),
        ("me@gmail.com", "my-normal-pass", "me@gmail.com", ["16 letters"]),
        ("me@gmail.com", PASSWORD, "nope", ["Send digest to"]),
    ],
)
def test_validate_gmail_settings(user, password, to, expected):
    problems = mailer.validate_gmail_settings(user, password, to)
    assert len(problems) == len(expected)
    for fragment, problem in zip(expected, problems, strict=True):
        assert fragment in problem


class RecordingSMTP:
    sent: list = []

    def __init__(self, host, port, timeout):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        RecordingSMTP.sent.append(("login", user, password))

    def send_message(self, msg):
        RecordingSMTP.sent.append(("send", msg["To"], msg["Subject"]))


def test_send_test_email_uses_the_digest_code_path():
    RecordingSMTP.sent = []
    mailer.send_test_email("me@gmail.com", "abcdefghijklmnop", "you@x.com", RecordingSMTP)
    assert RecordingSMTP.sent == [
        ("login", "me@gmail.com", "abcdefghijklmnop"),
        ("send", "you@x.com", "JobPilot test email"),
    ]


def test_saved_values_show_after_restart(tmp_path, clean_env):
    env = tmp_path / ".env"
    env.write_text(f"GEMINI_API_KEY={KEY}\nSMTP_USER=me@gmail.com\n", encoding="utf-8")
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n',
        encoding="utf-8",
    )
    clean_env.setenv("JOBPILOT_CONFIG", str(cfg))
    clean_env.setenv("JOBPILOT_ENV", str(env))
    at = open_page(AppTest.from_file(APP, default_timeout=30).run(), "settings")
    assert "Status: **set (ends with abcd)**" in [m.value for m in at.markdown]
    assert [t.value for t in at.text_input if t.label == "Your Gmail address"] == ["me@gmail.com"]


def test_gmail_form_validates_saves_and_sends(app, clean_env):
    at, env = app
    RecordingSMTP.sent = []
    clean_env.setattr(mailer.smtplib, "SMTP", RecordingSMTP)

    def fill(user, password):
        [box] = [t for t in at.text_input if t.label == "Your Gmail address"]
        box.input(user)
        [pw] = [t for t in at.text_input if t.label == "App password"]
        pw.input(password)
        [save] = [b for b in at.button if b.label == "Save Gmail settings"]
        save.click().run()

    fill("me@gmail.com", "my-normal-pass")
    assert any("16 letters" in e.value for e in at.error)
    assert not env.exists()  # nothing saved on invalid input

    fill("me@gmail.com", PASSWORD)
    saved = env.read_text(encoding="utf-8")
    assert "SMTP_USER=me@gmail.com" in saved and "DIGEST_TO=me@gmail.com" in saved
    assert "SMTP_APP_PASSWORD=abcdefghijklmnop" in saved  # spaces removed
    shown = " ".join(m.value for m in at.markdown)
    assert "App password: **set (ends with mnop)**" in shown and "abcdefgh" not in shown

    [send] = [b for b in at.button if b.label == "Send test email"]
    send.click().run()
    assert ("send", "me@gmail.com", "JobPilot test email") in RecordingSMTP.sent
    assert "Sent to me@gmail.com" in at.success[-1].value
