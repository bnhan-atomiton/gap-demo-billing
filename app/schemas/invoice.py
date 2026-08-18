"""Request and response bodies for `invoices`.

Three models rather than one, because the three directions genuinely differ: a
create body must not carry the primary key, an update body must be able to omit
every field, and a response body carries columns nobody is allowed to write.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import InvoiceStatus


class InvoiceCreate(BaseModel):
    """Body of `POST /invoices`.

    Anything the database can supply for itself is optional here — a nullable
    column, or one with a `DEFAULT`. Leave it out and the database's own default
    applies, because the router sends only the fields you actually set. The
    defaults are deliberately not repeated in this file: they live in the
    migration, and a copy here would go stale the first time one changed.
    """

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID
    issued_on: date
    status: InvoiceStatus | None = None
    total_cents: int | None = None


class InvoiceUpdate(BaseModel):
    """Body of `PATCH /invoices/{id}`.

    Every field optional, and the router reads it with `exclude_unset=True` —
    that is what separates "did not mention this column" from "set it to null".
    Without the distinction, a PATCH of one field blanks the rest of the row.
    """

    model_config = ConfigDict(extra="forbid")

    customer_id: UUID | None = None
    issued_on: date | None = None
    status: InvoiceStatus | None = None
    total_cents: int | None = None


class InvoiceRead(BaseModel):
    """One row of `invoices` on its way out.

    No length or precision bounds: these values came *from* the database, which
    already enforced them. Repeating the bounds here would only mean that a row
    predating a widening migration fails to serialise — a 500 on data that is
    perfectly valid.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    issued_on: date
    status: InvoiceStatus
    total_cents: int
