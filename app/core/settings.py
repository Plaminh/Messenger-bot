"""Application settings powered by pydantic-settings.

Enforces fail-fast validation on startup when required environment variables are missing.
"""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Messenger Friend Chatbot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Meta Messenger credentials
    META_VERIFY_TOKEN: str = Field(..., description="Token for Meta webhook verification challenge")
    META_PAGE_ACCESS_TOKEN: str = Field(..., description="Access token for Facebook Messenger Page")
    META_APP_SECRET: str = Field(..., description="App secret used for HMAC-SHA256 signature verification")
    META_API_VERSION: str = Field(default="v21.0", description="Graph API version")

    # Groq LLM settings
    GROQ_API_KEY: str = Field(..., description="Groq API Key")
    GROQ_MODEL_MAIN: str = Field(default="llama-3.3-70b-versatile", description="Main conversational model")
    GROQ_MODEL_FAST: str = Field(default="llama-3.1-8b-instant", description="Fast model for summary and extraction")
    DAILY_TOKEN_BUDGET_MAIN: int = Field(default=100_000, description="Daily token quota for main model")
    DAILY_TOKEN_BUDGET_FAST: int = Field(default=500_000, description="Daily token quota for fast model")

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string with pgvector support")

    # Memory & Embedder
    EMBEDDING_MODEL: str = Field(default="intfloat/multilingual-e5-small", description="Sentence transformer model")
    RETRIEVER_WEIGHT_COSINE: float = Field(default=1.0, description="Cosine similarity weight A")
    RETRIEVER_WEIGHT_RECENCY: float = Field(default=0.3, description="Recency decay weight B")
    RETRIEVER_WEIGHT_IMPORTANCE: float = Field(default=0.3, description="Importance score weight C")
    RETRIEVER_TAU_DAYS: float = Field(default=14.0, description="Exponential decay half-life factor in days")

    # Logging and Environment
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    TZ: str = Field(default="Asia/Ho_Chi_Minh", description="Application timezone")

    @property
    def async_database_url(self) -> str:
        """Ensure database URL has async driver (postgresql+psycopg://)."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Ensure database URL has sync driver for Alembic."""
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached instance of Settings."""
    return Settings()
