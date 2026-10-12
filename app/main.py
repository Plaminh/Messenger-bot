"""FastAPI application entrypoint for Messenger Friend Bot."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.logging import configure_logging, get_logger
from app.api.health import router as health_router
from app.api.webhook import router as webhook_router
from app.integrations.messenger.client import get_messenger_client, set_messenger_client

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing startup and graceful shutdown."""
    configure_logging()
    logger.info("Initializing Messenger Friend Bot...")
    from app.api.webhook import set_turn_handler
    from app.chat.orchestrator import get_orchestrator
    set_turn_handler(get_orchestrator().handle_turn)
    yield
    logger.info("Shutting down Messenger Friend Bot...")
    set_turn_handler(None)
    client = get_messenger_client()
    await client.aclose()
    set_messenger_client(None)


def create_app() -> FastAPI:
    """Create and configure FastAPI application instance."""
    app = FastAPI(
        title="Messenger Friend Bot",
        description="A warm, empathetic confidant chatbot for Facebook Messenger",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Mount routers
    app.include_router(health_router)
    app.include_router(webhook_router)

    return app


app = create_app()
