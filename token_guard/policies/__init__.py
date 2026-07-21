from token_guard.policies.base import AsyncBasePolicy, BasePolicy
from token_guard.policies.cost_policy import AsyncCostPolicy, CostPolicy
from token_guard.policies.factory import PolicyFactory
from token_guard.policies.fixed_window import AsyncFixedWindowPolicy, FixedWindowPolicy
from token_guard.policies.leaky_bucket import AsyncLeakyBucketPolicy, LeakyBucketPolicy
from token_guard.policies.models import PolicyContext, PolicyResult
from token_guard.policies.quota_policy import AsyncQuotaPolicy, QuotaPolicy
from token_guard.policies.role_policy import AsyncRolePolicy, RolePolicy
from token_guard.policies.sliding_window import AsyncSlidingWindowPolicy, SlidingWindowPolicy
from token_guard.policies.token_bucket import AsyncTokenBucketPolicy, TokenBucketPolicy

# Register built-in policies with PolicyFactory
PolicyFactory.register("fixed_window", FixedWindowPolicy)
PolicyFactory.register("async_fixed_window", AsyncFixedWindowPolicy)
PolicyFactory.register("sliding_window", SlidingWindowPolicy)
PolicyFactory.register("async_sliding_window", AsyncSlidingWindowPolicy)
PolicyFactory.register("token_bucket", TokenBucketPolicy)
PolicyFactory.register("async_token_bucket", AsyncTokenBucketPolicy)
PolicyFactory.register("leaky_bucket", LeakyBucketPolicy)
PolicyFactory.register("async_leaky_bucket", AsyncLeakyBucketPolicy)
PolicyFactory.register("cost", CostPolicy)
PolicyFactory.register("async_cost", AsyncCostPolicy)
PolicyFactory.register("quota", QuotaPolicy)
PolicyFactory.register("async_quota", AsyncQuotaPolicy)
PolicyFactory.register("role", RolePolicy)
PolicyFactory.register("async_role", AsyncRolePolicy)

__all__ = [
    "PolicyContext",
    "PolicyResult",
    "BasePolicy",
    "AsyncBasePolicy",
    "PolicyFactory",
    "FixedWindowPolicy",
    "AsyncFixedWindowPolicy",
    "SlidingWindowPolicy",
    "AsyncSlidingWindowPolicy",
    "TokenBucketPolicy",
    "AsyncTokenBucketPolicy",
    "LeakyBucketPolicy",
    "AsyncLeakyBucketPolicy",
    "CostPolicy",
    "AsyncCostPolicy",
    "QuotaPolicy",
    "AsyncQuotaPolicy",
    "RolePolicy",
    "AsyncRolePolicy",
]
