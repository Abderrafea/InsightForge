from dataclasses import dataclass, field

from app.config import Settings

DEFAULT_DENIED_SCHEMAS = frozenset(
    {
        "information_schema",
        "pg_catalog",
        "pg_toast",
    }
)

DEFAULT_DENIED_FUNCTIONS = frozenset(
    {
        "current_setting",
        "dblink_connect",
        "dblink_exec",
        "lo_export",
        "lo_import",
        "nextval",
        "pg_advisory_lock",
        "pg_advisory_lock_shared",
        "pg_advisory_xact_lock",
        "pg_advisory_xact_lock_shared",
        "pg_cancel_backend",
        "pg_file_rename",
        "pg_file_unlink",
        "pg_file_write",
        "pg_ls_dir",
        "pg_read_binary_file",
        "pg_read_file",
        "pg_reload_conf",
        "pg_sleep",
        "pg_stat_file",
        "pg_terminate_backend",
        "set_config",
        "setval",
    }
)


@dataclass(frozen=True, slots=True)
class QueryPolicy:
    max_rows: int = 1_000
    timeout_seconds: int = 10
    max_sql_length: int = 20_000
    max_joins: int = 8
    max_result_bytes: int = 1_000_000
    denied_schemas: frozenset[str] = field(default_factory=lambda: DEFAULT_DENIED_SCHEMAS)
    denied_functions: frozenset[str] = field(default_factory=lambda: DEFAULT_DENIED_FUNCTIONS)

    @classmethod
    def from_settings(cls, settings: Settings) -> "QueryPolicy":
        return cls(
            max_rows=settings.query_max_rows,
            timeout_seconds=settings.query_timeout_seconds,
            max_sql_length=settings.query_max_sql_length,
            max_joins=settings.query_max_joins,
            max_result_bytes=settings.query_max_result_bytes,
        )
