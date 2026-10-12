"""FastAPI application entrypoint for Messenger Friend Bot."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router
from app.chat.debounce import MessageDebouncer
from app.chat.orchestrator import ChatOrchestrator
from app.integrations.embedder import get_embedder
from app.integrations.messenger.client import MessengerClient
from app.integrations.messenger.dedupe import MessageDeduplicator

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing startup and graceful shutdown."""
    configure_logging()
    logger.info("Initializing Messenger Friend Bot...")

    embedder = get_embedder()
    if get_settings().EMBEDDING_PRELOAD:
        # Fail fast at startup instead of silently serving bad embeddings later
        await embedder.preload()

    messenger_client = MessengerClient()
    app.state.messenger_client = messenger_client
    app.state.orchestrator = ChatOrchestrator(messenger_client=messenger_client, embedder=embedder)
    app.state.debouncer = MessageDebouncer()
    app.state.deduplicator = MessageDeduplicator()

    yield

    logger.info("Shutting down Messenger Friend Bot...")
    client = getattr(app.state, "messenger_client", None)
    if client:
        await client.aclose()


def create_app() -> FastAPI:
    """Create and configure FastAPI application instance."""
    app = FastAPI(
        title="Messenger Friend Bot",
        description="A warm, empathetic confidant chatbot for Facebook Messenger",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Components are created once in lifespan(); nothing heavy is built at import time.
    # Mount routers
    app.include_router(health_router)
    app.include_router(webhook_router)

    return app


app = create_app()
