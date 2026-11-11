from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import open_page
from streamlit.testing.v1 import AppTest

from jobpilot.db import connect, init_db, insert_jobs, save_score
from jobpilot.models import Job, Score, Status
from jobpilot.views import (
    JobFilter,
    filter_jobs,
    md_escape,
    paginate,
    score_badge,
    sort_by_score,
    sort_jobs,
)

APP = str(Path(__file__).parents[1] / "app.py")

JOBS = [
    Job("a:1", "remoteok", "Senior .NET Developer", "Acme", "Remote", "https://a/1", "Azure"),
    Job("b:2", "greenhouse", "LLM Engineer", "GitLab", "Remote, Poland", "https://b/2"),
    Job("c:3", "remotive", "Data Analyst", "Beta", "Worldwide", "https://c/3", "uses .net"),
]
SCORES = {
    "a:1": Score("a:1", 85, "Strong C# match.", "m", "cv1"),
    "b:2": Score("b:2", 40, "Poland-only remote.", "m", "cv1"),
}  # c:3 is not scored yet


# --- pure helpers ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("f", "expected"),
    [
        (JobFilter(), ["a:1", "b:2", "c:3"]),
        (JobFilter(sources=frozenset({"greenhouse"})), ["b:2"]),
        (JobFilter(keyword=" .NET "), ["a:1", "c:3"]),  # title or description, trimmed
        (JobFilter(keyword="gitlab"), ["b:2"]),  # company
        (JobFilter(location="worldwide"), ["c:3"]),
        (JobFilter(sources=frozenset({"remoteok"}), keyword="llm"), []),  # filters combine
    ],
)
def test_filter_jobs(f, expected):
    assert [j.id for j in filter_jobs(JOBS, f)] == expected


@pytest.mark.parametrize(
    ("min_score", "expected"),
    [(0, ["a:1", "b:2", "c:3"]), (40, ["a:1", "b:2"]), (50, ["a:1"]), (90, [])],
)
def test_min_score_filter_hides_unscored_when_set(min_score, expected):
    assert [j.id for j in filter_jobs(JOBS, JobFilter(min_score=min_score), SCORES)] == expected


def test_sort_by_score_puts_best_first_and_unscored_last():
    unscored_first = [JOBS[2], JOBS[1], JOBS[0]]
    assert [j.id for j in sort_by_score(unscored_first, SCORES)] == ["a:1", "b:2", "c:3"]


def test_sort_newest_puts_undated_last():
    dated = [
        Job("o:1", "t", "Old", "C", "Remote", "u", posted_at=datetime(2026, 1, 1, tzinfo=UTC)),
        Job("n:1", "t", "New", "C", "Remote", "u", posted_at=datetime(2026, 11, 1, tzinfo=UTC)),
    ]
    jobs = (j for j in [JOBS[0], *dated])  # a generator: must still work
    assert [j.id for j in sort_jobs(jobs, SCORES, "Newest")] == ["n:1", "o:1", "a:1"]


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (None, ("Not scored", "gray")),
        (92, ("92 · strong", "green")),
        (75, ("75 · strong", "green")),
        (74, ("74 · fair", "orange")),
        (50, ("50 · fair", "orange")),
        (49, ("49 · weak", "red")),
    ],
)
def test_score_badge_colour_carries_meaning(score, expected):
    assert score_badge(score) == expected


@pytest.mark.parametrize(
    ("count", "page", "expected"),
    [(45, 1, (20, 3, 1)), (45, 3, (5, 3, 3)), (45, 9, (5, 3, 3)), (0, 1, (0, 1, 1))],
)
def test_paginate_clamps_page(count, page, expected):
    items, pages, shown = paginate(list(range(count)), page)
    assert (len(items), pages, shown) == expected


def test_md_escape_shows_text_literally():
    assert md_escape("# C# *fast*\nline 2") == r"\# C\# \*fast\*" + "  \nline 2"


# --- Jobs page ---------------------------------------------------------------------------


