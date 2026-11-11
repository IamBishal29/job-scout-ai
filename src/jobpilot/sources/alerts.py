"""LinkedIn / Indeed job-alert emails, read from Gmail over IMAP.

ToS-safe: we never scrape LinkedIn or Indeed. They email you alerts you subscribed to;
we read those emails from one Gmail label, read-only (BODY.PEEK keeps them unread).
"""

import contextlib
import email
import imaplib
import logging
from collections.abc import Callable
from datetime import timedelta
from email.message import EmailMessage
from email.policy import default as default_policy

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


def parse_linkedin(msg: EmailMessage) -> list[Job]:
    raise NotImplementedError("built from Syed's sample alert emails")


def parse_indeed(msg: EmailMessage) -> list[Job]:
    raise NotImplementedError("built from Syed's sample alert emails")


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
