"""Webhook endpoint for Meta Messenger integration.

Handles GET verification challenge and secure POST event ingestion.
Immediately acknowledges events with HTTP 200 and processes messages asynchronously.
"""

import json
from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.api.dependencies import (
    get_debouncer,
    get_deduplicator,
    get_messenger_client,
    get_orchestrator,
)
from app.chat.debounce import MessageDebouncer
from app.chat.orchestrator import ChatOrchestrator
from app.integrations.messenger.client import MessengerClient
from app.integrations.messenger.dedupe import MessageDeduplicator
from app.integrations.messenger.security import verify_meta_signature

logger = get_logger(__name__)

router = APIRouter(tags=["Webhook"])

NON_TEXT_FALLBACK_MESSAGE = (
    "Hihi mình chưa xem được ảnh, sticker hay nghe voice được nè. "
    "Bạn gõ chữ tâm sự với mình nha! 😊"
)


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


async def handle_messaging_event(
    messaging: dict[str, Any],
    orchestrator: ChatOrchestrator,
    debouncer: MessageDebouncer,
    deduplicator: MessageDeduplicator,
    messenger_client: Optional[MessengerClient] = None,
) -> None:
    """Process an individual messaging event extracted from webhook payload."""
    sender_info = messaging.get("sender")
    if not isinstance(sender_info, dict):
        return
    sender_id = sender_info.get("id")
    if not sender_id:
        return

    postback = messaging.get("postback")
    if isinstance(postback, dict):
        payload = postback.get("payload")
        if payload in {"GET_STARTED", "HELP"}:
            await orchestrator.handle_turn(sender_id, "/help")
        else:
            logger.info("Ignoring unknown postback payload")
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

        async def _run_orchestrator(psid: str, combined: str, mid: str | None = None) -> None:
            await orchestrator.handle_turn(psid, combined, mid=mid)

        await debouncer.add_message(sender_id, text, _run_orchestrator, mid=mid)
    else:
        # User sent non-text attachment (photo, sticker, audio, etc.)
        if messenger_client is None:
            logger.error("No MessengerClient available to answer non-text event")
            return
        await messenger_client.send_human_like_response(sender_id, NON_TEXT_FALLBACK_MESSAGE)


async def process_webhook_payload(
    payload_bytes: bytes,
    orchestrator: ChatOrchestrator,
    debouncer: MessageDebouncer,
    deduplicator: MessageDeduplicator,
    messenger_client: MessengerClient,
) -> None:
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
                await handle_messaging_event(
                    messaging,
                    orchestrator=orchestrator,
                    debouncer=debouncer,
                    deduplicator=deduplicator,
                    messenger_client=messenger_client,
                )
            except Exception as exc:
                logger.error("Error handling messaging event: %s", exc, exc_info=True)


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    orchestrator: ChatOrchestrator = Depends(get_orchestrator),
    debouncer: MessageDebouncer = Depends(get_debouncer),
    deduplicator: MessageDeduplicator = Depends(get_deduplicator),
    messenger_client: MessengerClient = Depends(get_messenger_client),
) -> Response:
    """Receive and securely process Meta Messenger events."""
    settings = get_settings()
    body = await request.body()

    if not verify_meta_signature(body, x_hub_signature_256, settings.META_APP_SECRET):
        logger.warning("Rejected webhook POST with invalid signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Fast 200 response to satisfy Meta webhook SLA, process payload in background
    background_tasks.add_task(
        process_webhook_payload,
        body,
        orchestrator=orchestrator,
        debouncer=debouncer,
        deduplicator=deduplicator,
        messenger_client=messenger_client,
    )

    return Response(content="EVENT_RECEIVED", status_code=200)
