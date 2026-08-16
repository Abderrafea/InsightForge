from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import AgentWorkflow
from app.agent.service import AgentService
from app.config import Settings, get_settings
from app.core.security import CredentialCipher
from app.database.app_database import get_db_session
from app.database.connection_manager import ExternalDatabaseConnectionManager
from app.database.schema_inspector import PostgreSQLSchemaInspector
from app.llm.base import LLMProvider
from app.llm.factory import LLMFactory
from app.query.executor import SafeQueryExecutor
from app.query.policy import QueryPolicy
from app.query.service import SafeQueryService
from app.query.validator import SQLValidator
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.database_connection_repository import DatabaseConnectionRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.query_execution_repository import QueryExecutionRepository
from app.repositories.schema_cache_repository import SchemaCacheRepository
from app.repositories.session_repository import SessionRepository
from app.services.dashboard_service import DashboardService
from app.services.database_connection_service import DatabaseConnectionService
from app.services.message_service import MessageService
from app.services.schema_inspection_service import SchemaInspectionService
from app.services.session_service import SessionService

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_credential_cipher(settings: Annotated[Settings, Depends(get_settings)]) -> CredentialCipher:
    return CredentialCipher(settings.secret_encryption_key.get_secret_value())


def get_external_database_manager(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ExternalDatabaseConnectionManager:
    return ExternalDatabaseConnectionManager(
        connect_timeout_seconds=settings.external_db_connect_timeout_seconds
    )


def get_schema_inspector() -> PostgreSQLSchemaInspector:
    return PostgreSQLSchemaInspector()


def get_query_policy(
    settings: Annotated[Settings, Depends(get_settings)],
) -> QueryPolicy:
    return QueryPolicy.from_settings(settings)


def get_sql_validator(
    policy: Annotated[QueryPolicy, Depends(get_query_policy)],
) -> SQLValidator:
    return SQLValidator(policy)


def get_safe_query_executor(
    manager: Annotated[ExternalDatabaseConnectionManager, Depends(get_external_database_manager)],
    cipher: Annotated[CredentialCipher, Depends(get_credential_cipher)],
    policy: Annotated[QueryPolicy, Depends(get_query_policy)],
) -> SafeQueryExecutor:
    return SafeQueryExecutor(manager, cipher, policy)


def get_session_service(db: DatabaseSession) -> SessionService:
    return SessionService(
        db,
        SessionRepository(db),
        DatabaseConnectionRepository(db),
    )


def get_message_service(db: DatabaseSession) -> MessageService:
    return MessageService(db, SessionRepository(db), MessageRepository(db))


def get_database_connection_service(
    db: DatabaseSession,
    manager: Annotated[ExternalDatabaseConnectionManager, Depends(get_external_database_manager)],
    cipher: Annotated[CredentialCipher, Depends(get_credential_cipher)],
) -> DatabaseConnectionService:
    return DatabaseConnectionService(db, DatabaseConnectionRepository(db), manager, cipher)


def get_schema_inspection_service(
    db: DatabaseSession,
    manager: Annotated[ExternalDatabaseConnectionManager, Depends(get_external_database_manager)],
    inspector: Annotated[PostgreSQLSchemaInspector, Depends(get_schema_inspector)],
    cipher: Annotated[CredentialCipher, Depends(get_credential_cipher)],
) -> SchemaInspectionService:
    return SchemaInspectionService(
        db,
        DatabaseConnectionRepository(db),
        SchemaCacheRepository(db),
        manager,
        inspector,
        cipher,
    )


def get_safe_query_service(
    db: DatabaseSession,
    schema_service: Annotated[SchemaInspectionService, Depends(get_schema_inspection_service)],
    validator: Annotated[SQLValidator, Depends(get_sql_validator)],
    executor: Annotated[SafeQueryExecutor, Depends(get_safe_query_executor)],
) -> SafeQueryService:
    return SafeQueryService(
        db,
        DatabaseConnectionRepository(db),
        SessionRepository(db),
        QueryExecutionRepository(db),
        schema_service,
        validator,
        executor,
    )


def get_dashboard_service(
    db: DatabaseSession,
    query_service: Annotated[SafeQueryService, Depends(get_safe_query_service)],
) -> DashboardService:
    return DashboardService(
        SessionRepository(db),
        DashboardRepository(db),
        query_service,
    )


def get_llm_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMProvider:
    return LLMFactory.create(settings)


def get_agent_workflow(
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
    schema_service: Annotated[SchemaInspectionService, Depends(get_schema_inspection_service)],
    query_service: Annotated[SafeQueryService, Depends(get_safe_query_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentWorkflow:
    return AgentWorkflow(provider, schema_service, query_service, settings)


def get_agent_service(
    db: DatabaseSession,
    workflow: Annotated[AgentWorkflow, Depends(get_agent_workflow)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentService:
    return AgentService(
        db,
        SessionRepository(db),
        MessageRepository(db),
        DashboardRepository(db),
        AgentRunRepository(db),
        workflow,
        settings.agent_max_context_messages,
    )
