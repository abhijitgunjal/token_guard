"""
demo_all_features.py
--------------------
Comprehensive local demonstration script testing ALL TokenGuard features, methods,
storage backends (InMemory, SQLite, Redis, PostgreSQL, DynamoDB), policies, and async/sync APIs.

To run:
    python examples/demo_all_features.py
"""

import asyncio
import os
import sys
from datetime import datetime

from token_guard import (
    # Core entry points
    TokenGuard,
    AsyncTokenGuard,
    TrackResult,
    
    # Storage backends
    InMemoryStorage,
    SQLiteStorage,
    RedisStorage,
    PostgreSQLStorage,
    DynamoDBStorage,
    AsyncInMemoryStorage,
    AsyncSQLiteStorage,
    AsyncRedisStorage,
    AsyncPostgreSQLStorage,
    AsyncDynamoDBStorage,
    StorageFactory,
    UserUsage,
    
    # Counter backends & factory
    OpenAITokenCounter,
    GroqTokenCounter,
    OpenRouterTokenCounter,
    BedrockTokenCounter,
    CounterFactory,
    BaseTokenCounter,
    
    # Alert handlers
    BaseAlertHandler,
    AsyncBaseAlertHandler,
    ConsoleAlertHandler,
    AlertManager,
    
    # Policies (v0.5.0 Policy Engine)
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
    PolicyFactory,
    PolicyContext,
    PolicyResult,
    BasePolicy,
)


def print_section(title: str):
    print(f"\n{'='*75}\n  {title}\n{'='*75}")


def print_result(label: str, result: TrackResult):
    print(f"\n[Result: {label}]")
    print(f"  User ID:          {result.user_id}")
    print(f"  Input Tokens:     {result.input_tokens}")
    print(f"  Output Tokens:    {result.output_tokens}")
    print(f"  Total Tokens:     {result.total_tokens}")
    print(f"  Cumulative Total: {result.cumulative_usage.total_tokens}")
    print(f"  Limit Exceeded:   {result.limit_exceeded}")
    print(f"  Utilization:      {result.utilization:.1%}")
    print(f"  Provider:         {result.provider}")
    print(f"  Storage Backend:  {result.storage_backend}")
    if result.policy_result:
        print(f"  Policy Allowed:   {result.policy_result.allowed}")
        print(f"  Policy Reason:    {result.policy_result.reason}")
        if result.policy_result.retry_after:
            print(f"  Retry After:      {result.policy_result.retry_after}s")


# =====================================================================
# 1. Custom Alert Handler Demo
# =====================================================================
class CustomAppAlertHandler(BaseAlertHandler):
    def send(self, user_id: str, usage: UserUsage, limit: int) -> None:
        print(f"  [CUSTOM ALERT] User '{user_id}' exceeded limit ({usage.total_tokens}/{limit} tokens)")


# =====================================================================
# 2. Custom Counter Backend Demo
# =====================================================================
class MockVertexCounter(BaseTokenCounter):
    @property
    def provider(self) -> str:
        return "vertexai_mock"

    def count(self, text: str) -> int:
        return len(text.split())  # simple word-count approximation for testing


# =====================================================================
# 3. Synchronous Testing Suite
# =====================================================================
def run_sync_tests():
    print_section("1. SYNCHRONOUS TRACKING & COUNTER BACKENDS")

    # A. Direct Usage Tracking (100% Exact - recommended for production)
    guard = TokenGuard(max_tokens=1000, alert_handlers=[ConsoleAlertHandler(), CustomAppAlertHandler()])
    res1 = guard.track_usage(user_id="alice", input_tokens=150, output_tokens=50)
    print_result("Direct exact tracking", res1)

    # B. Text Estimation with OpenAI Counter (tiktoken)
    res2 = guard.track(user_id="alice", input_text="What is machine learning?", output_text="Machine learning is a field of AI.")
    print_result("OpenAI tiktoken estimation", res2)

    # C. Model Auto-Detection via CounterFactory.auto()
    models = ["gpt-4o", "llama-3.3-70b-versatile", "openai/gpt-4o", "anthropic.claude-3-5-sonnet-20241022-v2:0"]
    for m in models:
        c = CounterFactory.auto(m)
        g = TokenGuard(max_tokens=5000, counter=c)
        r = g.track("bob", "Hello", "World")
        print(f"  Auto-detect '{m}' -> Counter Provider: {r.provider}")

    # D. Registering & using custom counter
    CounterFactory.register("vertex_mock", lambda model, **kw: MockVertexCounter())
    custom_counter = CounterFactory.create("vertex_mock", model="gemini-pro")
    custom_guard = TokenGuard(max_tokens=500, counter=custom_counter)
    res_custom = custom_guard.track("charlie", "This is a test prompt with seven words.", "Short answer.")
    print_result("Custom Counter (MockVertexCounter)", res_custom)

    # E. Usage inspection & reset
    print_section("2. USAGE INSPECTION & RESET (SYNC)")
    usage_alice = guard.get_usage("alice")
    print(f"  Get usage for 'alice': input={usage_alice.input_tokens}, output={usage_alice.output_tokens}, total={usage_alice.total_tokens}")
    
    all_users = guard.all_users()
    print(f"  All tracked users: {list(all_users.keys())}")
    
    guard.reset_usage("alice")
    print(f"  After reset, 'alice' total tokens: {guard.get_usage('alice').total_tokens}")


