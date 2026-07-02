from __future__ import annotations

import datetime

import pytest
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import BadRequestException
from app.schemas.pagination import (
    CURSOR_VERSION,
    build_cursor_page,
    decode_cursor,
    encode_cursor,
    keyset_filter,
    keyset_payload,
    keyset_sort_value,
    offset_payload,
    read_keyset,
    read_offset,
    trim_keyset_lookahead,
    trim_lookahead,
    trim_offset_lookahead,
)


def test_encode_decode_roundtrip():
    payload = {"v": CURSOR_VERSION, "o": 40}
    token = encode_cursor(payload)
    assert isinstance(token, str)
    assert "=" not in token  # url-safe, unpadded
    assert decode_cursor(token) == payload


def test_decode_rejects_garbage():
    with pytest.raises(BadRequestException) as exc:
        decode_cursor("!!!not-base64!!!")
    assert exc.value.error_code == "INVALID_CURSOR"


def test_decode_rejects_version_mismatch():
    token = encode_cursor({"v": 999, "o": 0})
    with pytest.raises(BadRequestException) as exc:
        decode_cursor(token)
    assert exc.value.error_code == "INVALID_CURSOR"


def test_keyset_payload_roundtrip():
    p = keyset_payload("2026-06-17T00:00:00Z", 100)
    assert read_keyset(p) == ("2026-06-17T00:00:00Z", 100)


def test_offset_payload_roundtrip():
    assert read_offset(offset_payload(60)) == 60


def test_trim_lookahead_trims_extra_row():
    rows = [3, 2, 1]

    page, has_more = trim_lookahead(rows, limit=2)

    assert page == [3, 2]
    assert has_more is True
    assert rows == [3, 2, 1]


def test_trim_lookahead_end_of_list():
    page, has_more = trim_lookahead([1], limit=2)

    assert page == [1]
    assert has_more is False


def test_trim_lookahead_rejects_non_positive_limit():
    with pytest.raises(ValueError, match="limit"):
        trim_lookahead([1], limit=0)


def test_trim_keyset_lookahead_payload_uses_last_returned_item():
    created = datetime.datetime(2026, 6, 17, 12, 0, 0)
    rows = [
        {"id": 3, "created_at": datetime.datetime(2026, 6, 18, 12, 0, 0)},
        {"id": 2, "created_at": created},
        {"id": 1, "created_at": datetime.datetime(2026, 6, 16, 12, 0, 0)},
    ]

    page, payload = trim_keyset_lookahead(
        rows,
        limit=2,
        sort_value=lambda item: item["created_at"],
        item_id=lambda item: item["id"],
    )

    assert [item["id"] for item in page] == [3, 2]
    assert payload == keyset_payload(created.isoformat(), 2)


def test_trim_keyset_lookahead_end_of_list_has_no_payload():
    rows = [{"id": 1, "created_at": datetime.datetime(2026, 6, 17, 12, 0, 0)}]

    page, payload = trim_keyset_lookahead(
        rows,
        limit=2,
        sort_value=lambda item: item["created_at"],
        item_id=lambda item: item["id"],
    )

    assert page == rows
    assert payload is None


def test_trim_offset_lookahead_payload_advances_by_returned_items():
    rows = [{"id": 3}, {"id": 2}, {"id": 1}]

    page, payload = trim_offset_lookahead(rows, limit=2, offset=20)

    assert page == rows[:2]
    assert payload == offset_payload(22)


def test_trim_offset_lookahead_end_of_list_has_no_payload():
    page, payload = trim_offset_lookahead([{"id": 1}], limit=2, offset=20)

    assert page == [{"id": 1}]
    assert payload is None


def test_build_cursor_page_has_more_true_drops_extra():
    # limit=2, but 3 rows were fetched (limit+1) -> has_more, only 2 returned
    rows = [{"id": 3}, {"id": 2}, {"id": 1}]
    page = build_cursor_page(
        rows[:2], limit=2, next_payload=offset_payload(2), total=None
    )
    assert page["has_more"] is True
    assert page["next_cursor"] is not None
    assert page["limit"] == 2
    assert "total" not in page or page["total"] is None
    assert len(page["items"]) == 2


def test_build_cursor_page_end_of_list():
    page = build_cursor_page([{"id": 1}], limit=20, next_payload=None, total=7)
    assert page["has_more"] is False
    assert page["next_cursor"] is None
    assert page["total"] == 7


# ---------------------------------------------------------------------------
# keyset_sort_value tests
# ---------------------------------------------------------------------------


def test_keyset_sort_value_datetime():
    dt = datetime.datetime(2026, 6, 17, 12, 0, 0)
    result = keyset_sort_value(dt)
    assert result == dt.isoformat()


def test_keyset_sort_value_date():
    d = datetime.date(2026, 6, 17)
    result = keyset_sort_value(d)
    assert result == d.isoformat()


def test_keyset_sort_value_str_passthrough():
    assert keyset_sort_value("hello") == "hello"


def test_keyset_sort_value_int_passthrough():
    assert keyset_sort_value(42) == 42


# ---------------------------------------------------------------------------
# keyset_filter tests
# ---------------------------------------------------------------------------


def test_keyset_filter_no_cursor_returns_none():
    from app.models.pm_leases import Lease

    result = keyset_filter(Lease.created_at, Lease.id, {})
    assert result is None


def test_keyset_filter_with_cursor_returns_expression():
    from app.models.pm_leases import Lease

    payload = keyset_payload("2026-06-17T00:00:00", 100)
    result = keyset_filter(Lease.created_at, Lease.id, payload, descending=True)
    assert result is not None
    assert isinstance(result, ColumnElement)
