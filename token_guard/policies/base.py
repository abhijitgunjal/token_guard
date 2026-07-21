from abc import ABC, abstractmethod
from typing import Any, Optional

from token_guard.policies.models import PolicyContext, PolicyResult


class BasePolicy(ABC):
    @abstractmethod
    def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        """Evaluate the policy synchronously against the given context and storage backend."""
        pass


class AsyncBasePolicy(ABC):
    @abstractmethod
    async def evaluate(self, context: PolicyContext, storage: Optional[Any] = None) -> PolicyResult:
        """Evaluate the policy asynchronously against the given context and storage backend."""
        pass
