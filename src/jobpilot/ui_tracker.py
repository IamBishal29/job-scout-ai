"""Tracker page: your applications grouped by status."""

import streamlit as st

from jobpilot import db
from jobpilot.config import Config
from jobpilot.models import Status
from jobpilot.ui_common import open_db


def render_tracker(config: Config) -> None:
    st.title("Tracker")
    with open_db(config) as conn:
        tracked = db.list_applications(conn)
    if not tracked:
        st.info("Nothing tracked yet. Open a job and set its status to Saved or Applied.")
    for status in Status:
        group = [(a, j) for a, j in tracked if a.status == status]
        if group:
            st.subheader(f"{status.value.title()} ({len(group)})")
            st.dataframe(
                [
                    {
                        "Title": j.title,
                        "Company": j.company,
                        "Applied": a.applied_at.date() if a.applied_at else None,
                        "Updated": a.updated_at.date(),
                        "Notes": a.notes,
                        "Link": j.url,
                    }
                    for a, j in group
                ],
                hide_index=True,
                column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")},
            )
