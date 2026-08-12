from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class SSLMode(StrEnum):
    DISABLE = "disable"
    ALLOW = "allow"
    PREFER = "prefer"
    REQUIRE = "require"
    VERIFY_CA = "verify-ca"
    VERIFY_FULL = "verify-full"


class DatabaseConnectionParameters(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65_535)
    database_name: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: SecretStr = Field(min_length=1, max_length=10_000)
    ssl_mode: SSLMode = SSLMode.PREFER

    @field_validator("host", "database_name", "username")
    @classmethod
    def must_be_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank")
        return cleaned


class DatabaseConnectionTest(DatabaseConnectionParameters):
    """Credentials used only for a transient connection test."""


class DatabaseConnectionCreate(DatabaseConnectionParameters):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Connection name must not be blank")
        return cleaned


class DatabaseConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    database_type: Literal["postgresql"]
    host: str
    port: int
    database_name: str
    username: str
    ssl_mode: SSLMode
    created_at: datetime
    updated_at: datetime


class ConnectionTestResult(BaseModel):
    success: Literal[True] = True
