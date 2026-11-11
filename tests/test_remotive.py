from datetime import UTC, datetime

import httpx
import pytest
from conftest import load_fixture, mock_client

from jobpilot.sources import remotive
from jobpilot.sources.http import USER_AGENT, html_to_text, make_client

FIXTURE = load_fixture("remotive.json")


def test_fetch_maps_jobs_and_skips_malformed():
    seen: list[httpx.Request] = []
    with mock_client(200, FIXTURE, seen) as client:
        jobs = remotive.fetch(client)

    assert len(seen) == 1  # one request per run (Remotive asks for few calls)
    assert str(seen[0].url) == remotive.API_URL
    assert seen[0].headers["User-Agent"] == USER_AGENT

    assert [j.id for j in jobs] == ["remotive:101", "remotive:102"]
    first = jobs[0]
    assert first.title == "Senior .NET Developer"
    assert first.company == "Acme"
    assert first.location == "Worldwide"
    assert first.url.startswith("https://remotive.com/")
    assert first.description == "Build APIs with ASP.NET Core & C#.\nRemote"
    assert first.posted_at == datetime(2026, 11, 8, 21, 47, 58, tzinfo=UTC)
    assert jobs[1].location == "Remote"  # empty location falls back to Remote


def test_fetch_raises_on_http_error():
    with mock_client(500, {}, []) as client, pytest.raises(httpx.HTTPStatusError):
        remotive.fetch(client)


def test_make_client_is_polite():
    with make_client() as client:
        assert client.headers["User-Agent"] == USER_AGENT
        assert client.timeout.read == 20.0


def test_html_to_text_handles_empty_and_entities():
    assert html_to_text("") == ""
    assert html_to_text("<p>a &lt; b</p><p>c</p>") == "a < b\nc"
    # escaped HTML (Arbeitnow, some Remote OK), even mixed with real tags
    assert html_to_text("&lt;p&gt;escaped &amp;amp; ok&lt;/p&gt;<br>") == "escaped & ok"
