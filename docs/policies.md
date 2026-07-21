# Policy Engine

TokenGuard v0.5.0 introduces a modular **Policy Engine** that evaluates token limits, sliding windows, rate-limiting algorithms, budgets, quotas, and role permissions before usage is recorded.

---

## Overview

The Policy Engine sits between token counting and storage update:

```
Request → Count Tokens → Evaluate Policies → Allowed? → Record Storage → Trigger Alerts
```

If any policy rejects a request:
- Evaluation stops immediately (short-circuit execution).
- Usage is not recorded.
- `result.limit_exceeded` is set to `True`.
- `result.policy_result` contains details (`allowed=False`, `reason`, `retry_after`, `metadata`).

---

## Built-in Policies

### 1. Sliding Window Policy
Maintains a rolling usage window divided into sub-buckets. Prevents burst volume at window boundary resets.

```python
from token_guard import TokenGuard, SlidingWindowPolicy

# Allow up to 100,000 tokens in any rolling 60-minute window
policy = SlidingWindowPolicy(limit=100_000, window=3600, buckets=60)
guard = TokenGuard(policy=policy)

result = guard.track_usage("alice", input_tokens=500, output_tokens=200)
```

### 2. Token Bucket Policy
Implements classic token bucket algorithm with capacity and continuous refill rate.

```python
from token_guard import TokenGuard, TokenBucketPolicy

# 50,000 token capacity, refilling at 1,000 tokens/second
policy = TokenBucketPolicy(capacity=50_000, refill_rate=1000.0)
guard = TokenGuard(policy=policy)
```

### 3. Fixed Window Policy
Counter that resets after a fixed window duration.

```python
from token_guard import TokenGuard, FixedWindowPolicy

# 10,000 tokens per 1 hour window
policy = FixedWindowPolicy(limit=10_000, window=3600)
guard = TokenGuard(policy=policy)
```

### 4. Leaky Bucket Policy
Smooths output traffic by leaking tokens at a constant rate.

```python
from token_guard import TokenGuard, LeakyBucketPolicy

# 20,000 token queue capacity, leaking at 500 tokens/second
policy = LeakyBucketPolicy(capacity=20_000, leak_rate=500.0)
guard = TokenGuard(policy=policy)
```

### 5. Cost Policy
Enforces spending limits in USD based on input and output token rates.

```python
from token_guard import TokenGuard, CostPolicy

policy = CostPolicy(
    daily_limit_usd=10.0,
    monthly_limit_usd=100.0,
    cost_per_1k_input_tokens=0.0015,
    cost_per_1k_output_tokens=0.002,
)
guard = TokenGuard(policy=policy)
```

### 6. Quota Policy
Enforces hard daily or monthly token quotas per user.

```python
from token_guard import TokenGuard, QuotaPolicy

policy = QuotaPolicy(daily_tokens=1_000_000, monthly_tokens=20_000_000)
guard = TokenGuard(policy=policy)
```

### 7. Role Policy
Configures token limits per user role (e.g. Admin, Developer, Guest).

```python
from token_guard import TokenGuard, RolePolicy

policy = RolePolicy(
    role_limits={
        "admin": float("inf"),
        "developer": 1_000_000,
        "guest": 50_000,
    },
    user_roles={"alice": "admin", "bob": "developer"},
    default_role="guest",
)
guard = TokenGuard(policy=policy)
```

---

## Combining Multiple Policies

You can pass multiple policies to `TokenGuard` or `AsyncTokenGuard`. All policies must approve the request:

```python
from token_guard import (
    TokenGuard,
    SlidingWindowPolicy,
    CostPolicy,
    RolePolicy,
)

guard = TokenGuard(
    policies=[
        SlidingWindowPolicy(limit=100_000, window=3600),
        CostPolicy(daily_limit_usd=25.0),
        RolePolicy(),
    ]
)
```

---

## Async Policies

Every built-in policy has an async equivalent (`AsyncSlidingWindowPolicy`, `AsyncTokenBucketPolicy`, `AsyncFixedWindowPolicy`, etc.) for non-blocking execution in `AsyncTokenGuard`:

```python
from token_guard import AsyncTokenGuard, AsyncSlidingWindowPolicy

policy = AsyncSlidingWindowPolicy(limit=100_000, window=3600)
guard = AsyncTokenGuard(policy=policy)

result = await guard.track_usage("alice", input_tokens=500, output_tokens=200)
```

---

## PolicyFactory

Instantiate policies using string keys via `PolicyFactory`:

```python
from token_guard import PolicyFactory, TokenGuard

policy = PolicyFactory.create("sliding_window", limit=100_000, window=3600)
guard = TokenGuard(policy=policy)
```

### Custom Policy Creation

Create a custom policy by subclassing `BasePolicy` (or `AsyncBasePolicy`) and registering it:

```python
from token_guard import BasePolicy, PolicyContext, PolicyResult, PolicyFactory, TokenGuard

class IPAddressPolicy(BasePolicy):
    def evaluate(self, context: PolicyContext, storage=None) -> PolicyResult:
        ip = context.metadata.get("ip")
        if ip == "192.168.1.100":
            return PolicyResult(allowed=False, reason="IP address blocked")
        return PolicyResult(allowed=True)

PolicyFactory.register("ip_address", IPAddressPolicy)
guard = TokenGuard(policy=PolicyFactory.create("ip_address"))
```
