"""The envelope every list endpoint returns."""

from __future__ import annotations

from pydantic import BaseModel


class Page[ItemT](BaseModel):
    """One page of rows, and enough context to ask for the next one.

    A bare list would be a smaller response and a worse API: a client handed
    back exactly `limit` rows cannot tell a full page from the end of the table,
    so it has to issue one more request every time to find out.
    """

    items: list[ItemT]
    total: int
    limit: int
    offset: int
