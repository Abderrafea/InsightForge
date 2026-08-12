from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalDatabaseCredentials:
    host: str
    port: int
    database_name: str
    username: str
    password: str
    ssl_mode: str
