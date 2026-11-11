import tomllib
from pathlib import Path

import pytest
from conftest import open_page
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parents[1]
APP = str(ROOT / "app.py")


@pytest.fixture
def fresh_app(tmp_path, monkeypatch):
    """A brand-new user: empty database, no .env, no CV."""
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n'
        f'[llm]\ncv_path="{(tmp_path / "cv.md").as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("JOBPILOT_CONFIG", str(cfg))
    monkeypatch.setenv("JOBPILOT_ENV", str(tmp_path / ".env"))
    return AppTest.from_file(APP, default_timeout=30).run()


@pytest.mark.parametrize(
    ("page", "title"),
    [("home", "Good"), ("jobs", "Jobs"), ("tracker", "Tracker"), ("settings", "Settings")],
)
def test_every_page_opens_for_a_new_user(fresh_app, page, title):
    at = open_page(fresh_app, page)
    assert not at.exception
    assert at.title[0].value.startswith(title)


def test_home_is_the_default_page(fresh_app):
    assert fresh_app.title[0].value.startswith("Good")  # Home greets you


def test_theme_uses_light_base_and_indigo_accent():
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text("utf-8"))["theme"]
    assert theme["base"] == "light" and theme["primaryColor"] == "#4F46E5"
    assert (
        tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text("utf-8"))["server"]["address"]
        == "localhost"
    )
