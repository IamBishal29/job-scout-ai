"""JobPilot dashboard. Run: streamlit run app.py

Streamlit re-runs this whole script top to bottom on every interaction.
Keep it thin: data comes from jobpilot.db, logic lives in jobpilot.views.
"""

import os

import streamlit as st

from jobpilot.config import ConfigError, load_config
from jobpilot.db import connect, init_db, list_jobs
from jobpilot.models import Job
from jobpilot.views import JobFilter, filter_jobs, md_escape, resolve_selection, to_rows

st.set_page_config(page_title="JobPilot", layout="wide")
st.title("JobPilot")

try:
    config = load_config(os.environ.get("JOBPILOT_CONFIG", "config.toml"))
except ConfigError as e:
    st.error(f"Config error: {e}")
    st.stop()

conn = connect(config.db_path)
init_db(conn)
jobs = list_jobs(conn)
conn.close()

if not jobs:
    st.info("No jobs yet. Run `python -m jobpilot fetch` first.")
    st.stop()

with st.sidebar:
    st.header("Filters")
    sources = st.multiselect("Source", sorted({j.source for j in jobs}))
    keyword = st.text_input("Keyword", placeholder="e.g. .NET, LLM, Azure")
    location = st.text_input("Location contains", placeholder="e.g. worldwide")

job_filter = JobFilter(frozenset(sources), keyword, location)
shown = filter_jobs(jobs, job_filter)
st.caption(f"Showing {len(shown)} of {len(jobs)} jobs. Applying is always done by you on the site.")


def show_detail(job: Job) -> None:
    st.subheader(job.title)
    posted = job.posted_at.date().isoformat() if job.posted_at else "unknown date"
    st.caption(f"{job.company} · {job.location} · {job.source} · posted {posted}")
    st.link_button("Open job posting", job.url)  # opens the site; you apply there yourself
    with st.container(height=500):
        st.markdown(md_escape(job.description) or "_No description provided._")


table_col, detail_col = st.columns([3, 2])
with table_col:
    event = st.dataframe(
        to_rows(shown),
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")},
        on_select="rerun",
        selection_mode="single-row",
        key=f"jobs_table_{hash(job_filter)}",  # new filters -> fresh table selection
    )

selected_rows = event.selection.rows if event else []
st.session_state.selected_job_id = resolve_selection(
    [j.id for j in shown], selected_rows, st.session_state.get("selected_job_id")
)

with detail_col:
    selected = next((j for j in shown if j.id == st.session_state.selected_job_id), None)
    if selected:
        show_detail(selected)
    else:
        st.info("Select a row to see the full job description.")
