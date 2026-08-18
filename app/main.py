"""The FastAPI application: health, error translation, and the CRUD routers."""

from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import engine, integrity_error_handler
from app.routers import customer, invoice, invoice_item, payment, plan
from app.settings import settings

app = FastAPI(
    title="billing",
    description="Customer billing: plans, invoices, line items, payments",
    version="1.0.0",
)

# Registered once, for every write in every router. See `app/db.py` for the
# SQLSTATE mapping and for why a delete blocked by dependents is a 409 while the
# same code on a create is a 422.
app.add_exception_handler(IntegrityError, integrity_error_handler)

app.include_router(plan.router)
app.include_router(customer.router)
app.include_router(invoice.router)
app.include_router(invoice_item.router)
app.include_router(payment.router)


@app.get("/healthz", tags=["health"])
def healthz() -> Response:
    """Ready to serve, and which release is serving.

    Non-200 until the database answers: this endpoint gates rolling deploys, so
    reporting healthy while unable to read is how a broken release replaces a
    working one. `release` echoes `GAP_RELEASE_ID` so a deploy can tell "the new
    tasks are up" apart from "the old tasks are still up and answering".
    """
    body = {"status": "ok", "release": settings().release_id}
    try:
        with Session(engine()) as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse({**body, "status": "unready"}, status_code=503)
    return JSONResponse(body)
