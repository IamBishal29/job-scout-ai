from email.message import EmailMessage
from pathlib import Path

import httpx
import pytest

from jobpilot.config import Config, SearchConfig
from jobpilot.models import Job
from jobpilot.pipeline import matches, run_fetch
from jobpilot.sources import alerts
from jobpilot.sources.alerts import AlertEmailSource, parse_alert, read_alert_emails


def raw_email(sender: str, subject: str) -> bytes:
    msg = EmailMessage()
    msg["From"], msg["Subject"] = sender, subject
    msg.set_content("hello")
    return msg.as_bytes()


class FakeIMAP:
    """Records the IMAP conversation instead of talking to Gmail."""

    def __init__(self, host, mailbox: dict[str, list[bytes]]):
        self.host, self.mailbox, self.calls = host, mailbox, []

    def login(self, user, password):
        self.calls.append(("login", user))

    def select(self, folder, readonly=False):
        self.calls.append(("select", folder, readonly))
        self.folder = folder.strip('"')
        return ("OK", [b"2"]) if self.folder in self.mailbox else ("NO", [b"unknown"])

    def search(self, charset, *criteria):
        self.calls.append(("search", *criteria))
        ids = " ".join(str(i + 1) for i in range(len(self.mailbox[self.folder])))
        return "OK", [ids.encode()]

    def fetch(self, num, spec):
        self.calls.append(("fetch", spec))
        return "OK", [(b"header", self.mailbox[self.folder][int(num) - 1])]

    def logout(self):
        self.calls.append(("logout",))


def test_reads_folder_read_only_without_marking_seen():
    mailbox = {"JobAlerts": [raw_email("jobs@linkedin.com", "A"), raw_email("x@y.z", "B")]}
    fake = FakeIMAP("", mailbox)
    msgs = read_alert_emails("me@gmail.com", "pw", "JobAlerts", 7, lambda host: fake)

    assert [m["Subject"] for m in msgs] == ["A", "B"]
    assert ("select", '"JobAlerts"', True) in fake.calls  # readonly
    assert {c[1] for c in fake.calls if c[0] == "fetch"} == {"(BODY.PEEK[])"}  # stays unread
    assert fake.calls[1][0] == "select" and fake.calls[-1] == ("logout",)
    assert fake.calls[2][1] == "SINCE"


def test_missing_label_raises_and_still_logs_out():
    fake = FakeIMAP("", {})
    with pytest.raises(ValueError, match="not found"):
        read_alert_emails("me", "pw", "Nope", 7, lambda host: fake)
    assert fake.calls[-1] == ("logout",)


def test_unknown_sender_is_ignored():
    msg = EmailMessage()
    msg["From"] = "newsletter@example.com"
    assert parse_alert(msg) == []


def test_source_dedupes_jobs_across_daily_alert_emails(monkeypatch):
    job = Job("alerts:linkedin:1", "alerts", ".NET Engineer", "Acme", "Unknown", "https://l/1")
    monkeypatch.setattr(alerts, "get_secret", lambda name: "x")
    monkeypatch.setattr(alerts, "read_alert_emails", lambda *a: [EmailMessage(), EmailMessage()])
    monkeypatch.setattr(alerts, "parse_alert", lambda msg: [job])
    assert AlertEmailSource("JobAlerts", 7).fetch(httpx.Client()) == [job]


def test_trusted_location_skips_location_but_not_role_check(tmp_path):
    from jobpilot import db

    search = SearchConfig(role_keywords=(".net",), locations=("remote",))
    unknown = Job("alerts:1", "alerts", ".NET Engineer", "Acme", "Unknown", "https://l/1")
    sales = Job("alerts:2", "alerts", "Sales Lead", "Acme", "Unknown", "https://l/2")
    assert not matches(unknown, search)
    assert matches(unknown, search, check_location=False)
    assert not matches(sales, search, check_location=False)

    trusted = AlertEmailSource("JobAlerts", 7)
    trusted.fetch = lambda client: [unknown, sales]
    conn = db.connect(tmp_path / "j.db")
    db.init_db(conn)
    cfg = Config(search=search, sources=("alerts",), db_path=Path("unused"))
    [result] = run_fetch(conn, cfg, httpx.Client(), {"alerts": trusted})
    assert (result.fetched, result.matched, result.new) == (2, 1, 1)
    conn.close()


FIXTURES = Path(__file__).parent / "fixtures" / "alerts"


def load_eml(name: str) -> EmailMessage:
    import email
    from email.policy import default

    return email.message_from_bytes((FIXTURES / name).read_bytes(), policy=default)


def test_parse_linkedin_alert_fixture():
    jobs = parse_alert(load_eml("linkedin_alert.eml"))
    assert [(j.title, j.company, j.location) for j in jobs] == [
        ("Senior .NET Developer", "Acme Cloud", "Dhaka, Bangladesh (Remote)"),
        ("AI Engineer (LLM Applications)", "Beta Labs", "Asia Pacific (Remote)"),
        ("Solutions Architect & Team Lead", "Gamma Systems", "Singapore"),
    ]  # logo link (no text) and "See all jobs" / "Manage alerts" links are ignored
    assert jobs[0].id == "alerts:linkedin:4012345678"
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/4012345678/"  # tracking dropped
    assert jobs[0].posted_at.isoformat() == "2026-11-10T06:12:00+00:00"


def test_parse_indeed_alert_fixture():
    jobs = parse_alert(load_eml("indeed_alert.eml"))
    assert [(j.id, j.company, j.location) for j in jobs] == [
        ("alerts:indeed:a1b2c3d4e5f60718", "Delta Software", "Remote"),
        ("alerts:indeed:0f1e2d3c4b5a6978", "Epsilon Tech Ltd", "Dhaka"),
    ]
    assert jobs[1].url == "https://www.indeed.com/viewjob?jk=0f1e2d3c4b5a6978"


def test_text_only_alert_yields_nothing():
    msg = EmailMessage()
    msg["From"] = "jobalerts-noreply@linkedin.com"
    msg.set_content("plain text only")
    assert parse_alert(msg) == []
