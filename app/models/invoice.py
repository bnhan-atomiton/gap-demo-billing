"""Invoice — the `invoices` table.

Written when this application was generated, from the schema in `ir.json`. That
file is a birth certificate, not a live source: this module is yours to edit,
schema changes from here are ordinary Alembic migrations in this repository, and
nothing will ever regenerate over the top of your changes.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import InvoiceStatus, labels


class Invoice(Base):
    """One row of `invoices`."""

    __tablename__ = "invoices"

    __table_args__ = (
        sa.Index(
            "ix_invoices_customer_id_issued_on",
            "customer_id",
            "issued_on",
            unique=False,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    customer_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    issued_on: Mapped[date] = mapped_column(
        sa.Date(),
        nullable=False,
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        sa.Enum(InvoiceStatus, name="invoice_status", values_callable=labels),
        nullable=False,
        server_default=sa.text("'draft'"),
    )
    total_cents: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    )
