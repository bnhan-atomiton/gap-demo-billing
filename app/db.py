"""The engine, the request-scoped session, and Postgres errors as HTTP ones.

The error translation lives here rather than in each router because it is
database knowledge, not routing knowledge, and because repeating a `try` /
`except IntegrityError` around every write in every router is five identical
blocks per table that will drift the first time one of them is edited.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.settings import settings

#: SQLSTATE → the status a *write* deserves. Postgres codes, class 23,
#: "integrity constraint violation".
_WRITE_STATUS: dict[str, int] = {
    "23502": 422,  # not_null_violation — a PATCH sent an explicit null
    "23503": 422,  # foreign_key_violation — the row this one points at is absent
    "23505": 409,  # unique_violation — something equal to this already exists
    "23514": 422,  # check_violation
}

#: The one code whose meaning depends on the verb. On a write, 23503 says the
#: parent is missing and the *request* is wrong. On a delete it says a child
#: still points here and an `ON DELETE RESTRICT` is holding — the request was
#: well formed and the current state refuses it, which is what 409 means.
_DELETE_OVERRIDE: dict[str, int] = {"23503": 409}


def integrity_status(sqlstate: str | None, method: str) -> int:
    """Map a constraint violation to a status code.

    An unrecognised SQLSTATE stays a 500 on purpose. A constraint nobody mapped
    is a bug in this application, and answering 4xx would tell the caller to fix
    a request that was fine.
    """
    if sqlstate is None:
        return 500
    if method.upper() == "DELETE" and sqlstate in _DELETE_OVERRIDE:
        return _DELETE_OVERRIDE[sqlstate]
    return _WRITE_STATUS.get(sqlstate, 500)


async def integrity_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Registered in `main.py` for `IntegrityError`.

    The signature is widened to `Exception` because that is what Starlette's
    handler registry is typed to accept; the registration is what narrows it.
    """
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    status = integrity_status(sqlstate, request.method)
    detail = (
        "the request conflicts with data that already exists"
        if status == 409
        else "the request violates a constraint on the data"
    )
    if status == 500:
        detail = "an unhandled database constraint was violated"
    return JSONResponse({"detail": detail, "sqlstate": sqlstate}, status_code=status)


@lru_cache(maxsize=1)
def engine() -> Engine:
    """Built on first use, not at import.

    An engine created at import time makes `import app.main` require a
    `DATABASE_URL`, which turns every unit test and every `--help` into a
    configuration problem. `pool_pre_ping` because a container outlives the
    connections a restarted database closed underneath it.
    """
    return create_engine(settings().database_url, pool_pre_ping=True)


def session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed either way."""
    with Session(engine()) as active:
        yield active


__all__ = ["engine", "integrity_error_handler", "integrity_status", "session"]
