from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.api_v1.endpoints.data_hub import bank_auctions, circle_rates, registry
from app.schemas.pagination import CursorParams


def _db_with_empty_scalars() -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db.execute.return_value = result
    return db


def _executed_sql(db: AsyncMock) -> str:
    return "\n".join(str(call.args[0]).lower() for call in db.execute.await_args_list)


@pytest.mark.asyncio
async def test_zoning_default_list_uses_single_data_query() -> None:
    db = _db_with_empty_scalars()

    await registry.list_zoning(
        sector=None,
        page=CursorParams(cursor=None, limit=20, include_total=False),
        db=db,
    )

    sql = _executed_sql(db)
    assert db.execute.await_count == 1
    assert "from zoning_data" in sql
    assert "count(" not in sql
    assert "max(" not in sql


@pytest.mark.asyncio
async def test_auctions_default_list_uses_single_data_query() -> None:
    db = _db_with_empty_scalars()

    await bank_auctions.list_auctions(
        type=None,
        bank=None,
        city=None,
        source=None,
        property_type=None,
        min_price=None,
        max_price=None,
        date_from=None,
        date_to=None,
        page=CursorParams(cursor=None, limit=20, include_total=False),
        db=db,
    )

    sql = _executed_sql(db)
    assert db.execute.await_count == 1
    assert "from bank_auctions" in sql
    assert "count(" not in sql
    assert "max(" not in sql


@pytest.mark.asyncio
async def test_circle_rates_default_list_uses_single_data_query() -> None:
    db = _db_with_empty_scalars()

    await circle_rates.list_circle_rates(
        sector=None,
        year=None,
        property_type=None,
        page=CursorParams(cursor=None, limit=20, include_total=False),
        db=db,
    )

    sql = _executed_sql(db)
    assert db.execute.await_count == 1
    assert "from circle_rates" in sql
    assert "count(" not in sql
    assert "max(" not in sql
