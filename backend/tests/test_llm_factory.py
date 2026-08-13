import pytest
from pydantic import SecretStr

from app.config import Settings
from app.llm.exceptions import ProviderConfigurationError, UnsupportedProviderError
from app.llm.factory import LLMFactory
from app.llm.providers.groq import GroqProvider


def settings(**overrides: object) -> Settings:
    values = {
        "app_database_url": SecretStr("sqlite+aiosqlite://"),
        "secret_encryption_key": SecretStr("test-key"),
        "ai_provider": "groq",
        "ai_model": "test-model",
        "groq_api_key": SecretStr("gsk_test"),
    }
    values.update(overrides)
    return Settings(**values)


def test_factory_creates_groq_adapter() -> None:
    provider = LLMFactory.create(settings())

    assert isinstance(provider, GroqProvider)
    assert provider.name == "groq"
    assert provider.model == "test-model"
    assert provider.capabilities.structured_output is True


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(UnsupportedProviderError):
        LLMFactory.create(settings(ai_provider="random_provider"))


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"ai_model": None}, "AI_MODEL"),
        ({"groq_api_key": None}, "GROQ_API_KEY"),
    ],
)
def test_factory_requires_groq_configuration(override: dict[str, object], expected: str) -> None:
    with pytest.raises(ProviderConfigurationError, match=expected):
        LLMFactory.create(settings(**override))
