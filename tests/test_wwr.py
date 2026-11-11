from datetime import UTC, datetime
from pathlib import Path

import httpx

from jobpilot.sources import weworkremotely as wwr
from jobpilot.sources.base import JobSource

FEED = (Path(__file__).parent / "fixtures" / "wwr.xml").read_bytes()


def client_for(responses: dict[str, httpx.Response], seen: list[str]) -> httpx.Client:
    """Mock client: first matching feed name decides the response; default is the fixture."""

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        for feed, response in responses.items():
            if feed in request.url.path:
                return response
        return httpx.Response(200, content=FEED)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_module_is_a_job_source():
    assert isinstance(wwr, JobSource)


def test_fetch_parses_items_and_dedupes_across_feeds():
    seen: list[str] = []
    with client_for({}, seen) as client:
        jobs = wwr.fetch(client)

    assert len(seen) == len(wwr.FEEDS)  # one request per feed
    # every feed returned the same 2 valid items: kept once each; broken item skipped
    assert [j.id for j in jobs] == [
        "weworkremotely:vertican-senior-applied-ai-engineer",
        "weworkremotely:untitled-role",
    ]
    job = jobs[0]
    assert job.company == "Vertican"
    assert job.title == "Senior Applied AI Engineer, Document Intelligence"
    assert job.location == "Anywhere in the World"
    assert job.description == "Headquarters: New Jersey\nLLM pipelines & Python"
    assert job.posted_at == datetime(2026, 11, 5, 17, 12, 27, tzinfo=UTC)

    no_company = jobs[1]
    assert (no_company.company, no_company.title) == ("", "Untitled Role Without Company")
    assert no_company.location == "Remote"


def test_failing_or_invalid_feed_is_skipped():
    responses = {
        wwr.FEEDS[0]: httpx.Response(500),
        wwr.FEEDS[1]: httpx.Response(200, content=b"<rss><not-closed>"),
    }
    with client_for(responses, []) as client:
        jobs = wwr.fetch(client)
    assert len(jobs) == 2  # remaining feeds still parsed
