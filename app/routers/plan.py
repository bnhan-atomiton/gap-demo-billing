"""CRUD routes for `plans`."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import session
from app.models.plan import Plan
from app.schemas.page import Page
from app.schemas.plan import PlanCreate, PlanRead, PlanUpdate

router = APIRouter(
    prefix="/plans",
    tags=["plans"],
)

#: The columns `?order_by=` will accept, spelled as a type rather than checked in
#: the handler. An unknown value is then a 422 from validation before any code
#: here runs, and `getattr` below can only ever reach a real mapped column — the
#: value never becomes part of a query string.
OrderBy = Literal[
    "id",
    "code",
    "monthly_cents",
    "seats",
]

DbSession = Annotated[Session, Depends(session)]

_NOT_FOUND = {
    status.HTTP_404_NOT_FOUND: {"description": "No such plan"},
}


def _get(db: Session, row_id: UUID) -> Plan:
    row = db.get(Plan, row_id)
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"no plan with id {row_id}",
        )
    return row


@router.get("")
def list_plans(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    order_by: OrderBy = "id",
    order: Literal["asc", "desc"] = "asc",
) -> Page[PlanRead]:
    """One page of rows.

    Ordered explicitly, and by the primary key unless asked otherwise: without an
    `ORDER BY` a `LIMIT`/`OFFSET` pair is free to return the same row on two
    consecutive pages and skip another entirely.
    """
    column = getattr(Plan, order_by)
    ordering = column.desc() if order == "desc" else column.asc()
    statement = select(Plan).order_by(ordering)
    rows = db.scalars(statement.limit(limit).offset(offset)).all()
    total = db.scalar(select(func.count()).select_from(Plan)) or 0
    return Page[PlanRead](
        items=[PlanRead.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreate,
    db: DbSession,
) -> PlanRead:
    """`exclude_unset`, so a field left out keeps the column's own default rather
    than overwriting it with a null."""
    row = Plan(**payload.model_dump(exclude_unset=True))
    db.add(row)
    db.commit()
    db.refresh(row)
    return PlanRead.model_validate(row)


@router.get("/{row_id}", responses=_NOT_FOUND)
def get_plan(
    row_id: UUID,
    db: DbSession,
) -> PlanRead:
    return PlanRead.model_validate(_get(db, row_id))


@router.patch("/{row_id}", responses=_NOT_FOUND)
def update_plan(
    row_id: UUID,
    payload: PlanUpdate,
    db: DbSession,
) -> PlanRead:
    """`exclude_unset` again, and here it is the whole point: without it every
    omitted field arrives as `None` and a PATCH of one column blanks the rest of
    the row."""
    row = _get(db, row_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return PlanRead.model_validate(row)


@router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_NOT_FOUND)
def delete_plan(
    row_id: UUID,
    db: DbSession,
) -> None:
    """A row something else still references raises `IntegrityError` here and
    leaves as a 409 — see the handler registered in `app/main.py`."""
    db.delete(_get(db, row_id))
    db.commit()
