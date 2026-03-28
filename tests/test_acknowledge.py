"""Tests for the /acknowledge endpoint and duplicate stop event suppression."""

import pytest
from httpx import AsyncClient, ASGITransport

from coral.web_server import app


@pytest.mark.asyncio
async def test_acknowledge_endpoint_inserts_event():
    """POST /api/sessions/live/{name}/acknowledge inserts an 'acknowledge' event
    and returns {"ok": True}. Subsequent stop events for the same session should
    be suppressed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First, create a "stop" event so the session appears done
        stop_resp = await client.post(
            "/api/sessions/live/test-agent/events",
            json={
                "event_type": "stop",
                "summary": "Agent finished",
                "session_id": "ack-test-123",
            },
        )
        assert stop_resp.status_code == 200

        # Now acknowledge the session
        ack_resp = await client.post(
            "/api/sessions/live/test-agent/acknowledge",
            params={"session_id": "ack-test-123"},
        )
        assert ack_resp.status_code == 200
        assert ack_resp.json() == {"ok": True}

        # A subsequent stop event for the same session should be suppressed
        dup_stop_resp = await client.post(
            "/api/sessions/live/test-agent/events",
            json={
                "event_type": "stop",
                "summary": "Agent stopped again",
                "session_id": "ack-test-123",
            },
        )
        assert dup_stop_resp.status_code == 200
        data = dup_stop_resp.json()
        assert data.get("ok") is True
        assert data.get("suppressed") is True


@pytest.mark.asyncio
async def test_duplicate_stop_event_suppression():
    """Inserting a 'stop' event for session X, then another 'stop' for the same
    session, should suppress the second one."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First stop event — should be inserted normally
        resp1 = await client.post(
            "/api/sessions/live/test-agent/events",
            json={
                "event_type": "stop",
                "summary": "Agent stopped",
                "session_id": "dup-stop-456",
            },
        )
        assert resp1.status_code == 200
        # Should return the event (not suppressed)
        data1 = resp1.json()
        assert data1.get("suppressed") is not True

        # Second stop event — should be suppressed
        resp2 = await client.post(
            "/api/sessions/live/test-agent/events",
            json={
                "event_type": "stop",
                "summary": "Agent stopped again",
                "session_id": "dup-stop-456",
            },
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("ok") is True
        assert data2.get("suppressed") is True


@pytest.mark.asyncio
async def test_stop_suppression_after_acknowledge():
    """After an 'acknowledge' event, subsequent stop events should be suppressed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Insert a normal event first (not stop)
        await client.post(
            "/api/sessions/live/test-agent/events",
            json={
                "event_type": "notification",
                "summary": "Permission prompt",
                "session_id": "ack-stop-789",
            },
        )

        # Acknowledge the session
        await client.post(
            "/api/sessions/live/test-agent/acknowledge",
            params={"session_id": "ack-stop-789"},
        )

        # Stop event after acknowledge should be suppressed
        resp = await client.post(
            "/api/sessions/live/test-agent/events",
            json={
                "event_type": "stop",
                "summary": "Agent stopped",
                "session_id": "ack-stop-789",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("suppressed") is True
