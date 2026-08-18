"""Customer — the `customers` table.

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


class Customer(Base):
    """One row of `customers`."""

    __tablename__ = "customers"

    __table_args__ = (
        sa.Index(
            "ix_customers_created_at",
            "created_at",
            unique=False,
        ),
    )

    id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    org_name: Mapped[str] = mapped_column(
        sa.String(255),
        nullable=False,
    )
    billing_email: Mapped[str] = mapped_column(
        sa.Text(),
        nullable=False,
        unique=True,
    )
    plan_id: Mapped[UUID] = mapped_column(
        sa.Uuid(as_uuid=True),
        sa.ForeignKey(
            "plans.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
