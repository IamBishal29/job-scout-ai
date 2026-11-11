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
_ESCAPED_TAG = re.compile(r"&lt;/?(p|div|span|br|ul|ol|li|h\d|strong|b|em|a)\b", re.IGNORECASE)


def make_client() -> httpx.Client:
    """An HTTP client with a polite User-Agent and a timeout. Use it in a `with` block."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
    )


def html_to_text(raw: str) -> str:
    """Very small HTML-to-text: keep paragraph breaks, drop tags, decode entities.

    Also handles HTML that arrives escaped ("&lt;p&gt;"), which some APIs send.
    """
    raw = raw or ""
    if _ESCAPED_TAG.search(raw):
        raw = html.unescape(raw)
    text = _BLOCK_END.sub("\n", raw)
    text = html.unescape(_TAG.sub("", text))
    return _BLANK_LINES.sub("\n\n", text).strip()


def fix_mojibake(text: str) -> str:
    """Repair UTF-8 text that was wrongly decoded as Latin-1 (e.g. "â" -> "—")."""
    if "â" not in text and "Ã" not in text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
