"""Plan — the `plans` table.

Written when this application was generated, from the schema in `ir.json`. That
file is a birth certificate, not a live source: this module is yours to edit,
schema changes from here are ordinary Alembic migrations in this repository, and
nothing will ever regenerate over the top of your changes.
"""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Plan(Base):
    """One row of `plans`."""

    __tablename__ = "plans"

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    code: Mapped[str] = mapped_column(
        sa.String(64),
        nullable=False,
        unique=True,
    )
    monthly_cents: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
    seats: Mapped[int | None] = mapped_column(
        sa.Integer(),
        nullable=True,
    )
