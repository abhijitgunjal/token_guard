"""
async_alert.py
--------------
Extensible async alert system for token limit violations.
"""

import abc
import asyncio
import logging
from token_guard.storage.models import UserUsage
from token_guard.alert import BaseAlertHandler

logger = logging.getLogger(__name__)


class AsyncBaseAlertHandler(abc.ABC):
    """Abstract base class for async alert handlers.

    To add a new async channel, subclass this and implement `send`.
    """

    @abc.abstractmethod
    async def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
        """
        Send an alert notification asynchronously.
        """


class AsyncAlertManager:
    """
    Manages one or more alert handlers (sync or async).
    """

    def __init__(
        self, handlers: list[BaseAlertHandler | AsyncBaseAlertHandler] | None = None
    ) -> None:
        from token_guard.alert import ConsoleAlertHandler
        self._handlers: list[BaseAlertHandler | AsyncBaseAlertHandler] = handlers or [
            ConsoleAlertHandler()
        ]

    def add_handler(self, handler: BaseAlertHandler | AsyncBaseAlertHandler) -> None:
        self._handlers.append(handler)

    async def trigger(self, user_id: str, usage: UserUsage, limit: int) -> None:
        for handler in self._handlers:
            try:
                if isinstance(handler, AsyncBaseAlertHandler):
                    await handler.send(user_id, usage, limit)
                else:
                    # Sync handler — run in thread executor to avoid blocking the event loop
                    await asyncio.to_thread(handler.send, user_id, usage, limit)
            except Exception as exc:
                logger.error(
                    "Async alert handler %s failed: %s",
                    type(handler).__name__,
                    exc,
                )
