"""Jobs page: scannable job cards, filters and sorting, details in a dialog."""

import sqlite3
from dataclasses import replace

import streamlit as st

from jobpilot import cover_letter, db, llm
from jobpilot.config import Config, ConfigError
from jobpilot.models import Job, Score, Status, utc_now
from jobpilot.tracker import change_status, next_statuses, update_notes
from jobpilot.ui_common import open_db
from jobpilot.views import (
    SORTS,
    JobFilter,
    filter_jobs,
    md_escape,
    paginate,
    score_badge,
    sort_jobs,
)

STATUS_COLOURS = {
    Status.NEW: "gray",
    Status.SAVED: "blue",
    Status.APPLIED: "violet",
    Status.INTERVIEW: "orange",
    Status.OFFER: "green",
    Status.REJECTED: "red",
}


def render_jobs(config: Config) -> None:
    st.title("Jobs")
    with open_db(config) as conn:
        jobs = db.list_jobs(conn)
        if not jobs:  # first run: point to the next step instead of an empty page
            st.info("No jobs yet. Add your settings in Settings, then click Fetch jobs on Home.")
            return
        statuses = db.application_statuses(conn)
        scores = db.get_scores(conn)

        with st.sidebar:
            st.header("Filters")
            sort_by = st.radio("Sort by", SORTS, horizontal=True)
            keyword = st.text_input("Keyword", placeholder="e.g. .NET, LLM, Azure")
            min_score = st.slider("Min match score", 0, 100, 0, step=5, help="0 shows unscored too")
            location = st.text_input("Location contains", placeholder="e.g. worldwide")
            sources = st.multiselect("Source", sorted({j.source for j in jobs}))

        job_filter = JobFilter(frozenset(sources), keyword, location, min_score)
        shown = sort_jobs(filter_jobs(jobs, job_filter, scores), scores, sort_by)
        page_key = f"page_{hash((job_filter, sort_by))}"  # new filters/sort -> back to page 1
        visible, pages, page = paginate(shown, st.session_state.get(page_key, 1))
        st.caption(
            f"{len(shown)} of {len(jobs)} jobs · {len(scores)} scored by AI · "
            "you always apply yourself on the company's site."
        )
        if not shown:
            st.info("No jobs match these filters. Try a lower Min match score or fewer keywords.")

        for job in visible:
            _job_card(job, scores.get(job.id), statuses.get(job.id, Status.NEW))
        _pager(page_key, page, pages)

        if job := next((j for j in jobs if j.id == st.session_state.get("details_job")), None):
            _details_dialog(conn, config, scores, job)


def _job_card(job: Job, score: Score | None, status: Status) -> None:
    with st.container(border=True):
        badge_col, text_col, button_col = st.columns([2, 8, 2], vertical_alignment="center")
        label, colour = score_badge(score.score if score else None)
        badge_col.badge(label, color=colour)
        if status != Status.NEW:
            badge_col.badge(status.value.title(), color=STATUS_COLOURS[status])
        text_col.markdown(
            f"**{md_escape(job.title)}**  \n{md_escape(job.company)} · {job.location}"
        )
        if score:
            text_col.caption(score.reason)
        if button_col.button("Details", key=f"details_{job.id}", width="stretch"):
            st.session_state.details_job = job.id
            st.rerun()
        button_col.link_button("Open posting", job.url, width="stretch")


def _pager(key: str, page: int, pages: int) -> None:
    if pages == 1:
        return
    prev_col, info_col, next_col = st.columns([1, 2, 1], vertical_alignment="center")
    if prev_col.button("Previous", disabled=page == 1, width="stretch"):
        st.session_state[key] = page - 1
        st.rerun()
    info_col.markdown(
        f"<p style='text-align:center'>Page {page} of {pages}</p>", unsafe_allow_html=True
    )
    if next_col.button("Next", disabled=page == pages, width="stretch"):
        st.session_state[key] = page + 1
        st.rerun()


def _close_details() -> None:
    st.session_state.details_job = None


@st.dialog("Job details", width="large", on_dismiss=_close_details)
def _details_dialog(conn: sqlite3.Connection, config: Config, scores: dict[str, Score], job: Job):
    st.subheader(job.title)
    posted = job.posted_at.date().isoformat() if job.posted_at else "unknown date"
    st.caption(f"{job.company} · {job.location} · {job.source} · posted {posted}")
    st.link_button("Open job posting", job.url, type="primary")  # you apply there yourself

    if score := scores.get(job.id):
        label, colour = score_badge(score.score)
        st.badge(f"Match {label}", color=colour)
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
            st.rerun()  # redraw cards; the dialog reopens with the new status

    _show_cover_letter(conn, config, job)

    with st.expander("Job description", expanded=True), st.container(height=350):
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
