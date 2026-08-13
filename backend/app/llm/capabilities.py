from pydantic import BaseModel, ConfigDict


class LLMCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    structured_output: bool
    tool_calling: bool
    json_mode: bool
