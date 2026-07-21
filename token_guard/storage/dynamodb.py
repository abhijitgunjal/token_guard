"""
storage/dynamodb.py
-------------------
AWS DynamoDB storage backends (sync and async) for TokenGuard.

Requires:
    pip install "llm-token-guard[dynamodb]"
  or:
    pip install boto3 aioboto3
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from token_guard.storage.async_base import AsyncBaseStorage
from token_guard.storage.base import BaseStorage
from token_guard.storage.models import UserUsage

logger = logging.getLogger(__name__)


class DynamoDBStorage(BaseStorage):
    """
    Synchronous AWS DynamoDB storage backend.

    Uses `boto3` to persist per-user token usage with atomic `ADD` update expressions.
    """

    def __init__(
        self,
        table_name: str = "token_guard_usage",
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        boto_resource: Optional[Any] = None,
    ) -> None:
        self.table_name = table_name
        self._region = region_name
        self._key_id = aws_access_key_id
        self._secret = aws_secret_access_key
        self._endpoint = endpoint_url
        self._resource = boto_resource
        self._table: Optional[Any] = None

    def _get_table(self) -> Any:
        if self._table is not None:
            return self._table

        if self._resource is None:
            try:
                import boto3
            except ImportError as exc:
                raise ImportError(
                    "Install boto3 to use DynamoDBStorage:\n"
                    "  pip install boto3\n"
                    "  or: pip install 'llm-token-guard[dynamodb]'"
                ) from exc

            kwargs: dict[str, Any] = {}
            if self._region:
                kwargs["region_name"] = self._region
            if self._key_id and self._secret:
                kwargs["aws_access_key_id"] = self._key_id
                kwargs["aws_secret_access_key"] = self._secret
            if self._endpoint:
                kwargs["endpoint_url"] = self._endpoint

            self._resource = boto3.resource("dynamodb", **kwargs)

        self._table = self._resource.Table(self.table_name)
        return self._table

    def add_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        table = self._get_table()
        now_str = datetime.now(timezone.utc).isoformat()
        table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="ADD input_tokens :in_tok, output_tokens :out_tok SET updated_at = :now",
            ExpressionAttributeValues={
                ":in_tok": input_tokens,
                ":out_tok": output_tokens,
                ":now": now_str,
            },
        )

    def get_usage(self, user_id: str) -> UserUsage:
        table = self._get_table()
        res = table.get_item(Key={"user_id": user_id})
        item = res.get("Item")
        if not item:
            return UserUsage()
        return UserUsage(
            input_tokens=int(item.get("input_tokens", 0)),
            output_tokens=int(item.get("output_tokens", 0)),
        )

    def reset_usage(self, user_id: str) -> None:
        table = self._get_table()
        table.delete_item(Key={"user_id": user_id})

    def all_users(self) -> dict[str, UserUsage]:
        table = self._get_table()
        res = table.scan()
        items = res.get("Items", [])
        result: dict[str, UserUsage] = {}
        for item in items:
            uid = item.get("user_id")
            if uid:
                result[uid] = UserUsage(
                    input_tokens=int(item.get("input_tokens", 0)),
                    output_tokens=int(item.get("output_tokens", 0)),
                )
        return result

    def ping(self) -> bool:
        try:
            table = self._get_table()
            # Calling table_status triggers a light metadata describe request
            return bool(table.table_status)
        except Exception as exc:
            logger.warning("DynamoDBStorage ping failed: %s", exc)
            return False


class AsyncDynamoDBStorage(AsyncBaseStorage):
    """
    Asynchronous AWS DynamoDB storage backend.

    Supports non-blocking operations via `aioboto3` or asyncio thread execution.
    """

    def __init__(
        self,
        table_name: str = "token_guard_usage",
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        sync_storage: Optional[DynamoDBStorage] = None,
    ) -> None:
        if sync_storage is not None:
            self._sync = sync_storage
        else:
            self._sync = DynamoDBStorage(
                table_name=table_name,
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                endpoint_url=endpoint_url,
            )

    async def add_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync.add_usage, user_id, input_tokens, output_tokens)

    async def get_usage(self, user_id: str) -> UserUsage:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync.get_usage, user_id)

    async def reset_usage(self, user_id: str) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._sync.reset_usage, user_id)

    async def all_users(self) -> dict[str, UserUsage]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync.all_users)

    async def ping(self) -> bool:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._sync.ping)
