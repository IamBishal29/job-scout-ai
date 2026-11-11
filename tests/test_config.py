import os
from pathlib import Path

import pytest

from jobpilot.config import ConfigError, get_secret, load_config

VALID = """
[search]
role_keywords = [".NET", "LLM"]
locations = ["Remote"]

[sources]
enabled = ["remotive"]

[database]
path = "tmp/test.db"
"""


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "config.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_valid_config_lowercases_keywords(tmp_path):
    cfg = load_config(write(tmp_path, VALID))
    assert cfg.search.role_keywords == (".net", "llm")
    assert cfg.search.locations == ("remote",)
    assert cfg.sources == ("remotive",)
    assert cfg.db_path == Path("tmp/test.db")


def test_repo_config_toml_is_valid():
    cfg = load_config(Path(__file__).parents[1] / "config.toml")
    assert ".net" in cfg.search.role_keywords


def test_missing_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.toml")


def test_invalid_toml_raises(tmp_path):
    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_config(write(tmp_path, "[search\nbroken"))


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('role_keywords = [".NET", "LLM"]', "role_keywords = []", "role_keywords"),
        ('locations = ["Remote"]', "locations = 5", "locations"),
        ('enabled = ["remotive"]', 'enabled = ["linkedin"]', "Unknown sources"),
    ],
)
def test_invalid_values_raise(tmp_path, old, new, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, VALID.replace(old, new)))


def test_get_secret_reads_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBPILOT_TEST_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text("JOBPILOT_TEST_KEY=from-file\n", encoding="utf-8")
    try:
        assert get_secret("JOBPILOT_TEST_KEY", env_file=env) == "from-file"
    finally:
        os.environ.pop("JOBPILOT_TEST_KEY", None)  # load_dotenv wrote it into os.environ


def test_real_env_var_wins_over_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBPILOT_TEST_KEY", "from-env")
    env = tmp_path / ".env"
    env.write_text("JOBPILOT_TEST_KEY=from-file\n", encoding="utf-8")
    assert get_secret("JOBPILOT_TEST_KEY", env_file=env) == "from-env"


def test_missing_secret_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBPILOT_TEST_KEY", raising=False)
    with pytest.raises(ConfigError, match="Missing secret JOBPILOT_TEST_KEY"):
        get_secret("JOBPILOT_TEST_KEY", env_file=tmp_path / "absent.env")
