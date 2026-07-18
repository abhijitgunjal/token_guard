"""
storage/models.py
-----------------
Shared data models for the storage layer.
Kept separate so backends can import without circular deps.
"""

from dataclasses import dataclass


@dataclass
class UserUsage:
    """Holds cumulative token usage for a single user."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Combined input + output token count."""
        return self.input_tokens + self.output_tokens

    def __repr__(self) -> str:
        return (
            f"UserUsage(input={self.input_tokens}, "
            f"output={self.output_tokens}, "
            f"total={self.total_tokens})"
        )
