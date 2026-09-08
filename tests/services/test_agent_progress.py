"""
Unit tests for the SSE agent-progress pub/sub.
"""

import asyncio

import pytest
from app.agent_progress import close_queue, get_queue, push_event, push_sentinel


@pytest.mark.asyncio
async def test_get_queue_is_idempotent():
    sid = "sess-idempotent"
    try:
        assert get_queue(sid) is get_queue(sid)
    finally:
        close_queue(sid)


@pytest.mark.asyncio
async def test_push_event_delivers_expected_shape():
    sid = "sess-shape"
    queue = get_queue(sid)
    try:
        push_event(sid, agent_id="janitor", status="running")
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event == {"agent_id": "janitor", "status": "running"}
    finally:
        close_queue(sid)


@pytest.mark.asyncio
async def test_push_event_includes_output_and_duration_when_given():
    sid = "sess-fields"
    queue = get_queue(sid)
    try:
        push_event(sid, agent_id="viz", status="done", output="ok", duration=120)
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event == {"agent_id": "viz", "status": "done", "output": "ok", "duration": 120}
    finally:
        close_queue(sid)


@pytest.mark.asyncio
async def test_push_sentinel_delivers_none():
    sid = "sess-sentinel"
    queue = get_queue(sid)
    try:
        push_sentinel(sid)
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event is None
    finally:
        close_queue(sid)


def test_push_event_for_unknown_session_is_silently_dropped():
    # No get_queue() call first, and no event loop running at all — must
    # not raise either way.
    push_event("no-such-session", agent_id="x", status="running")
    push_sentinel("no-such-session")


@pytest.mark.asyncio
async def test_close_queue_stops_further_delivery():
    sid = "sess-close"
    get_queue(sid)
    close_queue(sid)
    push_event(sid, agent_id="x", status="running")  # dropped, must not raise

    # A fresh get_queue() after close is a brand new, empty queue.
    new_queue = get_queue(sid)
    try:
        assert new_queue.empty()
    finally:
        close_queue(sid)


@pytest.mark.asyncio
async def test_push_event_from_a_worker_thread_is_delivered_safely():
    """The real production shape: get_queue() runs on the event loop (the
    SSE endpoint's coroutine), but a streaming LLM callback invoked via
    asyncio.to_thread calls push_event from a different OS thread. Queue
    mutation must still go through the owning loop rather than racing the
    consumer's own get() from another thread.
    """
    sid = "sess-thread"
    queue = get_queue(sid)

    def producer():
        for i in range(25):
            push_event(sid, agent_id="narrator", status="running", output=str(i))

    try:
        await asyncio.to_thread(producer)

        received = [await asyncio.wait_for(queue.get(), timeout=1) for _ in range(25)]
        assert [e["output"] for e in received] == [str(i) for i in range(25)]
    finally:
        close_queue(sid)
