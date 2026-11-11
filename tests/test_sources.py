from datetime import UTC, datetime

import httpx
import pytest
from conftest import load_fixture, mock_client

from jobpilot.sources import arbeitnow, remoteok, remotive
from jobpilot.sources.base import JobSource
from jobpilot.sources.http import fix_mojibake


@pytest.mark.parametrize("module", [remotive, remoteok, arbeitnow])
def test_every_source_module_satisfies_protocol(module):
    assert isinstance(module, JobSource)


def test_remoteok_skips_legal_notice_and_malformed_items():
    with mock_client(200, load_fixture("remoteok.json")) as client:
        jobs = remoteok.fetch(client)

    assert [j.id for j in jobs] == ["remoteok:201"]
    job = jobs[0]
    assert job.title == "Senior Software Engineer — Platform"  # mojibake repaired
    assert job.location == "Remote"
    assert job.description == "Go & Kubernetes"
    assert job.posted_at == datetime(2026, 11, 9, 22, 0, 2, tzinfo=UTC)


def test_arbeitnow_maps_remote_epoch_and_escaped_html():
    seen: list[httpx.Request] = []
    with mock_client(200, load_fixture("arbeitnow.json"), seen) as client:
        jobs = arbeitnow.fetch(client)

    assert len(seen) == 1  # page 1 only
    remote, onsite = jobs
    assert remote.id == "arbeitnow:backend-engineer-301"
    assert remote.location == "Remote (Berlin)"
    assert remote.description == "C# & Azure"
    assert remote.posted_at == datetime.fromtimestamp(1794380115, UTC)
    assert onsite.location == "Munich"


@pytest.mark.parametrize("module", [remoteok, arbeitnow])
def test_sources_raise_on_http_error(module):
    with mock_client(503, {}) as client, pytest.raises(httpx.HTTPStatusError):
        module.fetch(client)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CafÃ©", "Café"),
        ("plain text", "plain text"),
        ("already — fine", "already — fine"),
        ("â alone", "â alone"),  # not valid mojibake: left unchanged
    ],
)
def test_fix_mojibake(raw, expected):
    assert fix_mojibake(raw) == expected
