"""Remotive public API (https://remotive.com/api-documentation).

Terms: link back to the Remotive URL, credit Remotive as the source, and call
the API at most ~4 times a day. We fetch everything in one request and filter later.
"""

import logging
from datetime import UTC, datetime

import httpx

from jobpilot.models import Job
from jobpilot.sources.http import html_to_text

SOURCE = "remotive"
API_URL = "https://remotive.com/api/remote-jobs"

log = logging.getLogger(__name__)


def fetch(client: httpx.Client) -> list[Job]:
    """Download all current Remotive jobs. Raises httpx.HTTPError on network/HTTP errors."""
    response = client.get(API_URL)
    response.raise_for_status()
    jobs = []
    for raw in response.json().get("jobs", []):
        try:
            jobs.append(to_job(raw))
        except (KeyError, TypeError, ValueError) as e:
            log.warning("Skipping malformed Remotive job %r: %s", raw.get("id"), e)
    return jobs


def to_job(raw: dict) -> Job:
    """Map one Remotive API item (DTO) to our Job model."""
    return Job(
        id=f"{SOURCE}:{raw['id']}",
        source=SOURCE,
        title=raw["title"].strip(),
        company=raw.get("company_name", "").strip(),
        location=(raw.get("candidate_required_location") or "Remote").strip(),
        url=raw["url"],
        description=html_to_text(raw.get("description", "")),
        posted_at=_parse_date(raw.get("publication_date")),
    )


def _parse_date(value: str | None) -> datetime | None:
    """Remotive dates have no timezone; they are UTC."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
