from collections.abc import Sequence
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, BaseMessage
from pydantic import ValidationError

from app.llm.base import StructuredModel
from app.llm.capabilities import LLMCapabilities
from app.llm.exceptions import ProviderInvocationError, StructuredOutputError


class StructuredChatProvider:
    """One error/validation boundary shared by the chat-provider adapters."""

    def __init__(self, client: Any, *, name: str, model: str) -> None:
        self._client = client
        self._name = name
        self._model_name = model

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(structured_output=True, tool_calling=True, json_mode=False)

    def _provider_error(self, exc: Exception) -> ProviderInvocationError:
        # Never expose provider response bodies, prompts, keys or transport headers.
        status = getattr(exc, "status_code", None)
        if status in {401, 403}:
            return ProviderInvocationError(
                "The provider refused this API key. Check its access permissions and billing."
            )
        if status == 404:
            return ProviderInvocationError(
                "This model is unavailable for your provider account. Select another model."
            )
        if status == 429:
            return ProviderInvocationError(
                "The provider's request or usage limit was reached. "
                "Please retry later or check your quota."
            )
        if status == 400:
            return ProviderInvocationError(
                "The provider rejected this configuration. "
                "Choose a text model compatible with structured tool output."
            )
        return ProviderInvocationError()

    async def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        try:
            result = await self._client.ainvoke(list(messages))
        except Exception as exc:
            raise self._provider_error(exc) from exc
        if not isinstance(result, AIMessage):
            raise ProviderInvocationError("The AI provider returned an unexpected response")
        return result

    async def structured_output(
        self,
        messages: Sequence[BaseMessage],
        schema: type[StructuredModel],
    ) -> StructuredModel:
        try:
            # Tool output supports the existing dashboard schemas, including free-form
            # options dictionaries. Pydantic validates the complete response locally.
            client = self._structured_client(schema)
            result = await client.ainvoke(list(messages))
            return self._parse_structured_result(result, schema)
        except (ValidationError, OutputParserException) as exc:
            raise StructuredOutputError() from exc
        except ProviderInvocationError:
            raise
        except Exception as exc:
            raise self._provider_error(exc) from exc

    def _structured_client(self, schema: type[StructuredModel]) -> Any:
        return self._client.with_structured_output(schema, method="function_calling")

    def _parse_structured_result(
        self, result: Any, schema: type[StructuredModel]
    ) -> StructuredModel:
        return result if isinstance(result, schema) else schema.model_validate(result)
