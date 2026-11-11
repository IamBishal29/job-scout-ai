"""Shared start-up for every dashboard page: config, database, flash messages."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

import streamlit as st

from jobpilot import db
from jobpilot.config import Config, ConfigError, load_config


def load_app_config() -> Config:
    """config.toml (or JOBPILOT_CONFIG). Stops the page with a clear error if it's broken."""
    try:
        return load_config(os.environ.get("JOBPILOT_CONFIG", "config.toml"))
    except ConfigError as e:
        st.error(f"Config error: {e}")
        st.stop()


@contextmanager
def open_db(config: Config) -> Iterator[sqlite3.Connection]:
    """Connection for one page run; applies pending migrations; always closed."""
    conn = db.connect(config.db_path)
    try:
        db.init_db(conn)
        yield conn
    finally:
        conn.close()


ICONS = {  # one icon per message kind, used on every page
    "success": ":material/check_circle:",
    "info": ":material/info:",
    "warning": ":material/warning:",
    "error": ":material/error:",
}


def status_icon(ok: bool) -> str:
    """Coloured ✓ / ⚠ marker for markdown: set up vs. still missing."""
    return ":green[:material/check_circle:]" if ok else ":orange[:material/error:]"


def notify(kind: str, text: str) -> None:
    """st.success / info / warning / error with the matching icon."""
    getattr(st, kind)(text, icon=ICONS[kind])


def show_flash() -> None:
    """Show the message a previous run stored before calling st.rerun()."""
    if flash := st.session_state.pop("flash", None):
        notify("success", flash)
