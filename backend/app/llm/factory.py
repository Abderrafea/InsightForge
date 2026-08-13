from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.exceptions import ProviderConfigurationError, UnsupportedProviderError
from app.llm.providers.groq import GroqProvider


class LLMFactory:
    @staticmethod
    def create(settings: Settings) -> LLMProvider:
        provider_name = settings.ai_provider.strip().casefold()
        if provider_name != "groq":
            raise UnsupportedProviderError(settings.ai_provider)
        if not settings.ai_model or not settings.ai_model.strip():
            raise ProviderConfigurationError("AI_MODEL is required when AI_PROVIDER=groq")
        if settings.groq_api_key is None or not settings.groq_api_key.get_secret_value().strip():
            raise ProviderConfigurationError("GROQ_API_KEY is required when AI_PROVIDER=groq")

        provider = GroqProvider(
            model=settings.ai_model.strip(),
            api_key=settings.groq_api_key.get_secret_value(),
            temperature=settings.ai_temperature,
            timeout_seconds=settings.ai_provider_timeout_seconds,
            max_retries=settings.ai_provider_max_retries,
        )
        if not provider.capabilities.structured_output:
            raise ProviderConfigurationError(
                f"AI model '{provider.model}' does not support structured output"
            )
        return provider
