"""Pipeline actions as three cards on Home: fetch, score, digest (same actions as the CLI)."""

import streamlit as st

from jobpilot import actions
from jobpilot.config import Config
from jobpilot.ui_common import notify

SECONDS_PER_JOB = 6  # free-tier pacing (10 requests/minute), see [llm] requests_per_minute


def render_run(config: Config) -> None:
    ready = actions.readiness(config)
    if result := st.session_state.pop("run_result", None):  # outcome of the last click
        notify(*result)  # (kind, text) with the matching icon

    fetch_col, score_col, digest_col = st.columns(3)
    with fetch_col.container(border=True):
        _fetch_card(config)
    with score_col.container(border=True):
        _score_card(config, ready)
    with digest_col.container(border=True):
        _digest_card(config, ready)


def _fetch_card(config: Config) -> None:
    st.markdown("**:material/travel_explore: 1 · Find jobs**")
    st.caption("New jobs from all enabled sources. About a minute.")
    if st.button("Fetch jobs", type="primary", width="stretch"):
        with st.spinner("Fetching from job boards..."):
            results = actions.fetch_jobs(config)
        new = sum(r.new for r in results)
        errors = [f"{r.source}: {r.error}" for r in results if r.error]
        summary = f"{new} new job(s) from {len(results) - len(errors)} source(s)."
        _done("warning" if errors else "success", summary + _lines("Failed", errors))


def _score_card(config: Config, ready: actions.Readiness) -> None:
    st.markdown("**:material/auto_awesome: 2 · Score with AI**")
    missing = [n for n, ok in (("Gemini key", ready.gemini), ("CV", ready.cv)) if not ok]
    if missing:
        st.caption(f"Add your {' and '.join(missing)} in Settings first.")
    else:
        st.caption(f"About {SECONDS_PER_JOB}s per job. Scored jobs are skipped.")
    limit = st.number_input("How many jobs", 1, 100, 20, help="Free tier: keep batches small")
    if st.button("Score jobs", disabled=bool(missing), width="stretch"):
        bar = st.progress(0.0, text="Starting...")

        def progress(done: int, total: int) -> None:
            bar.progress(done / total, text=f"Scoring job {done + 1} of {total}...")

        try:
            run = actions.score_jobs(config, int(limit), on_progress=progress)
        except actions.ActionError as e:
            _done("error", str(e))
        else:
            note = f" {run.failed} failed and will retry next time." if run.failed else ""
            _done("warning" if run.failed else "success", f"Scored {run.scored} job(s).{note}")


def _digest_card(config: Config, ready: actions.Readiness) -> None:
    st.markdown("**:material/mail: 3 · Email digest**")
    if not ready.gmail:
        st.caption("Add your Gmail settings in Settings to send it.")
    else:
        st.caption(f"Your best new matches ({config.digest_min_score}+), never the same job twice.")
    if st.button("Preview digest", width="stretch"):
        built = actions.preview_digest(config)
        if built is None:
            st.info(f"Nothing new scored {config.digest_min_score}+ since the last digest.")
        else:
            with st.expander(built.subject, expanded=True):
                st.html(built.html)  # rendered here only; nothing is sent or marked
    if st.button("Send digest", disabled=not ready.gmail, width="stretch"):
        try:
            with st.spinner("Sending..."):
                built = actions.send_digest(config)
        except actions.ActionError as e:
            _done("error", str(e))
        else:
            if built is None:
                _done("info", "Nothing new to send.")
            else:
                _done("success", f"Sent: {built.subject} (jobs marked as emailed)")


def _lines(title: str, items: list[str]) -> str:
    return f"\n\n{title}: " + "; ".join(items) if items else ""


def _done(kind: str, text: str) -> None:
    """Remember the outcome and redraw, so every page shows the new data immediately."""
    st.session_state.run_result = (kind, text)
    st.rerun()
