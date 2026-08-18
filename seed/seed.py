"""Deterministic seed rows for billing. Nothing here touches a database.

The split is deliberate: this module computes rows, `__main__.py` writes them.
All of the logic worth testing lives on this side of it, so it can be tested
without a Postgres — and the loader is left with nothing but a transaction.

**Determinism comes from `hashlib`, never from `hash()`.** Python randomises the
hash of `str` and `bytes` per process unless `PYTHONHASHSEED` is fixed, so a
seeder keyed on `hash((table, column, row))` looks perfectly reproducible within
one run and produces different data on the next. `sha256` is stable across
processes, machines and releases.

Row keys are UUIDv5, which is a hash rather than a random draw. That is what
makes re-running the loader a no-op instead of a second copy of the data: the
same row computes the same key, and `ON CONFLICT DO NOTHING` discards it.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

#: Namespace for row keys. Derived from the app name, so two generated apps
#: sharing a database never compute the same key for different rows.
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "billing.seed")

#: Table order. Topological: a table appears after everything it references, so
#: a foreign key can always name a row that already exists.
TABLES: tuple[str, ...] = (
    "plans",
    "customers",
    "invoices",
    "invoice_items",
    "payments",
)

#: Declared row counts, straight from `ir.json`.
COUNTS: dict[str, int] = {
    "plans": 4,
    "customers": 120,
    "invoices": 640,
    "invoice_items": 2400,
    "payments": 580,
}

#: table → {column → parent table}. Read by the tests, and by anyone asking what
#: references what without re-reading five model modules.
FOREIGN_KEYS: dict[str, dict[str, str]] = {
    "plans": {},
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

# Vocabularies, one line each. `ruff format` never *packs* a collection: any
# tuple that does not fit on a single line comes back one element per line, and
# a trailing comma pins it that way, so a longer word list here is not a longer
# list — it is fifty more lines in a file meant to be skimmed on the way to the
# row builders. Variety is not what keeps a `unique` column distinct either;
# `_unique` below does that, and does it whatever these hold.
_WORDS = ("alpha", "atlas", "beacon", "cedar", "cobalt", "delta", "ember", "falcon", "harbor")
_SUFFIXES = ("Labs", "Works", "Group", "Systems", "Holdings", "Partners", "Industries")
_FIRST_NAMES = ("Ada", "Bo", "Chen", "Dara", "Eli", "Fen", "Gita", "Hugo", "Ines", "Jonas", "Kai")
_LAST_NAMES = ("Abara", "Bhatt", "Cruz", "Dahl", "Eze", "Guo", "Haddad", "Iyer", "Kovac")


def _rng(table: str, column: str, row: int) -> random.Random:
    """One independent stream per cell.

    Per cell rather than per row so that adding a column to the schema does not
    shift every value in every other column — the diff of a re-seeded database
    should be the column that changed.
    """
    digest = hashlib.sha256(f"{table}.{column}.{row}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def row_key(table: str, row: int) -> uuid.UUID:
    """The primary key of one seeded row: a hash, so it is the same every run."""
    return uuid.uuid5(NAMESPACE, f"{table}:{row}")


def _uuid(table: str, column: str, row: int) -> uuid.UUID:
    """A uuid column that is not a key. Hashed, so it is stable across runs —
    `uuid4()` here would make the seed data different on every load."""
    return uuid.uuid5(NAMESPACE, f"{table}.{column}:{row}")


def _fk(table: str, column: str, row: int, parent: str) -> uuid.UUID:
    count = COUNTS[parent]
    if count == 0:
        raise ValueError(
            f"{table}.{column} references {parent}, which is seeded with no rows. "
            f"A foreign key cannot point at an empty table."
        )
    return row_key(parent, _rng(table, column, row).randrange(count))


def _word(table: str, column: str, row: int) -> str:
    return _rng(table, column, row).choice(_WORDS)


def _company(table: str, column: str, row: int) -> str:
    rng = _rng(table, column, row)
    return f"{rng.choice(_WORDS).capitalize()} {rng.choice(_SUFFIXES)}"


def _person_name(table: str, column: str, row: int) -> str:
    rng = _rng(table, column, row)
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _email(table: str, column: str, row: int) -> str:
    rng = _rng(table, column, row)
    # `.invalid` is reserved by RFC 2606 and can never resolve. Seed data has a
    # way of reaching a mail sender eventually, and a real-looking domain here is
    # how test data becomes someone else's inbox.
    local = f"{rng.choice(_FIRST_NAMES).lower()}.{rng.choice(_LAST_NAMES).lower()}"
    return f"{local}@example.invalid"


def _sentence(table: str, column: str, row: int) -> str:
    rng = _rng(table, column, row)
    words = [rng.choice(_WORDS) for _ in range(rng.randint(4, 9))]
    return " ".join(words).capitalize() + "."


def _choice(table: str, column: str, row: int, values: tuple[Any, ...]) -> Any:
    return _rng(table, column, row).choice(values)


def _choice_unique(table: str, column: str, row: int, values: tuple[str, ...]) -> str:
    """One value per row, dealt without replacement, for a `unique` column.

    `_choice` draws independently, so four rows over four values come out
    distinct only 4!/4**4 ≈ 9% of the time — the rest is a unique violation
    partway through the load, on a file that renders identically every time.
    Dealing from a shuffled deck removes the draw rather than retrying it.

    The permutation is keyed on the column and not on any row, so every row
    agrees about the order; `-1` is the row index no row has.
    """
    order = list(values)
    _rng(table, column, -1).shuffle(order)
    return order[row]


def _unique(value: str, row: int, length: int | None) -> str:
    """A generated string made distinct per row, still inside a `varchar(n)`.

    The row index is the only thing separating two rows that drew the same
    words, so it is never what gets trimmed — `_truncate` cuts the tail, which
    is precisely where it lives. It also goes before an `@` when there is one,
    so an address stays an address.
    """
    head, at, domain = value.partition("@")
    suffix = str(row)
    if length is not None:
        head = head[: max(length - len(at) - len(domain) - len(suffix), 0)]
    return f"{head}{suffix}{at}{domain}"


def _int_range(table: str, column: str, row: int, low: int, high: int) -> int:
    return _rng(table, column, row).randint(low, high)


def _decimal_range(table: str, column: str, row: int, low: str, high: str, places: int) -> Decimal:
    rng = _rng(table, column, row)
    scale = 10**places
    drawn = rng.randint(int(Decimal(low) * scale), int(Decimal(high) * scale))
    return Decimal(drawn) / scale


def _date_range(table: str, column: str, row: int, low: str, high: str) -> date:
    start, end = date.fromisoformat(low), date.fromisoformat(high)
    return start + timedelta(days=_rng(table, column, row).randint(0, (end - start).days))


def _timestamp_range(table: str, column: str, row: int, low: str, high: str) -> datetime:
    start = datetime.fromisoformat(low)
    end = datetime.fromisoformat(high)
    drawn = _rng(table, column, row).randint(0, int((end - start).total_seconds()))
    return (start + timedelta(seconds=drawn)).astimezone(UTC)


def _truncate(value: str, length: int | None) -> str:
    """A `varchar(n)` refuses n+1 characters with a 500-shaped error partway
    through the load. Bounded here rather than hoped for."""
    return value if length is None else value[:length]


def _plans_row(row: int) -> dict[str, Any]:
    return {
        "id": row_key("plans", row),
        "code": _choice_unique("plans", "code", row, ("free", "starter", "team", "enterprise")),
        "monthly_cents": _int_range("plans", "monthly_cents", row, 0, 250000),
        "seats": _int_range("plans", "seats", row, 1, 500),
    }


def _customers_row(row: int) -> dict[str, Any]:
    return {
        "id": row_key("customers", row),
        "org_name": _truncate(_company("customers", "org_name", row), 255),
        "billing_email": _unique(_email("customers", "billing_email", row), row, None),
        "plan_id": _fk("customers", "plan_id", row, "plans"),
        "created_at": _timestamp_range(
            "customers",
            "created_at",
            row,
            "2024-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    }


def _invoices_row(row: int) -> dict[str, Any]:
    return {
        "id": row_key("invoices", row),
        "customer_id": _fk("invoices", "customer_id", row, "customers"),
        "issued_on": _date_range("invoices", "issued_on", row, "2024-01-01", "2026-06-30"),
        "status": _choice("invoices", "status", row, ("draft", "sent", "paid", "void")),
        "total_cents": _int_range("invoices", "total_cents", row, 0, 500000),
    }


def _invoice_items_row(row: int) -> dict[str, Any]:
    return {
        "id": row_key("invoice_items", row),
        "invoice_id": _fk("invoice_items", "invoice_id", row, "invoices"),
        "description": _sentence("invoice_items", "description", row),
        "qty": _int_range("invoice_items", "qty", row, 1, 20),
        "unit_cents": _int_range("invoice_items", "unit_cents", row, 100, 50000),
    }


def _payments_row(row: int) -> dict[str, Any]:
    return {
        "id": row_key("payments", row),
        "invoice_id": _fk("payments", "invoice_id", row, "invoices"),
        "method": _choice("payments", "method", row, ("card", "ach", "wire", "credit")),
        "paid_at": _timestamp_range(
            "payments",
            "paid_at",
            row,
            "2024-01-01T00:00:00+00:00",
            "2026-06-30T00:00:00+00:00",
        ),
    }


_BUILDERS = {
    "plans": _plans_row,
    "customers": _customers_row,
    "invoices": _invoices_row,
    "invoice_items": _invoice_items_row,
    "payments": _payments_row,
}


def rows_for(table: str) -> list[dict[str, Any]]:
    """Every seeded row for one table, in key order."""
    return [_BUILDERS[table](row) for row in range(COUNTS[table])]