def run_app(tmp_path, monkeypatch, jobs, page="jobs", scores=()):
    """Start the app on a temp DB/config and open `page` (default: the Jobs page)."""
    db = tmp_path / "jobs.db"
    conn = connect(db)
    init_db(conn)
    insert_jobs(conn, jobs)
    for score in scores:
        save_score(conn, score)
    conn.close()
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n'
        f'[sources]\nenabled=["remotive"]\n[database]\npath="{db.as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("JOBPILOT_CONFIG", str(cfg))
    return open_page(AppTest.from_file(APP, default_timeout=30).run(), page)


def card_titles(at) -> list[str]:
    """Card titles as shown: bold markdown, with md_escape's backslashes removed."""
    return [
        m.value.split("**")[1].replace("\\", "") for m in at.markdown if m.value.startswith("**")
    ]


def click(at, label: str, key: str | None = None):
    [button] = [b for b in at.button if b.label == label and (key is None or b.key == key)]
    return button.click().run()


def test_cards_show_badges_best_match_first_and_filter(tmp_path, monkeypatch):
    at = run_app(tmp_path, monkeypatch, JOBS, scores=SCORES.values())
    assert not at.exception
    assert card_titles(at) == ["Senior .NET Developer", "LLM Engineer", "Data Analyst"]
    badges = [m.value for m in at.markdown if "strong" in m.value or "Not scored" in m.value]
    assert badges  # colour badges rendered
    assert "Strong C# match." in [c.value for c in at.caption]

    at.sidebar.slider[0].set_value(50).run()
    assert card_titles(at) == ["Senior .NET Developer"]

    at.sidebar.slider[0].set_value(0).run()
    at.sidebar.text_input[0].input("llm").run()  # keyword box
    assert card_titles(at) == ["LLM Engineer"]


def test_empty_db_and_no_match_hints(tmp_path, monkeypatch):
    at = run_app(tmp_path, monkeypatch, [])
    assert "Fetch jobs on Home" in at.info[0].value

    at = run_app(tmp_path, monkeypatch, JOBS)
    at.sidebar.text_input[0].input("cobol").run()
    assert any("No jobs match these filters" in i.value for i in at.info)


def test_pagination_shows_20_per_page(tmp_path, monkeypatch):
    many = [
        Job(f"m:{n}", "t", f"Role {n:02d}", "Co", "Remote", f"https://m/{n}") for n in range(25)
    ]
    at = run_app(tmp_path, monkeypatch, many)
    assert len(card_titles(at)) == 20
    assert any("Page 1 of 2" in m.value for m in at.markdown)

    at = click(at, "Next")
    assert len(card_titles(at)) == 5
    assert any("Page 2 of 2" in m.value for m in at.markdown)


def test_details_dialog_shows_job_and_escapes_markdown(tmp_path, monkeypatch):
    db_jobs = [*JOBS[:1], Job("d:4", "s", "Tech Lead", "Zeta", "Remote", "https://d/4", "# Perks")]
    at = run_app(tmp_path, monkeypatch, db_jobs)
    assert not at.subheader  # no dialog until you ask

    at = click(at, "Details", key="details_d:4")
    assert at.subheader[0].value == "Tech Lead"
    assert any("Zeta" in c.value for c in at.caption)
    assert r"\# Perks" in [m.value for m in at.markdown]  # rendered literally, not as a heading


def test_save_status_from_dialog_shows_badge_and_tracker(tmp_path, monkeypatch):
    at = run_app(tmp_path, monkeypatch, JOBS, page="tracker")
    assert any("Nothing tracked yet" in i.value for i in at.info)

    at = open_page(at, "jobs")
    at = click(at, "Details", key="details_a:1")
    at.selectbox[0].set_value(Status.APPLIED)
    at.text_area[0].input("sent CV via site")
    at = click(at, "Save")

    assert not at.exception
    assert "is now 'applied'" in at.success[0].value
    assert any(m.value == "Applied" or "Applied" in m.value for m in at.markdown)  # status badge

    at = open_page(at, "tracker")
    assert "Applied (1)" in [h.value for h in at.subheader]
