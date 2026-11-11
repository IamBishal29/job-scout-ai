"""Save secrets entered in the UI to the local .env file (ADR 0004).

.env stays the single source of truth: the CLI, the scheduler and the UI all read it.
"""

import os
import re
from pathlib import Path


def env_path() -> Path:
    """Where .env lives. JOBPILOT_ENV overrides it (used by tests)."""
    return Path(os.environ.get("JOBPILOT_ENV", ".env"))


def save_secrets(values: dict[str, str], path: Path | None = None) -> None:
    """Insert or update KEY=value lines, keeping every other line and comment.

    Also updates os.environ, because load_dotenv() never overrides an existing variable:
    without this the running app would keep using the old value until restarted.
    """
    path = path or env_path()
    for key, value in values.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError(f"invalid setting name {key!r}")
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} must be a single line")  # no smuggling in extra settings

    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pending = dict(values)
    for i, line in enumerate(lines):
        match = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if match and match.group(1) in pending:
            key = match.group(1)
            lines[i] = f"{key}={_quote(pending.pop(key))}"
    lines += [f"{key}={_quote(value)}" for key, value in pending.items()]

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.replace(tmp, path)  # atomic: a crash never leaves a half-written .env
    os.environ.update(values)


def secret_status(name: str) -> str | None:
    """'set (…abcd)' style hint for the UI, or None. Never returns the secret itself."""
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    return f"set (ends with {value[-4:]})" if len(value) >= 12 else "set"


def _quote(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_\-.@:/+]*", value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
