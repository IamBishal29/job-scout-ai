"""LinkedIn / Indeed job-alert emails, read from Gmail over IMAP.

ToS-safe: we never scrape LinkedIn or Indeed. They email you alerts you subscribed to;
we read those emails from one Gmail label, read-only (BODY.PEEK keeps them unread).
"""

import contextlib
import email
import imaplib
import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

import httpx

from jobpilot.config import get_secret
from jobpilot.models import Job, utc_now

IMAP_HOST = "imap.gmail.com"

log = logging.getLogger(__name__)


def read_alert_emails(
    user: str,
    app_password: str,
    folder: str,
    days: int,
    imap_factory: Callable[[str], imaplib.IMAP4] | None = None,
) -> list[EmailMessage]:
    """Emails from the last `days` days in `folder`. Opened read-only: nothing changes."""
    factory = imap_factory or imaplib.IMAP4_SSL
    since = (utc_now() - timedelta(days=days)).strftime("%d-%b-%Y")
    imap = factory(IMAP_HOST)
    try:
        imap.login(user, app_password)
        status, _ = imap.select(f'"{folder}"', readonly=True)
        if status != "OK":
            raise ValueError(f"Gmail label/folder {folder!r} not found")
        _, data = imap.search(None, "SINCE", since)
        messages = []
        for num in data[0].split():
            _, parts = imap.fetch(num, "(BODY.PEEK[])")  # PEEK: do not mark as read
            raw = parts[0][1]
            messages.append(email.message_from_bytes(raw, policy=default_policy))
        return messages
    finally:
        with contextlib.suppress(imaplib.IMAP4.error, OSError):
            imap.logout()  # best effort: a failed logout must not hide the real result


def parse_alert(msg: EmailMessage) -> list[Job]:
    """Route an alert email to the parser for its sender."""
    sender = str(msg.get("From", "")).lower()
    if "linkedin.com" in sender:
        return parse_linkedin(msg)
    if "indeed.com" in sender:
        return parse_indeed(msg)
    return []


LINKEDIN_JOB = re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(\d+)")
INDEED_JOB = re.compile(r"indeed\.[a-z.]+/[^\s\"]*[?&]jk=([0-9a-f]+)")


def parse_linkedin(msg: EmailMessage) -> list[Job]:
    return _parse_cards(msg, LINKEDIN_JOB, "linkedin", "https://www.linkedin.com/jobs/view/{}/")


def parse_indeed(msg: EmailMessage) -> list[Job]:
    return _parse_cards(msg, INDEED_JOB, "indeed", "https://www.indeed.com/viewjob?jk={}")


class _Tokens(HTMLParser):
    """Flatten HTML into ("link", href, text) and ("text", text) tokens, in order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[tuple[str, ...]] = []
        self._href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href, self._link_text = dict(attrs).get("href") or "", []

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.tokens.append(("link", self._href, " ".join(self._link_text).strip()))
            self._href = None

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        if self._href is not None:
            self._link_text.append(text)
        else:
            self.tokens.append(("text", text))


def _parse_cards(msg: EmailMessage, pattern: re.Pattern, site: str, url: str) -> list[Job]:
    """Each job = a link matching `pattern` (its text is the title), followed by text lines
    with company and location, up to the next job link. Layout-agnostic on purpose:
    alert email HTML changes often, job links rarely do."""
    body = msg.get_body(preferencelist=("html",))
    if body is None:
        return []
    parser = _Tokens()
    parser.feed(body.get_content())
    tokens, posted = parser.tokens, _sent_at(msg)
    jobs: dict[str, Job] = {}
    for i, token in enumerate(tokens):
        match = pattern.search(token[1]) if token[0] == "link" else None
        if not match or not token[2] or match.group(1) in jobs:  # logo links have no text
            continue
        texts = []
        for nxt in tokens[i + 1 :]:
            if nxt[0] == "link" and pattern.search(nxt[1]):
                break
            if nxt[0] == "text":
                texts.append(nxt[1])
            if len(texts) == 2:
                break
        company, location = _company_location(texts)
        job_id = match.group(1)
        jobs[job_id] = Job(
            id=f"alerts:{site}:{job_id}",
            source="alerts",
            title=token[2],
            company=company,
            location=location,
            url=url.format(job_id),  # canonical link: drops the email's tracking parameters
            posted_at=posted,
        )
    return list(jobs.values())


def _company_location(texts: list[str]) -> tuple[str, str]:
    if texts and " · " in texts[0]:  # LinkedIn style: "Company · Location"
        company, location = texts[0].split(" · ", 1)
        return company.strip(), location.strip()
    company = texts[0] if texts else ""
    location = texts[1] if len(texts) > 1 else "Unknown"
    return company, location


def _sent_at(msg: EmailMessage) -> datetime | None:
    try:
        return parsedate_to_datetime(str(msg["Date"]))
    except (TypeError, ValueError):
        return None


class AlertEmailSource:
    """JobSource for alert emails. The httpx client is unused: this source speaks IMAP."""

    SOURCE = "alerts"
    TRUSTED_LOCATION = True  # the alert's own settings already chose the location

    def __init__(self, folder: str, days: int) -> None:
        self.folder, self.days = folder, days

    def fetch(self, client: httpx.Client) -> list[Job]:
        try:
            messages = read_alert_emails(
                get_secret("SMTP_USER"), get_secret("SMTP_APP_PASSWORD"), self.folder, self.days
            )
        except imaplib.IMAP4.error as e:
            raise ValueError(f"Gmail IMAP login/read failed: {type(e).__name__}") from e
        jobs: dict[str, Job] = {}
        for msg in messages:
            for job in parse_alert(msg):
                jobs.setdefault(job.id, job)  # the same job appears in many daily alerts
        return list(jobs.values())
