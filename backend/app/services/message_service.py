from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.message import Message
from app.repositories.message_repository import MessageRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.message import MessageCreate


class MessageService:
    def __init__(
        self,
        db: AsyncSession,
        sessions: SessionRepository,
        messages: MessageRepository,
    ) -> None:
        self._db = db
        self._sessions = sessions
        self._messages = messages

    async def create(self, session_id: UUID, request: MessageCreate) -> Message:
        session = await self._sessions.get(session_id)
        if session is None:
            raise NotFoundError("Session")

        message = await self._messages.create(session_id, request.role, request.content)
        session.updated_at = datetime.now(UTC)
        await self._db.commit()
        return message

    async def list_for_session(self, session_id: UUID) -> list[Message]:
        if await self._sessions.get(session_id) is None:
            raise NotFoundError("Session")
        return await self._messages.list_for_session(session_id)
