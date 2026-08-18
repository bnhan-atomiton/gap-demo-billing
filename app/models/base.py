"""The declarative base every model shares."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Holds the metadata Alembic reads to autogenerate migrations."""
