from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# Flexible document payloads should use JSONB on PostgreSQL for indexing/operator
# support while remaining JSON-compatible on SQLite in local test runs.
JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")
