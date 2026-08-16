from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.agent.models import AgentMessageRequest, AgentMessageResponse
from app.agent.service import AgentService
from app.dependencies import get_agent_service
from app.schemas.message import MessageRead

router = APIRouter(prefix="/sessions/{session_id}/agent", tags=["agent"])
AgentServiceDependency = Annotated[AgentService, Depends(get_agent_service)]


@router.post("/messages", response_model=AgentMessageResponse)
async def send_agent_message(
    session_id: UUID,
    request: AgentMessageRequest,
    service: AgentServiceDependency,
) -> AgentMessageResponse:
    message, dashboard, dashboard_version, change = await service.send_message(
        session_id, request
    )
    return AgentMessageResponse(
        message=MessageRead.model_validate(message),
        dashboard=dashboard,
        dashboard_version=dashboard_version,
        change=change,
    )
