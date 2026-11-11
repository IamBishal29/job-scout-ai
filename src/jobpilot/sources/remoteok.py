"""Remote OK public API (https://remoteok.com/api).

Terms: link back to the Remote OK URL and mention Remote OK as the source.
The first array item is a legal notice, not a job.
"""

import logging
from datetime import datetime

import httpx

from jobpilot.models import Job
from jobpilot.sources.http import fix_mojibake, html_to_text

SOURCE = "remoteok"
API_URL = "https://remoteok.com/api"

log = logging.getLogger(__name__)


def fetch(client: httpx.Client) -> list[Job]:
    response = client.get(API_URL)
    response.raise_for_status()
    jobs = []
    for raw in response.json():
        if "id" not in raw:  # legal notice / metadata item
            continue
        try:
            jobs.append(to_job(raw))
        except (KeyError, TypeError, ValueError) as e:
            log.warning("Skipping malformed Remote OK job %r: %s", raw.get("id"), e)
    return jobs


def to_job(raw: dict) -> Job:
    return Job(
        id=f"{SOURCE}:{raw['id']}",
        source=SOURCE,
        title=fix_mojibake(raw["position"]).strip(),
        company=fix_mojibake(raw.get("company", "")).strip(),
        location=(raw.get("location") or "Remote").strip(),
        url=raw["url"],
        description=html_to_text(fix_mojibake(raw.get("description", ""))),
        posted_at=datetime.fromisoformat(raw["date"]) if raw.get("date") else None,
    )
