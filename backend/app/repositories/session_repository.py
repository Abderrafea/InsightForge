from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.session import Session


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, title: str) -> Session:
        session = Session(title=title)
        self._db.add(session)
        await self._db.flush()
        return session

    async def list_recent(self) -> list[Session]:
        result = await self._db.scalars(
            select(Session).order_by(Session.updated_at.desc(), Session.created_at.desc())
        )
        return list(result)

    async def get(self, session_id: UUID) -> Session | None:
        return await self._db.get(Session, session_id)

    async def get_with_details(self, session_id: UUID) -> Session | None:
        result = await self._db.scalars(
            select(Session)
            .where(Session.id == session_id)
            .options(
                selectinload(Session.messages),
                selectinload(Session.database_connection),
                selectinload(Session.dashboard),
            )
        )
        return result.one_or_none()

    async def delete(self, session: Session) -> None:
        await self._db.delete(session)
