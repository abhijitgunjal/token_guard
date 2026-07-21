"""
exceptions.py
-------------
Custom exception hierarchy for TokenGuard.
"""

from __future__ import annotations


class TokenGuardError(Exception):
    """Base exception for all errors raised by TokenGuard."""
    pass


class ConfigurationError(TokenGuardError):
    """Raised when an invalid configuration or option is provided."""
    pass


class PolicyError(TokenGuardError):
    """Base exception for policy evaluation errors."""
    pass


class StorageError(TokenGuardError):
    """Base exception for storage backend errors."""
    pass


class RateLimitExceededError(PolicyError):
    """Raised when token usage exceeds configured limits."""

    def __init__(self, message: str, user_id: str, limit: int, used: int, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.user_id = user_id
        self.limit = limit
        self.used = used
        self.retry_after = retry_after
