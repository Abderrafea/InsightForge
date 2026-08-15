from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun, AgentRunStatus


class AgentRunRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, session_id: UUID, provider: str, model: str) -> AgentRun:
        run = AgentRun(
            session_id=session_id,
            status=AgentRunStatus.RUNNING,
            provider=provider,
            model=model,
        )
        self._db.add(run)
        await self._db.flush()
        return run

    async def get(self, run_id: UUID) -> AgentRun | None:
        return await self._db.get(AgentRun, run_id)
