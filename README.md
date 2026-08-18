# billing

Customer billing: plans, invoices, line items, payments

**This repository was generated** by the AutoDeployer Factory from the schema in
[`ir.json`](ir.json), and then handed to you. There is no round trip: nothing
regenerates over the top of it, so every edit you make is safe and `ir.json` is
a birth certificate rather than a source file. Change the schema by writing a
migration, the way you would in any other repository.

## What it is

| | |
|---|---|
| API | FastAPI, one CRUD router per table |
| Storage | Postgres, SQLAlchemy 2.0 typed models |
| Migrations | Alembic — `0001_initial_schema` is this schema, in DDL |
| Seeds | `python -m seed`, deterministic and re-runnable |

**Every route is unauthenticated.** The schema IR can describe tables, columns,
keys, enums and indexes; it cannot describe an auth model. That was a deliberate
limit on what generation promises, not an oversight — so this app belongs on an
internal network, behind something that does authenticate, until you add auth
yourself.

## Schema

| Table | Rows seeded | Columns |
|---|---|---|
| `plans` | 4 | id, code, monthly_cents, seats |
| `customers` | 120 | id, org_name, billing_email, plan_id, created_at |
| `invoices` | 640 | id, customer_id, issued_on, status, total_cents |
| `invoice_items` | 2400 | id, invoice_id, description, qty, unit_cents |
| `payments` | 580 | id, invoice_id, method, paid_at |

Enums: `invoice_status` (draft, sent, paid, void).

## Running it

```sh
uv sync
export DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/billing
uv run alembic upgrade head
uv run python -m seed
uv run uvicorn app.main:app --reload
```

Then `http://127.0.0.1:8000/docs`.

Every setting also accepts a `<NAME>_FILE` form naming a file to read the value
from, and **the `_FILE` form wins**. That is how this app receives a password in
production: the orchestrator mounts a secret at a path and sets
`DATABASE_URL_FILE`, so the credential never appears in an environment variable,
a service definition, or `docker inspect`.

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | Postgres DSN. `+psycopg` (psycopg 3) is required |
| `GAP_RELEASE_ID` | Echoed by `/healthz`. The deploy sets it |
| `PORT` | Bound on `0.0.0.0`. Defaults to 8000 |

## Tests

```sh
uv run pytest
```

They need a Postgres. `conftest.py` reads `TEST_DATABASE_URL` and skips rather
than running destructively against whatever `DATABASE_URL` happens to point at.

## Layout

```
app/models/     one module per table, SQLAlchemy
app/schemas/    one module per table, pydantic in/out
app/routers/    one module per table, CRUD
app/db.py       engine, session dependency, integrity-error mapping
app/settings.py environment and <NAME>_FILE resolution
migrations/     alembic
seed/           deterministic seed data
```
