from datetime import datetime, timezone
from typing import Any, List, Optional, Union

from token_guard.engine.evaluator import AsyncPolicyEvaluator, PolicyEvaluator
from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.models import PolicyContext, PolicyResult


class PolicyPipeline:
    def __init__(
        self,
        policies: Optional[List[Union[BasePolicy, AsyncBasePolicy]]] = None,
        evaluator: Optional[PolicyEvaluator] = None,
    ) -> None:
        self.evaluator = evaluator or PolicyEvaluator(policies=policies)

    def process(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "default",
        storage: Optional[Any] = None,
        metadata: Optional[dict] = None,
    ) -> PolicyResult:
        context = PolicyContext(
            user_id=user_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        return self.evaluator.evaluate(context, storage)


class AsyncPolicyPipeline:
    def __init__(
        self,
        policies: Optional[List[Union[BasePolicy, AsyncBasePolicy]]] = None,
        evaluator: Optional[AsyncPolicyEvaluator] = None,
    ) -> None:
        self.evaluator = evaluator or AsyncPolicyEvaluator(policies=policies)

    async def process(
        self,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "default",
        storage: Optional[Any] = None,
        metadata: Optional[dict] = None,
    ) -> PolicyResult:
        context = PolicyContext(
            user_id=user_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        return await self.evaluator.evaluate(context, storage)
