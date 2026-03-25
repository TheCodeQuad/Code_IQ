"""
In-memory progress event stream for repository pipelines.

This module provides a lightweight pub/sub layer used by the API router to
broadcast pipeline progress events and expose them over Server-Sent Events.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict


class RepoProgressBroadcaster:
    """Fan-out progress events to all subscribers of a repository."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, repo_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Register a new subscriber queue for a repository."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(repo_id, set()).add(queue)
        return queue

    async def unsubscribe(self, repo_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove a subscriber queue for a repository."""
        async with self._lock:
            queues = self._subscribers.get(repo_id)
            if not queues:
                return
            queues.discard(queue)
            if not queues:
                self._subscribers.pop(repo_id, None)

    async def publish(self, repo_id: str, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers of a repository."""
        event_payload = dict(event)
        event_payload.setdefault("repo_id", repo_id)
        event_payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        async with self._lock:
            queues = list(self._subscribers.get(repo_id, set()))

        for queue in queues:
            try:
                queue.put_nowait(event_payload)
            except asyncio.QueueFull:
                # Skip back-pressured subscribers to keep publishers non-blocking.
                continue


def format_sse_event(data: Dict[str, Any], *, event: str = "progress") -> str:
    """Format a dictionary as a text/event-stream message."""
    body = json.dumps(data, ensure_ascii=True)
    return f"event: {event}\ndata: {body}\n\n"


progress_broadcaster = RepoProgressBroadcaster()
