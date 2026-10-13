"""Privacy deletion and lightweight startup are release-critical."""

import importlib.util
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.chat.commands import handle_command
from app.db.models import Memory, Message, Summary, User
from app.db.store import add_memory, add_message, upsert_summary
from app.main import lifespan


@pytest.mark.asyncio
async def test_quen_removes_all_personal_data(db_session):
    user = User(fb_psid="privacy", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.commit()
    await add_message(db_session, user.id, "user", "private")
    await add_memory(db_session, user.id, "private memory", "other", 8)
    await upsert_summary(db_session, user.id, "private summary", 1)

    await handle_command(db_session, user, "/quen")

    for model in (User, Message, Memory, Summary):
        assert (await db_session.execute(select(model))).scalars().all() == []


@pytest.mark.asyncio
async def test_startup_has_no_torch_or_embedding_import_path():
    assert importlib.util.find_spec("app.integrations.embedder") is None
    fake_app = SimpleNamespace(state=SimpleNamespace())
    with patch.dict(sys.modules, {"torch": None, "sentence_transformers": None}):
        async with lifespan(fake_app):
            assert fake_app.state.orchestrator is not None

