from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool


class ForeignKeyMetadata(BaseModel):
    column: str
    references_schema: str
    references_table: str
    references_column: str


class TableMetadata(BaseModel):
    schema_name: str = Field(alias="schema", serialization_alias="schema")
    name: str
    columns: list[ColumnMetadata]
    foreign_keys: list[ForeignKeyMetadata]


class DatabaseSchemaMetadata(BaseModel):
    database: str
    schemas: list[str]
    tables: list[TableMetadata]
