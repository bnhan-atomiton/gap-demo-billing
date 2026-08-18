"""Payment — the `payments` table.

Written when this application was generated, from the schema in `ir.json`. That
file is a birth certificate, not a live source: this module is yours to edit,
schema changes from here are ordinary Alembic migrations in this repository, and
nothing will ever regenerate over the top of your changes.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Payment(Base):
    """One row of `payments`."""

    __tablename__ = "payments"

    __table_args__ = (
        sa.Index(
            "ix_payments_invoice_id",
            "invoice_id",
            unique=False,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    invoice_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey(
            "invoices.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    method: Mapped[str] = mapped_column(
        sa.String(32),
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
