from collections import defaultdict

from psycopg import AsyncConnection

from app.schemas.schema_inspection import (
    ColumnMetadata,
    DatabaseSchemaMetadata,
    ForeignKeyMetadata,
    TableMetadata,
)

COLUMN_QUERY = """
SELECT
    namespace.nspname AS schema_name,
    table_class.relname AS table_name,
    attribute.attname AS column_name,
    pg_catalog.format_type(attribute.atttypid, attribute.atttypmod) AS data_type,
    NOT attribute.attnotnull AS is_nullable,
    EXISTS (
        SELECT 1
        FROM pg_catalog.pg_index primary_index
        WHERE primary_index.indrelid = table_class.oid
          AND primary_index.indisprimary
          AND attribute.attnum = ANY(primary_index.indkey)
    ) AS is_primary_key
FROM pg_catalog.pg_attribute attribute
JOIN pg_catalog.pg_class table_class ON table_class.oid = attribute.attrelid
JOIN pg_catalog.pg_namespace namespace ON namespace.oid = table_class.relnamespace
WHERE table_class.relkind IN ('r', 'p')
  AND attribute.attnum > 0
  AND NOT attribute.attisdropped
  AND namespace.nspname NOT IN ('pg_catalog', 'information_schema')
  AND namespace.nspname NOT LIKE 'pg_toast%'
ORDER BY namespace.nspname, table_class.relname, attribute.attnum
"""

FOREIGN_KEY_QUERY = """
SELECT
    source_namespace.nspname AS source_schema,
    source_table.relname AS source_table,
    source_attribute.attname AS source_column,
    target_namespace.nspname AS target_schema,
    target_table.relname AS target_table,
    target_attribute.attname AS target_column
FROM pg_catalog.pg_constraint constraint_record
JOIN pg_catalog.pg_class source_table
  ON source_table.oid = constraint_record.conrelid
JOIN pg_catalog.pg_namespace source_namespace
  ON source_namespace.oid = source_table.relnamespace
JOIN pg_catalog.pg_class target_table
  ON target_table.oid = constraint_record.confrelid
JOIN pg_catalog.pg_namespace target_namespace
  ON target_namespace.oid = target_table.relnamespace
JOIN LATERAL unnest(constraint_record.conkey) WITH ORDINALITY
  AS source_key(attnum, position) ON TRUE
JOIN LATERAL unnest(constraint_record.confkey) WITH ORDINALITY
  AS target_key(attnum, position) ON source_key.position = target_key.position
JOIN pg_catalog.pg_attribute source_attribute
  ON source_attribute.attrelid = source_table.oid
 AND source_attribute.attnum = source_key.attnum
JOIN pg_catalog.pg_attribute target_attribute
  ON target_attribute.attrelid = target_table.oid
 AND target_attribute.attnum = target_key.attnum
WHERE constraint_record.contype = 'f'
  AND source_namespace.nspname NOT IN ('pg_catalog', 'information_schema')
  AND source_namespace.nspname NOT LIKE 'pg_toast%'
ORDER BY source_namespace.nspname, source_table.relname, source_key.position
"""


class PostgreSQLSchemaInspector:
    async def inspect(
        self, connection: AsyncConnection[tuple[object, ...]]
    ) -> DatabaseSchemaMetadata:
        database_result = await connection.execute("SELECT current_database()")
        database_row = await database_result.fetchone()
        database_name = str(database_row[0]) if database_row else "unknown"

        column_result = await connection.execute(COLUMN_QUERY)
        column_rows = await column_result.fetchall()
        foreign_key_result = await connection.execute(FOREIGN_KEY_QUERY)
        foreign_key_rows = await foreign_key_result.fetchall()

        columns_by_table: dict[tuple[str, str], list[ColumnMetadata]] = defaultdict(list)
        foreign_keys_by_table: dict[tuple[str, str], list[ForeignKeyMetadata]] = defaultdict(list)

        for row in column_rows:
            schema_name, table_name, column_name, data_type, nullable, primary_key = row
            columns_by_table[(str(schema_name), str(table_name))].append(
                ColumnMetadata(
                    name=str(column_name),
                    type=str(data_type),
                    nullable=bool(nullable),
                    primary_key=bool(primary_key),
                )
            )

        for row in foreign_key_rows:
            (
                source_schema,
                source_table,
                source_column,
                target_schema,
                target_table,
                target_column,
            ) = row
            foreign_keys_by_table[(str(source_schema), str(source_table))].append(
                ForeignKeyMetadata(
                    column=str(source_column),
                    references_schema=str(target_schema),
                    references_table=str(target_table),
                    references_column=str(target_column),
                )
            )

        tables = [
            TableMetadata(
                **{
                    "schema": schema_name,
                    "name": table_name,
                    "columns": columns,
                    "foreign_keys": foreign_keys_by_table[(schema_name, table_name)],
                }
            )
            for (schema_name, table_name), columns in columns_by_table.items()
        ]
        schemas = sorted({table.schema_name for table in tables})
        return DatabaseSchemaMetadata(database=database_name, schemas=schemas, tables=tables)
