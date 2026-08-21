from langchain_openai import ChatOpenAI

from app.llm.providers.structured import StructuredChatProvider


class OpenAIProvider(StructuredChatProvider):
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        temperature: float,
        timeout_seconds: int,
        max_retries: int,
    ) -> None:
        # Let the selected model use its supported temperature default; reasoning
        # models do not all accept a caller-supplied temperature.
        client = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url="https://api.openai.com/v1",
            timeout=timeout_seconds,
            max_retries=max_retries,
            max_completion_tokens=8192,
            use_responses_api=False,
        )
        super().__init__(client, name="openai", model=model)
