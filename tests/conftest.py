"""Fixtures for this app's tests: a database, a transaction, and a client.

Every test runs inside a transaction that is rolled back afterwards, so the
suite leaves the database exactly as it found it. That is what lets it run
against a seeded development database instead of needing an empty one.

**`TEST_DATABASE_URL`, never `DATABASE_URL`.** These tests create and delete
rows. Falling back to whichever database the app itself is configured for is how
a test run empties a development dataset, so an unset variable skips the suite
rather than reaching for the other one.
"""

from __future__ import annotations

import itertools
import os
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import partial
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session

from app.db import session
from app.main import app
from app.settings import settings

#: Advanced for every value built, so a `unique` column gets a distinct one on
#: every call without any test having to arrange it. Starts at 1: index 0 is
#: reserved for the keys in `ABSENT_IDS`, which nothing may hold.
_counter = itertools.count(1)


def _text(n: int, length: int | None = None) -> str:
    """A recognisably synthetic string, trimmed from the *front* when it must fit.

    The digits are what make two rows differ and they are at the end, so a
    `varchar(8)` keeps the tail and loses the prefix rather than the other way
    round — trimming the tail would turn two distinct values back into one.
    """
    value = f"test-{n}"
    return value if length is None else value[-length:]


def _uuid(n: int) -> str:
    return str(uuid.UUID(int=n))


def _date(n: int) -> str:
    return (date(2024, 1, 1) + timedelta(days=n)).isoformat()


def _timestamp(n: int) -> str:
    return (datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=n)).isoformat()


def _decimal(n: int, scale: int) -> str:
    return str(Decimal(n).quantize(Decimal(1).scaleb(-scale)))


def _plan_payload(n: int) -> dict[str, Any]:
    """One valid `plans` body.

    Foreign keys are absent on purpose: `_payload_for` fills them with the keys
    of parents it creates first, and a literal here would name a row that does
    not exist.
    """
    return {
        "code": _text(n, 64),
        "monthly_cents": n,
        "seats": n,
    }


def _customer_payload(n: int) -> dict[str, Any]:
    """One valid `customers` body.

    Foreign keys are absent on purpose: `_payload_for` fills them with the keys
    of parents it creates first, and a literal here would name a row that does
    not exist.
    """
    return {
        "org_name": _text(n, 255),
        "billing_email": _text(n),
        "created_at": _timestamp(n),
    }


def _invoice_payload(n: int) -> dict[str, Any]:
    """One valid `invoices` body.

    Foreign keys are absent on purpose: `_payload_for` fills them with the keys
    of parents it creates first, and a literal here would name a row that does
    not exist.
    """
    return {
        "issued_on": _date(n),
        "status": "draft",
        "total_cents": n,
    }


def _invoice_item_payload(n: int) -> dict[str, Any]:
    """One valid `invoice_items` body.

    Foreign keys are absent on purpose: `_payload_for` fills them with the keys
    of parents it creates first, and a literal here would name a row that does
    not exist.
    """
    return {
        "description": _text(n),
        "qty": n,
        "unit_cents": n,
    }


def _payment_payload(n: int) -> dict[str, Any]:
    """One valid `payments` body.

    Foreign keys are absent on purpose: `_payload_for` fills them with the keys
    of parents it creates first, and a literal here would name a row that does
    not exist.
    """
    return {
        "method": _text(n, 32),
        "paid_at": _timestamp(n),
    }


#: Table → a builder for one valid request body.
PAYLOADS: dict[str, Callable[[int], dict[str, Any]]] = {
    "plans": _plan_payload,
    "customers": _customer_payload,
    "invoices": _invoice_payload,
    "invoice_items": _invoice_item_payload,
    "payments": _payment_payload,
}

PRIMARY_KEYS: dict[str, str] = {
    "plans": "id",
    "customers": "id",
    "invoices": "id",
    "invoice_items": "id",
    "payments": "id",
}

