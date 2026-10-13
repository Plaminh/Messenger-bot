"""Security and filtering at the Messenger webhook boundary."""

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.webhook import handle_messaging_event
from app.integrations.messenger.security import verify_meta_signature


def test_webhook_signature_accepts_only_valid_hmac():
    body = b'{"object":"page"}'
    secret = "secret"
    valid = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_meta_signature(body, valid, secret)
    assert not verify_meta_signature(body, "sha256=wrong", secret)
    assert not verify_meta_signature(body, None, secret)


@pytest.mark.asyncio
async def test_echo_and_duplicate_events_never_reach_chat_pipeline():
    orchestrator = MagicMock()
    orchestrator.handle_turn = AsyncMock()
    debouncer = MagicMock()
    debouncer.add_message = AsyncMock()
    deduplicator = MagicMock()

    deduplicator.is_duplicate.return_value = False
    await handle_messaging_event(
        {"sender": {"id": "u"}, "message": {"mid": "echo", "text": "x", "is_echo": True}},
        orchestrator, debouncer, deduplicator,
    )

    deduplicator.is_duplicate.return_value = True
    await handle_messaging_event(
        {"sender": {"id": "u"}, "message": {"mid": "duplicate", "text": "x"}},
        orchestrator, debouncer, deduplicator,
    )

    debouncer.add_message.assert_not_awaited()
    orchestrator.handle_turn.assert_not_awaited()

