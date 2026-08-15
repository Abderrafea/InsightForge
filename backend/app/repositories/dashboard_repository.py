from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard import Dashboard, DashboardVersion
from app.schemas.dashboard import DashboardConfig


class DashboardRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_for_session(self, session_id: UUID) -> Dashboard | None:
        result = await self._db.scalars(select(Dashboard).where(Dashboard.session_id == session_id))
        return result.one_or_none()

    async def upsert_versioned(
        self,
        session_id: UUID,
        config: DashboardConfig,
        *,
        created_by_message_id: UUID | None = None,
    ) -> tuple[Dashboard, DashboardVersion]:
        dashboard = await self.get_for_session(session_id)
        if dashboard is None:
            dashboard = Dashboard(
                session_id=session_id,
                title=config.title,
                config_json=config.model_dump(mode="json"),
                current_version=1,
                last_modified_by_message_id=created_by_message_id,
            )
            self._db.add(dashboard)
            await self._db.flush()
        else:
            dashboard.title = config.title
            dashboard.config_json = config.model_dump(mode="json")
            dashboard.current_version += 1
            dashboard.last_modified_by_message_id = created_by_message_id

        version = DashboardVersion(
            dashboard_id=dashboard.id,
            version_number=dashboard.current_version,
            config_json=config.model_dump(mode="json"),
            created_by_message_id=created_by_message_id,
        )
        self._db.add(version)
        await self._db.flush()
        return dashboard, version

    async def list_versions(self, dashboard_id: UUID) -> list[DashboardVersion]:
        result = await self._db.scalars(
            select(DashboardVersion)
            .where(DashboardVersion.dashboard_id == dashboard_id)
            .order_by(DashboardVersion.version_number.desc())
        )
        return list(result)
