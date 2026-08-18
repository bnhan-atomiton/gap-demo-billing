"""Every model, imported so `Base.metadata` is complete.

Alembic autogenerate and `create_all` both read `Base.metadata`, and a model
module nobody imports is a table neither of them knows about. Import order does
not matter — SQLAlchemy resolves foreign keys by table name at mapper
configuration, not at import — so these are in the alphabetical order the
formatter wants rather than in dependency order. The place dependency order
*does* matter is seeding, and `seed/seed.py` carries it.
"""

from app.models.base import Base
from app.models.customer import Customer
from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.payment import Payment
from app.models.plan import Plan

__all__ = [
    "Base",
    "Customer",
    "Invoice",
    "InvoiceItem",
    "InvoiceStatus",
    "Payment",
    "Plan",
]
