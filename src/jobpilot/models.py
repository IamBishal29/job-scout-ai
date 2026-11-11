"""Domain models shared by fetchers, the database layer and the UI."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

_NON_ALNUM = re.compile(r"[^a-z0-9#+]+")  # keep '#' and '+' so "C#" != "C" and "C++" != "C"


def utc_now() -> datetime:
    return datetime.now(UTC)


def normalize(text: str) -> str:
    """Lowercase and collapse punctuation/whitespace: ' Senior .NET Dev! ' -> 'senior net dev'."""
    return _NON_ALNUM.sub(" ", text.lower()).strip()


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

    @property
    def dedupe_key(self) -> str:
        """Same company + title on any source -> same key. No company? Fall back to the URL."""
        company = normalize(self.company)
        basis = f"{company}|{normalize(self.title)}" if company else self.url.strip().lower()
        return hashlib.sha1(basis.encode("utf-8")).hexdigest()
