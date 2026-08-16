from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.session import Session
from app.repositories.database_connection_repository import DatabaseConnectionRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.session import SessionCreate, SessionUpdate


class SessionService:
    def __init__(
        self,
        db: AsyncSession,
        sessions: SessionRepository,
        connections: DatabaseConnectionRepository,
    ) -> None:
        self._db = db
        self._sessions = sessions
        self._connections = connections

    async def create(self, request: SessionCreate) -> Session:
        session = await self._sessions.create(request.title)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def list_sessions(self) -> list[Session]:
        return await self._sessions.list_recent()

    async def get_details(self, session_id: UUID) -> Session:
        session = await self._sessions.get_with_details(session_id)
        if session is None:
            raise NotFoundError("Session")
        return session

    async def delete(self, session_id: UUID) -> None:
        session = await self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Session")
        await self._sessions.delete(session)
        await self._db.commit()

    async def update(self, session_id: UUID, request: SessionUpdate) -> Session:
        session = await self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Session")
        session.title = request.title
        session.updated_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def attach_database_connection(self, session_id: UUID, connection_id: UUID) -> Session:
        session = await self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Session")
        connection = await self._connections.get(connection_id)
        if connection is None:
            raise NotFoundError("Database connection")

        session.database_connection_id = connection.id
        session.updated_at = datetime.now(UTC)
        await self._db.commit()
        attached = await self._sessions.get_with_details(session_id)
        if attached is None:
            raise NotFoundError("Session")
        return attached
