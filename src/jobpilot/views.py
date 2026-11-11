"""UI-independent view logic: filtering and table rows. No Streamlit imports here."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from jobpilot.models import Job, Score, Status


@dataclass(frozen=True, slots=True)
class JobFilter:
    """What the user picked in the sidebar. Empty values mean "no filter"."""

    sources: frozenset[str] = frozenset()
    keyword: str = ""
    location: str = ""
    min_score: int = 0  # 0 = show everything, including jobs not scored yet


def filter_jobs(
    jobs: Iterable[Job], f: JobFilter, scores: Mapping[str, Score] | None = None
) -> list[Job]:
    """Keep jobs matching every non-empty filter (case-insensitive).

    With min_score > 0 only scored jobs at or above it remain: an unscored job has no
    evidence of fit yet, so it must not sneak past a quality bar.
    """
    keyword, location = f.keyword.strip().lower(), f.location.strip().lower()
    scores = scores or {}
    return [
        job
        for job in jobs
        if (not f.min_score or (job.id in scores and scores[job.id].score >= f.min_score))
        and (not f.sources or job.source in f.sources)
        and (not location or location in job.location.lower())
        and (not keyword or keyword in f"{job.title} {job.company} {job.description}".lower())
    ]


def sort_by_score(jobs: Iterable[Job], scores: Mapping[str, Score]) -> list[Job]:
    """Best match first; unscored jobs after, keeping their existing (newest-first) order."""
    return sorted(jobs, key=lambda j: -scores[j.id].score if j.id in scores else 1)


def to_rows(
    jobs: Iterable[Job],
    statuses: Mapping[str, Status] | None = None,
    scores: Mapping[str, Score] | None = None,
) -> list[dict]:
    """Flatten jobs into table rows, in the column order the UI shows."""
    statuses, scores = statuses or {}, scores or {}
    return [
        {
            "Score": scores[job.id].score if job.id in scores else None,
            "Posted": job.posted_at.date() if job.posted_at else None,
            "Status": statuses.get(job.id, Status.NEW).value,
            "Title": job.title,
            "Company": job.company,
            "Location": job.location,
            "Source": job.source,
            "Why": scores[job.id].reason if job.id in scores else "",
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


STRONG_MATCH = 75  # score at/above which a job counts as a strong match
APPLIED_STAGES = frozenset({Status.APPLIED, Status.INTERVIEW, Status.OFFER})


@dataclass(frozen=True, slots=True)
class Stats:
    jobs: int
    scored: int
    strong: int
    applications: int
    interviews: int


def summarize(job_count: int, scores: Mapping[str, Score], statuses: Mapping[str, Status]) -> Stats:
    """The Home page numbers. Pure: easy to test, no database or UI."""
    return Stats(
        jobs=job_count,
        scored=len(scores),
        strong=sum(s.score >= STRONG_MATCH for s in scores.values()),
        applications=sum(st in APPLIED_STAGES for st in statuses.values()),
        interviews=sum(st in (Status.INTERVIEW, Status.OFFER) for st in statuses.values()),
    )


def top_matches(
    jobs: Iterable[Job],
    scores: Mapping[str, Score],
    statuses: Mapping[str, Status],
    n: int = 5,
) -> list[tuple[Job, Score]]:
    """Best scored jobs you haven't rejected yet, highest first."""
    candidates = [
        (job, scores[job.id])
        for job in jobs
        if job.id in scores and statuses.get(job.id) != Status.REJECTED
    ]
    return sorted(candidates, key=lambda pair: -pair[1].score)[:n]


def greeting(hour: int) -> str:
    if hour < 12:
        return "Good morning"
    return "Good afternoon" if hour < 18 else "Good evening"
