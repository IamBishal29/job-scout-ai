"""Home page. For now: the pipeline actions (the full Home page comes in #53)."""

import streamlit as st

from jobpilot.ui_common import load_app_config
from jobpilot.ui_run import render_run

st.title("Home")
render_run(load_app_config())
