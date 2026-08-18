"""`/healthz` — the endpoint a rolling deploy gates on.

The first two tests would both pass for an endpoint returning a constant. The
third is the one with the teeth: reporting healthy while unable to read the
database is exactly how a broken release replaces a working one, because the
orchestrator waits for a 200 and then retires the old tasks.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app import main
from app.settings import settings


def test_healthz_is_ok_while_the_database_answers(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"


def test_healthz_names_the_release_it_is_serving(client: TestClient) -> None:
    """The deploy compares this against the release it pushed. Without it, "the
    new tasks are up" and "the old ones are still answering" look the same."""
    response = client.get("/healthz")

    assert response.json()["release"] == settings().release_id


def test_healthz_refuses_while_the_database_does_not_answer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unreachable() -> None:
        raise SQLAlchemyError("no database")

    monkeypatch.setattr(main, "engine", unreachable)

    assert client.get("/healthz").status_code == 503
