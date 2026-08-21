from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.database_connection import DatabaseConnection
from app.models.query_execution import QueryExecution
from app.models.schema_cache import DatabaseSchemaCache
from app.models.session import Session
from app.models.user import User


async def erase_visitor(db: AsyncSession, user_id: UUID) -> None:
    """Remove only this visitor's history, credentials and identity."""
    connections = select(DatabaseConnection.id).where(DatabaseConnection.user_id == user_id)
    await db.execute(
        delete(QueryExecution).where(QueryExecution.database_connection_id.in_(connections))
    )
    # ORM cascades also make this operation work with SQLite test databases.
    for session in await db.scalars(select(Session).where(Session.user_id == user_id)):
        await db.delete(session)
    await db.flush()
    await db.execute(
        delete(DatabaseSchemaCache).where(
            DatabaseSchemaCache.database_connection_id.in_(connections)
        )
    )
    await db.execute(delete(DatabaseConnection).where(DatabaseConnection.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()


async def purge_expired_visitors(db: AsyncSession, settings: Settings) -> int:
    cutoff = datetime.now(UTC) - timedelta(hours=settings.visitor_session_hours)
    users = list(
        await db.scalars(
            select(User)
            .where(
                User.email.like("visitor-%@sessions.invalid"),
                User.created_at < cutoff,
            )
            .limit(20)
        )
    )
    for user in users:
        await erase_visitor(db, user.id)
    return len(users)
