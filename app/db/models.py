"""SQLAlchemy models for Messenger Friend Bot."""

from sqlalchemy import (
    Column,
    Integer,
    SmallInteger,
    String,
    Text,
    DateTime,
    Date,
    ForeignKey,
    JSON,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.db import Base

# Dialect-tolerant types for tests (SQLite) and production (PostgreSQL)
JSONB_TYPE = JSON().with_variant(JSONB, "postgresql")
ARRAY_INT_TYPE = JSON().with_variant(ARRAY(Integer), "postgresql")


class User(Base):
    """User account identified by Facebook Page-Scoped ID (PSID)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fb_psid = Column(String(128), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    style_profile = Column(JSONB_TYPE, nullable=False, default=dict)
    core_profile = Column(JSONB_TYPE, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_user_msg_at = Column(DateTime(timezone=True), nullable=True)
    # Highest message id already processed by the memory extractor
    last_extracted_message_id = Column(Integer, nullable=True)

    # Relationships
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Message(Base):
    """Individual conversational turns."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(16), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    mid = Column(String(255), unique=True, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user = relationship("User", back_populates="messages")


class Memory(Base):
    """Long-term distilled facts and semantic memories about user."""

    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # B-tree index on user_id for filtering before vector ranking
    # Note: HNSW index on embedding can be added when dataset grows large.
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    category = Column(String(32), nullable=False)  # person|event|preference|feeling|goal|other
    importance = Column(SmallInteger, nullable=False)  # 1-10
    # Historical column retained for compatibility; runtime no longer writes or searches it.
    embedding = Column(Vector(384), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # Lần tạo/cập nhật gần nhất của ký ức; không thay đổi khi ký ức được truy hồi.
    last_accessed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source_message_ids = Column(ARRAY_INT_TYPE, nullable=True, default=list)

    user = relationship("User", back_populates="memories")


class Summary(Base):
    """Rolling compressed conversation summary."""

    __tablename__ = "summaries"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content = Column(Text, nullable=False, default="")
    upto_message_id = Column(Integer, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="summary")


class LLMUsage(Base):
    """Daily token and request consumption tracker per model."""

    __tablename__ = "llm_usage"

    day = Column(Date, primary_key=True)
    model = Column(String(64), primary_key=True)
    tokens = Column(Integer, nullable=False, default=0)
    requests = Column(Integer, nullable=False, default=0)
