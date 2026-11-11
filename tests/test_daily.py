from pathlib import Path

import pytest

from jobpilot import __main__ as cli

CONFIG = str(Path(__file__).parents[1] / "config.toml")
SCRIPTS = Path(__file__).parents[1] / "scripts"


@pytest.fixture
def steps(monkeypatch):
    """Replace the real steps with recorders; each returns the code we choose."""
    calls: list[tuple] = []
    codes = {"fetch": 0, "score": 0, "digest": 0}

    def fake(name):
        def step(*args):
            calls.append((name, *args[1:]))
            if codes[name] == "crash":
                raise RuntimeError("boom")
            return codes[name]

        return step

    for name in codes:
        monkeypatch.setattr(cli, name, fake(name))
    return calls, codes


def test_daily_runs_fetch_score_digest_in_order(steps, capsys):
    calls, _ = steps
    assert cli.main(["--config", CONFIG, "daily", "--limit", "5", "--dry-run"]) == 0
    assert calls == [("fetch",), ("score", 5), ("digest", True)]
    assert "all steps OK" in capsys.readouterr().out


@pytest.mark.parametrize("bad", [1, 2, "crash"])
def test_daily_keeps_going_after_a_failed_step(steps, capsys, bad):
    calls, codes = steps
    codes["score"] = bad  # e.g. no CV / no API key yet
    assert cli.main(["--config", CONFIG, "daily"]) == 1
    assert [c[0] for c in calls] == ["fetch", "score", "digest"]  # digest still ran
    assert "failed: score" in capsys.readouterr().out


def test_scripts_call_the_daily_command():
    daily = (SCRIPTS / "daily.ps1").read_text(encoding="utf-8")
    assert '"daily"' in daily and ".venv\Scripts\python.exe" in daily
    assert "exit $LASTEXITCODE" in daily
    register = (SCRIPTS / "register-task.ps1").read_text(encoding="utf-8")
    assert "daily.ps1" in register and "Register-ScheduledTask" in register
