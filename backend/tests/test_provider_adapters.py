from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, SecretStr
from starlette.requests import Request

from app.config import Settings
from app.dependencies import get_llm_provider
from app.llm.exceptions import (
    ProviderConfigurationError,
    ProviderInvocationError,
    StructuredOutputError,
)
from app.llm.factory import LLMFactory
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.openai import OpenAIProvider
from app.schemas.dashboard import DashboardConfig


class Answer(BaseModel):
    answer: str


def settings(**overrides):
    values = dict(
        _env_file=None,
        app_env="testing",
        app_database_url="sqlite+aiosqlite://",
        secret_encryption_key="not-used",
        ai_provider="openai",
        ai_model="gpt-6-luna",
        openai_api_key=SecretStr("openai-test-key"),
        anthropic_api_key=SecretStr("anthropic-test-key"),
    )
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    ("name", "model", "adapter"),
    [
        ("openai", "gpt-6-luna", OpenAIProvider),
        ("anthropic", "claude-sonnet-5-5", AnthropicProvider),
    ],
)
def test_factory_and_schema_binding_without_network(name, model, adapter):
    provider = LLMFactory.create(settings(ai_provider=name, ai_model=model))
    assert isinstance(provider, adapter)
    assert provider.name == name and provider.model == model
    assert provider.capabilities.structured_output
    assert provider._structured_client(DashboardConfig) is not None
    assert provider._client.temperature is None


@pytest.mark.parametrize("adapter", [OpenAIProvider, AnthropicProvider])
async def test_adapters_validate_structured_output_and_invoke(adapter):
    provider = adapter(
        model="test-model", api_key="test-key", temperature=0, timeout_seconds=10, max_retries=0
    )
    client = Mock()
    runner = SimpleNamespace(ainvoke=AsyncMock(return_value={"answer": "ready"}))
    client.with_structured_output.return_value = runner
    client.ainvoke = AsyncMock(return_value=AIMessage(content="ready"))
    provider._client = client
    messages = [HumanMessage(content="test")]
    assert (await provider.structured_output(messages, Answer)).answer == "ready"
    expected_method = "json_schema" if adapter is AnthropicProvider else "function_calling"
    assert client.with_structured_output.call_args.kwargs["method"] == expected_method
    assert (await provider.invoke(messages)).content == "ready"
    runner.ainvoke.return_value = {"incorrect_field": "invalid"}
    with pytest.raises(StructuredOutputError):
        await provider.structured_output(messages, Answer)


@pytest.mark.parametrize("adapter", [OpenAIProvider, AnthropicProvider])
@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500])
async def test_provider_failures_do_not_leak_credentials(adapter, status):
    provider = adapter(
        model="test-model", api_key="secret-key", temperature=0, timeout_seconds=10, max_retries=0
    )
    error = RuntimeError("secret-key and private prompt must never be exposed")
    error.status_code = status
    provider._client = Mock()
    provider._client.with_structured_output.return_value = SimpleNamespace(
        ainvoke=AsyncMock(side_effect=error)
    )
    with pytest.raises(ProviderInvocationError) as caught:
        await provider.structured_output([HumanMessage(content="private prompt")], Answer)
    assert "secret-key" not in caught.value.message
    assert "private prompt" not in caught.value.message


@pytest.mark.parametrize("provider", ["groq", "openai", "anthropic"])
def test_visitor_provider_and_custom_model_use_only_visitor_key(provider, monkeypatch):
    config = settings(access_mode="public", groq_api_key="server-groq")
    received = []
    monkeypatch.setattr(LLMFactory, "create", lambda value: received.append(value) or "provider")
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"authorization", b"Bearer visitor-secret"),
                (b"x-ai-provider", provider.encode()),
                (b"x-ai-model", b"my-compatible-model-2026"),
            ],
        }
    )
    assert get_llm_provider(request, config) == "provider"
    selected = received[0]
    assert selected.ai_provider == provider and selected.ai_model == "my-compatible-model-2026"
    for name in ["groq", "openai", "anthropic"]:
        key = getattr(selected, name + "_api_key")
        assert (key.get_secret_value() if key else None) == (
            "visitor-secret" if name == provider else None
        )
    assert config.openai_api_key.get_secret_value() == "openai-test-key"


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_selected_provider_cannot_fall_back_to_another_server_key(provider):
    with pytest.raises(ProviderConfigurationError, match=provider.upper() + "_API_KEY"):
        LLMFactory.create(settings(ai_provider=provider, **{provider + "_api_key": None}))


@pytest.mark.parametrize(
    "model", ["https://attacker.example/model", "model\nHeader: value", "", "x" * 129]
)
def test_custom_model_id_is_bounded_and_is_not_an_endpoint(model):
    with pytest.raises(ProviderConfigurationError):
        LLMFactory.create(settings(ai_model=model))


async def test_claude_native_schema_preserves_dashboard_options_and_parameters():
    provider = AnthropicProvider(
        model="claude-sonnet-5-5",
        api_key="test-key",
        temperature=0,
        timeout_seconds=10,
        max_retries=0,
    )
    payload = {
        "title": "Sales",
        "queries": [
            {
                "id": "q1",
                "name": "Revenue",
                "sql": "SELECT 1 AS revenue",
                "parameters": '{"country":"FR"}',
            }
        ],
        "widgets": [
            {
                "id": "w1",
                "type": "kpi",
                "title": "Revenue",
                "query_id": "q1",
                "value_field": "revenue",
                "options": '{"color":"blue","format":{"currency":"EUR"}}',
            }
        ],
        "layout": [{"widget_id": "w1", "x": 0, "y": 0, "width": 6, "height": 2}],
    }
    client = Mock()
    client.with_structured_output.return_value = SimpleNamespace(
        ainvoke=AsyncMock(return_value=payload)
    )
    provider._client = client
    result = await provider.structured_output(
        [HumanMessage(content="Build a dashboard")], DashboardConfig
    )
    assert result.queries[0].parameters == {"country": "FR"}
    assert result.widgets[0].options == {"color": "blue", "format": {"currency": "EUR"}}
    schema = client.with_structured_output.call_args.args[0]
    assert schema["$defs"]["WidgetConfig"]["properties"]["options"]["type"] == "string"
    assert client.with_structured_output.call_args.kwargs["method"] == "json_schema"
    payload["widgets"][0]["options"] = "[]"
    with pytest.raises(StructuredOutputError):
        await provider.structured_output([], DashboardConfig)
