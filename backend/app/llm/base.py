from collections.abc import Sequence
from typing import Protocol, TypeVar

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel

from app.llm.capabilities import LLMCapabilities

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def capabilities(self) -> LLMCapabilities: ...

    async def invoke(self, messages: Sequence[BaseMessage]) -> AIMessage: ...

    async def structured_output(
        self,
        messages: Sequence[BaseMessage],
        schema: type[StructuredModel],
    ) -> StructuredModel: ...
