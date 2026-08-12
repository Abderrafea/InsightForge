import asyncio
import base64
import json
import math
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

import psycopg

from app.core.exceptions import ExternalDatabaseConnectionError
from app.core.security import CredentialCipher
from app.database.connection_manager import ExternalDatabaseConnectionManager
from app.database.external_database import ExternalDatabaseCredentials
from app.models.database_connection import DatabaseConnection
from app.query.exceptions import QueryEngineError, QueryErrorCode
from app.query.models import QueryResult
from app.query.policy import QueryPolicy


class SafeQueryExecutor:
    def __init__(
        self,
        manager: ExternalDatabaseConnectionManager,
        cipher: CredentialCipher,
        policy: QueryPolicy,
    ) -> None:
        self._manager = manager
        self._cipher = cipher
        self._policy = policy

    async def execute(
        self,
        connection_record: DatabaseConnection,
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> QueryResult:
        credentials = ExternalDatabaseCredentials(
            host=connection_record.host,
            port=connection_record.port,
            database_name=connection_record.database_name,
            username=connection_record.username,
            password=self._cipher.decrypt_secret(connection_record.encrypted_password),
            ssl_mode=connection_record.ssl_mode,
        )
        started_at = perf_counter()

        try:
            async with asyncio.timeout(self._policy.timeout_seconds + 1):
                async with self._manager.connection(credentials) as connection:
                    rows, columns, truncated = await self._execute_in_transaction(
                        connection, sql, parameters
                    )
        except ExternalDatabaseConnectionError as exc:
            raise QueryEngineError(
                QueryErrorCode.DATABASE_CONNECTION_FAILED, exc.user_message
            ) from exc
        except psycopg.errors.QueryCanceled as exc:
            raise QueryEngineError(
                QueryErrorCode.QUERY_TIMEOUT,
                f"Query exceeded the {self._policy.timeout_seconds}-second timeout.",
                status_code=408,
            ) from exc
        except TimeoutError as exc:
            raise QueryEngineError(
                QueryErrorCode.QUERY_TIMEOUT,
                f"Query exceeded the {self._policy.timeout_seconds}-second timeout.",
                status_code=408,
            ) from exc
        except psycopg.errors.UndefinedTable as exc:
            table_name = self._extract_identifier(exc, "relation")
            message = (
                f"Table '{table_name}' does not exist."
                if table_name
                else "A referenced table does not exist."
            )
            raise QueryEngineError(QueryErrorCode.UNKNOWN_TABLE, message) from exc
        except psycopg.errors.UndefinedColumn as exc:
            column_name = self._extract_identifier(exc, "column")
            message = (
                f"Column '{column_name}' does not exist."
                if column_name
                else "A referenced column does not exist."
            )
            raise QueryEngineError(QueryErrorCode.UNKNOWN_COLUMN, message) from exc
        except psycopg.errors.InsufficientPrivilege as exc:
            raise QueryEngineError(
                QueryErrorCode.PERMISSION_DENIED,
                "The read-only database user is not permitted to run this query.",
            ) from exc
        except psycopg.errors.SyntaxError as exc:
            raise QueryEngineError(
                QueryErrorCode.SYNTAX_ERROR, "PostgreSQL rejected the query syntax."
            ) from exc
        except psycopg.DatabaseError as exc:
            raise QueryEngineError(
                QueryErrorCode.QUERY_EXECUTION_FAILED,
                "PostgreSQL could not execute the analytical query.",
            ) from exc

        execution_time_ms = round((perf_counter() - started_at) * 1_000, 3)
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            execution_time_ms=execution_time_ms,
        )

    async def _execute_in_transaction(
        self,
        connection: psycopg.AsyncConnection[tuple[object, ...]],
        sql: str,
        parameters: Sequence[Any] | Mapping[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], list[str], bool]:
        async with connection.transaction():
            await connection.execute("SET TRANSACTION READ ONLY")
            await connection.execute(
                "SELECT set_config('statement_timeout', %s, true)",
                (f"{self._policy.timeout_seconds * 1_000}ms",),
            )
            cursor_name = f"insightforge_query_{uuid4().hex}"
            async with connection.cursor(name=cursor_name) as cursor:
                if parameters is None:
                    await cursor.execute(sql)
                else:
                    await cursor.execute(sql, parameters)
                if cursor.description is None:
                    raise QueryEngineError(
                        QueryErrorCode.QUERY_EXECUTION_FAILED,
                        "The query did not produce a tabular result.",
                    )
                columns = self._unique_column_names([column.name for column in cursor.description])
                rows, truncated = await self._fetch_controlled_rows(cursor, columns)
                return rows, columns, truncated

    async def _fetch_controlled_rows(
        self, cursor: Any, columns: list[str]
    ) -> tuple[list[dict[str, Any]], bool]:
        rows: list[dict[str, Any]] = []
        result_bytes = len(json.dumps({"columns": columns}, separators=(",", ":")).encode("utf-8"))
        truncated = False

        while len(rows) < self._policy.max_rows:
            batch_size = min(100, self._policy.max_rows - len(rows))
            batch = await cursor.fetchmany(batch_size)
            if not batch:
                break

            for raw_row in batch:
                safe_row = {
                    column: self._to_json_safe(value)
                    for column, value in zip(columns, raw_row, strict=True)
                }
                row_bytes = len(
                    json.dumps(
                        safe_row,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                if result_bytes + row_bytes > self._policy.max_result_bytes:
                    truncated = True
                    return rows, truncated
                rows.append(safe_row)
                result_bytes += row_bytes

            if len(batch) < batch_size:
                break

        if len(rows) == self._policy.max_rows:
            truncated = await cursor.fetchone() is not None
        return rows, truncated

    @classmethod
    def _to_json_safe(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else str(value)
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, timedelta):
            return value.total_seconds()
        if isinstance(value, (bytes, bytearray, memoryview)):
            return base64.b64encode(bytes(value)).decode("ascii")
        if isinstance(value, Enum):
            return cls._to_json_safe(value.value)
        if isinstance(value, Mapping):
            return {str(key): cls._to_json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            return [cls._to_json_safe(item) for item in value]
        return str(value)

    @staticmethod
    def _unique_column_names(names: list[str]) -> list[str]:
        seen: dict[str, int] = {}
        unique: list[str] = []
        for name in names:
            count = seen.get(name, 0) + 1
            seen[name] = count
            unique.append(name if count == 1 else f"{name}_{count}")
        return unique

    @staticmethod
    def _extract_identifier(error: psycopg.DatabaseError, object_type: str) -> str | None:
        primary_message = error.diag.message_primary or ""
        match = re.search(rf'{object_type} "([^"\r\n]{{1,255}})"', primary_message)
        return match.group(1) if match else None
