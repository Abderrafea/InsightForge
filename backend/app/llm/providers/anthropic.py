from typing import Any

from langchain_anthropic import ChatAnthropic

from app.llm.base import StructuredModel
from app.llm.exceptions import StructuredOutputError
from app.llm.providers.schema_wire import restore_maps, wire_schema
from app.llm.providers.structured import StructuredChatProvider


class AnthropicProvider(StructuredChatProvider):
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        temperature: float,
        timeout_seconds: int,
        max_retries: int,
    ) -> None:
        client = ChatAnthropic(
            model=model,
            api_key=api_key,
            base_url="https://api.anthropic.com",
            timeout=timeout_seconds,
            max_retries=max_retries,
            max_tokens=8192,
        )
        super().__init__(client, name="anthropic", model=model)

    def _structured_client(self, schema: type[StructuredModel]) -> Any:
        return self._client.with_structured_output(
            wire_schema(schema.model_json_schema()),
            method="json_schema",
        )

    def _parse_structured_result(
        self, result: Any, schema: type[StructuredModel]
    ) -> StructuredModel:
        try:
            restored = restore_maps(result, schema.model_json_schema())
        except (ValueError, KeyError, TypeError) as exc:
            raise StructuredOutputError() from exc
        return schema.model_validate(restored)
