"""Build the daily digest email (HTML + plain text). Sending happens elsewhere (#16)."""

import html
from dataclasses import dataclass
from datetime import datetime
from string import Template

from jobpilot.models import Job, Score

_PAGE = Template("""<!doctype html>
<html><body style="font-family:Segoe UI,Arial,sans-serif;max-width:640px;margin:auto">
<h2 style="margin-bottom:4px">JobPilot: $count new match$plural</h2>
<p style="color:#666;margin-top:0">$since</p>
$items
<p style="color:#666;font-size:12px">Scores are AI estimates. Open the dashboard to track,
draft a cover letter, and apply yourself. JobPilot never applies for you.</p>
</body></html>""")

_ITEM = Template("""<div style="border-top:1px solid #ddd;padding:10px 0">
  <div><b style="font-size:18px">$score</b>/100 &middot;
    <a href="$url">$title</a></div>
  <div style="color:#444">$company &middot; $location</div>
  <div style="color:#666;font-size:14px">$reason</div>
</div>""")


@dataclass(frozen=True, slots=True)
class Digest:
    subject: str
    html: str
    text: str
    job_ids: tuple[str, ...]


def build_digest(
    items: list[tuple[Job, Score]], now: datetime, last_sent: datetime | None
) -> Digest | None:
    """None when there is nothing new, so we never send an empty email."""
    if not items:
        return None
    count = len(items)
    plural = "" if count == 1 else "es"
    since = f"Since {last_sent:%d %b %Y %H:%M} UTC" if last_sent else "Your first digest"
    e = html.escape  # job text comes from the internet: never trust it inside HTML
    rendered = "\n".join(
        _ITEM.substitute(
            score=s.score,
            url=e(j.url, quote=True),
            title=e(j.title),
            company=e(j.company),
            location=e(j.location),
            reason=e(s.reason),
        )
        for j, s in items
    )
    text = "\n\n".join(
        f"{s.score}/100  {j.title} @ {j.company} ({j.location})\n{s.reason}\n{j.url}"
        for j, s in items
    )
    return Digest(
        subject=f"JobPilot {now:%d %b}: {count} new match{plural} (top {items[0][1].score})",
        html=_PAGE.substitute(count=count, plural=plural, since=since, items=rendered),
        text=f"JobPilot: {count} new match{plural}. {since}.\n\n{text}\n",
        job_ids=tuple(j.id for j, _ in items),
    )
