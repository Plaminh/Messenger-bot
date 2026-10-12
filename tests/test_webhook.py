"""Tests for webhook endpoints."""

import hashlib
import hmac
import json
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.core.settings import get_settings


@pytest.mark.asyncio
async def test_webhook_get_verify_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test_verify_token",
                "hub.challenge": "challenge_12345",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "challenge_12345"


@pytest.mark.asyncio
async def test_webhook_get_verify_forbidden():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "challenge_12345",
            },
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_post_returns_200_immediately_even_if_llm_slow():
    settings = get_settings()
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_id_1",
                "messaging": [
                    {
                        "sender": {"id": "user_psid_1"},
                        "message": {
                            "mid": "mid.fast_test_1",
                            "text": "Chào bạn nhé!",
                        },
                    }
                ],
            }
        ],
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(
        settings.META_APP_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/webhook",
            content=payload_bytes,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        assert resp.status_code == 200
        assert resp.text == "EVENT_RECEIVED"


@pytest.mark.asyncio
async def test_webhook_post_rejects_invalid_signature():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/webhook",
            content=b'{"object":"page"}',
            headers={"X-Hub-Signature-256": "sha256=invalid_hash"},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_webhook_post_non_text_attachment():
    settings = get_settings()
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_id_1",
                "messaging": [
                    {
                        "sender": {"id": "user_psid_sticker"},
                        "message": {
                            "mid": "mid.sticker_1",
                            "attachments": [{"type": "image", "payload": {}}],
                        },
                    }
                ],
            }
        ],
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(
        settings.META_APP_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    from app.api.dependencies import get_messenger_client

    mock_client = AsyncMock()
    app.dependency_overrides[get_messenger_client] = lambda: mock_client
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/webhook",
                content=payload_bytes,
                headers={"X-Hub-Signature-256": sig},
            )
            assert resp.status_code == 200

        # Background task runs
        mock_client.send_human_like_response.assert_awaited()
    finally:
        app.dependency_overrides.pop(get_messenger_client, None)
