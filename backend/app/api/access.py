from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.exceptions import ApplicationError
from app.core.visitors import COOKIE_NAME, read_visitor_cookie, visitor_cookie
from app.database.app_database import get_access_session, get_db_session
from app.models.user import User
from app.services.visitor_service import erase_visitor, purge_expired_visitors

router = APIRouter(prefix="/access", tags=["access"])
Config = Annotated[Settings, Depends(get_settings)]


@router.get("")
async def access_info(settings: Config, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {
        "public_visitors": settings.public_visitors,
        "models": settings.allowed_visitor_models if settings.public_visitors else [],
        "providers": settings.visitor_providers if settings.public_visitors else [],
        "allow_custom_models": settings.visitor_allow_custom_models,
        "session_hours": settings.visitor_session_hours,
    }


@router.post("")
async def start_visitor(
    request: Request,
    response: Response,
    settings: Config,
    db: Annotated[AsyncSession, Depends(get_access_session)],
) -> dict:
    if not settings.public_visitors:
        return {"ready": True}
    if request.headers.get("x-requested-with") != "InsightForge" or request.headers.get(
        "origin"
    ) not in {None, *settings.allowed_origins}:
        raise ApplicationError(
            "The request origin is not allowed", status_code=403, code="request_origin_rejected"
        )
    user_id = read_visitor_cookie(request.cookies.get(COOKIE_NAME, ""), settings)
    existing = await db.get(User, user_id) if user_id else None
    if existing is None:
        await purge_expired_visitors(db, settings)
        count = await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email.like("visitor-%@sessions.invalid"))
        )
        if count >= settings.max_visitors:
            raise ApplicationError(
                "The demo is at capacity. Please try again later",
                status_code=429,
                code="visitor_capacity",
            )
        user = User(email=f"visitor-{uuid4()}@sessions.invalid")
        db.add(user)
        await db.commit()
        user_id = user.id
        response.set_cookie(
            COOKIE_NAME,
            visitor_cookie(user_id, settings),
            httponly=True,
            secure=settings.production,
            samesite="strict",
            path="/",
            max_age=settings.visitor_session_hours * 3600,
        )
    response.headers["Cache-Control"] = "no-store"
    return {"ready": True}


@router.delete("", status_code=204)
async def end_visitor(
    settings: Config,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    if settings.public_visitors:
        await erase_visitor(db, db.info["visitor_id"])
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        COOKIE_NAME, path="/", secure=settings.production, httponly=True, samesite="strict"
    )
    return response
