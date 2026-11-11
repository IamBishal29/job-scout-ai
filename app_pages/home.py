"""Home page."""

from jobpilot.ui_common import load_app_config
from jobpilot.ui_home import render_home

render_home(load_app_config())
