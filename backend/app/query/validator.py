from collections import defaultdict

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.query.models import QueryValidationResult
from app.query.policy import QueryPolicy
from app.schemas.schema_inspection import DatabaseSchemaMetadata, TableMetadata

DISALLOWED_OPERATION_KEYS = frozenset(
    {
        "alter",
        "analyze",
        "begin",
        "call",
        "comment",
        "commit",
        "copy",
        "create",
        "delete",
        "do",
        "drop",
        "grant",
        "insert",
        "into",
        "load",
        "lock",
        "merge",
        "reset",
        "revoke",
        "rollback",
        "savepoint",
        "set",
        "transaction",
        "truncate",
        "update",
        "use",
        "vacuum",
    }
)


class SQLValidator:
    def __init__(self, policy: QueryPolicy) -> None:
        self._policy = policy

    def validate(
        self,
        sql: str,
        allowed_schema: DatabaseSchemaMetadata | None = None,
    ) -> QueryValidationResult:
        if not sql.strip():
            return self._invalid("SQL query must not be empty")
        if len(sql) > self._policy.max_sql_length:
            return self._invalid(
                f"SQL query exceeds the maximum length of {self._policy.max_sql_length} characters"
            )

        try:
            statements = [
                statement
                for statement in sqlglot.parse(sql, read="postgres")
                if statement is not None
            ]
        except ParseError:
            return self._invalid("SQL syntax is invalid")

        if not statements:
            return self._invalid("SQL query must contain a statement")

        errors: list[str] = []
        if len(statements) != 1:
            errors.append("Only one SQL statement is allowed")

        statement_type = self._statement_type(statements[0])
        referenced_tables: list[str] = []
        seen_references: set[str] = set()

        for statement in statements:
            self._validate_statement_root(statement, errors)
            self._validate_operations(statement, errors)
            self._validate_functions(statement, errors)
            self._validate_join_count(statement, errors)
            statement_references = self._validate_tables(statement, allowed_schema, errors)
            self._validate_qualified_columns(statement, allowed_schema, errors)
            for reference in statement_references:
                if reference not in seen_references:
                    referenced_tables.append(reference)
                    seen_references.add(reference)

        return QueryValidationResult(
            valid=not errors,
            errors=list(dict.fromkeys(errors)),
            referenced_tables=referenced_tables,
            statement_type=statement_type,
        )

    @staticmethod
    def _invalid(error: str) -> QueryValidationResult:
        return QueryValidationResult(valid=False, errors=[error])

    @staticmethod
    def _statement_type(statement: exp.Expression) -> str:
        if isinstance(statement, exp.Query):
            return "SELECT"
        if isinstance(statement, exp.Command):
            command_name = str(statement.this).strip().upper()
            return command_name or "COMMAND"
        return statement.key.upper()

    def _validate_statement_root(self, statement: exp.Expression, errors: list[str]) -> None:
        if not isinstance(statement, exp.Query):
            statement_type = self._statement_type(statement)
            errors.append(f"{statement_type} statements are not allowed")

    @staticmethod
    def _validate_operations(statement: exp.Expression, errors: list[str]) -> None:
        operations = {
            node.key.upper()
            for node in statement.walk()
            if node.key.lower() in DISALLOWED_OPERATION_KEYS
        }
        errors.extend(f"{operation} operations are not allowed" for operation in sorted(operations))

    def _validate_functions(self, statement: exp.Expression, errors: list[str]) -> None:
        denied_used: set[str] = set()
        for function in statement.find_all(exp.Func):
            function_name = function.sql_name().lower()
            if function_name == "anonymous":
                function_name = function.name.lower()
            if function_name in self._policy.denied_functions:
                denied_used.add(function_name)
        errors.extend(
            f"Function '{function_name}' is not allowed" for function_name in sorted(denied_used)
        )

    def _validate_join_count(self, statement: exp.Expression, errors: list[str]) -> None:
        join_count = sum(1 for _ in statement.find_all(exp.Join))
        if join_count > self._policy.max_joins:
            errors.append(f"Query uses {join_count} joins; the maximum is {self._policy.max_joins}")

    def _validate_tables(
        self,
        statement: exp.Expression,
        allowed_schema: DatabaseSchemaMetadata | None,
        errors: list[str],
    ) -> list[str]:
        cte_names = {
            self._normalize_identifier(cte.alias_or_name) for cte in statement.find_all(exp.CTE)
        }
        references: list[str] = []

        for table in statement.find_all(exp.Table):
            table_name = table.name
            if not table_name:
                continue
            normalized_name = self._normalize_identifier(table_name)
            schema_name = table.db
            normalized_schema = self._normalize_identifier(schema_name)

            if not schema_name and normalized_name in cte_names:
                continue

            display_name = f"{schema_name}.{table_name}" if schema_name else table_name
            references.append(display_name)

            if table.catalog:
                errors.append(f"Cross-database references are not allowed: {display_name}")
                continue
            if normalized_schema in self._policy.denied_schemas:
                errors.append(f"System schema access is not allowed: {schema_name}")
                continue
            if allowed_schema is None:
                continue

            known_table = self._resolve_table(allowed_schema, normalized_schema, normalized_name)
            if known_table is None:
                errors.append(f"Unknown table: {display_name}")

        return references

    def _validate_qualified_columns(
        self,
        statement: exp.Expression,
        allowed_schema: DatabaseSchemaMetadata | None,
        errors: list[str],
    ) -> None:
        if allowed_schema is None:
            return

        cte_or_derived_aliases = {
            self._normalize_identifier(expression.alias_or_name)
            for expression in (
                *statement.find_all(exp.CTE),
                *statement.find_all(exp.Subquery),
            )
            if expression.alias_or_name
        }
        alias_tables: dict[str, list[TableMetadata]] = defaultdict(list)

        for table in statement.find_all(exp.Table):
            table_name = self._normalize_identifier(table.name)
            schema_name = self._normalize_identifier(table.db)
            if not table.db and table_name in cte_or_derived_aliases:
                continue
            known_table = self._resolve_table(allowed_schema, schema_name, table_name)
            if known_table is None:
                continue
            alias = self._normalize_identifier(table.alias_or_name)
            alias_tables[alias].append(known_table)

        for column in statement.find_all(exp.Column):
            if column.is_star or not column.table:
                continue
            qualifier = self._normalize_identifier(column.table)
            if qualifier in cte_or_derived_aliases:
                continue
            candidates = alias_tables.get(qualifier, [])
            if len(candidates) != 1:
                continue
            column_name = self._normalize_identifier(column.name)
            known_columns = {
                self._normalize_identifier(item.name) for item in candidates[0].columns
            }
            if column_name not in known_columns:
                errors.append(f"Unknown column: {column.table}.{column.name}")

    @staticmethod
    def _resolve_table(
        schema: DatabaseSchemaMetadata,
        schema_name: str,
        table_name: str,
    ) -> TableMetadata | None:
        matches = [
            table
            for table in schema.tables
            if SQLValidator._normalize_identifier(table.name) == table_name
            and (
                not schema_name
                or SQLValidator._normalize_identifier(table.schema_name) == schema_name
            )
        ]
        return matches[0] if matches else None

    @staticmethod
    def _normalize_identifier(value: str) -> str:
        return value.casefold()
