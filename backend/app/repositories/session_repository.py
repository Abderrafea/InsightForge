from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError
from app.models.session import Session


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, title: str) -> Session:
        owner = self._db.info.get("visitor_id")
        if owner is not None:
            count = await self._db.scalar(
                select(func.count()).select_from(Session).where(Session.user_id == owner)
            )
            if count >= 20:
                raise BadRequestError(
                    "A visitor can create up to 20 sessions", code="visitor_limit"
                )
        session = Session(title=title, user_id=owner)
        self._db.add(session)
        await self._db.flush()
        return session

    async def list_recent(self) -> list[Session]:
        statement = select(Session).order_by(Session.updated_at.desc(), Session.created_at.desc())
        if "visitor_id" in self._db.info:
            statement = statement.where(Session.user_id == self._db.info["visitor_id"])
        result = await self._db.scalars(statement)
        return list(result)

    async def get(self, session_id: UUID) -> Session | None:
        statement = select(Session).where(Session.id == session_id)
        if "visitor_id" in self._db.info:
            statement = statement.where(Session.user_id == self._db.info["visitor_id"])
        return await self._db.scalar(statement)

    async def get_with_details(self, session_id: UUID) -> Session | None:
        if await self.get(session_id) is None:
            return None
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
