# AWS DynamoDB Storage Driver

TokenGuard v0.6.0 introduces native **AWS DynamoDB** storage drivers (`DynamoDBStorage` and `AsyncDynamoDBStorage`).

---

## Overview

Use DynamoDB when running serverless AWS infrastructure (AWS Lambda, ECS, Fargate, App Runner) and you want scalable, zero-maintenance token tracking across AWS regions.

### Key Features
- **Atomic `ADD` Updates**: Uses DynamoDB `update_item` with `ADD input_tokens :in_tok, output_tokens :out_tok` update expressions for lock-free, atomic increments across serverless instances.
- **Sync & Async Drivers**: `DynamoDBStorage` (sync via `boto3`) and `AsyncDynamoDBStorage` (async).
- **DynamoDB Local Support**: Easily pass `endpoint_url="http://localhost:8000"` for local development and offline testing.

---

## Installation

Install optional DynamoDB dependencies:

```bash
pip install "llm-token-guard[dynamodb]"
```

Or install `boto3` directly:
```bash
pip install boto3 aioboto3
```

---

## Usage

### 1. Synchronous (`DynamoDBStorage`)

```python
from token_guard import TokenGuard, DynamoDBStorage, SlidingWindowPolicy

storage = DynamoDBStorage(
    table_name="token_guard_usage",
    region_name="ap-south-1",
)
guard = TokenGuard(
    policy=SlidingWindowPolicy(limit=100_000, window=3600),
    storage=storage,
)

result = guard.track_usage("alice", input_tokens=400, output_tokens=100)
print(result.cumulative_usage.total_tokens)
```

### 2. Asynchronous (`AsyncDynamoDBStorage`)

```python
import asyncio
from token_guard import AsyncTokenGuard, AsyncDynamoDBStorage

async def main():
    storage = AsyncDynamoDBStorage(
        table_name="token_guard_usage",
        region_name="us-east-1",
    )
    guard = AsyncTokenGuard(storage=storage)

    result = await guard.track_usage("bob", input_tokens=250, output_tokens=50)
    print(result.cumulative_usage.total_tokens)

asyncio.run(main())
```

### 3. Factory & Environment Variables

```python
from token_guard import StorageFactory, TokenGuard

storage = StorageFactory.create("dynamodb", table_name="token_guard_usage", region_name="us-east-1")
guard = TokenGuard(storage=storage)
```

Or configure via environment variables:

```bash
export TOKEN_GUARD_STORAGE=dynamodb
export AWS_REGION=ap-south-1
export TOKEN_GUARD_TABLE=token_guard_usage
```

```python
from token_guard import StorageFactory, TokenGuard

guard = TokenGuard(storage=StorageFactory.from_env())
```

---

## Table Definition (IAM & AWS CLI)

Create the table using AWS CLI or Terraform:

```bash
aws dynamodb create-table \
    --table-name token_guard_usage \
    --attribute-definitions AttributeName=user_id,AttributeType=S \
    --key-schema AttributeName=user_id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST
```
