"""Jobs page."""

from jobpilot.ui_common import load_app_config
from jobpilot.ui_jobs import render_jobs

render_jobs(load_app_config())
