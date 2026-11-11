"""Arbeitnow public job board API (https://www.arbeitnow.com/api/job-board-api).

Free, please don't abuse, link back appreciated. We read page 1 only (newest ~300 jobs).
Descriptions arrive HTML-escaped; dates are Unix timestamps.
"""

import logging
from datetime import UTC, datetime

import httpx

from jobpilot.models import Job
from jobpilot.sources.http import html_to_text

SOURCE = "arbeitnow"
API_URL = "https://www.arbeitnow.com/api/job-board-api"

log = logging.getLogger(__name__)


def fetch(client: httpx.Client) -> list[Job]:
    response = client.get(API_URL)
    response.raise_for_status()
    jobs = []
    for raw in response.json().get("data", []):
        try:
            jobs.append(to_job(raw))
        except (KeyError, TypeError, ValueError) as e:
            log.warning("Skipping malformed Arbeitnow job %r: %s", raw.get("slug"), e)
    return jobs


def to_job(raw: dict) -> Job:
    location = (raw.get("location") or "").strip()
    if raw.get("remote"):
        location = f"Remote ({location})" if location else "Remote"
    created = raw.get("created_at")
    return Job(
        id=f"{SOURCE}:{raw['slug']}",
        source=SOURCE,
        title=raw["title"].strip(),
        company=raw.get("company_name", "").strip(),
        location=location or "Unknown",
        url=raw["url"],
        description=html_to_text(raw.get("description", "")),
        posted_at=datetime.fromtimestamp(created, UTC) if created else None,
    )
