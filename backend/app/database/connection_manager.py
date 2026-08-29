import asyncio
import ipaddress
import logging
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import certifi
import psycopg
from psycopg import AsyncConnection

from app.core.exceptions import ExternalDatabaseConnectionError
from app.database.external_database import ExternalDatabaseCredentials

logger = logging.getLogger(__name__)


class ExternalDatabaseConnectionManager:
    def __init__(
        self,
        connect_timeout_seconds: int = 5,
        allowed_targets: set[str] | None = None,
        require_tls: bool = False,
        public_only: bool = False,
    ) -> None:
        self._connect_timeout_seconds = connect_timeout_seconds
        self._allowed_targets = allowed_targets
        self._require_tls = require_tls
        self._public_only = public_only

    @asynccontextmanager
    async def connection(
        self, credentials: ExternalDatabaseCredentials
    ) -> AsyncIterator[AsyncConnection[tuple[object, ...]]]:
        target = f"{credentials.host.lower()}:{credentials.port}"
        if self._allowed_targets is not None and target not in self._allowed_targets:
            raise ExternalDatabaseConnectionError("This database host and port are not allowed")
        if self._require_tls and credentials.ssl_mode != "verify-full":
            raise ExternalDatabaseConnectionError(
                "Production database connections require verify-full TLS"
            )
        connection_options = {}
        checked_addresses: list[str | None] = [None]
        if credentials.ssl_mode in {"verify-full", "verify-ca"}:
            connection_options["sslrootcert"] = certifi.where()
        if self._public_only:
            if credentials.port not in {5432, 6543} or any(
                character in credentials.host for character in ",/\\ \t\r\n"
            ):
                raise ExternalDatabaseConnectionError(
                    "Use a public PostgreSQL host on port 5432 or 6543"
                )
            try:
                addresses = await asyncio.wait_for(
                    asyncio.get_running_loop().getaddrinfo(
                        credentials.host, credentials.port, type=socket.SOCK_STREAM
                    ),
                    timeout=self._connect_timeout_seconds,
                )
                ips = list(
                    dict.fromkeys(ipaddress.ip_address(address[4][0]) for address in addresses)
                )
            except (OSError, ValueError, TimeoutError) as exc:
                raise ExternalDatabaseConnectionError(
                    "The database hostname could not be resolved"
                ) from exc
            if not ips or any(
                not ip.is_global
                or (getattr(ip, "ipv4_mapped", None) is not None and not ip.ipv4_mapped.is_global)
                for ip in ips
            ):
                raise ExternalDatabaseConnectionError("Only public database addresses are allowed")
            # Keep resolver preference, and try the other address family before
            # additional addresses. IPv6-only hosting may require a DNS64 address.
            preferred = [ips[0]]
            alternate = next((ip for ip in ips if ip.version != ips[0].version), None)
            if alternate is not None:
                preferred.append(alternate)
            preferred.extend(ip for ip in ips if ip not in preferred)
            checked_addresses = [str(ip) for ip in preferred[:4]]
        try:
            for index, address in enumerate(checked_addresses):
                options = {**connection_options}
                if address is not None:
                    options["hostaddr"] = address
                try:
                    connection = await AsyncConnection.connect(
                        host=credentials.host,
                        port=credentials.port,
                        dbname=credentials.database_name,
                        user=credentials.username,
                        password=credentials.password,
                        sslmode=credentials.ssl_mode,
                        connect_timeout=self._connect_timeout_seconds,
                        autocommit=True,
                        **options,
                    )
                    break
                except (psycopg.errors.InvalidPassword, psycopg.errors.InvalidCatalogName):
                    raise
                except (psycopg.OperationalError, OSError, TimeoutError):
                    if index == len(checked_addresses) - 1:
                        raise
        except psycopg.errors.InvalidPassword as exc:
            raise ExternalDatabaseConnectionError(
                "Authentication failed. Check the database username and password."
            ) from exc
        except psycopg.errors.InvalidCatalogName as exc:
            raise ExternalDatabaseConnectionError(
                "The requested database does not exist or is not accessible."
            ) from exc
        except (psycopg.OperationalError, OSError, TimeoutError) as exc:
            message = str(exc).lower()
            reason = next(
                (
                    label
                    for fragment, label in [
                        ("certificate verify failed", "tls_certificate"),
                        ("root certificate", "tls_ca_file"),
                        ("network is unreachable", "network_unreachable"),
                        ("connection refused", "connection_refused"),
                        ("timeout", "timeout"),
                        ("timed out", "timeout"),
                        ("channel binding", "channel_binding"),
                        ("endpoint", "endpoint_routing"),
                    ]
                    if fragment in message
                ),
                "transport",
            )
            logger.warning("External database connection failed (%s)", reason)
            raise ExternalDatabaseConnectionError(
                "The database could not be reached. Check the host, port, SSL mode, "
                "and network access."
            ) from exc
        except psycopg.DatabaseError as exc:
            raise ExternalDatabaseConnectionError(
                "The database rejected the connection request."
            ) from exc

        try:
            yield connection
        finally:
            if not connection.closed:
                await connection.close()

    async def test_connection(self, credentials: ExternalDatabaseCredentials) -> None:
        try:
            async with self.connection(credentials) as connection:
                await connection.execute("SELECT 1")
        except ExternalDatabaseConnectionError:
            raise
        except psycopg.DatabaseError as exc:
            raise ExternalDatabaseConnectionError(
                "The database rejected the connection request."
            ) from exc
