from app.core.exceptions import ApplicationError, BadRequestError


class NoDatabaseConnectedError(BadRequestError):
    def __init__(self) -> None:
        super().__init__(
            "No database is connected to this session.",
            code="session_database_connection_required",
        )


class DashboardValidationError(ApplicationError):
    def __init__(
        self, message: str = "The AI generated an invalid dashboard configuration"
    ) -> None:
        super().__init__(message, status_code=502, code="dashboard_validation_error")


class AgentExecutionError(ApplicationError):
    def __init__(
        self, message: str = "The dashboard agent could not complete this request"
    ) -> None:
        super().__init__(message, status_code=500, code="agent_execution_error")
