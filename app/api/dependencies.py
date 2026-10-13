"""FastAPI dependencies for injecting components stored in app.state."""

from fastapi import Request

from app.chat.debounce import MessageDebouncer
from app.chat.orchestrator import ChatOrchestrator
from app.integrations.messenger.client import MessengerClient
from app.integrations.messenger.dedupe import MessageDeduplicator


def get_orchestrator(request: Request) -> ChatOrchestrator:
    """Retrieve ChatOrchestrator from application state."""
    return request.app.state.orchestrator


def get_debouncer(request: Request) -> MessageDebouncer:
    """Retrieve MessageDebouncer from application state."""
    return request.app.state.debouncer


def get_deduplicator(request: Request) -> MessageDeduplicator:
    """Retrieve MessageDeduplicator from application state."""
    return request.app.state.deduplicator


def get_messenger_client(request: Request) -> MessengerClient:
    """Retrieve MessengerClient from application state."""
    return request.app.state.messenger_client
