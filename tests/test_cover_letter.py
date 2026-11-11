from pathlib import Path

import pytest
from conftest import open_page
from streamlit.testing.v1 import AppTest

from jobpilot import db, llm
from jobpilot.cover_letter import (
    SYSTEM_PROMPT,
    build_prompt,
    generate_draft,
    placeholders,
    unsupported_numbers,
)
from jobpilot.llm import FakeLlmClient
from jobpilot.matcher import cv_hash
from jobpilot.models import Job

APP = str(Path(__file__).parents[1] / "app.py")
CV = "Syed. Senior .NET developer, 10 years C#, ASP.NET Core, Azure. Built 3 internal tools."
JOB = Job(
    "a:1", "t", "Senior .NET Engineer", "Acme", "Remote", "https://a/1", "5+ years C#. Kafka."
)
DRAFT = "Dear [Hiring Manager],\nI bring 10 years of C# and led 12 projects at Acme.\n[Your Name]"


def test_prompt_has_grounding_rules_cv_and_job():
    prompt = build_prompt(JOB, CV)
    assert CV in prompt and "Senior .NET Engineer" in prompt and "Kafka" in prompt
    assert "ONLY facts stated in the CV" in SYSTEM_PROMPT
    assert "Never invent" in SYSTEM_PROMPT


def test_generate_draft_uses_system_prompt_and_records_cv_version():
    fake = FakeLlmClient(["  Dear [Hiring Manager], ...  "])
    letter = generate_draft(fake, JOB, CV, "m")
    assert letter.body == "Dear [Hiring Manager], ..."
    assert (letter.job_id, letter.model, letter.cv_hash) == ("a:1", "m", cv_hash(CV))
    assert fake.prompts == [build_prompt(JOB, CV)]


def test_placeholders_listed_once():
    assert placeholders(DRAFT + " [Hiring Manager]") == ["[Hiring Manager]", "[Your Name]"]


def test_unsupported_numbers_flags_invented_claims():
    assert unsupported_numbers(DRAFT, CV, JOB.description) == ["12"]  # 10 is in the CV
    assert unsupported_numbers("No numbers here.", CV) == []


@pytest.fixture
def app(tmp_path, monkeypatch):
    cv = tmp_path / "cv.md"
    cv.write_text(CV, encoding="utf-8")
    conn = db.connect(tmp_path / "j.db")
    db.init_db(conn)
    db.insert_jobs(conn, [JOB])
    conn.close()
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[search]\nrole_keywords=["x"]\nlocations=["remote"]\n[sources]\nenabled=["remotive"]\n'
        f'[database]\npath="{(tmp_path / "j.db").as_posix()}"\n[llm]\ncv_path="{cv.as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("JOBPILOT_CONFIG", str(cfg))
    monkeypatch.setattr(llm, "make_llm_client", lambda c: FakeLlmClient([DRAFT]))
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["details_job"] = "a:1"  # open the details dialog
    return open_page(at.run(), "jobs"), tmp_path / "j.db"


def test_generate_save_edit_and_warnings_in_app(app):
    at, db_path = app
    at.button(key="gen_a:1").click().run()
    assert not at.exception
    assert "Draft ready" in at.success[0].value

    warnings = " ".join(w.value for w in at.warning)
    assert "[Hiring Manager]" in warnings and "12" in warnings
    assert at.code[0].value == DRAFT

    at.text_area[1].input("Dear Ms Rahman,\nI bring 10 years of C#.").run()
    at.button(key="save_draft_a:1").click().run()
    conn = db.connect(db_path)
    assert db.get_cover_letter(conn, "a:1").body.startswith("Dear Ms Rahman")
    conn.close()
    assert not at.warning  # placeholders filled, numbers grounded
