from datetime import UTC, datetime

import pytest

from jobpilot import db
from jobpilot.digest import build_digest
from jobpilot.models import Job, Score

NOW = datetime(2026, 11, 12, 7, 0, tzinfo=UTC)
JOBS = [
    Job("a:1", "t", "Senior .NET Engineer", "Acme", "Remote", "https://a/1"),
    Job("b:2", "t", "LLM Engineer", "Beta", "Worldwide", "https://b/2"),
    Job("c:3", "t", "Sales Rep", "Gamma", "Remote", "https://c/3"),
    Job("d:4", "t", "Tech Lead", "Delta", "Remote", "https://d/4"),  # never scored
]
SCORES = [
    Score("a:1", 88, "Strong C# and Azure match.", "m", "cv"),
    Score("b:2", 72, "LLM focus fits your direction.", "m", "cv"),
    Score("c:3", 15, "Not a technical role.", "m", "cv"),
]


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "j.db")
    db.init_db(c)
    db.insert_jobs(c, JOBS)
    for s in SCORES:
        db.save_score(c, s)
    yield c
    c.close()


def test_candidates_are_scored_above_threshold_best_first(conn):
    items = db.digest_candidates(conn, min_score=60, limit=10)
    assert [(j.id, s.score) for j, s in items] == [("a:1", 88), ("b:2", 72)]
    assert [j.id for j, _ in db.digest_candidates(conn, min_score=60, limit=1)] == ["a:1"]


def test_marked_jobs_are_never_emailed_twice(conn):
    assert db.last_digest_at(conn) is None
    db.mark_digested(conn, ["a:1"], NOW)
    db.mark_digested(conn, ["a:1"], NOW)  # retry-safe (idempotent)
    assert [j.id for j, _ in db.digest_candidates(conn, 60, 10)] == ["b:2"]
    assert db.last_digest_at(conn) == NOW


def test_build_digest_renders_html_and_text(conn):
    digest = build_digest(db.digest_candidates(conn, 60, 10), NOW, last_sent=None)
    assert digest.subject == "JobPilot 12 Nov: 2 new matches (top 88)"
    assert digest.job_ids == ("a:1", "b:2")
    for part in ("Senior .NET Engineer", "Acme", "88", "Strong C# and Azure match.", "https://a/1"):
        assert part in digest.html and part in digest.text
    assert "Your first digest" in digest.html
    assert "never applies for you" in digest.html


def test_build_digest_escapes_untrusted_job_text():
    job = Job("x:1", "t", "<script>alert(1)</script> Dev", "A&B", "Remote", 'https://x/"1')
    digest = build_digest([(job, Score("x:1", 70, "Fits <b>well</b>", "m", "cv"))], NOW, NOW)
    assert "<script>" not in digest.html
    assert "&lt;script&gt;" in digest.html and "A&amp;B" in digest.html
    assert 'href="https://x/&quot;1"' in digest.html
    assert "1 new match." in digest.text and "Since 12 Nov 2026 07:00 UTC" in digest.text


def test_nothing_new_means_no_email():
    assert build_digest([], NOW, None) is None
