from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import get_dashboard_service
from app.schemas.dashboard import DashboardDataRead, DashboardRead
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/sessions/{session_id}/dashboard", tags=["dashboards"])
DashboardServiceDependency = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get("", response_model=DashboardDataRead)
async def get_dashboard(
    session_id: UUID,
    service: DashboardServiceDependency,
) -> DashboardDataRead:
    dashboard, query_results = await service.get_with_data(session_id)
    return DashboardDataRead(
        dashboard=DashboardRead.model_validate(dashboard),
        query_results=query_results,
    )
