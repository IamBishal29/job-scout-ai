import io
from pathlib import Path

import pytest
from conftest import open_page
from pypdf import PdfReader, PdfWriter
from streamlit.testing.v1 import AppTest

from jobpilot.cv_import import CvImportError, clean, cv_info, extract_text, save_cv

APP = str(Path(__file__).parents[1] / "app.py")
LINES = [
    "Test Candidate - Senior .NET Developer",
    "Ten years of C#, ASP.NET Core, Azure, SQL Server and microservices.",
    "Now building LLM applications in Python: prompts, scoring, retrieval.",
    "Led a team of five engineers delivering payment and banking systems.",
]


def make_pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with a real text layer (what pypdf can read)."""
    text_ops = " ".join(f"({line}) Tj T*" for line in lines)
    content = f"BT /F1 11 Tf 72 720 Td 14 TL {text_ops} ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out


def pdf_from_writer(writer: PdfWriter) -> bytes:
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extracts_text_from_pdf():
    text = extract_text("CV.PDF", make_pdf(LINES))
    assert "Senior .NET Developer" in text and "LLM applications" in text


def test_scanned_pdf_without_text_is_rejected_with_advice():
    writer = PdfWriter()
    writer.add_blank_page(612, 792)  # what a scanned page looks like to a text extractor
    with pytest.raises(CvImportError, match="scanned PDF"):
        extract_text("scan.pdf", pdf_from_writer(writer))


def test_password_protected_pdf_is_rejected():
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(make_pdf(LINES))))
    writer.encrypt("secret")
    with pytest.raises(CvImportError, match="password-protected"):
        extract_text("cv.pdf", pdf_from_writer(writer))


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("cv.txt", "﻿".encode() + "\n".join(LINES).encode("utf-8")),  # UTF-8 with BOM
        ("cv.md", "\n".join(LINES).replace("-", "–").encode("cp1252")),  # old Windows file
    ],
)
def test_reads_text_files_in_common_encodings(name, data):
    text = extract_text(name, data)
    assert text.startswith("Test Candidate")


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("cv.docx", b"PK...", "Unsupported file type .docx"),
        ("cv.pdf", b"not a pdf at all", "Could not read"),
        ("cv.txt", b"x" * (5 * 1024 * 1024 + 1), "larger than 5 MB"),
    ],
)
def test_rejects_bad_uploads(name, data, message):
    with pytest.raises(CvImportError, match=message):
        extract_text(name, data)


def test_clean_and_save_and_info(tmp_path):
    assert clean("a  \r\n\n\n\nb\n") == "a\n\nb"
    path = tmp_path / "sub" / "cv.md"
    assert not cv_info(path).exists
    save_cv(path, "one two three\n\n\n\nfour")
    assert path.read_text(encoding="utf-8") == "one two three\n\nfour\n"
    info = cv_info(path)
    assert (info.exists, info.words) == (True, 4)


def test_upload_edit_and_save_in_settings(tmp_path, monkeypatch):
    cv_path = tmp_path / "cv.md"
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n'
        f'[llm]\ncv_path="{cv_path.as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("JOBPILOT_CONFIG", str(cfg))
    monkeypatch.setenv("JOBPILOT_ENV", str(tmp_path / ".env"))
    at = open_page(AppTest.from_file(APP, default_timeout=30).run(), "settings")
    assert any("Status: **not set**. Scoring" in m.value for m in at.markdown)

    at.file_uploader[0].upload("cv.pdf", make_pdf(LINES), "application/pdf").run()
    assert not at.error
    [box] = [t for t in at.text_area if t.label == "CV text"]
    assert "Senior .NET Developer" in box.value

    box.input(box.value.replace("five engineers", "six engineers")).run()  # user fixes a typo
    [save] = [b for b in at.button if b.label == "Save CV"]
    save.click().run()

    assert "six engineers" in cv_path.read_text(encoding="utf-8")
    assert "CV saved" in at.success[0].value
    assert any("Status: **saved**" in m.value for m in at.markdown)
