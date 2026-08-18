"""`python -m seed` — load the deterministic seed data, idempotently.

Everything interesting is in `seed.py`; this file is a transaction and nothing
else. That is the point of the split: the rows can be checked without a
database, so the only thing left here to get wrong is the write.

**Idempotent by key, not by emptiness.** The obvious loader checks whether a
table has rows and skips it if so, which quietly does nothing after a partial
load — exactly the state you want to repair. Seed keys are UUIDv5 hashes of
(table, row), so re-running computes the same keys and `ON CONFLICT DO NOTHING`
discards the ones already present and inserts the ones that are missing.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import insert

from app.models import Base
from app.settings import settings
from seed.seed import COUNTS, TABLES, rows_for

#: Rows per `INSERT`. Large enough that 2,400 rows is a handful of statements,
#: small enough to stay well inside Postgres' 65,535 bind-parameter limit for a
#: wide table: 500 rows x 20 columns is 10,000 parameters.
CHUNK = 500


def main() -> int:
    engine = create_engine(settings().database_url)
    inserted = 0

    with engine.begin() as connection:
        for name in TABLES:
            table = Base.metadata.tables[name]
            rows = rows_for(name)
            if not rows:
                continue

            counter = select(func.count()).select_from(table)
            # Counted rather than summed from `result.rowcount`. An `executemany`
            # without `RETURNING` leaves rowcount at -1 on psycopg3, so the
            # obvious version reports "inserted -5 new rows" on a load that
            # worked — and, worse, reports the same -5 on the re-run that
            # inserted nothing, which is precisely the number this line exists
            # to distinguish.
            before = connection.execute(counter).scalar_one()
            for start in range(0, len(rows), CHUNK):
                statement = insert(table).on_conflict_do_nothing(
                    index_elements=[table.primary_key.columns.keys()[0]]
                )
                connection.execute(statement, rows[start : start + CHUNK])

            total = connection.execute(counter).scalar_one()
            inserted += total - before
            print(f"{name}: {total} rows (declared {COUNTS[name]}, {total - before} new)")

    print(f"inserted {inserted} new rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
