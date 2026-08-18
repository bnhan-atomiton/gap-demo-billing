"""Configuration, read from the environment once.

Every key may also arrive as `<NAME>_FILE`, whose value is a *path* whose
contents are the value. That is how a Docker Swarm secret reaches this process
without ever appearing in a service spec — a literal there lands in the cluster's
Raft store and in the output of `docker service inspect`, readable by anyone who
can reach the daemon, and it stays there after the secret is rotated.

`<NAME>_FILE` wins when both forms are set. Rotation replaces the file; a plain
variable inherited from somewhere else would otherwise pin the old value and the
rotation would look like it had worked.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def resolve(name: str, default: str | None = None) -> str | None:
    """`<NAME>_FILE` first, then `<NAME>`, then the default."""
    path = os.environ.get(f"{name}_FILE")
    if path:
        # Stripped: a secret written by Swarm has no trailing newline and one
        # written by hand does. A DSN carrying a "\n" fails to connect, with an
        # error that says nothing about a newline.
        return Path(path).read_text(encoding="utf-8").strip()
    return os.environ.get(name, default)


#: The SQLAlchemy dialect for the driver this app actually installs.
#:
#: `pyproject.toml` pins `psycopg[binary]` — psycopg 3 — and nothing else. A DSN
#: spelled `postgresql://` selects SQLAlchemy's *default* Postgres dialect, which
#: is psycopg2, and the process dies on `import psycopg2` at first connect.
DRIVER = "psycopg"

#: What a plain Postgres URL looks like before a driver is chosen.
_BARE_SCHEME = "postgresql://"


def with_driver(dsn: str) -> str:
    """Name the installed driver in a DSN that does not already name one.

    The platform mints a plain libpq URL — `postgresql://user:pw@host:5432/db` —
    and is right to. `postgresql+psycopg://` is a SQLAlchemy spelling that
    `psycopg.connect` itself rejects, and the same secret is handed to adopted
    repos that may be on psycopg2 or asyncpg. Which driver to use is knowledge
    this app has and the platform does not.

    A DSN that already names one is left exactly as it is: someone who wrote
    `postgresql+asyncpg://` meant it, and silently rewriting it would be a
    connection to somewhere other than where they said.
    """
    if dsn.startswith(_BARE_SCHEME):
        return f"postgresql+{DRIVER}://{dsn[len(_BARE_SCHEME) :]}"
    return dsn


@dataclass(frozen=True, slots=True)
class Settings:
    """Everything this app reads from its environment.

    `PORT` is deliberately absent. The process binds it through the `uvicorn`
    command in the Dockerfile, and a second reading of it here would be a second
    source of truth for the one value the platform checks against reality.
    """

    database_url: str
    release_id: str

    @classmethod
    def from_environment(cls) -> Settings:
        database_url = resolve("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is not set. Provide it directly, or as DATABASE_URL_FILE "
                "pointing at a file containing the DSN."
            )
        # Empty rather than a guess: `/healthz` reports what it was told, and an
        # invented release id is worse than an obviously blank one — the platform
        # compares this value against the release it deployed.
        return cls(
            database_url=with_driver(database_url),
            release_id=resolve("GAP_RELEASE_ID", "") or "",
        )


@lru_cache(maxsize=1)
def settings() -> Settings:
    """Read once per process. Call `settings.cache_clear()` in a test that needs
    to change the environment underneath it."""
    return Settings.from_environment()
