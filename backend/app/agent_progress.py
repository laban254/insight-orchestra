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
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# session_id → asyncio.Queue; only populated by get_queue()
_queues: Dict[str, asyncio.Queue] = {}


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
        logger.debug(f"push_event: no queue for session {session_id!r}, dropping event")
        return

    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(queue.put_nowait, value)
    except RuntimeError:
        # No running loop — direct put (unit tests / sync contexts)
        queue.put_nowait(value)
    except Exception as e:
        logger.warning(f"Failed to enqueue event for session {session_id}: {e}")


def push_event(
    session_id: str,
    agent_id: str,
    status: str,
    output: Optional[str] = None,
    duration: Optional[int] = None,
) -> None:
    """Push a real agent progress event into the session queue."""
    event: Dict[str, Any] = {"agent_id": agent_id, "status": status}
    if output is not None:
        event["output"] = output
    if duration is not None:
        event["duration"] = duration
    _enqueue(session_id, event)


def push_sentinel(session_id: str) -> None:
    """Push None sentinel so the SSE generator knows to close the stream."""
    _enqueue(session_id, None)
