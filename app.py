"""JobPilot dashboard. Run: streamlit run app.py

Streamlit re-runs this whole script top to bottom on every interaction.
Keep it thin: data comes from jobpilot.db, logic lives in jobpilot.views.
"""

import os

import streamlit as st

from jobpilot.config import ConfigError, load_config
from jobpilot.db import connect, init_db, list_jobs
from jobpilot.views import JobFilter, filter_jobs, to_rows

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

shown = filter_jobs(jobs, JobFilter(frozenset(sources), keyword, location))
st.caption(f"Showing {len(shown)} of {len(jobs)} jobs. Applying is always done by you on the site.")
st.dataframe(
    to_rows(shown),
    hide_index=True,
    column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")},
)
