"""Storage layer providing CRUD for users, messages, memories, and summaries."""

from datetime import datetime
from typing import Any, Optional, Sequence
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.memory.models import Memory, Message, Summary, User

logger = get_logger(__name__)


async def get_or_create_user(
    session: AsyncSession,
    fb_psid: str,
    display_name: Optional[str] = None,
) -> User:
    """Retrieve existing user by fb_psid or create a new user profile."""
    stmt = select(User).where(User.fb_psid == fb_psid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        user.last_seen_at = func.now()
        if display_name and not user.display_name:
            user.display_name = display_name
    else:
        user = User(
            fb_psid=fb_psid,
            display_name=display_name,
            style_profile={},
            core_profile={},
        )
        session.add(user)

    await session.commit()
    await session.refresh(user)
    return user


async def update_user_profiles(
    session: AsyncSession,
    user_id: int,
    *,
    style_profile: Optional[dict[str, Any]] = None,
    core_profile: Optional[dict[str, Any]] = None,
    display_name: Optional[str] = None,
    last_user_msg_at: Optional[datetime] = None,
) -> None:
    """Update profile data and timestamps for specified user."""
    values: dict[str, Any] = {"last_seen_at": func.now()}
    if style_profile is not None:
        values["style_profile"] = style_profile
    if core_profile is not None:
        values["core_profile"] = core_profile
    if display_name is not None:
        values["display_name"] = display_name
    if last_user_msg_at is not None:
        values["last_user_msg_at"] = last_user_msg_at

    stmt = update(User).where(User.id == user_id).values(**values)
    await session.execute(stmt)
    await session.commit()


async def add_message(
    session: AsyncSession,
    user_id: int,
    role: str,
    content: str,
    mid: Optional[str] = None,
) -> Message:
    """Insert a message record."""
    msg = Message(
        user_id=user_id,
        role=role,
        content=content,
        mid=mid,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def get_recent_messages(
    session: AsyncSession,
    user_id: int,
    limit: int = 50,
) -> list[Message]:
    """Retrieve up to limit recent messages in ascending chronological order."""
    stmt = (
        select(Message)
        .where(Message.user_id == user_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def get_unsummarized_messages(
    session: AsyncSession,
    user_id: int,
    upto_message_id: Optional[int] = None,
) -> list[Message]:
    """Retrieve messages not yet covered by rolling summary in chronological order."""
    stmt = select(Message).where(Message.user_id == user_id)
    if upto_message_id is not None:
        stmt = stmt.where(Message.id > upto_message_id)
    stmt = stmt.order_by(Message.id.asc())

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_user_message_count(session: AsyncSession, user_id: int) -> int:
    """Count total user-originated messages."""
    stmt = select(func.count(Message.id)).where(
        Message.user_id == user_id,
        Message.role == "user",
    )
    result = await session.execute(stmt)
    count = result.scalar()
    return count or 0


async def get_summary(session: AsyncSession, user_id: int) -> Optional[Summary]:
    """Retrieve current conversation summary for user."""
    stmt = select(Summary).where(Summary.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_summary(
    session: AsyncSession,
    user_id: int,
    content: str,
    upto_message_id: int,
) -> Summary:
    """Insert or update conversation summary."""
    summary = await get_summary(session, user_id)
    if summary:
        summary.content = content
        summary.upto_message_id = upto_message_id
        summary.updated_at = func.now()
    else:
        summary = Summary(
            user_id=user_id,
            content=content,
            upto_message_id=upto_message_id,
        )
        session.add(summary)

    await session.commit()
    await session.refresh(summary)
    return summary


async def add_memory(
    session: AsyncSession,
    user_id: int,
    content: str,
    category: str,
    importance: int,
    embedding: list[float],
    source_message_ids: Optional[list[int]] = None,
) -> Memory:
    """Insert a new semantic memory."""
    mem = Memory(
        user_id=user_id,
        content=content,
        category=category,
        importance=max(1, min(10, importance)),
        embedding=embedding,
        source_message_ids=source_message_ids or [],
    )
    session.add(mem)
    await session.commit()
    await session.refresh(mem)
    return mem


async def update_memory(
    session: AsyncSession,
    memory_id: int,
    content: str,
    category: str,
    importance: int,
    embedding: list[float],
) -> None:
    """Update content and vector representation of an existing memory."""
    stmt = (
        update(Memory)
        .where(Memory.id == memory_id)
        .values(
            content=content,
            category=category,
            importance=max(1, min(10, importance)),
            embedding=embedding,
            last_accessed_at=func.now(),
        )
    )
    await session.execute(stmt)
    await session.commit()


async def delete_memory(session: AsyncSession, memory_id: int) -> None:
    """Delete a memory by id."""
    stmt = delete(Memory).where(Memory.id == memory_id)
    await session.execute(stmt)
    await session.commit()


async def get_all_memories(session: AsyncSession, user_id: int) -> list[Memory]:
    """Retrieve all memories stored for a user."""
    stmt = (
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.importance.desc(), Memory.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_all_user_data(session: AsyncSession, user_id: int) -> None:
    """Completely wipe all user data across all tables via cascade deletion."""
    stmt = delete(User).where(User.id == user_id)
    await session.execute(stmt)
    await session.commit()
    logger.info("Wiped all records for user_id=%d", user_id)
