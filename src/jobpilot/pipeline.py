"""Fetch -> filter -> dedupe -> store. Safe to run repeatedly (idempotent)."""

import logging
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

import httpx

from jobpilot.config import Config, SearchConfig
from jobpilot.db import insert_jobs
from jobpilot.models import Job
from jobpilot.sources import arbeitnow, remoteok, remotive, weworkremotely
from jobpilot.sources.base import JobSource

SOURCES: dict[str, JobSource] = {
    m.SOURCE: m for m in (remotive, remoteok, arbeitnow, weworkremotely)
}

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceResult:
    source: str
    fetched: int = 0
    matched: int = 0
    new: int = 0
    error: str | None = None


def matches(job: Job, search: SearchConfig) -> bool:
    """Title has a role keyword, location has a wanted place and no excluded region."""
    title, location = job.title.lower(), job.location.lower()
    return (
        any(k in title for k in search.role_keywords)
        and any(k in location for k in search.locations)
        and not any(k in location for k in search.exclude_locations)
    )


def run_fetch(
    conn: sqlite3.Connection,
    config: Config,
    client: httpx.Client,
    sources: Mapping[str, JobSource] = SOURCES,
) -> list[SourceResult]:
    """Run every enabled source. One failing source never stops the others."""
    results = []
    for name in config.sources:
        try:
            jobs = sources[name].fetch(client)
        except (httpx.HTTPError, ValueError) as e:
            log.warning("Source %s failed: %s", name, e)
            results.append(SourceResult(name, error=str(e) or type(e).__name__))
            continue
        wanted = [job for job in jobs if matches(job, config.search)]
        results.append(SourceResult(name, len(jobs), len(wanted), insert_jobs(conn, wanted)))
    return results
