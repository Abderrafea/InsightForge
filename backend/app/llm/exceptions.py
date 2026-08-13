from app.core.exceptions import ApplicationError


class ProviderConfigurationError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500, code="provider_configuration_error")


class UnsupportedProviderError(ProviderConfigurationError):
    def __init__(self, provider: str) -> None:
        super().__init__(f"AI provider '{provider}' is not supported")
        self.code = "unsupported_ai_provider"


class ProviderInvocationError(ApplicationError):
    def __init__(self, message: str = "The AI provider is temporarily unavailable") -> None:
        super().__init__(message, status_code=502, code="ai_provider_error")


class StructuredOutputError(ProviderInvocationError):
    def __init__(self) -> None:
        super().__init__("The AI provider returned an invalid structured response")
        self.code = "structured_output_error"
