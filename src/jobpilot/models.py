"""Domain models shared by fetchers, the database layer and the UI."""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

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


class Status(StrEnum):
    """Where I am with a job. Stored as text in the applications table."""

    NEW = "new"
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"


# Light state machine: move forward, get rejected, or step back one stage to fix a mistake.
ALLOWED: dict[Status, frozenset[Status]] = {
    Status.NEW: frozenset({Status.SAVED, Status.APPLIED}),
    Status.SAVED: frozenset({Status.NEW, Status.APPLIED, Status.REJECTED}),
    Status.APPLIED: frozenset({Status.SAVED, Status.INTERVIEW, Status.REJECTED}),
    Status.INTERVIEW: frozenset({Status.APPLIED, Status.OFFER, Status.REJECTED}),
    Status.OFFER: frozenset({Status.INTERVIEW, Status.REJECTED}),
    Status.REJECTED: frozenset({Status.SAVED, Status.APPLIED, Status.INTERVIEW}),
}


@dataclass(frozen=True, slots=True)
class Application:
    """My tracking data for one job. A job without a row is implicitly NEW."""

    job_id: str
    status: Status = Status.NEW
    notes: str = ""
    applied_at: datetime | None = None
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class Score:
    """How well a job fits my CV, judged by the LLM. Cached: one per job."""

    job_id: str
    score: int  # 0-100
    reason: str
    model: str
    cv_hash: str  # which CV version was used (lets us spot stale scores later)
    scored_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class CoverLetter:
    """A draft I edit and send myself. JobPilot never sends it anywhere."""

    job_id: str
    body: str
    model: str
    cv_hash: str
    generated_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
