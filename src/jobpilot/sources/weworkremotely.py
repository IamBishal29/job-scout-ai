"""We Work Remotely RSS feeds (https://weworkremotely.com/remote-job-rss-feed).

No JSON API, so we read the per-category RSS feeds. Item titles are "Company: Job title".
Jobs can appear in several categories; we keep each guid once.
"""

import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx

from jobpilot.models import Job
from jobpilot.sources.http import html_to_text

SOURCE = "weworkremotely"
BASE_URL = "https://weworkremotely.com/categories"
FEEDS = (
    "remote-back-end-programming-jobs",
    "remote-full-stack-programming-jobs",
    "remote-programming-jobs",
    "remote-management-and-finance-jobs",
)

log = logging.getLogger(__name__)


def fetch(client: httpx.Client) -> list[Job]:
    """Fetch all feeds. A failing feed is logged and skipped so the others still count."""
    jobs: dict[str, Job] = {}
    for feed in FEEDS:
        try:
            response = client.get(f"{BASE_URL}/{feed}.rss")
            response.raise_for_status()
            items = ET.fromstring(response.content).iter("item")
        except (httpx.HTTPError, ET.ParseError) as e:
            log.warning("Skipping WWR feed %s: %s", feed, e)
            continue
        for item in items:
            try:
                job = to_job(item)
            except (AttributeError, KeyError, TypeError, ValueError) as e:
                log.warning("Skipping malformed WWR item in %s: %s", feed, e)
                continue
            jobs.setdefault(job.id, job)
    return list(jobs.values())


def to_job(item: ET.Element) -> Job:
    """Map one RSS <item> to Job."""
    url = _text(item, "link") or _text(item, "guid")
    if not url:
        raise ValueError("item has no link")
    company, _, title = _text(item, "title").partition(": ")
    if not title:  # no "Company: " prefix
        company, title = "", company
    pub_date = _text(item, "pubDate")
    return Job(
        id=f"{SOURCE}:{url.rstrip('/').rsplit('/', 1)[-1]}",
        source=SOURCE,
        title=title.strip(),
        company=company.strip(),
        location=_text(item, "region") or "Remote",
        url=url,
        description=html_to_text(_text(item, "description")),
        posted_at=parsedate_to_datetime(pub_date) if pub_date else None,
    )


def _text(item: ET.Element, tag: str) -> str:
    return (item.findtext(tag) or "").strip()
