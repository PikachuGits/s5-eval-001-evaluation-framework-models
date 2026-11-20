"""Database primitives shared by the S5-EVAL-001 models.

The delivery targets PostgreSQL 16 and uses ``gen_random_uuid()``, ``JSONB``
and ``TEXT[]``.  The connection URL is read from ``DATABASE_URL`` so the same
metadata can be pointed at the reviewer's database; there is deliberately no
fallback to a developer machine's default database.
"""

from __future__ import annotations

import os

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for the five evaluation tables in this delivery."""

    metadata = MetaData()


def get_database_url() -> str:
    """Return the configured database URL or fail loudly."""

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required, e.g. "
            "postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DB_NAME"
        )
    return url
