import asyncio
import time
from datetime import datetime, timezone
import pytest

from token_guard import (
    AsyncCostPolicy,
    AsyncFixedWindowPolicy,
    AsyncLeakyBucketPolicy,
    AsyncPolicyEvaluator,
    AsyncQuotaPolicy,
    AsyncRolePolicy,
    AsyncSlidingWindowPolicy,
    AsyncTokenBucketPolicy,
    AsyncTokenGuard,
    BasePolicy,
    CostPolicy,
    FixedWindowPolicy,
    LeakyBucketPolicy,
    PolicyContext,
    PolicyEvaluator,
    PolicyFactory,
    PolicyResult,
    QuotaPolicy,
    RolePolicy,
    SlidingWindowPolicy,
    TokenBucketPolicy,
    TokenGuard,
)


class TestPolicyModels:
    def test_policy_context_initialization(self):
        ctx = PolicyContext(user_id="user1", input_tokens=10, output_tokens=20)
        assert ctx.total_tokens == 30
        assert ctx.user_id == "user1"
        assert ctx.model == "default"

    def test_policy_result(self):
        res = PolicyResult(allowed=False, reason="limit hit", retry_after=5.0)
        assert not res.allowed
        assert res.reason == "limit hit"
        assert res.retry_after == 5.0


class TestPolicyFactory:
    def test_list_policies(self):
        policies = PolicyFactory.list_policies()
        assert "fixed_window" in policies
        assert "sliding_window" in policies
        assert "token_bucket" in policies
        assert "leaky_bucket" in policies

    def test_create_fixed_window(self):
        policy = PolicyFactory.create("fixed_window", limit=100)
        assert isinstance(policy, FixedWindowPolicy)
        assert policy.limit == 100

    def test_create_unknown_policy_raises(self):
        with pytest.raises(ValueError, match="Unknown policy"):
            PolicyFactory.create("nonexistent_policy")

    def test_custom_policy_registration(self):
        class CustomTestPolicy(BasePolicy):
            def evaluate(self, context, storage=None):
                return PolicyResult(allowed=True)

        PolicyFactory.register("custom_test", CustomTestPolicy)
        policy = PolicyFactory.create("custom_test")
        assert isinstance(policy, CustomTestPolicy)


class TestFixedWindowPolicy:
    def test_fixed_window_under_limit(self):
        policy = FixedWindowPolicy(limit=100, window=3600)
        ctx = PolicyContext(user_id="alice", input_tokens=40, output_tokens=10)
        res = policy.evaluate(ctx)
        assert res.allowed

    def test_fixed_window_exceeded(self):
        policy = FixedWindowPolicy(limit=50, window=3600)
        ctx1 = PolicyContext(user_id="alice", input_tokens=40, output_tokens=0)
        assert policy.evaluate(ctx1).allowed

        ctx2 = PolicyContext(user_id="alice", input_tokens=20, output_tokens=0)
        res2 = policy.evaluate(ctx2)
        assert not res2.allowed
        assert "exceeded" in res2.reason

    @pytest.mark.asyncio
    async def test_async_fixed_window(self):
        policy = AsyncFixedWindowPolicy(limit=50, window=3600)
        ctx1 = PolicyContext(user_id="alice", input_tokens=30, output_tokens=0)
        res1 = await policy.evaluate(ctx1)
        assert res1.allowed

        ctx2 = PolicyContext(user_id="alice", input_tokens=30, output_tokens=0)
        res2 = await policy.evaluate(ctx2)
        assert not res2.allowed


class TestSlidingWindowPolicy:
    def test_sliding_window_basic(self):
        policy = SlidingWindowPolicy(limit=100, window=3600, buckets=60)
        ctx = PolicyContext(user_id="bob", input_tokens=50, output_tokens=0)
        assert policy.evaluate(ctx).allowed

        ctx2 = PolicyContext(user_id="bob", input_tokens=60, output_tokens=0)
        res2 = policy.evaluate(ctx2)
        assert not res2.allowed

    @pytest.mark.asyncio
    async def test_async_sliding_window(self):
        policy = AsyncSlidingWindowPolicy(limit=100, window=3600, buckets=60)
        ctx = PolicyContext(user_id="bob", input_tokens=50, output_tokens=0)
        res = await policy.evaluate(ctx)
        assert res.allowed


class TestTokenBucketPolicy:
    def test_token_bucket_capacity_and_refill(self):
        policy = TokenBucketPolicy(capacity=100, refill_rate=10.0)
        ctx1 = PolicyContext(user_id="charlie", input_tokens=80, output_tokens=0)
        assert policy.evaluate(ctx1).allowed

        ctx2 = PolicyContext(user_id="charlie", input_tokens=30, output_tokens=0)
        res2 = policy.evaluate(ctx2)
        assert not res2.allowed
        assert res2.retry_after > 0

    @pytest.mark.asyncio
    async def test_async_token_bucket(self):
        policy = AsyncTokenBucketPolicy(capacity=100, refill_rate=10.0)
        ctx1 = PolicyContext(user_id="charlie", input_tokens=50, output_tokens=0)
        res1 = await policy.evaluate(ctx1)
        assert res1.allowed


