"""Greenhouse public job boards (https://developers.greenhouse.io/job-board.html).

Many companies host careers pages on Greenhouse; each has a board token, e.g.
https://job-boards.greenhouse.io/gitlab -> "gitlab". No API key needed.
"""

import logging
from datetime import datetime

import httpx

from jobpilot.models import Job
from jobpilot.sources.http import html_to_text

API_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"

log = logging.getLogger(__name__)


class GreenhouseSource:
    """One source covering several company boards. Satisfies the JobSource Protocol."""

    SOURCE = "greenhouse"

    def __init__(self, boards: tuple[str, ...]) -> None:
        self.boards = boards

    def fetch(self, client: httpx.Client) -> list[Job]:
        jobs = []
        for board in self.boards:
            try:
                response = client.get(API_URL.format(board=board))
                response.raise_for_status()
                items = response.json().get("jobs", [])
            except (httpx.HTTPError, ValueError) as e:
                log.warning("Skipping Greenhouse board %s: %s", board, e)
                continue
            for raw in items:
                try:
                    jobs.append(to_job(raw, board))
                except (KeyError, TypeError, ValueError) as e:
                    log.warning("Skipping malformed Greenhouse job on %s: %s", board, e)
        return jobs


def to_job(raw: dict, board: str) -> Job:
    published = raw.get("first_published") or raw.get("updated_at")
    return Job(
        id=f"greenhouse:{board}:{raw['id']}",
        source="greenhouse",
        title=raw["title"].strip(),
        company=(raw.get("company_name") or board).strip(),
        location=((raw.get("location") or {}).get("name") or "Unknown").strip(),
        url=raw["absolute_url"],
        description=html_to_text(raw.get("content", "")),
        posted_at=datetime.fromisoformat(published) if published else None,
    )
