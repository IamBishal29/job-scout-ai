from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from jobpilot import __main__ as cli
from jobpilot.config import Config, SearchConfig
from jobpilot.db import connect, init_db, list_jobs
from jobpilot.models import Job
from jobpilot.pipeline import SourceResult, matches, run_fetch

SEARCH = SearchConfig(
    role_keywords=(".net", "llm"), locations=("remote",), exclude_locations=("us only",)
)


def job(source: str, n: int, title: str, company: str = "Acme", location: str = "Remote") -> Job:
    return Job(f"{source}:{n}", source, title, company, location, f"https://{source}.test/{n}")


def fake_source(name: str, jobs: list[Job] | None = None, error: Exception | None = None):
    def fetch(client):
        if error:
            raise error
        return jobs

    return SimpleNamespace(SOURCE=name, fetch=fetch)


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "jobs.db")
    init_db(c)
    yield c
    c.close()


def config(*sources: str) -> Config:
    return Config(search=SEARCH, sources=sources, db_path=Path("unused.db"))


def test_dedupe_key_ignores_case_punctuation_and_source():
    a = job("remoteok", 1, "Senior .NET Developer", "Acme Inc.")
    b = job("weworkremotely", 9, "senior  .net developer!", "ACME inc")
    assert a.dedupe_key == b.dedupe_key
    assert a.dedupe_key != job("x", 1, "Senior C# Developer", "Acme Inc.").dedupe_key


def test_dedupe_key_falls_back_to_url_without_company():
    a, b = job("x", 1, "LLM Engineer", company=""), job("x", 2, "LLM Engineer", company="")
    assert a.dedupe_key != b.dedupe_key  # different URLs -> different jobs


@pytest.mark.parametrize(
    ("title", "location", "expected"),
    [
        ("Senior .NET Developer", "Remote", True),
        ("LLM Engineer", "Remote - Worldwide", True),
        ("Account Executive", "Remote", False),  # no role keyword
        ("Senior .NET Developer", "Berlin", False),  # not a wanted location
        ("Senior .NET Developer", "Remote (US only)", False),  # excluded region
    ],
)
def test_matches(title, location, expected):
    assert matches(job("x", 1, title, location=location), SEARCH) is expected


def test_run_fetch_filters_dedupes_across_sources_and_is_idempotent(conn):
    sources = {
        "a": fake_source("a", [job("a", 1, ".NET Dev"), job("a", 2, "Sales Rep")]),
        "b": fake_source("b", [job("b", 7, ".NET Dev"), job("b", 8, "LLM Engineer")]),
    }
    first = run_fetch(conn, config("a", "b"), httpx.Client(), sources)
    assert first == [SourceResult("a", 2, 1, 1), SourceResult("b", 2, 2, 1)]  # b:7 = dup of a:1
    assert {j.id for j in list_jobs(conn)} == {"a:1", "b:8"}

    second = run_fetch(conn, config("a", "b"), httpx.Client(), sources)
    assert [r.new for r in second] == [0, 0]


def test_failing_source_does_not_stop_others(conn):
    sources = {
        "down": fake_source("down", error=httpx.ConnectError("no network")),
        "up": fake_source("up", [job("up", 1, "LLM Engineer")]),
    }
    results = run_fetch(conn, config("down", "up"), httpx.Client(), sources)
    assert results[0] == SourceResult("down", error="no network")
    assert results[1].new == 1


def test_format_results_shows_counts_errors_and_total():
    text = cli.format_results([SourceResult("a", 10, 4, 3), SourceResult("b", error="boom")])
    assert "a" in text and "ERROR: boom" in text
    assert text.splitlines()[-1].split() == ["total", "10", "4", "3"]


def test_cli_reports_config_error(tmp_path, capsys):
    assert cli.main(["--config", str(tmp_path / "missing.toml"), "fetch"]) == 2
    assert "Config error" in capsys.readouterr().err
