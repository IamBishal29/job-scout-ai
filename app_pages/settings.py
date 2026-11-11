"""Settings page."""

import streamlit as st

from jobpilot.ui_common import load_app_config
from jobpilot.ui_settings import render_settings

st.title("Settings")
render_settings(load_app_config())
