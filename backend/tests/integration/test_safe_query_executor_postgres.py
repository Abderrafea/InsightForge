import os

import psycopg
import pytest
from cryptography.fernet import Fernet

from app.core.security import CredentialCipher
from app.database.connection_manager import ExternalDatabaseConnectionManager
from app.database.external_database import ExternalDatabaseCredentials
from app.models.database_connection import DatabaseConnection
from app.query.exceptions import QueryEngineError, QueryErrorCode
from app.query.executor import SafeQueryExecutor
from app.query.policy import QueryPolicy

pytestmark = pytest.mark.integration
RUN_INTEGRATION = os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") == "1"


def credentials() -> ExternalDatabaseCredentials:
    return ExternalDatabaseCredentials(
        host=os.environ["TEST_EXTERNAL_DB_HOST"],
        port=int(os.environ.get("TEST_EXTERNAL_DB_PORT", "5432")),
        database_name=os.environ["TEST_EXTERNAL_DB_NAME"],
        username=os.environ["TEST_EXTERNAL_DB_USER"],
        password=os.environ["TEST_EXTERNAL_DB_PASSWORD"],
        ssl_mode=os.environ.get("TEST_EXTERNAL_DB_SSL_MODE", "prefer"),
    )


def executor(
    max_rows: int = 20, max_result_bytes: int = 100_000
) -> tuple[SafeQueryExecutor, DatabaseConnection]:
    key = Fernet.generate_key().decode("ascii")
    cipher = CredentialCipher(key)
    details = credentials()
    record = DatabaseConnection(
        name="Integration demo",
        database_type="postgresql",
        host=details.host,
        port=details.port,
        database_name=details.database_name,
        username=details.username,
        encrypted_password=cipher.encrypt_secret(details.password),
        ssl_mode=details.ssl_mode,
    )
    policy = QueryPolicy(
        max_rows=max_rows,
        timeout_seconds=1,
        max_result_bytes=max_result_bytes,
    )
    manager = ExternalDatabaseConnectionManager(connect_timeout_seconds=5)
    return SafeQueryExecutor(manager, cipher, policy), record


@pytest.mark.skipif(not RUN_INTEGRATION, reason="PostgreSQL integration tests disabled")
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id, status FROM orders ORDER BY id LIMIT 3",
        "SELECT COUNT(*) AS total FROM orders",
        "SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY status",
        "SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id LIMIT 5",
        "WITH totals AS (SELECT SUM(total_amount) AS revenue FROM orders) SELECT * FROM totals",
    ],
)
async def test_analytical_queries_execute_against_postgres(sql: str) -> None:
    query_executor, record = executor()

    result = await query_executor.execute(record, sql)

    assert result.row_count > 0
    assert result.columns
    assert result.execution_time_ms >= 0


@pytest.mark.skipif(not RUN_INTEGRATION, reason="PostgreSQL integration tests disabled")
async def test_row_and_payload_limits_are_enforced() -> None:
    query_executor, record = executor(max_rows=5)
    limited = await query_executor.execute(record, "SELECT * FROM orders ORDER BY id")
    tiny_executor, tiny_record = executor(max_result_bytes=1_024)
    oversized = await tiny_executor.execute(tiny_record, "SELECT repeat('x', 5000) AS large_value")

    assert limited.row_count == 5
    assert limited.truncated is True
    assert oversized.row_count == 0
    assert oversized.truncated is True


@pytest.mark.skipif(not RUN_INTEGRATION, reason="PostgreSQL integration tests disabled")
async def test_postgres_types_are_json_safe() -> None:
    query_executor, record = executor()

    result = await query_executor.execute(
        record,
        "SELECT now() AS at, DATE '2026-08-11' AS day, "
        "12.34::numeric AS amount, "
        "'12345678-1234-5678-1234-567812345678'::uuid AS identifier",
    )

    row = result.rows[0]
    assert isinstance(row["at"], str)
    assert row["day"] == "2026-08-11"
    assert row["amount"] == "12.34"
    assert row["identifier"] == "12345678-1234-5678-1234-567812345678"


@pytest.mark.skipif(not RUN_INTEGRATION, reason="PostgreSQL integration tests disabled")
async def test_statement_timeout_is_enforced() -> None:
    query_executor, record = executor()

    with pytest.raises(QueryEngineError) as caught:
        await query_executor.execute(record, "SELECT count(*) FROM generate_series(1, 1000000000)")

    assert caught.value.query_code == QueryErrorCode.QUERY_TIMEOUT


@pytest.mark.skipif(not RUN_INTEGRATION, reason="PostgreSQL integration tests disabled")
async def test_demo_user_is_read_only_and_connections_close() -> None:
    manager = ExternalDatabaseConnectionManager(connect_timeout_seconds=5)
    async with manager.connection(credentials()) as connection:
        closed_connection = connection
        result = await connection.execute("SELECT 1")
        assert (await result.fetchone())[0] == 1

        for sql in (
            "INSERT INTO customers (name, email, country) VALUES ('x', 'x@example.com', 'MA')",
            "UPDATE orders SET status = 'paid'",
            "DELETE FROM order_items",
            "DROP TABLE products",
            "ALTER TABLE orders ADD COLUMN forbidden integer",
            "CREATE TABLE forbidden_table (id integer)",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                await connection.execute(sql)

    assert closed_connection.closed
