"""Application tracking rules. Pure functions: no database, no UI."""

from dataclasses import replace
from datetime import datetime

from jobpilot.models import ALLOWED, Application, Status, utc_now


class InvalidTransition(ValueError):
    """Raised for a status change the state machine does not allow."""


def next_statuses(current: Status) -> list[Status]:
    """Statuses the UI may offer: the current one first, then the allowed moves in order."""
    return [current, *(s for s in Status if s in ALLOWED[current])]


def change_status(app: Application, new: Status, now: datetime | None = None) -> Application:
    """Return the application moved to `new`. Records applied_at the first time we apply."""
    if new == app.status:
        return app
    if new not in ALLOWED[app.status]:
        raise InvalidTransition(f"Cannot move from {app.status} to {new}")
    now = now or utc_now()
    applied_at = app.applied_at or (now if new == Status.APPLIED else None)
    return replace(app, status=new, applied_at=applied_at, updated_at=now)


def update_notes(app: Application, notes: str, now: datetime | None = None) -> Application:
    notes = notes.strip()
    if notes == app.notes:
        return app
    return replace(app, notes=notes, updated_at=now or utc_now())
