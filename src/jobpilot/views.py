"""UI-independent view logic: filtering and table rows. No Streamlit imports here."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from jobpilot.models import Job, Status


@dataclass(frozen=True, slots=True)
class JobFilter:
    """What the user picked in the sidebar. Empty values mean "no filter"."""

    sources: frozenset[str] = frozenset()
    keyword: str = ""
    location: str = ""


def filter_jobs(jobs: Iterable[Job], f: JobFilter) -> list[Job]:
    """Keep jobs matching every non-empty filter (case-insensitive)."""
    keyword, location = f.keyword.strip().lower(), f.location.strip().lower()
    return [
        job
        for job in jobs
        if (not f.sources or job.source in f.sources)
        and (not location or location in job.location.lower())
        and (not keyword or keyword in f"{job.title} {job.company} {job.description}".lower())
    ]


def to_rows(jobs: Iterable[Job], statuses: Mapping[str, Status] | None = None) -> list[dict]:
    """Flatten jobs into table rows, in the column order the UI shows."""
    statuses = statuses or {}
    return [
        {
            "Posted": job.posted_at.date() if job.posted_at else None,
            "Status": statuses.get(job.id, Status.NEW).value,
            "Title": job.title,
            "Company": job.company,
            "Location": job.location,
            "Source": job.source,
            "Link": job.url,
        }
        for job in jobs
    ]


def resolve_selection(
    shown_ids: list[str], selected_rows: list[int], previous_id: str | None
) -> str | None:
    """Which job is selected after this rerun?

    A fresh table click wins. Otherwise keep the earlier choice (stored by id, not row
    number) as long as that job is still visible under the current filters.
    """
    if selected_rows and 0 <= selected_rows[0] < len(shown_ids):
        return shown_ids[selected_rows[0]]
    return previous_id if previous_id in shown_ids else None


_MD_SPECIAL = str.maketrans({c: "\\" + c for c in "\\`*_{}[]<>()#+-.!|$~"})


def md_escape(text: str) -> str:
    """Show text literally in st.markdown: escape Markdown symbols, keep line breaks."""
    return text.translate(_MD_SPECIAL).replace("\n", "  \n")
