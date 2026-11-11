"""Load settings from config.toml and secrets from the environment / .env."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_CONFIG_PATH = Path("config.toml")
DEFAULT_LLM_MODEL = "gemini-flash-latest"  # Google alias for the current Flash model
KNOWN_SOURCES = frozenset(
    {"remotive", "remoteok", "arbeitnow", "weworkremotely", "greenhouse", "lever", "alerts"}
)
BOARD_SOURCES = ("greenhouse", "lever")  # sources configured with a list of companies


class ConfigError(Exception):
    """Raised when config.toml or a required secret is missing or invalid."""


@dataclass(frozen=True, slots=True)
class SearchConfig:
    role_keywords: tuple[str, ...]
    locations: tuple[str, ...]
    exclude_locations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Config:
    search: SearchConfig
    sources: tuple[str, ...]
    db_path: Path
    boards: dict[str, tuple[str, ...]] = field(default_factory=dict)
    llm_model: str = DEFAULT_LLM_MODEL
    llm_requests_per_minute: int = 10
    cv_path: Path = Path("cv.md")
    based_in: str = ""
    digest_top_n: int = 10
    digest_min_score: int = 60
    alerts_folder: str = "JobAlerts"
    alerts_days: int = 7


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> Config:
    """Read and validate config.toml. Raises ConfigError with a helpful message."""
    path = Path(path)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError as e:
        raise ConfigError(f"Config file not found: {path}") from e
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {path}: {e}") from e

    search = data.get("search", {})
    sources = _string_list(data.get("sources", {}), "enabled", "sources")
    unknown = set(sources) - KNOWN_SOURCES
    if unknown:
        raise ConfigError(f"Unknown sources in [sources].enabled: {sorted(unknown)}")

    return Config(
        search=SearchConfig(
            role_keywords=tuple(k.lower() for k in _string_list(search, "role_keywords", "search")),
            locations=tuple(k.lower() for k in _string_list(search, "locations", "search")),
            exclude_locations=tuple(
                k.lower()
                for k in _string_list(search, "exclude_locations", "search", optional=True)
            ),
        ),
        sources=tuple(sources),
        boards={
            name: tuple(_string_list(data.get("boards", {}), name, "boards", optional=True))
            for name in BOARD_SOURCES
        },
        llm_model=str(data.get("llm", {}).get("model") or DEFAULT_LLM_MODEL),
        llm_requests_per_minute=int(data.get("llm", {}).get("requests_per_minute", 10)),
        cv_path=Path(data.get("llm", {}).get("cv_path", "cv.md")),
        based_in=str(data.get("profile", {}).get("based_in", "")),
        digest_top_n=int(data.get("digest", {}).get("top_n", 10)),
        digest_min_score=int(data.get("digest", {}).get("min_score", 60)),
        alerts_folder=str(data.get("alerts", {}).get("imap_folder", "JobAlerts")),
        alerts_days=int(data.get("alerts", {}).get("days", 7)),
        db_path=Path(data.get("database", {}).get("path", "data/jobpilot.db")),
    )


def get_secret(name: str, env_file: Path | str = ".env") -> str:
    """Return a secret from the environment, loading .env first if it exists.

    Real environment variables win over .env values (override=False).
    """
    load_dotenv(env_file, override=False)
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"Missing secret {name}. Add it to .env (see .env.example).")
    return value


def _string_list(table: dict, key: str, section: str, optional: bool = False) -> list[str]:
    value = table.get(key)
    if optional and value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"[{section}].{key} must be a list of strings")
    if not value and not optional:
        raise ConfigError(f"[{section}].{key} must be a non-empty list of strings")
    return value
