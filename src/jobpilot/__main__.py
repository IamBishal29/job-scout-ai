"""Command line: `python -m jobpilot fetch | score | llm-check`."""

import argparse
import logging
import sys
from collections.abc import Sequence

from jobpilot import __version__, llm, matcher
from jobpilot.config import DEFAULT_CONFIG_PATH, Config, ConfigError, load_config
from jobpilot.db import connect, init_db
from jobpilot.pipeline import SourceResult, run_fetch
from jobpilot.sources.http import make_client


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobpilot", description="JobPilot job search helper")
    parser.add_argument("--version", action="version", version=f"JobPilot {__version__}")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="path to config.toml")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("fetch", help="fetch jobs from all enabled sources into the database")
    commands.add_parser("llm-check", help="send one tiny prompt to check your Gemini key/model")
    score_cmd = commands.add_parser("score", help="score unscored jobs against your CV (LLM)")
    score_cmd.add_argument("--limit", type=int, default=20, help="max jobs per run (default 20)")
    args = parser.parse_args(argv)

    if args.command is None:
        print(f"JobPilot {__version__}")
        parser.print_help()
        return 0

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    try:
        config = load_config(args.config)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2

    if args.command == "llm-check":
        return llm_check(config)
    if args.command == "score":
        return score(config, args.limit)

    conn = connect(config.db_path)
    try:
        init_db(conn)
        with make_client() as client:
            results = run_fetch(conn, config, client)
    finally:
        conn.close()
    print(format_results(results))
    return 1 if all(r.error for r in results) else 0


def llm_check(config: Config) -> int:
    """Prove the API key and model work, without ever printing the key."""
    try:
        reply = llm.make_llm_client(config).generate("Reply with exactly: JobPilot OK")
    except (ConfigError, llm.LlmError) as e:
        print(f"LLM check failed: {e}", file=sys.stderr)
        return 1
    print(f"Model {config.llm_model} replied: {reply}")
    return 0


def score(config: Config, limit: int) -> int:
    """Score up to `limit` new jobs against the CV. Already-scored jobs are skipped (cached)."""
    try:
        cv_text = config.cv_path.read_text(encoding="utf-8")
        client = llm.make_llm_client(config)
    except FileNotFoundError:
        print(f"CV not found at {config.cv_path}. Save your CV there as text.", file=sys.stderr)
        return 2
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 2
    conn = connect(config.db_path)
    try:
        init_db(conn)
        run = matcher.score_jobs(conn, client, cv_text, config, limit, config.llm_model)
    finally:
        conn.close()
    print(f"Scored {run.scored} job(s), {run.failed} failed (failed ones retry next run).")
    return 1 if run.failed and not run.scored else 0


def format_results(results: list[SourceResult]) -> str:
    lines = [f"{'source':<16}{'fetched':>8}{'matched':>9}{'new':>6}"]
    for r in results:
        if r.error:
            lines.append(f"{r.source:<16}  ERROR: {r.error}")
        else:
            lines.append(f"{r.source:<16}{r.fetched:>8}{r.matched:>9}{r.new:>6}")
    total = [sum(getattr(r, f) for r in results) for f in ("fetched", "matched", "new")]
    lines.append(f"{'total':<16}{total[0]:>8}{total[1]:>9}{total[2]:>6}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
