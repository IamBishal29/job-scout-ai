"""Home page: what to do next, how the search is going, one-click actions, top matches."""

from datetime import datetime

import streamlit as st

from jobpilot import actions, db
from jobpilot.config import Config
from jobpilot.ui_common import open_db
from jobpilot.ui_run import render_run
from jobpilot.views import STRONG_MATCH, greeting, summarize, top_matches

SETTINGS = "app_pages/settings.py"
JOBS = "app_pages/jobs.py"


def render_home(config: Config, now: datetime | None = None) -> None:
    st.title(f"{greeting((now or datetime.now()).hour)}!")
    st.caption("Here's your job search at a glance. JobPilot prepares; you apply.")
    _setup_checklist(actions.readiness(config))

    with open_db(config) as conn:
        jobs = db.list_jobs(conn)
        scores = db.get_scores(conn)
        statuses = db.application_statuses(conn)
    stats = summarize(len(jobs), scores, statuses)

    cards = st.columns(4)
    for col, (label, value, hint) in zip(
        cards,
        [
            ("Jobs found", stats.jobs, "Matching your roles and locations"),
            ("Scored by AI", stats.scored, "Ranked against your CV"),
            ("Strong matches", stats.strong, f"Score {STRONG_MATCH}+"),
            ("Applications", stats.applications, f"{stats.interviews} at interview or offer"),
        ],
        strict=True,
    ):
        col.metric(label, value, help=hint, border=True)

    st.subheader("Actions")
    render_run(config)

    st.subheader("Top matches")
    if not jobs:
        st.info("No jobs yet. Click **Fetch jobs** above to get started.")
        return
    best = top_matches(jobs, scores, statuses)
    if not best:
        st.info("Jobs are in. Click **Score jobs** to see which ones fit your CV best.")
        return
    for job, score in best:
        with st.container(border=True):
            score_col, text_col = st.columns([1, 9])
            score_col.markdown(f"### {score.score}")
            text_col.markdown(f"**{job.title}**  \n{job.company} · {job.location}")
            text_col.caption(score.reason)
    st.page_link(JOBS, label="See all jobs", icon=":material/arrow_forward:")


def _setup_checklist(ready: actions.Readiness) -> None:
    steps = [("Gemini key", ready.gemini), ("CV", ready.cv), ("Gmail (optional)", ready.gmail)]
    if all(done for _, done in steps):
        st.success("All set: AI scoring, cover letters and the daily email are ready.")
        return
    with st.container(border=True):
        st.markdown("**Finish setting up**")
        cols = st.columns(len(steps) + 1)
        for col, (name, done) in zip(cols, steps, strict=False):
            icon = (
                ":green[:material/check_circle:]"
                if done
                else ":gray[:material/radio_button_unchecked:]"
            )
            col.markdown(f"{icon} {name}")
        cols[-1].page_link(SETTINGS, label="Open Settings", icon=":material/settings:")
