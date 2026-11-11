"""Jobs page: filter, rank and open jobs; track them; draft cover letters.

Moved unchanged from the old single-page app.py (#52); the card redesign comes in #54.
"""

import sqlite3
from dataclasses import replace

import streamlit as st

from jobpilot import cover_letter, db, llm
from jobpilot.config import Config, ConfigError
from jobpilot.models import Job, Score, utc_now
from jobpilot.tracker import change_status, next_statuses, update_notes
from jobpilot.ui_common import open_db
from jobpilot.views import (
    JobFilter,
    filter_jobs,
    md_escape,
    resolve_selection,
    sort_by_score,
    to_rows,
)


def render_jobs(config: Config) -> None:
    st.title("Jobs")
    with open_db(config) as conn:
        jobs = db.list_jobs(conn)
        if not jobs:  # first run: point to the next step instead of an empty table
            st.info("No jobs yet. Add your settings in Settings, then click Fetch jobs on Home.")
            return
        statuses = db.application_statuses(conn)
        scores = db.get_scores(conn)

        with st.sidebar:
            st.header("Filters")
            sources = st.multiselect("Source", sorted({j.source for j in jobs}))
            keyword = st.text_input("Keyword", placeholder="e.g. .NET, LLM, Azure")
            location = st.text_input("Location contains", placeholder="e.g. worldwide")
            min_score = st.slider("Min match score", 0, 100, 0, step=5, help="0 shows unscored too")

        job_filter = JobFilter(frozenset(sources), keyword, location, min_score)
        shown = sort_by_score(filter_jobs(jobs, job_filter, scores), scores)
        st.caption(
            f"Showing {len(shown)} of {len(jobs)} jobs ({len(scores)} scored), best match first. "
            "You always apply yourself on the site."
        )

        table_col, detail_col = st.columns([3, 2])
        with table_col:
            event = st.dataframe(
                to_rows(shown, statuses, scores),
                hide_index=True,
                column_config={
                    "Score": st.column_config.ProgressColumn(
                        "Score", min_value=0, max_value=100, format="%d"
                    ),
                    "Why": st.column_config.TextColumn("Why", width="medium"),
                    "Link": st.column_config.LinkColumn("Link", display_text="Open"),
                },
                on_select="rerun",
                selection_mode="single-row",
                key=f"jobs_table_{hash(job_filter)}",  # new filters -> fresh table selection
            )
        st.session_state.selected_job_id = resolve_selection(
            [j.id for j in shown],
            event.selection.rows if event else [],
            st.session_state.get("selected_job_id"),
        )
        with detail_col:
            selected = next((j for j in shown if j.id == st.session_state.selected_job_id), None)
            if selected:
                _show_detail(conn, config, scores, selected)
            else:
                st.info("Select a row to see the full job description.")


def _show_detail(conn: sqlite3.Connection, config: Config, scores: dict[str, Score], job: Job):
    st.subheader(job.title)
    posted = job.posted_at.date().isoformat() if job.posted_at else "unknown date"
    st.caption(f"{job.company} · {job.location} · {job.source} · posted {posted}")
    st.link_button("Open job posting", job.url)  # opens the site; you apply there yourself

    if score := scores.get(job.id):
        st.metric("Match", f"{score.score}/100")
        st.write(score.reason)
        st.caption(f"AI estimate by {score.model} on {score.scored_at.date()}. Use your judgement.")
    else:
        st.caption("Not scored yet. Click Score jobs on Home.")

    app = db.get_application(conn, job.id)
    with st.form(f"track_{job.id}"):
        new_status = st.selectbox(
            "Status", next_statuses(app.status), format_func=lambda s: s.value.title()
        )
        notes = st.text_area("Notes", app.notes, placeholder="contact, salary, next step...")
        if st.form_submit_button("Save"):
            updated = update_notes(change_status(app, new_status), notes)
            db.save_application(conn, updated)
            st.session_state.flash = f"Saved: {job.title} is now '{updated.status}'."
            st.rerun()  # redraw so the table and tracker show the new status

    _show_cover_letter(conn, config, job)

    with st.container(height=400):
        st.markdown(md_escape(job.description) or "_No description provided._")


def _read_cv(config: Config) -> str | None:
    try:
        return config.cv_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def _show_cover_letter(conn: sqlite3.Connection, config: Config, job: Job) -> None:
    draft = db.get_cover_letter(conn, job.id)
    with st.expander("Cover letter draft", expanded=draft is not None):
        st.caption("Draft only: JobPilot never sends anything. Edit it, then paste it yourself.")
        cv_text = _read_cv(config)
        if st.button("Regenerate draft" if draft else "Generate draft", key=f"gen_{job.id}"):
            if cv_text is None:
                st.error(f"CV not found at {config.cv_path}. Add it in Settings.")
                return
            try:
                client = llm.make_llm_client(config)
                letter = cover_letter.generate_draft(client, job, cv_text, config.llm_model)
            except (ConfigError, llm.LlmError) as e:
                st.error(f"Could not generate a draft: {e}")
                return
            db.save_cover_letter(conn, letter)
            st.session_state.flash = f"Draft ready for {job.title}. Check it before using it."
            st.rerun()
        if draft is None:
            return

        # key includes generated_at: a regenerated draft gets a fresh text box
        body = st.text_area(
            "Your draft", draft.body, height=300, key=f"draft_{job.id}_{draft.generated_at}"
        )
        if st.button("Save edits", key=f"save_draft_{job.id}"):
            db.save_cover_letter(conn, replace(draft, body=body, updated_at=utc_now()))
            st.session_state.flash = "Draft saved."
            st.rerun()
        if gaps := cover_letter.placeholders(body):
            st.warning("Fill in before sending: " + ", ".join(gaps))
        sources = (cv_text or "", job.title, job.description)
        if numbers := cover_letter.unsupported_numbers(body, *sources):
            st.warning("Numbers not found in your CV or the job, check them: " + ", ".join(numbers))
        st.code(body, language=None, wrap_lines=True)  # has a copy button
