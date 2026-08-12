from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies import get_message_service
from app.schemas.message import MessageCreate, MessageRead
from app.services.message_service import MessageService

router = APIRouter(prefix="/sessions/{session_id}/messages", tags=["messages"])
MessageServiceDependency = Annotated[MessageService, Depends(get_message_service)]


@router.post("", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def create_message(
    session_id: UUID,
    request: MessageCreate,
    service: MessageServiceDependency,
) -> MessageRead:
    return MessageRead.model_validate(await service.create(session_id, request))


@router.get("", response_model=list[MessageRead])
async def list_messages(session_id: UUID, service: MessageServiceDependency) -> list[MessageRead]:
    messages = await service.list_for_session(session_id)
    return [MessageRead.model_validate(message) for message in messages]
