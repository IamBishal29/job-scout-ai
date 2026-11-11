"""Load settings from config.toml and secrets from the environment / .env."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_CONFIG_PATH = Path("config.toml")
KNOWN_SOURCES = frozenset({"remotive", "remoteok", "arbeitnow", "weworkremotely"})


class ConfigError(Exception):
    """Raised when config.toml or a required secret is missing or invalid."""


@dataclass(frozen=True, slots=True)
class SearchConfig:
    role_keywords: tuple[str, ...]
    locations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Config:
    search: SearchConfig
    sources: tuple[str, ...]
    db_path: Path


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
        ),
        sources=tuple(sources),
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


def _string_list(table: dict, key: str, section: str) -> list[str]:
    value = table.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"[{section}].{key} must be a non-empty list of strings")
    return value
