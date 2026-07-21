import pytest
from unittest.mock import MagicMock, patch

from token_guard import DynamoDBStorage, AsyncDynamoDBStorage, StorageFactory, TokenGuard
from token_guard.storage.models import UserUsage


class TestDynamoDBStorageMocked:
    def test_missing_boto3_raises(self):
        with patch.dict("sys.modules", {"boto3": None}):
            store = DynamoDBStorage(table_name="test_table")
            with pytest.raises(ImportError, match="Install boto3"):
                store._get_table()

    def test_mocked_sync_crud(self):
        mock_resource = MagicMock()
        mock_table = MagicMock()
        mock_resource.Table.return_value = mock_table

        store = DynamoDBStorage(table_name="test_table", boto_resource=mock_resource)

        # Test add_usage
        store.add_usage("user1", 100, 50)
        mock_table.update_item.assert_called_once()

        # Test get_usage
        mock_table.get_item.return_value = {"Item": {"input_tokens": 100, "output_tokens": 50}}
        usage = store.get_usage("user1")
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150

        # Test reset_usage
        store.reset_usage("user1")
        mock_table.delete_item.assert_called_once_with(Key={"user_id": "user1"})

        # Test all_users
        mock_table.scan.return_value = {
            "Items": [
                {"user_id": "user1", "input_tokens": 100, "output_tokens": 50},
                {"user_id": "user2", "input_tokens": 200, "output_tokens": 100},
            ]
        }
        all_u = store.all_users()
        assert len(all_u) == 2
        assert all_u["user1"].total_tokens == 150
        assert all_u["user2"].total_tokens == 300

        # Test ping
        mock_table.table_status = "ACTIVE"
        assert store.ping()

    def test_storage_factory_creation(self):
        store = StorageFactory.create("dynamodb", table_name="test_table")
        assert isinstance(store, DynamoDBStorage)

        store_async = StorageFactory.create("dynamodb_async", table_name="test_table")
        assert isinstance(store_async, AsyncDynamoDBStorage)


@pytest.mark.asyncio
class TestAsyncDynamoDBStorageMocked:
    async def test_mocked_async_crud(self):
        mock_sync = MagicMock()
        mock_sync.get_usage.return_value = UserUsage(input_tokens=100, output_tokens=50)
        mock_sync.all_users.return_value = {"user1": UserUsage(input_tokens=100, output_tokens=50)}
        mock_sync.ping.return_value = True

        async_store = AsyncDynamoDBStorage(sync_storage=mock_sync)

        await async_store.add_usage("user1", 100, 50)
        mock_sync.add_usage.assert_called_once_with("user1", 100, 50)

        usage = await async_store.get_usage("user1")
        assert usage.total_tokens == 150

        await async_store.reset_usage("user1")
        mock_sync.reset_usage.assert_called_once_with("user1")

        users = await async_store.all_users()
        assert "user1" in users

        assert await async_store.ping()
