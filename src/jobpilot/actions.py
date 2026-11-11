"""The pipeline actions, shared by the CLI (__main__) and the dashboard (Run tab).

Each action returns data, never prints, and turns expected problems into ActionError
with a message a user can act on. One implementation, two front ends.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass

from jobpilot import db, llm, mailer, matcher
from jobpilot.config import Config, ConfigError, get_secret
from jobpilot.digest import Digest, build_digest
from jobpilot.env_store import load_env
from jobpilot.models import utc_now
from jobpilot.pipeline import SourceResult, run_fetch
from jobpilot.sources.http import make_client


class ActionError(Exception):
    """Expected problem (missing CV, key, Gmail...). The message is shown to the user."""


@dataclass(frozen=True, slots=True)
class Readiness:
    gemini: bool
    cv: bool
    gmail: bool


def readiness(config: Config) -> Readiness:
    load_env()
    return Readiness(
        gemini=bool(os.environ.get("GEMINI_API_KEY")),
        cv=config.cv_path.exists(),
        gmail=all(os.environ.get(n) for n in ("SMTP_USER", "SMTP_APP_PASSWORD", "DIGEST_TO")),
    )


def fetch_jobs(config: Config) -> list[SourceResult]:
    conn = db.connect(config.db_path)
    try:
        db.init_db(conn)
        with make_client() as client:
            return run_fetch(conn, config, client)
    finally:
        conn.close()


def score_jobs(
    config: Config, limit: int, on_progress: Callable[[int, int], None] | None = None
) -> matcher.ScoreRun:
    try:
        cv_text = config.cv_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise ActionError(f"CV not found at {config.cv_path}. Add it in Settings.") from e
    try:
        client = llm.make_llm_client(config)
    except ConfigError as e:
        raise ActionError(str(e)) from e
    conn = db.connect(config.db_path)
    try:
        db.init_db(conn)
        return matcher.score_jobs(
            conn, client, cv_text, config, limit, config.llm_model, on_progress=on_progress
        )
    finally:
        conn.close()


def preview_digest(config: Config) -> Digest | None:
    """Build the digest without sending or marking anything (dry run)."""
    conn = db.connect(config.db_path)
    try:
        db.init_db(conn)
        items = db.digest_candidates(conn, config.digest_min_score, config.digest_top_n)
        return build_digest(items, utc_now(), db.last_digest_at(conn))
    finally:
        conn.close()


def send_digest(config: Config) -> Digest | None:
    """Build -> send -> mark. Marking only after a successful send makes reruns safe."""
    built = preview_digest(config)
    if built is None:
        return None
    try:
        sender = get_secret("SMTP_USER")
        message = mailer.build_message(built, sender, get_secret("DIGEST_TO"))
        mailer.send_message(message, sender, get_secret("SMTP_APP_PASSWORD"))
    except (ConfigError, mailer.MailError) as e:
        raise ActionError(f"Digest not sent: {e}") from e
    conn = db.connect(config.db_path)
    try:
        db.mark_digested(conn, built.job_ids, utc_now())
    finally:
        conn.close()
    return built
