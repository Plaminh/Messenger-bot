"""FastAPI dependencies for injecting components stored in app.state."""

from typing import Optional
from fastapi import Request

from app.chat.debounce import MessageDebouncer
from app.chat.orchestrator import ChatOrchestrator
from app.integrations.messenger.client import MessengerClient
from app.integrations.messenger.dedupe import MessageDeduplicator


def get_orchestrator(request: Request) -> ChatOrchestrator:
    """Retrieve ChatOrchestrator from application state."""
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        orchestrator = ChatOrchestrator(messenger_client=get_messenger_client(request))
        request.app.state.orchestrator = orchestrator
    return orchestrator


def get_debouncer(request: Request) -> MessageDebouncer:
    """Retrieve MessageDebouncer from application state."""
    debouncer = getattr(request.app.state, "debouncer", None)
    if debouncer is None:
        debouncer = MessageDebouncer()
        request.app.state.debouncer = debouncer
    return debouncer


def get_deduplicator(request: Request) -> MessageDeduplicator:
    """Retrieve MessageDeduplicator from application state."""
    deduplicator = getattr(request.app.state, "deduplicator", None)
    if deduplicator is None:
        deduplicator = MessageDeduplicator()
        request.app.state.deduplicator = deduplicator
    return deduplicator


def get_messenger_client(request: Request) -> MessengerClient:
    """Retrieve MessengerClient from application state or create default."""
    if hasattr(request, "app"):
        client = getattr(request.app.state, "messenger_client", None)
        if client is not None:
            return client
    return MessengerClient()
