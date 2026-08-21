from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.message import Message, MessageRole


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, session_id: UUID, role: MessageRole, content: str) -> Message:
        if "visitor_id" in self._db.info:
            count = await self._db.scalar(
                select(func.count()).select_from(Message).where(Message.session_id == session_id)
            )
            if count >= (98 if role == MessageRole.USER else 100):
                raise BadRequestError(
                    "This demo session has reached its message limit", code="visitor_limit"
                )
        message = Message(session_id=session_id, role=role, content=content)
        self._db.add(message)
        await self._db.flush()
        await self._db.refresh(message)
        return message

    async def list_for_session(self, session_id: UUID) -> list[Message]:
        result = await self._db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list(result)
