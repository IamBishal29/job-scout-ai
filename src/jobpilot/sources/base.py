"""The contract every job source follows."""

from typing import Protocol, runtime_checkable

import httpx

from jobpilot.models import Job


@runtime_checkable
class JobSource(Protocol):
    """Anything with a SOURCE name and a fetch(client) function is a job source.

    Our source *modules* (remotive, remoteok, ...) satisfy this structurally:
    no base class or registration needed (duck typing, checked by type checkers).
    """

    SOURCE: str

    def fetch(self, client: httpx.Client) -> list[Job]: ...
