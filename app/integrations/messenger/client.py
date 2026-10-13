"""Meta Messenger Graph API client.

Handles asynchronous message delivery, sender actions (mark_seen, typing_on),
intelligent paragraph bubble splitting, and human-like typing delays.
"""

import asyncio
from typing import Any, List, Optional
import httpx

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

MESSENGER_CHAR_LIMIT = 1900  # Conservative limit below Facebook's 2000 chars limit


class DeliveryError(RuntimeError):
    """Raised when no bubble, or only part of a reply, reached Messenger."""

    def __init__(self, sent_bubbles: int, total_bubbles: int) -> None:
        self.sent_bubbles = sent_bubbles
        self.total_bubbles = total_bubbles
        super().__init__(f"Messenger delivered {sent_bubbles}/{total_bubbles} bubbles")


class MessengerClient:
    """Asynchronous client for sending messages via Meta Graph API."""

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        settings: Optional[Any] = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client or httpx.AsyncClient(timeout=10.0)
        api_version = getattr(self._settings, "META_API_VERSION", "v21.0")
        self._base_url = f"https://graph.facebook.com/{api_version}/me/messages"

    async def aclose(self) -> None:
        """Close underlying HTTP client."""
        await self._client.aclose()

    async def send_action(self, recipient_psid: str, action: str) -> bool:
        """Send a sender action such as 'mark_seen', 'typing_on', 'typing_off'."""
        payload = {
            "recipient": {"id": recipient_psid},
            "sender_action": action,
        }
        params = {"access_token": self._settings.META_PAGE_ACCESS_TOKEN}

        for attempt in range(2):
            try:
                response = await self._client.post(self._base_url, params=params, json=payload)
                if response.status_code == 200:
                    return True
                logger.warning(
                    "Sender action %s failed with status %d: %s",
                    action,
                    response.status_code,
                    response.text,
                )
            except httpx.RequestError as exc:
                logger.warning("Attempt %d failed sending action %s: %s", attempt + 1, action, exc)
                await asyncio.sleep(0.5)

        return False

    async def send_text(self, recipient_psid: str, text: str) -> bool:
        """Send a single text message bubble."""
        payload = {
            "recipient": {"id": recipient_psid},
            "message": {"text": text},
        }
        params = {"access_token": self._settings.META_PAGE_ACCESS_TOKEN}

        for attempt in range(2):
            try:
                response = await self._client.post(self._base_url, params=params, json=payload)
                if response.status_code == 200:
                    return True
                logger.warning(
                    "Send text failed with status %d: %s",
                    response.status_code,
                    response.text,
                )
            except httpx.RequestError as exc:
                logger.warning("Attempt %d failed sending text message: %s", attempt + 1, exc)
                await asyncio.sleep(0.5)

        return False

    def split_into_bubbles(self, text: str, max_bubbles: int = 3) -> List[str]:
        """Split text into at most `max_bubbles` natural paragraph bubbles.

        Ensures no bubble exceeds MESSENGER_CHAR_LIMIT.
        """
        raw_paras = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
        if not raw_paras:
            return [text.strip()] if text.strip() else []

        bubbles: List[str] = []
        if len(raw_paras) <= max_bubbles:
            bubbles = raw_paras
        else:
            # First max_bubbles - 1 paragraphs stay distinct
            bubbles = raw_paras[: max_bubbles - 1]
            # Remaining paragraphs merge into the last bubble
            bubbles.append("\n\n".join(raw_paras[max_bubbles - 1 :]))

        # Enforce character limit on each bubble
        refined_bubbles: List[str] = []
        for b in bubbles:
            if len(b) <= MESSENGER_CHAR_LIMIT:
                refined_bubbles.append(b)
            else:
                # Split large bubble by chunks
                curr = b
                while len(curr) > MESSENGER_CHAR_LIMIT:
                    split_idx = curr.rfind("\n", 0, MESSENGER_CHAR_LIMIT)
                    if split_idx == -1:
                        split_idx = curr.rfind(". ", 0, MESSENGER_CHAR_LIMIT)
                    if split_idx == -1:
                        split_idx = MESSENGER_CHAR_LIMIT
                    else:
                        split_idx += 1  # include period or newline
                    refined_bubbles.append(curr[:split_idx].strip())
                    curr = curr[split_idx:].strip()
                if curr:
                    refined_bubbles.append(curr)

        return refined_bubbles

    async def send_human_like_response(self, recipient_psid: str, response_text: str) -> None:
        """Deliver response with mark_seen, typing indicators, and natural staggered delays."""
        # 1. Mark as seen
        await self.send_action(recipient_psid, "mark_seen")

        bubbles = self.split_into_bubbles(response_text, max_bubbles=3)
        if not bubbles:
            return

        sent_bubbles = 0
        for bubble in bubbles:
            # 2. Show typing indicator
            await self.send_action(recipient_psid, "typing_on")

            # Delay proportional to length (e.g. 0.5s to 2.5s)
            delay = min(2.5, max(0.5, len(bubble) * 0.015))
            await asyncio.sleep(delay)

            # 3. Send bubble
            if not await self.send_text(recipient_psid, bubble):
                raise DeliveryError(sent_bubbles, len(bubbles))
            sent_bubbles += 1
