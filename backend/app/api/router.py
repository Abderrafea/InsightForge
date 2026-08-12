from fastapi import APIRouter

from app.api import database_connections, messages, queries, sessions

api_router = APIRouter(prefix="/api")
api_router.include_router(sessions.router)
api_router.include_router(messages.router)
api_router.include_router(database_connections.router)
api_router.include_router(queries.router)