#: Table → its foreign-key columns and the table each one points at. Read by
#: `_payload_for`, which walks it to create the parents a row needs.
PARENTS: dict[str, dict[str, str]] = {
    "customers": {
        "plan_id": "plans",
    },
    "invoices": {
        "customer_id": "customers",
    },
    "invoice_items": {
        "invoice_id": "invoices",
    },
    "payments": {
        "invoice_id": "invoices",
    },
}

#: A key of the right type that no created row holds — the subject of every
#: "unknown id" test. Built at runtime rather than written out, because a uuid
#: literal in a generated file is indistinguishable from a generator that
#: invented one.
ABSENT_IDS: dict[str, Any] = {
    "plans": _uuid(0),
    "customers": _uuid(0),
    "invoices": _uuid(0),
    "invoice_items": _uuid(0),
    "payments": _uuid(0),
}


def _payload_for(client: TestClient, table: str, **overrides: Any) -> dict[str, Any]:
    """A complete body, with every parent row it references created first.

    A foreign key named in `overrides` is left alone — a test that supplies its
    own parent, or a deliberately absent one, does not want a second row created
    and immediately orphaned.
    """
    body = PAYLOADS[table](next(_counter))
    for column, parent in PARENTS.get(table, {}).items():
        if column not in overrides:
            body[column] = _create(client, parent)[PRIMARY_KEYS[parent]]
    body.update(overrides)
    return body


def _create(client: TestClient, table: str, **overrides: Any) -> dict[str, Any]:
    """One row, through the API rather than through an INSERT.

    Which is the point: a row created this way has passed the request schema, the
    model and the response schema, so a round trip built on it proves the three
    agree.
    """
    response = client.post(f"/{table}", json=_payload_for(client, table, **overrides))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """The test database, and the app pointed at it for the duration.

    `/healthz` opens its own connection rather than taking the request session,
    so leaving `DATABASE_URL` alone would have the health tests checking a
    different database from every other test in the suite.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    settings.cache_clear()
    try:
        yield url
    finally:
        if previous is None:
            del os.environ["DATABASE_URL"]
        else:
            os.environ["DATABASE_URL"] = previous
        settings.cache_clear()


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    built = create_engine(database_url, pool_pre_ping=True)
    try:
        yield built
    finally:
        built.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    """One transaction per test, rolled back however the test ends."""
    with engine.connect() as open_connection:
        transaction = open_connection.begin()
        try:
            yield open_connection
        finally:
            transaction.rollback()


@pytest.fixture
def client(connection: Connection) -> Iterator[TestClient]:
    """The app, with every request's session bound to this test's transaction.

    A session *per request*, not one shared with the test: that is what the app
    does in production, and sharing one would keep a row a cascade had deleted
    alive in an identity map, so the request that should 404 would be handed the
    stale object instead.

    `join_transaction_mode="create_savepoint"` is what makes each router's own
    `commit()` a savepoint release rather than a real commit, so the rollback
    above still undoes everything they wrote.
    """

    def _session() -> Iterator[Session]:
        with Session(bind=connection, join_transaction_mode="create_savepoint") as request:
            yield request

    app.dependency_overrides[session] = _session
    try:
        with TestClient(app) as running:
            yield running
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def create(client: TestClient) -> Callable[..., dict[str, Any]]:
    """`create("plans")` → the created row, parents and all."""
    return partial(_create, client)


@pytest.fixture
def payload(client: TestClient) -> Callable[..., dict[str, Any]]:
    """The same body `create` would post, without posting it."""
    return partial(_payload_for, client)


@pytest.fixture
def new_value() -> Callable[[str, str], Any]:
    """A different value for one column, so a PATCH has something to show."""

    def _new_value(table: str, column: str) -> Any:
        return PAYLOADS[table](next(_counter))[column]

    return _new_value


@pytest.fixture
def primary_key() -> dict[str, str]:
    return PRIMARY_KEYS


@pytest.fixture
def absent_id() -> dict[str, Any]:
    return ABSENT_IDS
