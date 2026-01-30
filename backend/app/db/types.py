"""Database type helpers.

These types keep models portable across DB backends (Postgres in prod, SQLite in tests).
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    - PostgreSQL: uses native UUID (returns uuid.UUID objects)
    - SQLite/others: stores as CHAR(36) (returns uuid.UUID objects)
    """

    cache_ok = True
    impl = CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        if dialect.name == "postgresql":
            # PG UUID(as_uuid=True) accepts uuid.UUID
            return value

        if isinstance(value, uuid.UUID):
            return str(value)

        # Accept strings and coerce to canonical UUID string
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))
