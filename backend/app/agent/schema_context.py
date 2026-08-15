from app.schemas.schema_inspection import DatabaseSchemaMetadata


def compact_schema(schema: DatabaseSchemaMetadata) -> str:
    tables: list[str] = []
    for table in schema.tables:
        lines = [f"Table: {table.schema_name}.{table.name}"]
        foreign_keys = {foreign_key.column: foreign_key for foreign_key in table.foreign_keys}
        for column in table.columns:
            markers: list[str] = []
            if column.primary_key:
                markers.append("PK")
            if column.name in foreign_keys:
                reference = foreign_keys[column.name]
                markers.append(
                    "FK -> "
                    f"{reference.references_schema}.{reference.references_table}."
                    f"{reference.references_column}"
                )
            suffix = f" ({', '.join(markers)})" if markers else ""
            nullable = " nullable" if column.nullable else ""
            lines.append(f"- {column.name}: {column.type}{nullable}{suffix}")
        tables.append("\n".join(lines))
    return "\n\n".join(tables)