# =====================================================================
# 4. Storage Backends Testing (Memory, SQLite, Redis, PostgreSQL, DynamoDB)
# =====================================================================
def run_storage_tests():
    print_section("3. STORAGE BACKENDS (InMemory, SQLite, Redis, PostgreSQL, DynamoDB)")

    # A. SQLite Storage
    db_file = "demo_test.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    sqlite_store = StorageFactory.create("sqlite", path=db_file)
    guard_sqlite = TokenGuard(max_tokens=2000, storage=sqlite_store)
    res_sql = guard_sqlite.track_usage("david", input_tokens=400, output_tokens=100)
    print_result("SQLite Storage", res_sql)

    # B. Redis Storage
    print("\n  Testing Redis Storage...")
    try:
        redis_store = StorageFactory.create("redis", host="localhost", port=6379, ttl=3600)
        if redis_store.ping():
            guard_redis = TokenGuard(max_tokens=5000, storage=redis_store)
            res_redis = guard_redis.track_usage("eve", input_tokens=250, output_tokens=50)
            print_result("Redis Storage (Connected!)", res_redis)
        else:
            print("  [WARNING] Redis server reachable check returned False.")
    except Exception as e:
        print(f"  [INFO] Redis not running locally on port 6379 ({type(e).__name__}: {e})")

    # C. PostgreSQL Storage (Factory Check)
    print("\n  Testing PostgreSQL Storage (Factory Check)...")
    try:
        pg_store = StorageFactory.create("postgres", connection_string="postgresql://localhost:5432/token_guard", auto_create=False)
        print(f"  PostgreSQLStorage instantiated via StorageFactory: class={type(pg_store).__name__}")
    except Exception as e:
        print(f"  [INFO] PostgreSQL driver setup info: {e}")

    # D. DynamoDB Storage (Factory Check)
    print("\n  Testing DynamoDB Storage (Factory Check)...")
    try:
        dynamo_store = StorageFactory.create("dynamodb", table_name="token_guard_usage")
        print(f"  DynamoDBStorage instantiated via StorageFactory: class={type(dynamo_store).__name__}")
    except Exception as e:
        print(f"  [INFO] DynamoDB driver setup info: {e}")

    # E. StorageFactory via Environment Variables & Config Dicts
    print("\n  Testing StorageFactory configurations...")
    config_storage = StorageFactory.from_config({"backend": "sqlite", "path": ":memory:"})
    guard_cfg = TokenGuard(max_tokens=1000, storage=config_storage)
    res_cfg = guard_cfg.track_usage("frank", input_tokens=100, output_tokens=50)
    print(f"  Factory from_config: storage_backend={res_cfg.storage_backend}")

    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass


