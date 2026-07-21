import os
import pytest
from unittest.mock import MagicMock, patch

from token_guard import (
    TokenGuard,
    AsyncTokenGuard,
    FixedWindowPolicy,
    AsyncFixedWindowPolicy,
    SlidingWindowPolicy,
    AsyncSlidingWindowPolicy,
    TokenBucketPolicy,
    AsyncTokenBucketPolicy,
    LeakyBucketPolicy,
    AsyncLeakyBucketPolicy,
    CostPolicy,
    AsyncCostPolicy,
    QuotaPolicy,
    AsyncQuotaPolicy,
    RolePolicy,
    AsyncRolePolicy,
    PolicyPipeline,
    AsyncPolicyPipeline,
    StorageFactory,
    PostgreSQLStorage,
    AsyncPostgreSQLStorage,
    DynamoDBStorage,
    AsyncDynamoDBStorage,
    OpenAITokenCounter,
)
from token_guard.exceptions import TokenGuardError, PolicyError, StorageError, RateLimitExceededError
from token_guard.policies.models import PolicyContext, PolicyResult


class TestPolicyEdgeCases:
    def test_policy_invalid_arguments_raise_value_error(self):
        with pytest.raises(ValueError):
            FixedWindowPolicy(limit=0)
        with pytest.raises(ValueError):
            FixedWindowPolicy(limit=100, window=0)
        with pytest.raises(ValueError):
            FixedWindowPolicy(limit=100, max_users=0)

        with pytest.raises(ValueError):
            SlidingWindowPolicy(limit=0)
        with pytest.raises(ValueError):
            SlidingWindowPolicy(limit=100, buckets=0)

        with pytest.raises(ValueError):
            TokenBucketPolicy(capacity=0, refill_rate=1.0)
        with pytest.raises(ValueError):
            TokenBucketPolicy(capacity=100, refill_rate=0.0)

        with pytest.raises(ValueError):
            LeakyBucketPolicy(capacity=0, leak_rate=1.0)
        with pytest.raises(ValueError):
            LeakyBucketPolicy(capacity=100, leak_rate=0.0)

        with pytest.raises(ValueError):
            CostPolicy(daily_limit_usd=0.0)
        with pytest.raises(ValueError):
            CostPolicy(monthly_limit_usd=-5.0)

        with pytest.raises(ValueError):
            QuotaPolicy(daily_tokens=0)
        with pytest.raises(ValueError):
            QuotaPolicy(monthly_tokens=-10)

    def test_fixed_window_eviction(self):
        policy = FixedWindowPolicy(limit=1000, window=3600, max_users=2)
        ctx1 = PolicyContext(user_id="user1", model="m", input_tokens=10, output_tokens=10, total_tokens=20)
        ctx2 = PolicyContext(user_id="user2", model="m", input_tokens=10, output_tokens=10, total_tokens=20)
        ctx3 = PolicyContext(user_id="user3", model="m", input_tokens=10, output_tokens=10, total_tokens=20)

        policy.evaluate(ctx1)
        policy.evaluate(ctx2)
        policy.evaluate(ctx3)

        assert len(policy._state) <= 3

    def test_sliding_window_eviction(self):
        policy = SlidingWindowPolicy(limit=1000, window=3600, max_users=2)
        ctx1 = PolicyContext(user_id="user1", model="m", input_tokens=10, output_tokens=10, total_tokens=20)
        ctx2 = PolicyContext(user_id="user2", model="m", input_tokens=10, output_tokens=10, total_tokens=20)
        ctx3 = PolicyContext(user_id="user3", model="m", input_tokens=10, output_tokens=10, total_tokens=20)

        policy.evaluate(ctx1)
        policy.evaluate(ctx2)
        policy.evaluate(ctx3)

        assert len(policy._state) <= 3

    def test_token_bucket_refill_and_limit(self):
        policy = TokenBucketPolicy(capacity=50, refill_rate=1000.0)
        ctx = PolicyContext(user_id="tb_user", model="m", input_tokens=60, output_tokens=0, total_tokens=60)
        res = policy.evaluate(ctx)
        assert not res.allowed
        assert res.retry_after >= 0

    def test_leaky_bucket_leak_and_limit(self):
        policy = LeakyBucketPolicy(capacity=50, leak_rate=1.0)
        ctx = PolicyContext(user_id="lb_user", model="m", input_tokens=60, output_tokens=0, total_tokens=60)
        res = policy.evaluate(ctx)
        assert not res.allowed

    def test_cost_policy_monthly_limit(self):
        policy = CostPolicy(monthly_limit_usd=0.01, cost_per_1k_input_tokens=0.01)
        ctx1 = PolicyContext(user_id="c_user", model="m", input_tokens=500, output_tokens=0, total_tokens=500)
        assert policy.evaluate(ctx1).allowed

        ctx2 = PolicyContext(user_id="c_user", model="m", input_tokens=1000, output_tokens=0, total_tokens=1000)
        res2 = policy.evaluate(ctx2)
        assert not res2.allowed
        assert "cost limit" in res2.reason.lower()

    def test_quota_policy_monthly_limit(self):
        policy = QuotaPolicy(monthly_tokens=500)
        ctx1 = PolicyContext(user_id="q_user", model="m", input_tokens=300, output_tokens=0, total_tokens=300)
        assert policy.evaluate(ctx1).allowed

        ctx2 = PolicyContext(user_id="q_user", model="m", input_tokens=300, output_tokens=0, total_tokens=300)
        res2 = policy.evaluate(ctx2)
        assert not res2.allowed
        assert "quota" in res2.reason.lower()

    def test_role_policy_default_role(self):
        policy = RolePolicy(
            role_limits={"guest": 100},
            user_roles={},
            default_role="guest",
        )
        ctx = PolicyContext(user_id="unknown_user", model="m", input_tokens=150, output_tokens=0, total_tokens=150)
        res = policy.evaluate(ctx)
        assert not res.allowed
        assert "Role 'guest'" in res.reason