class TestLeakyBucketPolicy:
    def test_leaky_bucket_capacity(self):
        policy = LeakyBucketPolicy(capacity=100, leak_rate=5.0)
        ctx1 = PolicyContext(user_id="dave", input_tokens=80, output_tokens=0)
        assert policy.evaluate(ctx1).allowed

        ctx2 = PolicyContext(user_id="dave", input_tokens=30, output_tokens=0)
        res2 = policy.evaluate(ctx2)
        assert not res2.allowed

    @pytest.mark.asyncio
    async def test_async_leaky_bucket(self):
        policy = AsyncLeakyBucketPolicy(capacity=100, leak_rate=5.0)
        ctx = PolicyContext(user_id="dave", input_tokens=50, output_tokens=0)
        res = await policy.evaluate(ctx)
        assert res.allowed


class TestCostPolicy:
    def test_cost_policy_daily_limit(self):
        policy = CostPolicy(daily_limit_usd=0.01, cost_per_1k_input_tokens=0.005)
        # 1,000 tokens = $0.005
        ctx1 = PolicyContext(user_id="eve", input_tokens=1000, output_tokens=0)
        assert policy.evaluate(ctx1).allowed

        # Additional 2,000 tokens = $0.010 -> total $0.015 > $0.01
        ctx2 = PolicyContext(user_id="eve", input_tokens=2000, output_tokens=0)
        res2 = policy.evaluate(ctx2)
        assert not res2.allowed

    @pytest.mark.asyncio
    async def test_async_cost_policy(self):
        policy = AsyncCostPolicy(daily_limit_usd=1.0)
        ctx = PolicyContext(user_id="eve", input_tokens=100, output_tokens=0)
        res = await policy.evaluate(ctx)
        assert res.allowed


class TestQuotaPolicy:
    def test_quota_policy_daily(self):
        policy = QuotaPolicy(daily_tokens=500)
        ctx1 = PolicyContext(user_id="frank", input_tokens=300, output_tokens=0)
        assert policy.evaluate(ctx1).allowed

        ctx2 = PolicyContext(user_id="frank", input_tokens=300, output_tokens=0)
        res2 = policy.evaluate(ctx2)
        assert not res2.allowed

    @pytest.mark.asyncio
    async def test_async_quota_policy(self):
        policy = AsyncQuotaPolicy(daily_tokens=500)
        ctx = PolicyContext(user_id="frank", input_tokens=200, output_tokens=0)
        res = await policy.evaluate(ctx)
        assert res.allowed


class TestRolePolicy:
    def test_role_policy_mapping(self):
        policy = RolePolicy(
            role_limits={"admin": 1000, "guest": 100},
            user_roles={"grace": "guest", "helen": "admin"},
        )

        ctx_guest = PolicyContext(user_id="grace", input_tokens=150, output_tokens=0)
        assert not policy.evaluate(ctx_guest).allowed

        ctx_admin = PolicyContext(user_id="helen", input_tokens=150, output_tokens=0)
        assert policy.evaluate(ctx_admin).allowed

    @pytest.mark.asyncio
    async def test_async_role_policy(self):
        policy = AsyncRolePolicy(
            role_limits={"guest": 100},
            user_roles={"grace": "guest"},
        )
        ctx = PolicyContext(user_id="grace", input_tokens=50, output_tokens=0)
        res = await policy.evaluate(ctx)
        assert res.allowed


class TestPolicyEngineEvaluator:
    def test_evaluator_short_circuits(self):
        p1 = FixedWindowPolicy(limit=100, window=3600)
        p2 = FixedWindowPolicy(limit=10, window=3600)  # restrictive policy

        evaluator = PolicyEvaluator(policies=[p1, p2])
        ctx = PolicyContext(user_id="ian", input_tokens=20, output_tokens=0)
        res = evaluator.evaluate(ctx)
        assert not res.allowed

    @pytest.mark.asyncio
    async def test_async_evaluator_short_circuits(self):
        p1 = AsyncFixedWindowPolicy(limit=100, window=3600)
        p2 = AsyncFixedWindowPolicy(limit=10, window=3600)

        evaluator = AsyncPolicyEvaluator(policies=[p1, p2])
        ctx = PolicyContext(user_id="ian", input_tokens=20, output_tokens=0)
        res = await evaluator.evaluate(ctx)
        assert not res.allowed


class TestTokenGuardPolicyIntegration:
    def test_token_guard_with_sliding_window_policy(self):
        policy = SlidingWindowPolicy(limit=100, window=3600)
        guard = TokenGuard(policy=policy)

        res1 = guard.track_usage("user_a", input_tokens=60, output_tokens=0)
        assert not res1.limit_exceeded
        assert res1.policy_result.allowed

        res2 = guard.track_usage("user_a", input_tokens=50, output_tokens=0)
        assert res2.limit_exceeded
        assert not res2.policy_result.allowed

    @pytest.mark.asyncio
    async def test_async_token_guard_with_token_bucket_policy(self):
        policy = AsyncTokenBucketPolicy(capacity=100, refill_rate=10.0)
        guard = AsyncTokenGuard(policy=policy)

        res1 = await guard.track_usage("user_b", input_tokens=60, output_tokens=0)
        assert not res1.limit_exceeded
        assert res1.policy_result.allowed

        res2 = await guard.track_usage("user_b", input_tokens=50, output_tokens=0)
        assert res2.limit_exceeded
        assert not res2.policy_result.allowed
