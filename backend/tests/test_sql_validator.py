import pytest

from app.query.policy import QueryPolicy
from app.query.validator import SQLValidator
from app.schemas.schema_inspection import (
    ColumnMetadata,
    DatabaseSchemaMetadata,
    TableMetadata,
)


@pytest.fixture
def schema() -> DatabaseSchemaMetadata:
    def table(name: str, columns: list[str]) -> TableMetadata:
        return TableMetadata(
            **{
                "schema": "public",
                "name": name,
                "columns": [
                    ColumnMetadata(
                        name=column,
                        type="text",
                        nullable=False,
                        primary_key=column == "id",
                    )
                    for column in columns
                ],
                "foreign_keys": [],
            }
        )

    return DatabaseSchemaMetadata(
        database="demo_ecommerce",
        schemas=["public"],
        tables=[
            table(
                "orders",
                ["id", "customer_id", "total_amount", "status", "created_at"],
            ),
            table("customers", ["id", "name", "email", "created_at"]),
            table("products", ["id", "name", "price"]),
            table("order_items", ["id", "order_id", "product_id", "quantity"]),
        ],
    )


@pytest.fixture
def validator() -> SQLValidator:
    return SQLValidator(QueryPolicy())


@pytest.mark.parametrize(
    "sql, expected_tables",
    [
        ("SELECT * FROM orders", ["orders"]),
        ("SELECT COUNT(*) FROM orders", ["orders"]),
        (
            "SELECT customer_id, SUM(total_amount) FROM orders GROUP BY customer_id",
            ["orders"],
        ),
        (
            "WITH revenue AS (SELECT SUM(total_amount) AS total FROM orders) SELECT * FROM revenue",
            ["orders"],
        ),
        (
            "SELECT o.id, c.name FROM orders o JOIN customers c ON c.id = o.customer_id",
            ["orders", "customers"],
        ),
        (
            "SELECT summary.status FROM (SELECT status FROM orders) summary",
            ["orders"],
        ),
        (
            "-- monthly revenue\nSELECT DATE_TRUNC('month', created_at) FROM orders GROUP BY 1",
            ["orders"],
        ),
    ],
)
def test_valid_analytical_queries(
    validator: SQLValidator,
    schema: DatabaseSchemaMetadata,
    sql: str,
    expected_tables: list[str],
) -> None:
    result = validator.validate(sql, schema)

    assert result.valid is True
    assert result.errors == []
    assert result.statement_type == "SELECT"
    assert result.referenced_tables == expected_tables


@pytest.mark.parametrize(
    "sql, statement_type",
    [
        ("DELETE FROM orders", "DELETE"),
        ("UPDATE orders SET status = 'paid'", "UPDATE"),
        ("DROP TABLE customers", "DROP"),
        ("CREATE TABLE test(id int)", "CREATE"),
        ("INSERT INTO orders (id) VALUES (1)", "INSERT"),
        ("ALTER TABLE orders ADD COLUMN unsafe int", "ALTER"),
        ("TRUNCATE TABLE orders", "TRUNCATETABLE"),
        ("SET search_path = public", "SET"),
        ("BEGIN", "TRANSACTION"),
        ("COMMIT", "COMMIT"),
    ],
)
def test_non_select_statements_are_rejected(
    validator: SQLValidator,
    schema: DatabaseSchemaMetadata,
    sql: str,
    statement_type: str,
) -> None:
    result = validator.validate(sql, schema)

    assert result.valid is False
    assert result.statement_type == statement_type
    assert any("not allowed" in error for error in result.errors)


def test_multiple_statements_are_rejected(
    validator: SQLValidator, schema: DatabaseSchemaMetadata
) -> None:
    result = validator.validate("SELECT * FROM orders; DROP TABLE orders;", schema)

    assert result.valid is False
    assert "Only one SQL statement is allowed" in result.errors
    assert "orders" in result.referenced_tables


@pytest.mark.parametrize("sql", ["", "   ", "-- comment only"])
def test_empty_sql_is_rejected(
    validator: SQLValidator, schema: DatabaseSchemaMetadata, sql: str
) -> None:
    result = validator.validate(sql, schema)

    assert result.valid is False


def test_malformed_sql_is_rejected(validator: SQLValidator, schema: DatabaseSchemaMetadata) -> None:
    result = validator.validate("SELECT * FROM (", schema)

    assert result.valid is False
    assert result.errors == ["SQL syntax is invalid"]


def test_long_sql_is_rejected(schema: DatabaseSchemaMetadata) -> None:
    validator = SQLValidator(QueryPolicy(max_sql_length=100))

    result = validator.validate("SELECT '" + ("x" * 101) + "'", schema)

    assert result.valid is False
    assert "maximum length" in result.errors[0]


def test_unknown_table_is_rejected(validator: SQLValidator, schema: DatabaseSchemaMetadata) -> None:
    result = validator.validate("SELECT * FROM orderzz", schema)

    assert result.valid is False
    assert "Unknown table: orderzz" in result.errors


def test_qualified_unknown_column_is_rejected(
    validator: SQLValidator, schema: DatabaseSchemaMetadata
) -> None:
    result = validator.validate("SELECT o.pricee FROM orders o", schema)

    assert result.valid is False
    assert "Unknown column: o.pricee" in result.errors


def test_system_schema_is_rejected(validator: SQLValidator, schema: DatabaseSchemaMetadata) -> None:
    result = validator.validate("SELECT * FROM pg_catalog.pg_user", schema)

    assert result.valid is False
    assert "System schema access is not allowed: pg_catalog" in result.errors


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT pg_catalog.pg_read_file('/etc/passwd')",
        "SELECT pg_terminate_backend(1)",
        "SELECT set_config('search_path', 'public', false)",
        "SELECT nextval('orders_id_seq')",
    ],
)
def test_dangerous_functions_are_rejected(
    validator: SQLValidator, schema: DatabaseSchemaMetadata, sql: str
) -> None:
    result = validator.validate(sql, schema)

    assert result.valid is False
    assert any("Function" in error for error in result.errors)


def test_join_limit_is_enforced(schema: DatabaseSchemaMetadata) -> None:
    validator = SQLValidator(QueryPolicy(max_joins=1))
    sql = (
        "SELECT * FROM orders o "
        "JOIN customers c ON c.id = o.customer_id "
        "JOIN order_items oi ON oi.order_id = o.id"
    )

    result = validator.validate(sql, schema)

    assert result.valid is False
    assert "Query uses 2 joins; the maximum is 1" in result.errors


def test_cte_with_mutation_is_rejected(
    validator: SQLValidator, schema: DatabaseSchemaMetadata
) -> None:
    result = validator.validate(
        "WITH removed AS (DELETE FROM orders RETURNING id) SELECT * FROM removed",
        schema,
    )

    assert result.valid is False
    assert any("DELETE" in error for error in result.errors)