class TestPipelineEdgeCases:
    def test_policy_pipeline_sync(self):
        policy = FixedWindowPolicy(limit=100)
        pipeline = PolicyPipeline(policies=[policy])
        res = pipeline.process(user_id="p_user", input_tokens=50, output_tokens=0)
        assert res.allowed

    @pytest.mark.asyncio
    async def test_policy_pipeline_async(self):
        policy = AsyncFixedWindowPolicy(limit=100)
        pipeline = AsyncPolicyPipeline(policies=[policy])
        res = await pipeline.process(user_id="p_user", input_tokens=50, output_tokens=0)
        assert res.allowed


class TestStorageEdgeCases:
    def test_storage_factory_env_overrides(self):
        env = {
            "TOKEN_GUARD_STORAGE": "postgres",
            "DATABASE_URL": "postgresql://localhost:5432/envdb",
            "TOKEN_GUARD_TTL": "3600",
            "TOKEN_GUARD_KEY_PREFIX": "env_prefix",
        }
        with patch.dict(os.environ, env, clear=True):
            store = StorageFactory.from_env(auto_create=False)
            assert isinstance(store, PostgreSQLStorage)

    def test_storage_factory_dynamodb_env(self):
        env = {
            "TOKEN_GUARD_STORAGE": "dynamodb",
            "AWS_REGION": "us-west-2",
            "TOKEN_GUARD_TABLE": "env_table",
        }
        with patch.dict(os.environ, env, clear=True):
            store = StorageFactory.from_env()
            assert isinstance(store, DynamoDBStorage)
            assert store.table_name == "env_table"

    def test_postgres_ping_failure_handled(self):
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("DB Connection Lost")
        store = PostgreSQLStorage(connection=mock_conn, auto_create=False)
        assert not store.ping()

    @pytest.mark.asyncio
    async def test_async_postgres_ping_failure_handled(self):
        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("Async DB Connection Lost")
        store = AsyncPostgreSQLStorage(pool=mock_pool, auto_create=False)
        assert not await store.ping()

    def test_dynamodb_ping_failure_handled(self):
        mock_resource = MagicMock()
        mock_resource.Table.side_effect = Exception("AWS Credentials Invalid")
        store = DynamoDBStorage(table_name="t", boto_resource=mock_resource)
        assert not store.ping()

    @pytest.mark.asyncio
    async def test_async_dynamodb_ping_failure_handled(self):
        mock_sync = MagicMock()
        mock_sync.ping.side_effect = Exception("AWS Error")
        store = AsyncDynamoDBStorage(sync_storage=mock_sync)
        assert not await store.ping()


class TestTokenGuardProperties:
    def test_guard_provider_property(self):
        guard = TokenGuard(counter=OpenAITokenCounter())
        assert guard.provider == "openai"
        assert guard.storage_backend == "InMemoryStorage"

    @pytest.mark.asyncio
    async def test_async_guard_provider_property(self):
        async_guard = AsyncTokenGuard(counter=OpenAITokenCounter())
        assert async_guard.provider == "openai"
        assert async_guard.storage_backend == "AsyncInMemoryStorage"
