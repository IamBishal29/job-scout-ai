"""JobPilot dashboard. Run: streamlit run app.py

This file only sets up the window and the sidebar menu. Each page in app_pages/ is a few lines
that call a render function in the jobpilot package, where the real (tested) code lives.
"""

import streamlit as st

from jobpilot.ui_common import show_flash

st.set_page_config(page_title="JobPilot", page_icon=":material/work:", layout="wide")

page = st.navigation(
    [
        st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("app_pages/jobs.py", title="Jobs", icon=":material/work:"),
        st.Page("app_pages/tracker.py", title="Tracker", icon=":material/view_kanban:"),
        st.Page("app_pages/settings.py", title="Settings", icon=":material/settings:"),
    ]
)
with st.sidebar:
    st.caption("JobPilot finds and prepares. You review and apply yourself.")

show_flash()  # message stored by the previous run (e.g. "Saved")
page.run()
