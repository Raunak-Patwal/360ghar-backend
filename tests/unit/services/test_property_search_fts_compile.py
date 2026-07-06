"""Regression tests for property full-text search SQL compilation."""

from __future__ import annotations

import pytest
from sqlalchemy import Column, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.exc import CompileError

from app.models.properties import Property
from app.services.property.search import _property_ts_vector_column


def test_nameless_tsvector_column_reproduces_sentry_compile_error():
    nameless_vector = Column(None, TSVECTOR())
    search_query = func.plainto_tsquery("english", "apartment")
    statement = select(1).where(nameless_vector.op("@@")(search_query))

    with pytest.raises(CompileError, match="name"):
        statement.compile(dialect=postgresql.dialect())


def test_property_search_uses_named_table_tsvector_for_match_and_rank():
    search_vector = _property_ts_vector_column()
    search_query = func.plainto_tsquery("english", "apartment")
    statement = (
        select(Property.id)
        .where(search_vector.op("@@")(search_query))
        .order_by(func.ts_rank(search_vector, search_query).desc())
    )

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert search_vector.name == "__ts_vector__"
    assert search_vector.table is Property.__table__
    assert "properties.__ts_vector__ @@ plainto_tsquery" in compiled
    assert "ts_rank(properties.__ts_vector__, plainto_tsquery" in compiled
