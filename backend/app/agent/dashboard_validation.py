from app.agent.exceptions import DashboardValidationError
from app.agent.models import GeneratedQuery
from app.query.models import QueryResult
from app.schemas.dashboard import DashboardConfig, WidgetType


def validate_generated_dashboard(
    dashboard: DashboardConfig,
    generated_queries: list[GeneratedQuery],
    query_results: dict[str, QueryResult],
) -> None:
    expected_queries = {query.id: query for query in generated_queries}
    configured_queries = {query.id: query for query in dashboard.queries}
    if configured_queries.keys() != expected_queries.keys():
        raise DashboardValidationError("Dashboard queries do not match the validated query plan")
    for query_id, configured in configured_queries.items():
        expected = expected_queries[query_id]
        if configured.sql.strip() != expected.sql.strip():
            raise DashboardValidationError("Dashboard SQL differs from the validated SQL")

    for widget in dashboard.widgets:
        if widget.query_id is None or widget.query_id not in query_results:
            raise DashboardValidationError(f"Widget '{widget.id}' has no query result")
        fields = set(query_results[widget.query_id].columns)
        required_fields: set[str] = set()
        if widget.value_field:
            required_fields.add(widget.value_field)
        if widget.x_field:
            required_fields.add(widget.x_field)
        required_fields.update(widget.y_fields)
        missing = required_fields - fields
        if missing:
            raise DashboardValidationError(
                f"Widget '{widget.id}' references unavailable result fields"
            )
        if widget.type == WidgetType.TABLE and not fields:
            raise DashboardValidationError(f"Table widget '{widget.id}' has no result fields")
