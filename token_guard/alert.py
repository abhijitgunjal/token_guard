"""
alert.py
--------
Extensible alert system for token limit violations.

MVP ships with ConsoleAlertHandler.
New channels (Slack, email, webhook) can be added by subclassing
BaseAlertHandler and registering with AlertManager.
"""

import abc
import logging
from token_guard.tracker import UserUsage

logger = logging.getLogger(__name__)


class BaseAlertHandler(abc.ABC):
    """Abstract base class for alert handlers.

    To add a new channel, subclass this and implement `send`.
    """

    @abc.abstractmethod
    def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
        """
        Send an alert notification.

        Args:
            user_id: The user whose limit was exceeded.
            usage:   Current usage statistics.
            limit:   The configured token limit.
        """


class ConsoleAlertHandler(BaseAlertHandler):
    """Prints a warning to stdout/stderr via the logging module."""

    def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
        message = (
            f"[TokenGuard] ⚠️  LIMIT EXCEEDED — user='{user_id}' | "
            f"total={usage.total_tokens} tokens | "
            f"(input={usage.input_tokens}, output={usage.output_tokens}) | "
            f"limit={limit}"
        )
        logger.warning(message)
        print(message)


class AlertManager:
    """
    Manages one or more alert handlers.

    By default, a ConsoleAlertHandler is registered.
    Additional handlers can be added at construction time or
    at runtime via `add_handler`.

    Args:
        handlers: Optional list of BaseAlertHandler instances.
                  Defaults to [ConsoleAlertHandler()].
    """

    def __init__(
        self, handlers: list[BaseAlertHandler] | None = None
    ) -> None:
        self._handlers: list[BaseAlertHandler] = handlers or [
            ConsoleAlertHandler()
        ]

    def add_handler(self, handler: BaseAlertHandler) -> None:
        """Register an additional alert handler.

        Args:
            handler: A BaseAlertHandler implementation to add.
        """
        self._handlers.append(handler)

    def trigger(self, user_id: str, usage: UserUsage, limit: int) -> None:
        """
        Fire all registered alert handlers.

        Args:
            user_id: The user whose limit was exceeded.
            usage:   Current usage statistics.
            limit:   The configured token limit.
        """
        for handler in self._handlers:
            try:
                handler.send(user_id, usage, limit)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Alert handler %s failed: %s",
                    type(handler).__name__,
                    exc,
                )
