from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Canonical SSE event type constants — use these instead of raw strings.
SSE_SWIPE = "swipe"
SSE_NOTIFICATION = "notification"
SSE_VISIT_UPDATED = "visit_updated"
SSE_PROPERTY_UPDATE = "property_update"
SSE_NEW_NOTIFICATION = "new_notification"


class SSESubscriberLimitError(RuntimeError):
    """Raised when the process-level SSE subscriber cap is reached."""


class SSEEventBus:
    """Lightweight pub/sub that maps user_id to a set of asyncio queues.

    Service methods call ``emit(user_id, event_dict)`` after DB commit.
    The SSE endpoint consumes from its queue via ``subscribe`` / ``unsubscribe``.
    """

    _FULL_THRESHOLD = 3
    _QUEUE_MAX_SIZE = 32
    _REAP_EVERY_EMITS = 10
    _MAX_GLOBAL_SUBSCRIBERS = 500
    _QUEUE_TTL_SECONDS = 30 * 60

    def __init__(self) -> None:
        self._queues: dict[int, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._full_counts: dict[int, int] = {}
        self._last_activity: dict[int, float] = {}
        self._lock = asyncio.Lock()
        self._emit_count = 0

    async def subscribe(self, user_id: int) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._QUEUE_MAX_SIZE)
        async with self._lock:
            if self._subscriber_count_locked() >= self._MAX_GLOBAL_SUBSCRIBERS:
                raise SSESubscriberLimitError("SSE subscriber limit reached")
            self._queues.setdefault(user_id, []).append(queue)
            self._last_activity[id(queue)] = time.monotonic()
        return queue

    async def touch(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Mark a queue as actively consumed by its SSE response task."""
        async with self._lock:
            queue_id = id(queue)
            if queue_id in self._last_activity:
                self._last_activity[queue_id] = time.monotonic()

    async def unsubscribe(self, user_id: int, queue: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            queues = self._queues.get(user_id)
            if queues is None:
                return
            try:
                queues.remove(queue)
            except ValueError:
                pass
            self._full_counts.pop(id(queue), None)
            self._last_activity.pop(id(queue), None)
            if not queues:
                del self._queues[user_id]

    async def emit(self, user_id: int, event: dict[str, Any]) -> None:
        """Fire-and-forget push to all queues for *user_id*.

        Non-blocking: drops the oldest item when a queue is full.
        Periodically reaps dead queues (those whose consumer has abandoned them).

        Must be called from an async context (e.g., ``await sse_bus.emit(...)``).
        """
        should_reap = False
        async with self._lock:
            queues = self._queues.get(user_id)
            if not queues:
                return
            for q in queues:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        q.put_nowait(event)
                    except asyncio.QueueFull:
                        logger.warning("SSE queue full for user %s, dropping event", user_id)

            self._emit_count += 1
            if self._emit_count % self._REAP_EVERY_EMITS == 0:
                should_reap = True

        if should_reap:
            await self._reap_dead_queues_async()

    async def _reap_dead_queues_async(self) -> None:
        """Reap queues that have been full for multiple consecutive cycles."""
        now = time.monotonic()
        async with self._lock:
            stale_users: list[int] = []
            for uid, queues in list(self._queues.items()):
                alive: list[asyncio.Queue[dict[str, Any]]] = []
                for q in queues:
                    queue_id = id(q)
                    last_activity = self._last_activity.get(queue_id, now)
                    if now - last_activity > self._QUEUE_TTL_SECONDS:
                        logger.warning("SSE queue reaped for user %s after inactivity TTL", uid)
                        self._full_counts.pop(queue_id, None)
                        self._last_activity.pop(queue_id, None)
                    elif q.full():
                        count = self._full_counts.get(queue_id, 0) + 1
                        self._full_counts[queue_id] = count
                        if count < self._FULL_THRESHOLD:
                            alive.append(q)
                        else:
                            logger.warning(
                                "SSE queue reaped for user %s after %d full cycles",
                                uid,
                                count,
                            )
                            self._full_counts.pop(queue_id, None)
                            self._last_activity.pop(queue_id, None)
                    else:
                        self._full_counts.pop(queue_id, None)
                        alive.append(q)
                if alive:
                    self._queues[uid] = alive
                else:
                    stale_users.append(uid)
            for uid in stale_users:
                self._queues.pop(uid, None)

    def _subscriber_count_locked(self) -> int:
        return sum(len(queues) for queues in self._queues.values())


sse_bus = SSEEventBus()
