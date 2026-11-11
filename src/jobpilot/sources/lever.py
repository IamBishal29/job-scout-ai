"""Lever public postings API (https://github.com/lever/postings-api).

Companies on Lever have a site name, e.g. https://jobs.lever.co/toptal -> "toptal".
No API key needed.
"""

import logging
from datetime import UTC, datetime

import httpx

from jobpilot.models import Job

API_URL = "https://api.lever.co/v0/postings/{company}?mode=json"

log = logging.getLogger(__name__)


class LeverSource:
    """One source covering several Lever companies. Satisfies the JobSource Protocol."""

    SOURCE = "lever"

    def __init__(self, companies: tuple[str, ...]) -> None:
        self.companies = companies

    def fetch(self, client: httpx.Client) -> list[Job]:
        jobs = []
        for company in self.companies:
            try:
                response = client.get(API_URL.format(company=company))
                response.raise_for_status()
                items = response.json()
                if not isinstance(items, list):  # e.g. {"ok": false, "error": "Document not found"}
                    raise ValueError(f"unexpected response: {str(items)[:80]}")
            except (httpx.HTTPError, ValueError) as e:
                log.warning("Skipping Lever company %s: %s", company, e)
                continue
            for raw in items:
                try:
                    jobs.append(to_job(raw, company))
                except (KeyError, TypeError, ValueError) as e:
                    log.warning("Skipping malformed Lever posting at %s: %s", company, e)
        return jobs


def to_job(raw: dict, company: str) -> Job:
    location = ((raw.get("categories") or {}).get("location") or "").strip()
    if raw.get("workplaceType") == "remote":
        location = f"Remote ({location})" if location else "Remote"
    created = raw.get("createdAt")
    return Job(
        id=f"lever:{company}:{raw['id']}",
        source="lever",
        title=raw["text"].strip(),
        company=company.title(),  # Lever has no company name field; "toptal" -> "Toptal"
        location=location or "Unknown",
        url=raw["hostedUrl"],
        description=(raw.get("descriptionPlain") or "").strip(),
        posted_at=datetime.fromtimestamp(created / 1000, UTC) if created else None,
    )
