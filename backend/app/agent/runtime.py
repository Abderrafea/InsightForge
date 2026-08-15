from dataclasses import dataclass

from app.config import Settings
from app.llm.base import LLMProvider
from app.query.service import SafeQueryService
from app.services.schema_inspection_service import SchemaInspectionService


@dataclass(frozen=True, slots=True)
class AgentRuntime:
    provider: LLMProvider
    schema_service: SchemaInspectionService
    query_service: SafeQueryService
    settings: Settings
