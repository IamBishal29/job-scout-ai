import json
from dataclasses import replace
from pathlib import Path

import pytest

from jobpilot import __main__ as cli
from jobpilot import db, llm
from jobpilot.config import load_config
from jobpilot.llm import FakeLlmClient, LlmError
from jobpilot.matcher import (
    MAX_DESCRIPTION_CHARS,
    ScoreError,
    build_prompt,
    cv_hash,
    parse_score,
    score_jobs,
)
from jobpilot.models import Job

CONFIG = replace(load_config(Path(__file__).parents[1] / "config.toml"), llm_requests_per_minute=30)
CV = "Senior .NET developer, 10 years C#, ASP.NET Core, Azure. Learning LLM engineering."
JOBS = [
    Job(f"t:{n}", "t", f"Backend Engineer {n}", "Acme", "Remote", f"https://t/{n}", "C# role")
    for n in range(3)
]


def reply(score, reason="Good C# match."):
    return json.dumps({"score": score, "reason": reason})


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "jobs.db")
    db.init_db(c)
    db.insert_jobs(c, JOBS)
    yield c
    c.close()


def test_prompt_contains_cv_job_location_and_caps_description():
    job = replace(
        JOBS[0], location="Remote, Poland", description="x" * (MAX_DESCRIPTION_CHARS + 50)
    )
    prompt = build_prompt(job, CV, CONFIG)
    assert CV in prompt
    assert "Based in: Dhaka, Bangladesh" in prompt
    assert "Location: Remote, Poland" in prompt
    assert "x" * (MAX_DESCRIPTION_CHARS + 1) not in prompt


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (reply(82), (82, "Good C# match.")),
        ("```json\n" + reply(55.6) + "\n```", (56, "Good C# match.")),  # fenced, float
    ],
)
def test_parse_score_accepts_valid_json(text, expected):
    assert parse_score(text) == expected


@pytest.mark.parametrize(
    "text",
    ["Sure! 80/100", "[80]", reply(140), reply(-1), reply(True), reply("80"), reply(70, "  ")],
)
def test_parse_score_rejects_garbage(text):
    with pytest.raises(ScoreError):
        parse_score(text)


def test_score_jobs_saves_paces_and_never_rescores(conn):
    fake, sleeps = FakeLlmClient([reply(90), reply(40), reply(70)]), []
    run = score_jobs(conn, fake, CV, CONFIG, limit=10, model="m", sleep=sleeps.append)

    assert (run.scored, run.failed) == (3, 0)
    assert sleeps == [2.0, 2.0]  # 30 rpm -> 2s between calls, none before the first
    scores = db.get_scores(conn)
    assert sorted(s.score for s in scores.values()) == [40, 70, 90]
    assert {s.cv_hash for s in scores.values()} == {cv_hash(CV)}

    again = score_jobs(conn, fake, CV, CONFIG, limit=10, model="m", sleep=sleeps.append)
    assert again.scored == 0 and len(fake.prompts) == 3  # cached: no new LLM calls


def test_failures_are_counted_and_retried_next_run(conn):
    def flaky(prompt):
        if "Engineer 1" in prompt:
            raise LlmError("quota")
        return "not json" if "Engineer 2" in prompt else reply(60)

    run = score_jobs(
        conn, FakeLlmClient(flaky), CV, CONFIG, limit=10, model="m", sleep=lambda s: None
    )
    assert (run.scored, run.failed) == (1, 2)
    assert {j.id for j in db.unscored_jobs(conn)} == {"t:1", "t:2"}


def test_limit_caps_llm_calls(conn):
    fake = FakeLlmClient([reply(50)])
    assert score_jobs(conn, fake, CV, CONFIG, limit=1, model="m", sleep=lambda s: None).scored == 1
    assert len(db.unscored_jobs(conn)) == 2


def test_score_cli(tmp_path, monkeypatch, capsys):
    cv = tmp_path / "cv.md"
    cv.write_text(CV, encoding="utf-8")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n'
        f'[llm]\ncv_path="{cv.as_posix()}"\nrequests_per_minute=6000\n',
        encoding="utf-8",
    )
    c = db.connect(tmp_path / "j.db")
    db.init_db(c)
    db.insert_jobs(c, JOBS[:1])
    c.close()
    monkeypatch.setattr(llm, "make_llm_client", lambda cfg: FakeLlmClient([reply(77)]))

    assert cli.main(["--config", str(cfg_file), "score", "--limit", "5"]) == 0
    assert "Scored 1 job(s), 0 failed" in capsys.readouterr().out