# =====================================================================
# 5. Policy Engine Testing (v0.5.0 Algorithms)
# =====================================================================
def run_policy_tests():
    print_section("4. POLICY ENGINE (v0.5.0 Algorithms)")

    # A. Sliding Window Policy
    print("\n  [Policy 1: SlidingWindowPolicy]")
    sw_policy = SlidingWindowPolicy(limit=100, window=3600, buckets=60)
    guard_sw = TokenGuard(policy=sw_policy)
    print("  Call 1 (60 tokens): limit_exceeded =", guard_sw.track_usage("p_user", 50, 10).limit_exceeded)
    res_sw2 = guard_sw.track_usage("p_user", 50, 0)
    print(f"  Call 2 (50 tokens -> exceeds 100 limit): limit_exceeded={res_sw2.limit_exceeded}")
    if res_sw2.policy_result:
        print(f"  Reason: {res_sw2.policy_result.reason}")

    # B. Token Bucket Policy
    print("\n  [Policy 2: TokenBucketPolicy]")
    tb_policy = TokenBucketPolicy(capacity=200, refill_rate=10.0)
    guard_tb = TokenGuard(policy=tb_policy)
    res_tb = guard_tb.track_usage("tb_user", 150, 0)
    print(f"  Token Bucket (150/200 tokens used): allowed={res_tb.policy_result.allowed}")

    # C. Cost Policy
    print("\n  [Policy 3: CostPolicy]")
    cost_policy = CostPolicy(daily_limit_usd=0.01, cost_per_1k_input_tokens=0.005)
    guard_cost = TokenGuard(policy=cost_policy)
    res_c1 = guard_cost.track_usage("cost_user", input_tokens=1000, output_tokens=0)  # $0.005
    print(f"  Call 1 ($0.005): allowed={res_c1.policy_result.allowed}")
    res_c2 = guard_cost.track_usage("cost_user", input_tokens=2000, output_tokens=0)  # +$0.010 = $0.015 > $0.01
    print(f"  Call 2 (total $0.015 > $0.01 limit): allowed={res_c2.policy_result.allowed}, reason={res_c2.policy_result.reason}")

    # D. Quota & Role Policies
    print("\n  [Policy 4: Quota & Role Policies]")
    quota_policy = QuotaPolicy(daily_tokens=500)
    role_policy = RolePolicy(
        role_limits={"admin": float("inf"), "guest": 100},
        user_roles={"admin_user": "admin", "guest_user": "guest"},
    )
    guard_multi = TokenGuard(policies=[quota_policy, role_policy])
    res_guest = guard_multi.track_usage("guest_user", 150, 0)
    print(f"  Guest user (150 > 100 limit): allowed={res_guest.policy_result.allowed}, reason={res_guest.policy_result.reason}")
    res_admin = guard_multi.track_usage("admin_user", 300, 0)
    print(f"  Admin user (300 tokens): allowed={res_admin.policy_result.allowed}")


# =====================================================================
# 6. Asynchronous Testing Suite
# =====================================================================
async def run_async_tests():
    print_section("5. ASYNCHRONOUS API (AsyncTokenGuard)")

    # A. Async Memory & Tracking
    async_guard = AsyncTokenGuard(max_tokens=1000, storage=AsyncInMemoryStorage())
    res_async1 = await async_guard.track_usage("async_alice", input_tokens=120, output_tokens=30)
    print_result("Async direct tracking", res_async1)

    res_async2 = await async_guard.track("async_alice", input_text="Async test prompt", output_text="Async response")
    print_result("Async text estimation", res_async2)

    # B. Async SQLite Storage
    async_db = "async_demo_test.db"
    if os.path.exists(async_db):
        try:
            os.remove(async_db)
        except Exception:
            pass

    async_sqlite_store = AsyncSQLiteStorage(path=async_db)
    async_guard_sqlite = AsyncTokenGuard(max_tokens=2000, storage=async_sqlite_store)
    res_async_sql = await async_guard_sqlite.track_usage("async_david", input_tokens=300, output_tokens=50)
    print_result("Async SQLite Storage", res_async_sql)

    # C. Async Policies (AsyncSlidingWindowPolicy)
    print("\n  Testing Async Policies...")
    async_sw = AsyncSlidingWindowPolicy(limit=200, window=3600)
    async_policy_guard = AsyncTokenGuard(policy=async_sw)
    res_asw1 = await async_policy_guard.track_usage("async_p_user", 150, 0)
    print(f"  Async Sliding Window (150/200 tokens): allowed={res_asw1.policy_result.allowed}")
    res_asw2 = await async_policy_guard.track_usage("async_p_user", 100, 0)
    print(f"  Async Sliding Window (total 250 > 200 limit): allowed={res_asw2.policy_result.allowed}")

    # D. Async Redis Storage
    print("\n  Testing Async Redis Storage...")
    try:
        async_redis_store = AsyncRedisStorage(host="localhost", port=6379, ttl=3600)
        if await async_redis_store.ping():
            async_guard_redis = AsyncTokenGuard(max_tokens=5000, storage=async_redis_store)
            res_aredis = await async_guard_redis.track_usage("async_eve", input_tokens=200, output_tokens=40)
            print_result("Async Redis Storage (Connected!)", res_aredis)
        else:
            print("  [WARNING] Async Redis server reachable check returned False.")
    except Exception as e:
        print(f"  [INFO] Async Redis not running locally on port 6379 ({type(e).__name__}: {e})")

    # Cleanup
    if os.path.exists(async_db):
        try:
            os.remove(async_db)
        except Exception:
            pass


# =====================================================================
# Main Execution Entry
# =====================================================================
if __name__ == "__main__":
    print(f"Starting TokenGuard Local Feature Verification Suite...")
    print(f"Time: {datetime.now().isoformat()}")
    
    # Run sync test suite
    run_sync_tests()
    run_storage_tests()
    run_policy_tests()
    
    # Run async test suite
    asyncio.run(run_async_tests())
    
    print_section("LOCAL TEST SUITE COMPLETED SUCCESSFULLY!")
