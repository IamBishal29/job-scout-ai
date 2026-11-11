"""Tracker page: a board with one column per stage of your applications."""

from datetime import datetime

import streamlit as st

from jobpilot import db
from jobpilot.config import Config
from jobpilot.models import Status
from jobpilot.ui_common import notify, open_db
from jobpilot.views import BOARD, ago, board_columns, md_escape


def render_tracker(config: Config, now: datetime | None = None) -> None:
    st.title("Tracker")
    with open_db(config) as conn:
        tracked = db.list_applications(conn)
    if not tracked:
        notify(
            "info",
            "Nothing tracked yet. On Jobs, open a job's **Details** and set it to Saved "
            "or Applied.",
        )
        return

    columns = board_columns(tracked)
    active = sum(len(columns[s]) for s in BOARD)
    st.caption(f"{active} active application(s) · {len(columns[Status.REJECTED])} closed")

    now = now or datetime.now(tracked[0][0].updated_at.tzinfo)
    for column, status in zip(st.columns(len(BOARD)), BOARD, strict=True):
        with column:
            st.markdown(f"**{status.value.title()}** · {len(columns[status])}")
            if not columns[status]:
                st.caption("Nothing here yet")
            for app, job in columns[status]:
                _card(app, job, now)

    if rejected := columns[Status.REJECTED]:
        with st.expander(f"Rejected ({len(rejected)})"):
            for _app, job in rejected:
                st.markdown(f"~~{md_escape(job.title)}~~ · {md_escape(job.company)}")


def _card(app, job, now: datetime) -> None:
    with st.container(border=True):
        st.markdown(f"**{md_escape(job.title)}**  \n{md_escape(job.company)}")
        when = app.applied_at if app.status != Status.SAVED and app.applied_at else app.updated_at
        verb = "saved" if app.status == Status.SAVED else "applied"
        st.caption(f"{verb.title()} {ago(when, now)}")
        if app.notes:
            st.caption(f":material/sticky_note_2: {app.notes.splitlines()[0][:80]}")
        st.link_button("Open posting", job.url, width="stretch")
