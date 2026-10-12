"""Tests verifying dependency injection via app.state and FastAPI Depends."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient
import hmac
import hashlib
import json

from app.api.dependencies import (
    get_debouncer,
    get_deduplicator,
    get_messenger_client,
    get_orchestrator,
)
from app.chat.debounce import MessageDebouncer
from app.chat.orchestrator import ChatOrchestrator
from app.core.settings import get_settings
from app.integrations.messenger.client import MessengerClient
from app.integrations.messenger.dedupe import MessageDeduplicator
from app.main import app, lifespan


@pytest.mark.asyncio
async def test_app_state_contains_required_components():
    """Verify app.state holds all core singleton components without globals."""
    assert hasattr(app.state, "orchestrator")
    assert isinstance(app.state.orchestrator, ChatOrchestrator)

    assert hasattr(app.state, "debouncer")
    assert isinstance(app.state.debouncer, MessageDebouncer)

    assert hasattr(app.state, "deduplicator")
    assert isinstance(app.state.deduplicator, MessageDeduplicator)

    assert hasattr(app.state, "messenger_client")
    assert isinstance(app.state.messenger_client, MessengerClient)


@pytest.mark.asyncio
async def test_lifespan_lifecycle_startup_and_shutdown():
    """Verify lifespan initializes components on app.state and cleanly tears down."""
    mock_app = MagicMock()
    mock_app.state = MagicMock()

    async with lifespan(mock_app):
        assert mock_app.state.messenger_client is not None
        assert mock_app.state.orchestrator is not None
        assert mock_app.state.debouncer is not None
        assert mock_app.state.deduplicator is not None
        # Mock client for teardown verification
        client_mock = AsyncMock()
        mock_app.state.messenger_client = client_mock

    client_mock.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_dependency_overrides_without_monkeypatching():
    """Verify FastAPI Depends overrides work cleanly without touching global variables."""
    settings = get_settings()

    mock_custom_orchestrator = MagicMock(spec=ChatOrchestrator)
    mock_custom_orchestrator.handle_turn = AsyncMock()

    mock_custom_debouncer = MessageDebouncer(delay=0.01)

    app.dependency_overrides[get_orchestrator] = lambda: mock_custom_orchestrator
    app.dependency_overrides[get_debouncer] = lambda: mock_custom_debouncer

    try:
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "page_id_di",
                    "messaging": [
                        {
                            "sender": {"id": "user_di_123"},
                            "message": {
                                "mid": "mid.di_test_1",
                                "text": "Tin nhắn thử nghiệm Dependency Injection",
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

        # Wait for debouncer delay to flush
        import asyncio
        await asyncio.sleep(0.05)

        # Injected orchestrator should have been called
        mock_custom_orchestrator.handle_turn.assert_awaited_once_with(
            "user_di_123",
            "Tin nhắn thử nghiệm Dependency Injection",
            mid="mid.di_test_1",
        )
    finally:
        app.dependency_overrides.clear()
