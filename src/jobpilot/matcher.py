"""Score jobs against my CV with an LLM. Structured JSON out, validated, cached in SQLite."""

import hashlib
import json
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass

from jobpilot import db
from jobpilot.config import Config
from jobpilot.llm import LlmClient, LlmError
from jobpilot.models import Job, Score

log = logging.getLogger(__name__)

MAX_DESCRIPTION_CHARS = 6000  # long postings cost tokens and rarely add signal at the end

SYSTEM_PROMPT = """You are an experienced technical recruiter.
Judge how well ONE job fits ONE candidate. Be strict and realistic.
Scoring guide:
- 80-100: strong fit; candidate could apply today
- 50-79: partial fit; some gaps or a stretch
- 0-49: poor fit, OR the candidate cannot take it (e.g. location/visa/timezone restriction)
Answer ONLY with JSON: {"score": <integer 0-100>, "reason": "<max 2 short sentences>"}"""


class ScoreError(ValueError):
    """The model's reply was not a valid score."""


@dataclass(frozen=True, slots=True)
class ScoreRun:
    scored: int = 0
    failed: int = 0


def cv_hash(cv_text: str) -> str:
    return hashlib.sha1(cv_text.strip().encode("utf-8")).hexdigest()[:12]


def build_prompt(job: Job, cv_text: str, config: Config) -> str:
    description = job.description[:MAX_DESCRIPTION_CHARS]
    roles = ", ".join(config.search.role_keywords)
    return f"""## Candidate
Based in: {config.based_in or "not specified"} (can only take jobs open to this location)
Target roles: {roles}

### CV
{cv_text.strip()}

## Job
Title: {job.title}
Company: {job.company}
Location: {job.location}

### Description
{description}"""


def parse_score(text: str) -> tuple[int, str]:
    """Validate the model's JSON. Raises ScoreError instead of storing garbage."""
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ScoreError(f"not JSON: {text[:80]!r}") from e
    if not isinstance(data, dict):
        raise ScoreError("JSON is not an object")
    score, reason = data.get("score"), data.get("reason")
    if isinstance(score, bool) or not isinstance(score, int | float) or not 0 <= score <= 100:
        raise ScoreError(f"score must be a number 0-100, got {score!r}")
    if not isinstance(reason, str) or not reason.strip():
        raise ScoreError("reason must be a non-empty string")
    return round(score), reason.strip()[:300]


def score_jobs(
    conn: sqlite3.Connection,
    llm: LlmClient,
    cv_text: str,
    config: Config,
    limit: int,
    model: str,
    sleep: Callable[[float], None] = time.sleep,
) -> ScoreRun:
    """Score up to `limit` unscored jobs. Failures stay unscored and are retried next run."""
    pause = 60.0 / max(config.llm_requests_per_minute, 1)
    version = cv_hash(cv_text)
    scored = failed = 0
    for i, job in enumerate(db.unscored_jobs(conn, limit)):
        if i:
            sleep(pause)  # pace requests to respect the free tier per-minute quota
        try:
            reply = llm.generate(
                build_prompt(job, cv_text, config), system=SYSTEM_PROMPT, json_output=True
            )
            value, reason = parse_score(reply)
        except (LlmError, ScoreError) as e:
            log.warning("Could not score %s: %s", job.id, e)
            failed += 1
            continue
        db.save_score(conn, Score(job.id, value, reason, model, version))
        scored += 1
    return ScoreRun(scored, failed)
