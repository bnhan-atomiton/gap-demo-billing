"""Initial schema for billing.

The birth certificate in DDL form: this is the schema in `ir.json`, written once
when the application was generated. Everything after it is a migration you wrote
in this repository, on top of this one. Nothing regenerates over the top.

The revision id is a hash of `ir.json` rather than the random one Alembic
generates, so re-rendering the same schema produces the same file — and two apps
born from different schemas can never collide on an id, which in a shared
database would stamp the wrong schema as applied.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "cab0197b72e7"
down_revision = None
branch_labels = None
depends_on = None

invoice_status_type = postgresql.ENUM(
    "draft",
    "sent",
    "paid",
    "void",
    name="invoice_status",
    # The type is created explicitly in `upgrade()`. Left to itself SQLAlchemy
    # emits `CREATE TYPE` from inside the first `CREATE TABLE` that mentions it,
    # which puts the statement in a place the reader of this file cannot see.
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    invoice_status_type.create(bind, checkfirst=False)

    op.create_table(
        "plans",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(64),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "monthly_cents",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "seats",
            sa.Integer(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "customers",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "org_name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "billing_email",
            sa.Text(),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "plan_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_customers_created_at",
        "customers",
        [
            "created_at",
        ],
        unique=False,
    )
    op.create_table(
        "invoices",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "issued_on",
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            "status",
            invoice_status_type,
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "total_cents",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_invoices_customer_id_issued_on",
        "invoices",
        [
            "customer_id",
            "issued_on",
        ],
        unique=False,
    )
    op.create_table(
        "invoice_items",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "qty",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "unit_cents",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_invoice_items_invoice_id",
        "invoice_items",
        [
            "invoice_id",
        ],
        unique=False,
    )
    op.create_table(
        "payments",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "method",
            sa.String(32),
            nullable=False,
        ),
        sa.Column(
            "paid_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_payments_invoice_id",
        "payments",
        [
            "invoice_id",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payments_invoice_id",
        table_name="payments",
    )
    op.drop_table("payments")
    op.drop_index(
        "ix_invoice_items_invoice_id",
        table_name="invoice_items",
    )
    op.drop_table("invoice_items")
    op.drop_index(
        "ix_invoices_customer_id_issued_on",
        table_name="invoices",
    )
    op.drop_table("invoices")
    op.drop_index(
        "ix_customers_created_at",
        table_name="customers",
    )
    op.drop_table("customers")
    op.drop_table("plans")

    bind = op.get_bind()
    invoice_status_type.drop(bind, checkfirst=False)
