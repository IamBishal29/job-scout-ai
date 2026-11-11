"""Run tab: fetch, score and digest from the dashboard (same actions as the CLI)."""

import streamlit as st

from jobpilot import actions
from jobpilot.config import Config

SECONDS_PER_JOB = 6  # free-tier pacing (10 requests/minute), see [llm] requests_per_minute


def render_run(config: Config) -> None:
    ready = actions.readiness(config)
    if result := st.session_state.pop("run_result", None):  # outcome of the last click
        kind, text = result
        getattr(st, kind)(text)

    st.subheader("1. Fetch jobs")
    st.caption("Collects new jobs from all enabled sources. Takes about a minute.")
    if st.button("Fetch jobs"):
        with st.spinner("Fetching from job boards..."):
            results = actions.fetch_jobs(config)
        new = sum(r.new for r in results)
        errors = [f"{r.source}: {r.error}" for r in results if r.error]
        summary = f"{new} new job(s) from {len(results) - len(errors)} source(s)."
        _done("warning" if errors else "success", summary + _lines("Failed", errors))

    st.subheader("2. Score jobs against your CV")
    missing = [n for n, ok in (("Gemini key", ready.gemini), ("CV", ready.cv)) if not ok]
    if missing:
        st.info(f"Add your {' and '.join(missing)} in the Settings tab first.")
    limit = st.number_input("How many jobs", 1, 100, 20, help="Free tier: keep batches small")
    st.caption(f"About {SECONDS_PER_JOB}s per job. Already-scored jobs are skipped.")
    if st.button("Score jobs", disabled=bool(missing)):
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

    st.subheader("3. Daily digest email")
    if not ready.gmail:
        st.info("Add your Gmail settings in the Settings tab to send the digest.")
    preview_col, send_col = st.columns(2)
    if preview_col.button("Preview digest"):
        built = actions.preview_digest(config)
        if built is None:
            st.info(f"Nothing new scored {config.digest_min_score}+ since the last digest.")
        else:
            st.write(f"**{built.subject}**")
            st.html(built.html)  # rendered here only; nothing is sent or marked
    if send_col.button("Send digest", disabled=not ready.gmail):
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
    """Remember the outcome and redraw, so the Jobs tab shows the new data immediately."""
    st.session_state.run_result = (kind, text)
    st.rerun()
