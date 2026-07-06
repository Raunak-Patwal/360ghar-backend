"""Tests for the after_commit push-notification scheduling in conversations."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


def test_schedule_after_commit_notify_defers_until_commit():
    """The notification task must NOT be created until the transaction commits."""
    from app.services.flatmates.conversations import _schedule_after_commit_notify

    captured: dict[str, object] = {}

    def fake_listens_for(_target, _identifier, **_kw):
        def deco(fn):
            captured["on_commit"] = fn
            return fn

        return deco

    fake_db = SimpleNamespace(sync_session=object())

    with (
        patch("sqlalchemy.event.listens_for", side_effect=fake_listens_for),
        patch("app.services.flatmates.conversations.asyncio.create_task") as mock_task,
    ):
        mock_task.side_effect = lambda coro: coro.close()
        _schedule_after_commit_notify(
            fake_db, peer_id=5, sender_name="Sender", conversation_id=9
        )
        # Registered, but deferred — no task before commit.
        mock_task.assert_not_called()

        # Commit fires the listener.
        on_commit = captured["on_commit"]
        assert callable(on_commit)
        on_commit(fake_db.sync_session)
        mock_task.assert_called_once()
