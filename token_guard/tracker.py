"""
tracker.py
----------
Backwards-compatibility shim.

UsageTracker and UserUsage are now in token_guard.storage.
This module re-exports them so existing code keeps working.

Prefer importing from token_guard.storage directly:
    from token_guard.storage import InMemoryStorage, UserUsage
"""

from token_guard.storage.models import UserUsage
from token_guard.storage.memory import InMemoryStorage as UsageTracker

__all__ = ["UserUsage", "UsageTracker"]
