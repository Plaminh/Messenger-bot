"""Application settings powered by pydantic-settings.

Enforces fail-fast validation on startup when required environment variables are missing.
"""

from functools import lru_cache
from pydantic import Field, model_validator
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
    GROQ_MODEL_MAIN: str = Field(default="openai/gpt-oss-120b", description="Main conversational model")
    GROQ_MODEL_FAST: str = Field(default="openai/gpt-oss-20b", description="Fast model for summary and extraction")
    GROQ_MAX_COMPLETION_TOKENS: int = Field(default=2048, ge=256, le=8192)
    GROQ_LENGTH_RETRY_MAX_COMPLETION_TOKENS: int = Field(default=4096, ge=512, le=16384)
    DAILY_TOKEN_BUDGET_MAIN: int = Field(default=100_000, description="Daily token quota for main model")
    DAILY_TOKEN_BUDGET_FAST: int = Field(default=500_000, description="Daily token quota for fast model")

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string with pgvector support")

    # Logging; local time is fixed to Asia/Ho_Chi_Minh in prompt and budget code.
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    @model_validator(mode="after")
    def validate_groq_completion_budgets(self) -> "Settings":
        if self.GROQ_LENGTH_RETRY_MAX_COMPLETION_TOKENS <= self.GROQ_MAX_COMPLETION_TOKENS:
            raise ValueError(
                "GROQ_LENGTH_RETRY_MAX_COMPLETION_TOKENS must be greater than "
                "GROQ_MAX_COMPLETION_TOKENS"
            )
        return self

    @property
    def async_database_url(self) -> str:
        """Ensure database URL has async driver (postgresql+psycopg://)."""
        url = self.DATABASE_URL
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
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
