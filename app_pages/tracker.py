"""Tracker page."""

from jobpilot.ui_common import load_app_config
from jobpilot.ui_tracker import render_tracker

render_tracker(load_app_config())
