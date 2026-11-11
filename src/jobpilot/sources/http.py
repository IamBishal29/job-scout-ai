"""Shared HTTP helpers for all job sources."""

import html
import re

import httpx

from jobpilot import __version__

USER_AGENT = f"JobPilot/{__version__} (personal job search tool)"
TIMEOUT_SECONDS = 20.0

_TAG = re.compile(r"<[^>]+>")
_BLOCK_END = re.compile(r"</(p|div|li|h\d)>|<br\s*/?>", re.IGNORECASE)
_BLANK_LINES = re.compile(r"\n\s*\n+")


def make_client() -> httpx.Client:
    """An HTTP client with a polite User-Agent and a timeout. Use it in a `with` block."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def html_to_text(raw: str) -> str:
    """Very small HTML-to-text: keep paragraph breaks, drop tags, decode entities."""
    text = _BLOCK_END.sub("\n", raw or "")
    text = html.unescape(_TAG.sub("", text))
    return _BLANK_LINES.sub("\n\n", text).strip()
