"""Only fully delivered replies become assistant history."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.orchestrator import ChatOrchestrator
from app.db.models import LLMUsage, Message
from app.integrations.llm.base import LLMResult
from app.integrations.messenger.client import DeliveryError, MessengerClient


@pytest.mark.asyncio
async def test_messenger_reports_partial_delivery():
    client = MessengerClient(client=MagicMock(), settings=MagicMock(META_API_VERSION="v21.0"))
    client.send_action = AsyncMock(return_value=True)
    client.send_text = AsyncMock(side_effect=[True, False])
    client.split_into_bubbles = MagicMock(return_value=["one", "two"])

    with patch("app.integrations.messenger.client.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(DeliveryError) as raised:
            await client.send_human_like_response("u", "one\n\ntwo")

    assert (raised.value.sent_bubbles, raised.value.total_bubbles) == (1, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("sent_bubbles", [0, 1])
async def test_failed_or_partial_delivery_keeps_input_and_usage_only(db_session, sent_bubbles):
    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    messenger = MagicMock()
    messenger.send_human_like_response = AsyncMock(side_effect=DeliveryError(sent_bubbles, 2))
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=LLMResult("reply", 7, "main-model", "main"))
    orchestrator = ChatOrchestrator(
        session_factory=factory, messenger_client=messenger, llm_provider=llm, inactivity_delay=60
    )

    await orchestrator.handle_turn(f"user-{sent_bubbles}", "incoming", mid=f"mid-{sent_bubbles}")

    messages = (await db_session.execute(select(Message.role, Message.content))).all()
    usage = (await db_session.execute(select(LLMUsage.tokens))).scalar_one()
    assert messages == [("user", "incoming")]
    assert usage == 7

