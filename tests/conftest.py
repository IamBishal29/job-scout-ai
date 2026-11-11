import json
from pathlib import Path

import httpx

from jobpilot.sources.http import make_client

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text("utf-8"))


def mock_client(status: int, payload, seen: list[httpx.Request] | None = None) -> httpx.Client:
    """An httpx client that never hits the network: every request returns `payload`."""

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler), headers=make_client().headers)
