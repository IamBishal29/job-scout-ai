"""Turn an uploaded CV (PDF / TXT / MD) into plain text and save it as the CV file.

Pure functions, no Streamlit: the UI shows the result for the user to correct before saving.
"""

import io
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_BYTES = 5 * 1024 * 1024  # a CV is never this big; protects against wrong uploads
SUPPORTED = (".pdf", ".txt", ".md")


class CvImportError(ValueError):
    """The file can't be turned into CV text. The message says what to do instead."""


@dataclass(frozen=True, slots=True)
class CvInfo:
    exists: bool
    updated_at: datetime | None = None
    words: int = 0


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise CvImportError("File is larger than 5 MB. Upload the CV itself, not a portfolio.")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise CvImportError(f"Unsupported file type {suffix or '(none)'}. Use PDF, TXT or MD.")
    text = _pdf_text(data) if suffix == ".pdf" else _decode(data)
    text = clean(text)
    if len(text.split()) < 20:
        raise CvImportError(
            "Almost no text found. If this is a scanned PDF (an image), export your CV as a "
            "text-based PDF or paste it into a .txt file instead."
        )
    return text


def clean(text: str) -> str:
    """Trim trailing spaces and collapse runs of blank lines that PDF extraction leaves."""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def save_cv(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(clean(text) + "\n", encoding="utf-8")
    os.replace(tmp, path)  # atomic: a crash never leaves half a CV


def cv_info(path: Path) -> CvInfo:
    if not path.exists():
        return CvInfo(exists=False)
    updated = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    return CvInfo(True, updated, len(path.read_text(encoding="utf-8").split()))


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise CvImportError("This PDF is password-protected. Save an unprotected copy first.")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except PdfReadError as e:
        raise CvImportError(f"Could not read this PDF ({type(e).__name__}).") from e


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")  # also strips the BOM Notepad sometimes adds
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")  # older Windows text files
