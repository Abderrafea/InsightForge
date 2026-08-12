from enum import StrEnum

from app.core.exceptions import ApplicationError


class QueryErrorCode(StrEnum):
    UNKNOWN_TABLE = "UNKNOWN_TABLE"
    UNKNOWN_COLUMN = "UNKNOWN_COLUMN"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    QUERY_TIMEOUT = "QUERY_TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    QUERY_VALIDATION_FAILED = "QUERY_VALIDATION_FAILED"
    DATABASE_CONNECTION_FAILED = "DATABASE_CONNECTION_FAILED"
    QUERY_EXECUTION_FAILED = "QUERY_EXECUTION_FAILED"


class QueryEngineError(ApplicationError):
    def __init__(
        self,
        code: QueryErrorCode,
        message: str,
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(message, status_code=status_code, code=code.value)
        self.query_code = code


class QueryValidationFailedError(QueryEngineError):
    def __init__(self, errors: list[str]) -> None:
        message = errors[0] if errors else "The SQL query did not pass validation."
        super().__init__(QueryErrorCode.QUERY_VALIDATION_FAILED, message)
        self.errors = errors
