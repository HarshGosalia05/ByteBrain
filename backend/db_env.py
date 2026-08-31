"""Dependency-free database connection configuration loader.

Reads DB_* connection values from the repository-root ``.env.local`` / ``.env``
(the same convention ``app.core.config.Settings`` uses) and the process
environment, with the process environment taking precedence over the files --
matching pydantic-settings behaviour.  No credential or hostname is hardcoded.

This module imports only the standard library so it can be imported from any
Python environment (backend venv, ml venv, or a one-off utility script) without
pulling in the ``etl``/``app`` packages or any third-party driver.
"""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

ENV_FILES = tuple(
    str(p) for p in (REPO_ROOT / ".env.local", REPO_ROOT / ".env") if p.exists()
)


def _dot_env_values() -> dict:
    values = {}
    for path in ENV_FILES:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    values[key.strip()] = val.strip().strip("\"'")
        except OSError:
            continue
    return values


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    name: str
    user: str
    password: str


def db_config() -> DbConfig:
    """Resolve the database connection configuration, failing closed.

    Raises RuntimeError when no DB_PASSWORD can be resolved, so no script ever
    connects without credentials or falls back to a hardcoded secret.
    """
    file_values = _dot_env_values()

    def pick(key: str, default: str) -> str:
        return os.getenv(key) or file_values.get(key) or default

    host = pick("DB_HOST", "localhost")
    port = int(pick("DB_PORT", "5432"))
    name = pick("DB_NAME", "postgres")
    user = pick("DB_USER", "postgres")
    password = pick("DB_PASSWORD", "")

    if not password:
        raise RuntimeError(
            "DB_PASSWORD is not set. Provide it via the environment or "
            f"{REPO_ROOT / '.env.local'}."
        )

    return DbConfig(host=host, port=port, name=name, user=user, password=password)