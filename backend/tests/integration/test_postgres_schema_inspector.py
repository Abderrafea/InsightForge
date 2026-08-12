import os

import pytest

from app.database.connection_manager import ExternalDatabaseConnectionManager
from app.database.external_database import ExternalDatabaseCredentials
from app.database.schema_inspector import PostgreSQLSchemaInspector

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_INTEGRATION_TESTS") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION_TESTS=1 to test against demo PostgreSQL",
)
async def test_real_postgres_primary_and_foreign_key_discovery() -> None:
    credentials = ExternalDatabaseCredentials(
        host=os.environ["TEST_EXTERNAL_DB_HOST"],
        port=int(os.environ.get("TEST_EXTERNAL_DB_PORT", "5432")),
        database_name=os.environ["TEST_EXTERNAL_DB_NAME"],
        username=os.environ["TEST_EXTERNAL_DB_USER"],
        password=os.environ["TEST_EXTERNAL_DB_PASSWORD"],
        ssl_mode=os.environ.get("TEST_EXTERNAL_DB_SSL_MODE", "prefer"),
    )
    manager = ExternalDatabaseConnectionManager(connect_timeout_seconds=5)

    async with manager.connection(credentials) as connection:
        schema = await PostgreSQLSchemaInspector().inspect(connection)

    tables = {(table.schema_name, table.name): table for table in schema.tables}
    assert {"customers", "products", "orders", "order_items"}.issubset(
        {table_name for _, table_name in tables}
    )

    orders = tables[("public", "orders")]
    columns = {column.name: column for column in orders.columns}
    assert columns["id"].primary_key is True
    assert columns["customer_id"].nullable is False
    assert any(
        foreign_key.column == "customer_id"
        and foreign_key.references_table == "customers"
        and foreign_key.references_column == "id"
        for foreign_key in orders.foreign_keys
    )
