"""
Agent Progress — lightweight in-process pub/sub for real-time SSE streaming.

Usage (producer side, inside an agent call):
    from app.agent_progress import push_event
    push_event(session_id, agent_id="janitor", status="running")
    # ... do work ...
    push_event(session_id, agent_id="janitor", status="done", output="Cleaned 3 dupes", duration=240)

Usage (consumer side, inside the SSE endpoint):
    from app.agent_progress import get_queue, close_queue
    queue = get_queue(session_id)
    # read events until sentinel (None) is received
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Global registry: session_id → asyncio.Queue
_queues: Dict[str, asyncio.Queue] = {}


def get_queue(session_id: str) -> asyncio.Queue:
    """Get or create a queue for this session."""
    if session_id not in _queues:
        _queues[session_id] = asyncio.Queue()
    return _queues[session_id]


def close_queue(session_id: str) -> None:
    """Remove the queue after the SSE connection closes."""
    _queues.pop(session_id, None)


def push_event(
    session_id: str,
    agent_id: str,
    status: str,
    output: Optional[str] = None,
    duration: Optional[int] = None,
) -> None:
    """
    Push a real agent progress event into the session queue.

    This is safe to call from synchronous code — it uses
    asyncio.get_event_loop().call_soon_threadsafe() so it works even if
    the producer is running in a thread pool (FastAPI's default for sync routes).

    Args:
        session_id: The session to publish to.
        agent_id:   One of "janitor", "hypothesis", "debate", "viz".
        status:     "running" | "done" | "error"
        output:     Optional short summary text shown under the agent card.
        duration:   Optional elapsed milliseconds shown in the UI.
    """
    if session_id not in _queues:
        _queues[session_id] = asyncio.Queue()

    event: Dict[str, Any] = {"agent_id": agent_id, "status": status}
    if output is not None:
        event["output"] = output
    if duration is not None:
        event["duration"] = duration

    queue = _queues[session_id]

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — schedule thread-safe put
            loop.call_soon_threadsafe(queue.put_nowait, event)
        else:
            queue.put_nowait(event)
    except Exception as e:
        logger.warning(f"Failed to push agent event for session {session_id}: {e}")


def push_sentinel(session_id: str) -> None:
    """Push None sentinel so the SSE generator knows to close the stream."""
    push_event_raw(session_id, None)


def push_event_raw(session_id: str, value) -> None:
    """Push any value (including None sentinel) into the queue."""
    if session_id not in _queues:
        _queues[session_id] = asyncio.Queue()
    queue = _queues[session_id]
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.call_soon_threadsafe(queue.put_nowait, value)
        else:
            queue.put_nowait(value)
    except Exception as e:
        logger.warning(f"Failed to push raw event for session {session_id}: {e}")
