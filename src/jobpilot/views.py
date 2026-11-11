"""UI-independent view logic: filtering and table rows. No Streamlit imports here."""

from collections.abc import Iterable
from dataclasses import dataclass

from jobpilot.models import Job


@dataclass(frozen=True, slots=True)
class JobFilter:
    """What the user picked in the sidebar. Empty values mean "no filter"."""

    sources: frozenset[str] = frozenset()
    keyword: str = ""
    location: str = ""


def filter_jobs(jobs: Iterable[Job], f: JobFilter) -> list[Job]:
    """Keep jobs matching every non-empty filter (case-insensitive)."""
    keyword, location = f.keyword.strip().lower(), f.location.strip().lower()
    return [
        job
        for job in jobs
        if (not f.sources or job.source in f.sources)
        and (not location or location in job.location.lower())
        and (not keyword or keyword in f"{job.title} {job.company} {job.description}".lower())
    ]


def to_rows(jobs: Iterable[Job]) -> list[dict]:
    """Flatten jobs into table rows, in the column order the UI shows."""
    return [
        {
            "Posted": job.posted_at.date() if job.posted_at else None,
            "Title": job.title,
            "Company": job.company,
            "Location": job.location,
            "Source": job.source,
            "Link": job.url,
        }
        for job in jobs
    ]
