"""Enum types declared by the schema.

`StrEnum` rather than `Enum`: the values are what Postgres stores and what the
API returns, so a member that does not compare equal to its own string is a
class of bug with no upside.
"""

from enum import StrEnum


def labels(enum: type[StrEnum]) -> list[str]:
    """The Postgres labels of an enum type, in declaration order.

    Passed to every `sa.Enum(...)` in the models as `values_callable`. Without
    it SQLAlchemy persists each member's *name* — `DRAFT` — while the migration
    created the type from the schema's labels, which are the *values* —
    `draft`. Nothing catches that at import: the app starts, serves reads, and
    fails on the first write with `invalid input value for enum`.
    """
    return [member.value for member in enum]


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    VOID = "void"
