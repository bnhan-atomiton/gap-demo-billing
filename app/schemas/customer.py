"""Request and response bodies for `customers`.

Three models rather than one, because the three directions genuinely differ: a
create body must not carry the primary key, an update body must be able to omit
every field, and a response body carries columns nobody is allowed to write.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    """Body of `POST /customers`.

    Anything the database can supply for itself is optional here — a nullable
    column, or one with a `DEFAULT`. Leave it out and the database's own default
    applies, because the router sends only the fields you actually set. The
    defaults are deliberately not repeated in this file: they live in the
    migration, and a copy here would go stale the first time one changed.
    """

    model_config = ConfigDict(extra="forbid")

    org_name: str = Field(max_length=255)
    billing_email: str
    plan_id: UUID
    created_at: datetime | None = None


class CustomerUpdate(BaseModel):
    """Body of `PATCH /customers/{id}`.

    Every field optional, and the router reads it with `exclude_unset=True` —
    that is what separates "did not mention this column" from "set it to null".
    Without the distinction, a PATCH of one field blanks the rest of the row.
    """

    model_config = ConfigDict(extra="forbid")

    org_name: str | None = Field(default=None, max_length=255)
    billing_email: str | None = None
    plan_id: UUID | None = None
    created_at: datetime | None = None


class CustomerRead(BaseModel):
    """One row of `customers` on its way out.

    No length or precision bounds: these values came *from* the database, which
    already enforced them. Repeating the bounds here would only mean that a row
    predating a widening migration fails to serialise — a 500 on data that is
    perfectly valid.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_name: str
    billing_email: str
    plan_id: UUID
    created_at: datetime
