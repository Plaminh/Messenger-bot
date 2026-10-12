"""Webhook endpoint for Meta Messenger integration.

Handles GET verification challenge and secure POST event ingestion.
Immediately acknowledges events with HTTP 200 and processes messages asynchronously.
"""

import json
from collections.abc import Callable, Coroutine
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.messenger.client import get_messenger_client
from app.messenger.dedupe import deduplicator
from app.messenger.security import verify_meta_signature
from app.chat.debounce import debouncer

logger = get_logger(__name__)

router = APIRouter(tags=["Webhook"])

NON_TEXT_FALLBACK_MESSAGE = (
    "Hihi mình chưa xem được ảnh, sticker hay nghe voice được nè. "
    "Bạn gõ chữ tâm sự với mình nha! 😊"
)

# Pluggable turn processor (orchestrator attaches here)
_turn_handler: Callable[[str, str], Coroutine[Any, Any, None]] | None = None


def set_turn_handler(handler: Callable[[str, str], Coroutine[Any, Any, None]] | None) -> None:
    """Set the turn processing coroutine (called by orchestrator)."""
    global _turn_handler
    _turn_handler = handler


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> Response:
    """Verify Meta Webhook subscription token."""
    settings = get_settings()

    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        logger.info("Meta webhook verification challenge passed")
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    logger.warning("Meta webhook verification failed: invalid token or mode")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


async def handle_messaging_event(messaging: dict[str, Any]) -> None:
    """Process an individual messaging event extracted from webhook payload."""
    sender_info = messaging.get("sender")
    if not isinstance(sender_info, dict):
        return
    sender_id = sender_info.get("id")
    if not sender_id:
        return

    message = messaging.get("message")
    if not message or message.get("is_echo"):
        return

    mid = message.get("mid")
    if mid and deduplicator.is_duplicate(mid):
        logger.info("Ignoring duplicate message mid: %s", mid)
        return

    text = message.get("text")
    if text:
        text = text.strip()
        if not text:
            return

        async def _run_orchestrator(psid: str, combined: str) -> None:
            if _turn_handler is not None:
                await _turn_handler(psid, combined)
            else:
                client = get_messenger_client()
                await client.send_human_like_response(
                    psid,
                    "Chào bạn! Hệ thống đang khởi động, hãy thử lại sau ít phút nhé.",
                )

        await debouncer.add_message(sender_id, text, _run_orchestrator)
    else:
        # User sent non-text attachment (photo, sticker, audio, etc.)
        client = get_messenger_client()
        await client.send_human_like_response(sender_id, NON_TEXT_FALLBACK_MESSAGE)


async def process_webhook_payload(payload_bytes: bytes) -> None:
    """Parse and dispatch events from validated webhook payload."""
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to parse webhook JSON payload: %s", exc)
        return

    if data.get("object") != "page":
        return

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            try:
                await handle_messaging_event(messaging)
            except Exception as exc:
                logger.error("Error handling messaging event: %s", exc, exc_info=True)


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> Response:
    """Receive and securely process Meta Messenger events."""
    settings = get_settings()
    body = await request.body()

    if not verify_meta_signature(body, x_hub_signature_256, settings.META_APP_SECRET):
        logger.warning("Rejected webhook POST with invalid signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Fast 200 response to satisfy Meta webhook SLA, process payload in background
    background_tasks.add_task(process_webhook_payload, body)

    return Response(content="EVENT_RECEIVED", status_code=200)
