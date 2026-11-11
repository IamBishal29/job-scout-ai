import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from jobpilot import llm
from jobpilot.env_store import save_secrets, secret_status
from jobpilot.llm import FakeLlmClient

APP = str(Path(__file__).parents[1] / "app.py")
KEY = "AIzaSyTEST-key-1234567890abcd"


@pytest.fixture
def clean_env(monkeypatch):
    """Register vars with monkeypatch so whatever save_secrets writes is undone afterwards."""
    for name in ("GEMINI_API_KEY", "OTHER"):
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
    return AppTest.from_file(APP, default_timeout=30).run(), tmp_path / ".env"


def test_settings_tab_reachable_on_first_run_and_saves_key(app):
    at, env = app
    assert "No jobs yet" in at.info[0].value  # empty DB no longer hides the other tabs
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
