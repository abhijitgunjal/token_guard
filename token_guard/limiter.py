"""
limiter.py
----------
Enforces token usage limits per user.
Supports both total and per-request limits.
"""

from token_guard.tracker import UserUsage


class LimitManager:
    """
    Checks whether a user's token usage has exceeded configured limits.

    Args:
        max_tokens: The maximum total tokens (input + output) allowed
                    per user before an alert is triggered.
    """

    def __init__(self, max_tokens: int) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer.")
        self.max_tokens = max_tokens

    def check(self, usage: UserUsage) -> bool:
        """
        Determine whether the given usage has exceeded the limit.

        Args:
            usage: A UserUsage object with current cumulative counts.

        Returns:
            True  → limit exceeded (alert should be triggered).
            False → still within limits.
        """
        return usage.total_tokens > self.max_tokens

    def utilization(self, usage: UserUsage) -> float:
        """
        Calculate what fraction of the limit has been consumed.

        Args:
            usage: A UserUsage object with current cumulative counts.

        Returns:
            A float in [0.0, ∞) representing usage / limit.
            Values > 1.0 mean the limit has been exceeded.
        """
        return usage.total_tokens / self.max_tokens
