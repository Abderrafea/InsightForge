import re

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.exceptions import ProviderConfigurationError, UnsupportedProviderError
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.groq import GroqProvider
from app.llm.providers.openai import OpenAIProvider


class LLMFactory:
    @staticmethod
    def create(settings: Settings) -> LLMProvider:
        provider_name = settings.ai_provider.strip().casefold()
        providers = {
            "groq": (GroqProvider, settings.groq_api_key, "GROQ_API_KEY"),
            "openai": (OpenAIProvider, settings.openai_api_key, "OPENAI_API_KEY"),
            "anthropic": (AnthropicProvider, settings.anthropic_api_key, "ANTHROPIC_API_KEY"),
        }
        if provider_name not in providers:
            raise UnsupportedProviderError(settings.ai_provider)
        adapter, api_key, key_name = providers[provider_name]
        if not settings.ai_model or not settings.ai_model.strip():
            raise ProviderConfigurationError(
                f"AI_MODEL is required when AI_PROVIDER={provider_name}"
            )
        if "://" in settings.ai_model or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", settings.ai_model.strip()
        ):
            raise ProviderConfigurationError("Enter a valid model ID, not a URL or display name")
        if api_key is None or not api_key.get_secret_value().strip():
            raise ProviderConfigurationError(
                f"{key_name} is required when AI_PROVIDER={provider_name}"
            )

        provider = adapter(
            model=settings.ai_model.strip(),
            api_key=api_key.get_secret_value().strip(),
            temperature=settings.ai_temperature,
            timeout_seconds=settings.ai_provider_timeout_seconds,
            max_retries=settings.ai_provider_max_retries,
        )
        if not provider.capabilities.structured_output:
            raise ProviderConfigurationError(
                f"AI model '{provider.model}' does not support structured output"
            )
        return provider
