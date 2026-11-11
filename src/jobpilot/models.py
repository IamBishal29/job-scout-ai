"""Domain models shared by fetchers, the database layer and the UI."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Job:
    """One job posting, normalized from any source.

    `id` is unique per source posting, e.g. "remotive:12345".
    Cross-source duplicate detection happens later in the pipeline.
    """

    id: str
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    posted_at: datetime | None = None
    fetched_at: datetime = field(default_factory=utc_now)
