from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.exceptions import ApplicationError
from app.models.user import User

COOKIE_NAME = "insightforge_visitor"


def visitor_cookie(user_id: UUID, settings: Settings) -> str:
    return (
        Fernet(settings.secret_encryption_key.get_secret_value())
        .encrypt(f"visitor:v1:{user_id}".encode())
        .decode()
    )


def read_visitor_cookie(value: str, settings: Settings) -> UUID | None:
    try:
        payload = (
            Fernet(settings.secret_encryption_key.get_secret_value())
            .decrypt(
                value.encode(),
                ttl=settings.visitor_session_hours * 3600,
            )
            .decode()
        )
        if not payload.startswith("visitor:v1:"):
            return None
        return UUID(payload.removeprefix("visitor:v1:"))
    except (InvalidToken, ValueError, UnicodeError):
        return None


async def scope_visitor(db: AsyncSession, request: Request, settings: Settings) -> None:
    if not settings.public_visitors:
        return
    user_id = read_visitor_cookie(request.cookies.get(COOKIE_NAME, ""), settings)
    if user_id is None or await db.get(User, user_id) is None:
        raise ApplicationError(
            "Start or resume your private visitor session",
            status_code=401,
            code="visitor_session_required",
        )
    db.info["visitor_id"] = user_id
