from datetime import UTC, datetime
from pathlib import Path

import httpx

from jobpilot.config import Config, SearchConfig, load_config
from jobpilot.pipeline import build_sources
from jobpilot.sources.base import JobSource
from jobpilot.sources.greenhouse import GreenhouseSource
from jobpilot.sources.lever import LeverSource

GREENHOUSE = {
    "jobs": [
        {
            "id": 8638232002,
            "title": "Senior Backend Engineer (.NET)",
            "company_name": "GitLab",
            "location": {"name": "Remote, EMEA"},
            "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/8638232002",
            "first_published": "2026-07-22T13:38:40-04:00",
            "content": "&lt;p&gt;C# &amp;amp; Go&lt;/p&gt;",
        },
        {"id": 2, "company_name": "GitLab"},  # malformed: no title/url
    ]
}
LEVER = [
    {
        "id": "a9653cf8",
        "text": "AI Engineer",
        "categories": {"location": "Worldwide"},
        "workplaceType": "remote",
        "hostedUrl": "https://jobs.lever.co/toptal/a9653cf8",
        "createdAt": 1789027672366,
        "descriptionPlain": "Build LLM apps.\n",
    }
]


def client(routes: dict[str, httpx.Response]) -> httpx.Client:
    """Mock client: the first route whose key is in the URL answers; anything else is 404."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        return next((r for key, r in routes.items() if key in url), httpx.Response(404))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_board_sources_satisfy_protocol():
    assert isinstance(GreenhouseSource(()), JobSource)
    assert isinstance(LeverSource(()), JobSource)


def test_greenhouse_maps_jobs_and_skips_missing_board():
    source = GreenhouseSource(("gitlab", "does-not-exist"))
    with client({"/boards/gitlab/": httpx.Response(200, json=GREENHOUSE)}) as c:
        jobs = source.fetch(c)

    assert [j.id for j in jobs] == ["greenhouse:gitlab:8638232002"]
    job = jobs[0]
    assert (job.company, job.location) == ("GitLab", "Remote, EMEA")
    assert job.description == "C# & Go"
    assert job.posted_at == datetime(2026, 7, 22, 17, 38, 40, tzinfo=UTC)


def test_lever_maps_remote_and_ms_timestamp_and_skips_error_payload():
    source = LeverSource(("toptal", "gone"))
    routes = {
        "/postings/toptal": httpx.Response(200, json=LEVER),
        "/postings/gone": httpx.Response(200, json={"ok": False, "error": "Document not found"}),
    }
    with client(routes) as c:
        jobs = source.fetch(c)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == "lever:toptal:a9653cf8"
    assert (job.company, job.location) == ("Toptal", "Remote (Worldwide)")
    assert job.description == "Build LLM apps."
    assert job.posted_at == datetime.fromtimestamp(1789027672.366, UTC)


def test_build_sources_uses_boards_from_config():
    cfg = Config(
        search=SearchConfig(role_keywords=("x",), locations=("remote",)),
        sources=("greenhouse",),
        db_path=Path("unused.db"),
        boards={"greenhouse": ("gitlab",), "lever": ()},
    )
    sources = build_sources(cfg)
    assert {"remotive", "remoteok", "arbeitnow", "weworkremotely", "greenhouse", "lever"} <= set(
        sources
    )
    assert sources["greenhouse"].boards == ("gitlab",)


def test_repo_config_lists_boards():
    cfg = load_config(Path(__file__).parents[1] / "config.toml")
    assert "gitlab" in cfg.boards["greenhouse"]
    assert "toptal" in cfg.boards["lever"]
