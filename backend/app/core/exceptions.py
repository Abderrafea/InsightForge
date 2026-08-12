class ApplicationError(Exception):
    def __init__(self, message: str, *, status_code: int, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class NotFoundError(ApplicationError):
    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} was not found", status_code=404, code="not_found")


class BadRequestError(ApplicationError):
    def __init__(self, message: str, *, code: str = "bad_request") -> None:
        super().__init__(message, status_code=400, code=code)


class ConfigurationError(ApplicationError):
    def __init__(self, message: str = "The server is not configured correctly") -> None:
        super().__init__(message, status_code=500, code="configuration_error")


class ExternalDatabaseConnectionError(Exception):
    """A sanitized external database error safe to surface to a client."""

    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message
