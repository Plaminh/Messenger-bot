"""Messenger profile names are fetched safely and persisted once."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.commands import handle_command
from app.chat.orchestrator import ChatOrchestrator
from app.db.models import User
from app.integrations.llm.base import LLMResult
from app.integrations.messenger.client import MessengerClient
from app.persona.prompt import assemble_system_prompt


def _profile_client(response=None, side_effect=None):
    http_client = MagicMock()
    http_client.get = AsyncMock(return_value=response, side_effect=side_effect)
    settings = MagicMock(META_API_VERSION="v21.0", META_PAGE_ACCESS_TOKEN="secret-token")
    return MessengerClient(client=http_client, settings=settings), http_client


@pytest.mark.asyncio
async def test_fetch_first_name_success_uses_bearer_header_only():
    response = MagicMock(status_code=200)
    response.json.return_value = {"first_name": "  Minh Anh  "}
    client, http_client = _profile_client(response=response)

    assert await client.fetch_first_name("psid-1") == ("Minh Anh", True)
    kwargs = http_client.get.await_args.kwargs
    assert kwargs["headers"] == {"Authorization": "Bearer secret-token"}
    assert kwargs["params"] == {"fields": "first_name"}
    assert kwargs["timeout"] == 3.0
    assert "secret-token" not in http_client.get.await_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [(404, (None, True)), (429, (None, False)), (503, (None, False))],
)
async def test_fetch_first_name_status_semantics(status, expected):
    response = MagicMock(status_code=status)
    client, _ = _profile_client(response=response)
    assert await client.fetch_first_name("psid-2") == expected


@pytest.mark.asyncio
async def test_fetch_first_name_network_error_and_unsafe_names():
    request = httpx.Request("GET", "https://graph.facebook.com")
    client, _ = _profile_client(side_effect=httpx.ReadTimeout("timeout", request=request))
    assert await client.fetch_first_name("psid-3") == (None, False)

    for unsafe_name in ("Minh\nBậy", "Minh_Anh", "A" * 41):
        response = MagicMock(status_code=200)
        response.json.return_value = {"first_name": unsafe_name}
        client, _ = _profile_client(response=response)
        assert await client.fetch_first_name("psid-3") == (None, True)


def test_prompt_only_includes_name_line_when_name_exists():
    common = dict(
        core_profile={},
        style_profile={},
        relevant_memories=[],
        summary_content=None,
        recent_user_messages=[],
    )
    named = assemble_system_prompt(display_name="An", **common)
    unnamed = assemble_system_prompt(display_name=None, **common)
    assert "Tên gọi của người dùng: An" in named
    assert "Tên gọi của người dùng:" not in unnamed


@pytest.mark.asyncio
async def test_nho_reads_display_name(db_session):
    user = User(fb_psid="named", display_name="Linh", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.flush()
    reply = await handle_command(db_session, user, "/nho")
    assert "Tên bạn: Linh" in reply


@pytest.mark.asyncio
async def test_name_lookup_is_persisted_once_and_failure_does_not_block(db_session, mock_llm):
    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    messenger = MagicMock()
    messenger.fetch_first_name = AsyncMock(return_value=("Hà", True))
    orchestrator = ChatOrchestrator(
        messenger_client=messenger,
        session_factory=factory,
        llm_provider=mock_llm,
    )

    ctx = await orchestrator.prepare_context("lookup-once", "xin chào")
    assert ctx is not None and ctx.display_name == "Hà"
    await orchestrator.persist_turn(ctx, LLMResult("chào bạn", 0, "test", "main"))
    second = await orchestrator.prepare_context("lookup-once", "lần hai")
    assert second is not None and second.display_name == "Hà"
    messenger.fetch_first_name.assert_awaited_once()

    failing = MagicMock()
    failing.fetch_first_name = AsyncMock(side_effect=RuntimeError("network"))
    other = ChatOrchestrator(
        messenger_client=failing,
        session_factory=factory,
        llm_provider=mock_llm,
    )
    assert await other.prepare_context("lookup-fails", "vẫn trò chuyện") is not None
