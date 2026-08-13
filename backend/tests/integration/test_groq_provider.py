import os

import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.config import Settings
from app.llm.factory import LLMFactory

pytestmark = pytest.mark.integration
RUN_GROQ = os.getenv("RUN_GROQ_INTEGRATION_TESTS") == "1"


class GroqSmokeResult(BaseModel):
    answer: str


@pytest.mark.skipif(not RUN_GROQ, reason="Live Groq integration test disabled")
async def test_groq_structured_output() -> None:
    provider = LLMFactory.create(Settings())  # type: ignore[call-arg]

    result = await provider.structured_output(
        [HumanMessage(content="Return the single word ready in the answer field.")],
        GroqSmokeResult,
    )

    assert result.answer.strip().casefold() == "ready"
