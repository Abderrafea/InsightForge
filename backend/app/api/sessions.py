from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_session_service
from app.schemas.session import SessionCreate, SessionDetails, SessionRead, SessionUpdate
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])
SessionServiceDependency = Annotated[SessionService, Depends(get_session_service)]


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(request: SessionCreate, service: SessionServiceDependency) -> SessionRead:
    return SessionRead.model_validate(await service.create(request))


@router.get("", response_model=list[SessionRead])
async def list_sessions(service: SessionServiceDependency) -> list[SessionRead]:
    sessions = await service.list_sessions()
    return [SessionRead.model_validate(session) for session in sessions]


@router.get("/{session_id}", response_model=SessionDetails)
async def get_session(session_id: UUID, service: SessionServiceDependency) -> SessionDetails:
    return SessionDetails.model_validate(await service.get_details(session_id))


@router.patch("/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: UUID,
    request: SessionUpdate,
    service: SessionServiceDependency,
) -> SessionRead:
    return SessionRead.model_validate(await service.update(session_id, request))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: UUID, service: SessionServiceDependency) -> Response:
    await service.delete(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{session_id}/database-connection/{connection_id}",
    response_model=SessionDetails,
)
async def attach_database_connection(
    session_id: UUID,
    connection_id: UUID,
    service: SessionServiceDependency,
) -> SessionDetails:
    session = await service.attach_database_connection(session_id, connection_id)
    return SessionDetails.model_validate(session)
