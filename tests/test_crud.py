"""CRUD round trips, and every promise `ir.json` makes about deleting a row.

Everything here is parametrised over the tables in the schema, so this file grows
and shrinks with it rather than naming the tables somebody had last week. Rows
are created through the API rather than inserted, which is what makes a round
trip worth running: it proves the request schema, the model and the response
schema agree, and an INSERT would prove only that the database accepts data.

The fixtures roll every test back, so the suite can run against a seeded
database without emptying it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

#: Topological — a parent appears before every table that points at it.
TABLES = (
    "plans",
    "customers",
    "invoices",
    "invoice_items",
    "payments",
)

#: (table, column) — one column per table whose new value is distinguishable
#: from its old one. An enum or a `jsonb` object is neither, so a table with
#: nothing else is absent here rather than tested against itself.
PATCHABLE = (
    ("plans", "code"),
    ("customers", "org_name"),
    ("invoices", "total_cents"),
    ("invoice_items", "description"),
    ("payments", "method"),
)

#: (table, foreign-key column, the table it points at).
FOREIGN_KEYS = (
    ("customers", "plan_id", "plans"),
    ("invoices", "customer_id", "customers"),
    ("invoice_items", "invoice_id", "invoices"),
    ("payments", "invoice_id", "invoices"),
)

#: (parent, child, the child's foreign-key column) for `ON DELETE RESTRICT` —
#: and for `NO ACTION`, which Postgres refuses at the same moment.
RESTRICTED = (
    ("plans", "customers", "plan_id"),
    ("invoices", "payments", "invoice_id"),
)

#: … and for `ON DELETE CASCADE`.
CASCADED = (
    ("customers", "invoices", "customer_id"),
    ("invoices", "invoice_items", "invoice_id"),
)


@pytest.mark.parametrize("table", TABLES)
def test_a_row_round_trips(
    client: TestClient,
    create: Callable[..., dict[str, Any]],
    primary_key: dict[str, str],
    table: str,
) -> None:
    created = create(table)

    fetched = client.get(f"/{table}/{created[primary_key[table]]}")

    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == created


@pytest.mark.parametrize("table", TABLES)
def test_a_created_row_is_counted_once(
    client: TestClient,
    create: Callable[..., dict[str, Any]],
    table: str,
) -> None:
    """Against the total rather than against the first page: on a seeded table
    the new row is on page forty-eight, and looking for it there would make this
    a test of the ordering."""
    before = client.get(f"/{table}", params={"limit": 1}).json()["total"]

    create(table)

    assert client.get(f"/{table}", params={"limit": 1}).json()["total"] == before + 1


@pytest.mark.parametrize("table", TABLES)
def test_a_page_reports_its_own_bounds(
    client: TestClient,
    create: Callable[..., dict[str, Any]],
    table: str,
) -> None:
    """The envelope, not the rows. A client handed back exactly `limit` items and
    nothing else cannot tell a full page from the end of the table."""
    create(table)

    page = client.get(f"/{table}", params={"limit": 1, "offset": 0}).json()

    assert page["limit"] == 1
    assert page["offset"] == 0
    assert page["total"] >= 1
    assert len(page["items"]) == 1


@pytest.mark.parametrize("table", TABLES)
def test_an_unknown_id_is_404(
    client: TestClient,
    absent_id: dict[str, Any],
    table: str,
) -> None:
    assert client.get(f"/{table}/{absent_id[table]}").status_code == 404


@pytest.mark.parametrize("table", TABLES)
def test_a_deleted_row_is_gone(
    client: TestClient,
    create: Callable[..., dict[str, Any]],
    primary_key: dict[str, str],
    table: str,
) -> None:
    row_id = create(table)[primary_key[table]]

    assert client.delete(f"/{table}/{row_id}").status_code == 204
    assert client.get(f"/{table}/{row_id}").status_code == 404


@pytest.mark.parametrize(("table", "column"), PATCHABLE)
def test_patching_one_column_leaves_the_others_alone(
    client: TestClient,
    create: Callable[..., dict[str, Any]],
    new_value: Callable[[str, str], Any],
    primary_key: dict[str, str],
    table: str,
    column: str,
) -> None:
    """A PATCH sends only the fields it means to change. Without `exclude_unset`
    in the router every omitted one arrives as a null and blanks the row, which
    is what the second assertion is here to notice."""
    created = create(table)
    replacement = new_value(table, column)

    updated = client.patch(f"/{table}/{created[primary_key[table]]}", json={column: replacement})

    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body[column] == replacement
    assert body[column] != created[column]
    assert {name: value for name, value in body.items() if name != column} == {
        name: value for name, value in created.items() if name != column
    }


@pytest.mark.parametrize(("table", "column", "parent"), FOREIGN_KEYS)
def test_a_create_naming_an_absent_parent_is_422(
    client: TestClient,
    payload: Callable[..., dict[str, Any]],
    absent_id: dict[str, Any],
    table: str,
    column: str,
    parent: str,
) -> None:
    """422, not a 500 out of a constraint violation: the request named a row that
    does not exist, which is something the caller can fix."""
    body = payload(table, **{column: absent_id[parent]})

    response = client.post(f"/{table}", json=body)

    assert response.status_code == 422, response.text


@pytest.mark.parametrize(("parent", "child", "column"), RESTRICTED)
def test_deleting_a_referenced_row_is_409(
    client: TestClient,
    create: Callable[..., dict[str, Any]],
    primary_key: dict[str, str],
    parent: str,
    child: str,
    column: str,
) -> None:
    """The request was well formed and the current state refuses it, which is
    what 409 means. The row survives."""
    parent_id = create(parent)[primary_key[parent]]
    create(child, **{column: parent_id})

    response = client.delete(f"/{parent}/{parent_id}")

    assert response.status_code == 409, response.text
    assert client.get(f"/{parent}/{parent_id}").status_code == 200


@pytest.mark.parametrize(("parent", "child", "column"), CASCADED)
def test_deleting_a_row_takes_its_dependents_with_it(
    client: TestClient,
    create: Callable[..., dict[str, Any]],
    primary_key: dict[str, str],
    parent: str,
    child: str,
    column: str,
) -> None:
    parent_id = create(parent)[primary_key[parent]]
    dependent_id = create(child, **{column: parent_id})[primary_key[child]]

    assert client.delete(f"/{parent}/{parent_id}").status_code == 204
    assert client.get(f"/{child}/{dependent_id}").status_code == 404
