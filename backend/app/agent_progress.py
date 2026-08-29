"""
Agent Progress — lightweight in-process pub/sub for real-time SSE streaming.

Usage (consumer side — register BEFORE the pipeline runs):
    queue = get_queue(session_id)   # creates the slot

Usage (producer side — inside agent calls):
    push_event(session_id, agent_id="janitor", status="running")
    push_event(session_id, agent_id="janitor", status="done", output="...", duration=240)

push_event silently drops events for unknown session_ids so orphaned queues
can never accumulate.  The SSE endpoint owns the queue lifecycle via
get_queue() / close_queue().
"""

import asyncio
import logging
from typing import Any

from app.utils.log_utils import safe_log_value

logger = logging.getLogger(__name__)

# session_id → asyncio.Queue; only populated by get_queue()
_queues: dict[str, asyncio.Queue] = {}


def get_queue(session_id: str) -> asyncio.Queue:
    """Register and return the event queue for this session."""
    if session_id not in _queues:
        _queues[session_id] = asyncio.Queue()
    return _queues[session_id]


def close_queue(session_id: str) -> None:
    """Remove the queue after the SSE connection closes."""
    _queues.pop(session_id, None)


def _enqueue(session_id: str, value: Any) -> None:
    """
    Thread-safe enqueue. Only writes if the session already has a registered
    queue — this prevents orphaned queues from accumulating when callers
    forget to open the SSE stream first.
    """
    queue = _queues.get(session_id)
    if queue is None:
        # Worth a warning, not a debug line: the usual cause is this process
        # not being the one holding the SSE connection, which silently empties
        # the whole agent timeline. See the worker note in backend/Dockerfile.
        logger.warning(
            "push_event: no queue for session %s in this process, dropping event",
            safe_log_value(session_id),
        )
        return

    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(queue.put_nowait, value)
    except RuntimeError:
        # No running loop — direct put (unit tests / sync contexts)
        queue.put_nowait(value)
    except Exception as e:
        logger.warning(
            "Failed to enqueue event for session %s: %s",
            safe_log_value(session_id),
            safe_log_value(e),
        )


def push_event(
    session_id: str | None,
    agent_id: str,
    status: str,
    output: str | None = None,
    duration: int | None = None,
) -> None:
    if session_id is None:
        return
    """Push a real agent progress event into the session queue."""
    event: dict[str, Any] = {"agent_id": agent_id, "status": status}
    if output is not None:
        event["output"] = output
    if duration is not None:
        event["duration"] = duration
    _enqueue(session_id, event)


def push_sentinel(session_id: str | None) -> None:
    if session_id is None:
        return
    """Push None sentinel so the SSE generator knows to close the stream."""
    _enqueue(session_id, None)
