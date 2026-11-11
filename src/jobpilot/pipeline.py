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
from jobpilot.sources.alerts import AlertEmailSource
from jobpilot.sources.base import JobSource
from jobpilot.sources.greenhouse import GreenhouseSource
from jobpilot.sources.lever import LeverSource


def build_sources(config: Config) -> dict[str, JobSource]:
    """All available sources: fixed feeds (modules) + company boards built from config."""
    fixed: list[JobSource] = [remotive, remoteok, arbeitnow, weworkremotely]
    boards: list[JobSource] = [
        GreenhouseSource(config.boards.get("greenhouse", ())),
        LeverSource(config.boards.get("lever", ())),
        AlertEmailSource(config.alerts_folder, config.alerts_days),
    ]
    return {s.SOURCE: s for s in fixed + boards}


log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceResult:
    source: str
    fetched: int = 0
    matched: int = 0
    new: int = 0
    error: str | None = None


def matches(job: Job, search: SearchConfig, check_location: bool = True) -> bool:
    """Title has a role keyword, location has a wanted place and no excluded region.

    check_location=False for sources whose own settings already chose the location
    (job-alert emails); the LLM score still judges whether you can take the job.
    """
    title, location = job.title.lower(), job.location.lower()
    location_ok = any(k in location for k in search.locations) and not any(
        k in location for k in search.exclude_locations
    )
    return any(k in title for k in search.role_keywords) and (location_ok or not check_location)


def run_fetch(
    conn: sqlite3.Connection,
    config: Config,
    client: httpx.Client,
    sources: Mapping[str, JobSource] | None = None,
) -> list[SourceResult]:
    """Run every enabled source. One failing source never stops the others."""
    sources = build_sources(config) if sources is None else sources
    results = []
    for name in config.sources:
        try:
            jobs = sources[name].fetch(client)
        except (httpx.HTTPError, ValueError) as e:
            log.warning("Source %s failed: %s", name, e)
            results.append(SourceResult(name, error=str(e) or type(e).__name__))
            continue
        check_location = not getattr(sources[name], "TRUSTED_LOCATION", False)
        wanted = [job for job in jobs if matches(job, config.search, check_location)]
        results.append(SourceResult(name, len(jobs), len(wanted), insert_jobs(conn, wanted)))
    return results
