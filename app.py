"""JobPilot dashboard. Run: streamlit run app.py

Streamlit re-runs this whole script top to bottom on every interaction.
Keep it thin: data comes from jobpilot.db, rules from jobpilot.tracker, logic from jobpilot.views.
"""

import os

import streamlit as st

from jobpilot import db
from jobpilot.config import ConfigError, load_config
from jobpilot.models import Job, Status
from jobpilot.tracker import change_status, next_statuses, update_notes
from jobpilot.views import JobFilter, filter_jobs, md_escape, resolve_selection, to_rows

st.set_page_config(page_title="JobPilot", layout="wide")
st.title("JobPilot")

try:
    config = load_config(os.environ.get("JOBPILOT_CONFIG", "config.toml"))
except ConfigError as e:
    st.error(f"Config error: {e}")
    st.stop()

conn = db.connect(config.db_path)
db.init_db(conn)  # also applies pending migrations
jobs = db.list_jobs(conn)
statuses = db.application_statuses(conn)

if flash := st.session_state.pop("flash", None):  # message from the previous run
    st.success(flash)

if not jobs:
    st.info("No jobs yet. Run `python -m jobpilot fetch` first.")
    st.stop()


def show_detail(job: Job) -> None:
    st.subheader(job.title)
    posted = job.posted_at.date().isoformat() if job.posted_at else "unknown date"
    st.caption(f"{job.company} · {job.location} · {job.source} · posted {posted}")
    st.link_button("Open job posting", job.url)  # opens the site; you apply there yourself

    app = db.get_application(conn, job.id)
    with st.form(f"track_{job.id}"):
        new_status = st.selectbox(
            "Status", next_statuses(app.status), format_func=lambda s: s.value.title()
        )
        notes = st.text_area("Notes", app.notes, placeholder="contact, salary, next step...")
        if st.form_submit_button("Save"):
            updated = update_notes(change_status(app, new_status), notes)
            db.save_application(conn, updated)
            st.session_state.flash = f"Saved: {job.title} is now '{updated.status}'."
            st.rerun()  # redraw so the table and tracker show the new status

    with st.container(height=400):
        st.markdown(md_escape(job.description) or "_No description provided._")


jobs_tab, tracker_tab = st.tabs(["Jobs", "Tracker"])

with jobs_tab:
    with st.sidebar:
        st.header("Filters")
        sources = st.multiselect("Source", sorted({j.source for j in jobs}))
        keyword = st.text_input("Keyword", placeholder="e.g. .NET, LLM, Azure")
        location = st.text_input("Location contains", placeholder="e.g. worldwide")

    job_filter = JobFilter(frozenset(sources), keyword, location)
    shown = filter_jobs(jobs, job_filter)
    st.caption(f"Showing {len(shown)} of {len(jobs)} jobs. You always apply yourself on the site.")

    table_col, detail_col = st.columns([3, 2])
    with table_col:
        event = st.dataframe(
            to_rows(shown, statuses),
            hide_index=True,
            column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")},
            on_select="rerun",
            selection_mode="single-row",
            key=f"jobs_table_{hash(job_filter)}",  # new filters -> fresh table selection
        )
    st.session_state.selected_job_id = resolve_selection(
        [j.id for j in shown],
        event.selection.rows if event else [],
        st.session_state.get("selected_job_id"),
    )
    with detail_col:
        selected = next((j for j in shown if j.id == st.session_state.selected_job_id), None)
        if selected:
            show_detail(selected)
        else:
            st.info("Select a row to see the full job description.")

with tracker_tab:
    tracked = db.list_applications(conn)
    if not tracked:
        st.info("Nothing tracked yet. Select a job and set its status to Saved or Applied.")
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

conn.close()
