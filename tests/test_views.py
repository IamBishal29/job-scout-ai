from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from jobpilot.db import connect, init_db, insert_jobs, save_score
from jobpilot.models import Job, Score, Status
from jobpilot.views import (
    JobFilter,
    filter_jobs,
    md_escape,
    resolve_selection,
    sort_by_score,
    to_rows,
)

APP = str(Path(__file__).parents[1] / "app.py")


JOBS = [
    Job("a:1", "remoteok", "Senior .NET Developer", "Acme", "Remote", "https://a/1", "Azure"),
    Job("b:2", "greenhouse", "LLM Engineer", "GitLab", "Remote, Poland", "https://b/2"),
    Job("c:3", "remotive", "Data Analyst", "Beta", "Worldwide", "https://c/3", "uses .net"),
]


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


def test_to_rows_defaults_status_to_new():

    assert to_rows(JOBS[:1])[0]["Status"] == "new"


def test_to_rows_formats_date_and_keeps_link():

    job = Job(
        "x:1", "s", "T", "C", "Remote", "https://x", posted_at=datetime(2026, 11, 5, tzinfo=UTC)
    )

    assert to_rows([job], {"x:1": Status.APPLIED}) == [
        {
            "Score": None,
            "Posted": datetime(2026, 11, 5).date(),
            "Status": "applied",
            "Title": "T",
            "Company": "C",
            "Location": "Remote",
            "Source": "s",
            "Why": "",
            "Link": "https://x",
        }
    ]


def run_app(tmp_path, monkeypatch, jobs):

    db = tmp_path / "jobs.db"

    conn = connect(db)

    init_db(conn)

    insert_jobs(conn, jobs)

    conn.close()

    cfg = tmp_path / "config.toml"

    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n'
        f'[sources]\nenabled=["remotive"]\n[database]\npath="{db.as_posix()}"\n',
        encoding="utf-8",
    )

    monkeypatch.setenv("JOBPILOT_CONFIG", str(cfg))

    return AppTest.from_file(APP, default_timeout=30).run()


def test_app_shows_jobs_and_filters(tmp_path, monkeypatch):

    at = run_app(tmp_path, monkeypatch, JOBS)

    assert not at.exception

    assert len(at.dataframe[0].value) == 3

    at.sidebar.text_input[0].input("llm").run()  # keyword box

    assert list(at.dataframe[0].value["Title"]) == ["LLM Engineer"]


def test_app_with_empty_db_shows_hint(tmp_path, monkeypatch):

    at = run_app(tmp_path, monkeypatch, [])

    assert not at.exception

    assert "python -m jobpilot fetch" in at.info[0].value


@pytest.mark.parametrize(
    ("rows", "previous", "expected"),
    [
        ([1], None, "b:2"),  # fresh click wins
        ([1], "a:1", "b:2"),  # ...even over an earlier choice
        ([], "c:3", "c:3"),  # no click: keep earlier choice while visible
        ([], "z:9", None),  # earlier choice filtered out
        ([7], "a:1", "a:1"),  # stale row index is ignored
    ],
)
def test_resolve_selection(rows, previous, expected):

    assert resolve_selection(["a:1", "b:2", "c:3"], rows, previous) == expected


def test_md_escape_shows_text_literally():

    assert md_escape("# C# *fast*\nline 2") == r"\# C\# \*fast\*" + "  \nline 2"


def test_app_shows_detail_for_selected_job(tmp_path, monkeypatch):

    db_jobs = [*JOBS[:1], Job("d:4", "s", "Tech Lead", "Zeta", "Remote", "https://d/4", "# Perks")]

    at = run_app(tmp_path, monkeypatch, db_jobs)

    assert "Select a row" in at.info[0].value  # nothing selected yet

    at.session_state["selected_job_id"] = "d:4"

    at.run()

    assert at.subheader[0].value == "Tech Lead"

    assert "Zeta" in at.caption[1].value

    assert r"\# Perks" in [m.value for m in at.markdown]  # rendered literally, not as a heading

    at.sidebar.text_input[0].input(".net").run()  # filter hides the selected job

    assert "Tech Lead" not in [h.value for h in at.subheader]


def test_app_saves_status_and_shows_it_in_tracker(tmp_path, monkeypatch):

    at = run_app(tmp_path, monkeypatch, JOBS)

    assert any("Nothing tracked yet" in i.value for i in at.info)

    at.session_state["selected_job_id"] = "a:1"

    at.run()

    at.selectbox[0].set_value(Status.APPLIED)

    at.text_area[0].input("sent CV via site")

    at.button[0].click().run()  # the form's Save button

    assert not at.exception

    assert "is now 'applied'" in at.success[0].value

    table = at.dataframe[0].value.set_index("Title")

    assert table.loc["Senior .NET Developer", "Status"] == "applied"

    assert "Applied (1)" in [h.value for h in at.subheader]  # tracker tab heading


SCORES = {
    "a:1": Score("a:1", 85, "Strong C# match.", "m", "cv1"),
    "b:2": Score("b:2", 40, "Poland-only remote.", "m", "cv1"),
}  # c:3 is not scored yet


@pytest.mark.parametrize(
    ("min_score", "expected"),
    [(0, ["a:1", "b:2", "c:3"]), (40, ["a:1", "b:2"]), (50, ["a:1"]), (90, [])],
)
def test_min_score_filter_hides_unscored_when_set(min_score, expected):
    f = JobFilter(min_score=min_score)
    assert [j.id for j in filter_jobs(JOBS, f, SCORES)] == expected


def test_sort_by_score_puts_best_first_and_unscored_last():
    unscored_first = [JOBS[2], JOBS[1], JOBS[0]]
    assert [j.id for j in sort_by_score(unscored_first, SCORES)] == ["a:1", "b:2", "c:3"]


def test_rows_include_score_and_reason():
    rows = to_rows(JOBS[:1], scores=SCORES)
    assert (rows[0]["Score"], rows[0]["Why"]) == (85, "Strong C# match.")


def test_app_sorts_by_score_filters_and_shows_match(tmp_path, monkeypatch):
    at = run_app(tmp_path, monkeypatch, JOBS)
    conn = connect(tmp_path / "jobs.db")
    for score in SCORES.values():
        save_score(conn, score)
    conn.close()
    at.run()

    assert list(at.dataframe[0].value["Title"])[:2] == ["Senior .NET Developer", "LLM Engineer"]
    assert "(2 scored)" in at.caption[0].value

    at.sidebar.slider[0].set_value(50).run()
    assert list(at.dataframe[0].value["Title"]) == ["Senior .NET Developer"]

    at.session_state["selected_job_id"] = "a:1"
    at.run()
    assert at.metric[0].value == "85/100"
    assert "Strong C# match." in [m.value for m in at.markdown]
