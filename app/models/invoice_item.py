"""InvoiceItem — the `invoice_items` table.

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


class InvoiceItem(Base):
    """One row of `invoice_items`."""

    __tablename__ = "invoice_items"

    __table_args__ = (
        sa.Index(
            "ix_invoice_items_invoice_id",
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
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        sa.Text(),
        nullable=False,
    )
    qty: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        server_default=sa.text("1"),
    )
    unit_cents: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
