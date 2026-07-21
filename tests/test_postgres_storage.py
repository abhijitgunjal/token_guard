import pytest
from unittest.mock import MagicMock, patch

from token_guard import PostgreSQLStorage, AsyncPostgreSQLStorage, StorageFactory, TokenGuard
from token_guard.storage.models import UserUsage


class TestPostgreSQLStorageMocked:
    def test_missing_psycopg_raises(self):
        with patch.dict("sys.modules", {"psycopg": None}):
            store = PostgreSQLStorage(connection_string="postgresql://localhost/db", auto_create=False)
            with pytest.raises(ImportError, match="Install psycopg"):
                store._get_connection()

    def test_mocked_sync_crud(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        store = PostgreSQLStorage(connection=mock_conn, auto_create=False)
        
        # Test add_usage
        store.add_usage("user1", 100, 50)
        mock_cursor.execute.assert_called()

        # Test get_usage
        mock_cursor.fetchone.return_value = (100, 50)
        usage = store.get_usage("user1")
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150

        # Test reset_usage
        store.reset_usage("user1")
        mock_cursor.execute.assert_called()

        # Test all_users
        mock_cursor.fetchall.return_value = [("user1", 100, 50), ("user2", 200, 100)]
        all_u = store.all_users()
        assert len(all_u) == 2
        assert all_u["user1"].total_tokens == 150
        assert all_u["user2"].total_tokens == 300

        # Test ping
        mock_cursor.fetchone.return_value = (1,)
        assert store.ping()

    def test_storage_factory_creation(self):
        store = StorageFactory.create("postgres", connection_string="postgresql://localhost/db", auto_create=False)
        assert isinstance(store, PostgreSQLStorage)

        store_async = StorageFactory.create("postgres_async", connection_string="postgresql://localhost/db", auto_create=False)
        assert isinstance(store_async, AsyncPostgreSQLStorage)

    def test_from_url(self):
        store = StorageFactory.from_url("postgresql://localhost/testdb", auto_create=False)
        assert isinstance(store, PostgreSQLStorage)


@pytest.mark.asyncio
class TestAsyncPostgreSQLStorageMocked:
    async def test_missing_asyncpg_raises(self):
        with patch.dict("sys.modules", {"asyncpg": None}):
            store = AsyncPostgreSQLStorage(connection_string="postgresql://localhost/db", auto_create=False)
            with pytest.raises(ImportError, match="Install asyncpg"):
                await store._get_pool()
