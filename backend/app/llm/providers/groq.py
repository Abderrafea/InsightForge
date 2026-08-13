from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage
from langchain_groq import ChatGroq
from pydantic import ValidationError

from app.llm.base import StructuredModel
from app.llm.capabilities import LLMCapabilities
from app.llm.exceptions import ProviderInvocationError, StructuredOutputError


class GroqProvider:
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        temperature: float,
        timeout_seconds: int,
        max_retries: int,
    ) -> None:
        self._model_name = model
        self._client = ChatGroq(
            model=model,
            api_key=api_key,
            temperature=temperature,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        self._capabilities = LLMCapabilities(
            structured_output=True,
            tool_calling=True,
            json_mode=True,
        )

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def capabilities(self) -> LLMCapabilities:
        return self._capabilities

    async def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage:
        try:
            response = await self._client.ainvoke(list(messages))
        except Exception as exc:
            raise ProviderInvocationError() from exc
        if not isinstance(response, AIMessage):
            raise ProviderInvocationError("The AI provider returned an unexpected response")
        return response

    async def structured_output(
        self,
        messages: Sequence[BaseMessage],
        schema: type[StructuredModel],
    ) -> StructuredModel:
        try:
            structured_client = self._client.with_structured_output(schema)
            response = await structured_client.ainvoke(list(messages))
            if isinstance(response, schema):
                return response
            return schema.model_validate(response)
        except ValidationError as exc:
            raise StructuredOutputError() from exc
        except ProviderInvocationError:
            raise
        except Exception as exc:
            raise ProviderInvocationError() from exc
