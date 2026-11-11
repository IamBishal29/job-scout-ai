"""JobPilot dashboard. Run: streamlit run app.py

Streamlit re-runs this whole script top to bottom on every interaction.
Keep it thin: data comes from jobpilot.db, rules from jobpilot.tracker, logic from jobpilot.views.
"""

import os
from dataclasses import replace

import streamlit as st

from jobpilot import cover_letter, db, llm
from jobpilot.config import ConfigError, load_config
from jobpilot.models import Job, Status, utc_now
from jobpilot.tracker import change_status, next_statuses, update_notes
from jobpilot.ui_settings import render_settings
from jobpilot.views import (
    JobFilter,
    filter_jobs,
    md_escape,
    resolve_selection,
    sort_by_score,
    to_rows,
)

st.set_page_config(page_title="JobPilot", layout="wide")
st.title("JobPilot")

try:
    config = load_config(os.environ.get("JOBPILOT_CONFIG", "config.toml"))
except ConfigError as e:
    st.error(f"Config error: {e}")
    st.stop()

conn = db.connect(config.db_path)
db.init_db(conn)  # also applies pending migrations
jobs = db.list_jobs(conn)
statuses = db.application_statuses(conn)
scores = db.get_scores(conn)

if flash := st.session_state.pop("flash", None):  # message from the previous run
    st.success(flash)


def show_detail(job: Job) -> None:
    st.subheader(job.title)
    posted = job.posted_at.date().isoformat() if job.posted_at else "unknown date"
    st.caption(f"{job.company} · {job.location} · {job.source} · posted {posted}")
    st.link_button("Open job posting", job.url)  # opens the site; you apply there yourself

    if score := scores.get(job.id):
        st.metric("Match", f"{score.score}/100")
        st.write(score.reason)
        st.caption(f"AI estimate by {score.model} on {score.scored_at.date()}. Use your judgement.")
    else:
        st.caption("Not scored yet. Run `python -m jobpilot score`.")

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

    show_cover_letter(job)

    with st.container(height=400):
        st.markdown(md_escape(job.description) or "_No description provided._")


def read_cv() -> str | None:
    try:
        return config.cv_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def show_cover_letter(job: Job) -> None:
    draft = db.get_cover_letter(conn, job.id)
    with st.expander("Cover letter draft", expanded=draft is not None):
        st.caption("Draft only: JobPilot never sends anything. Edit it, then paste it yourself.")
        cv_text = read_cv()
        if st.button("Regenerate draft" if draft else "Generate draft", key=f"gen_{job.id}"):
            if cv_text is None:
                st.error(f"CV not found at {config.cv_path}. Save your CV there as text.")
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


jobs_tab, tracker_tab, settings_tab = st.tabs(["Jobs", "Tracker", "Settings"])

with jobs_tab:
    if not jobs:  # first run: still show the tabs so Settings is reachable
        st.info(
            "No jobs yet. Add your settings in the Settings tab, then run "
            "`python -m jobpilot fetch`."
        )
    else:
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
                show_detail(selected)
            else:
                st.info("Select a row to see the full job description.")

with tracker_tab:
    tracked = db.list_applications(conn)
    if not tracked:
        st.info("Nothing tracked yet. Select a job and set its status to Saved or Applied.")
    for status in Status:
        group = [(a, j) for a, j in tracked if a.status == status]
        if group:
            st.subheader(f"{status.value.title()} ({len(group)})")
            st.dataframe(
                [
                    {
                        "Title": j.title,
                        "Company": j.company,
                        "Applied": a.applied_at.date() if a.applied_at else None,
                        "Updated": a.updated_at.date(),
                        "Notes": a.notes,
                        "Link": j.url,
                    }
                    for a, j in group
                ],
                hide_index=True,
                column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")},
            )

conn.close()

with settings_tab:
    render_settings(config)
