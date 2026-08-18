"""CRUD routes for `payments`."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import session
from app.models.payment import Payment
from app.schemas.page import Page
from app.schemas.payment import PaymentCreate, PaymentRead, PaymentUpdate

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)

#: The columns `?order_by=` will accept, spelled as a type rather than checked in
#: the handler. An unknown value is then a 422 from validation before any code
#: here runs, and `getattr` below can only ever reach a real mapped column — the
#: value never becomes part of a query string.
OrderBy = Literal[
    "id",
    "invoice_id",
    "method",
    "paid_at",
]

DbSession = Annotated[Session, Depends(session)]

_NOT_FOUND = {
    status.HTTP_404_NOT_FOUND: {"description": "No such payment"},
}


def _get(db: Session, row_id: UUID) -> Payment:
    row = db.get(Payment, row_id)
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"no payment with id {row_id}",
        )
    return row


@router.get("")
def list_payments(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    order_by: OrderBy = "id",
    order: Literal["asc", "desc"] = "asc",
) -> Page[PaymentRead]:
    """One page of rows.

    Ordered explicitly, and by the primary key unless asked otherwise: without an
    `ORDER BY` a `LIMIT`/`OFFSET` pair is free to return the same row on two
    consecutive pages and skip another entirely.
    """
    column = getattr(Payment, order_by)
    ordering = column.desc() if order == "desc" else column.asc()
    statement = select(Payment).order_by(ordering)
    rows = db.scalars(statement.limit(limit).offset(offset)).all()
    total = db.scalar(select(func.count()).select_from(Payment)) or 0
    return Page[PaymentRead](
        items=[PaymentRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    db: DbSession,
) -> PaymentRead:
    """`exclude_unset`, so a field left out keeps the column's own default rather
    than overwriting it with a null."""
    row = Payment(**payload.model_dump(exclude_unset=True))
    db.add(row)
    db.commit()
    db.refresh(row)
    return PaymentRead.model_validate(row)


@router.get("/{row_id}", responses=_NOT_FOUND)
def get_payment(
    row_id: UUID,
    db: DbSession,
) -> PaymentRead:
    return PaymentRead.model_validate(_get(db, row_id))


@router.patch("/{row_id}", responses=_NOT_FOUND)
def update_payment(
    row_id: UUID,
    payload: PaymentUpdate,
    db: DbSession,
) -> PaymentRead:
    """`exclude_unset` again, and here it is the whole point: without it every
    omitted field arrives as `None` and a PATCH of one column blanks the rest of
    the row."""
    row = _get(db, row_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return PaymentRead.model_validate(row)


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_NOT_FOUND)
def delete_payment(
    row_id: UUID,
    db: DbSession,
) -> None:
    """A row something else still references raises `IntegrityError` here and
    leaves as a 409 — see the handler registered in `app/main.py`."""
    db.delete(_get(db, row_id))
    db.commit()
