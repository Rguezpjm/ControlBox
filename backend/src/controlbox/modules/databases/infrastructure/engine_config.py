from dataclasses import dataclass

from controlbox.config.settings import Settings
from controlbox.modules.databases.domain.entities import DatabaseEngineType


@dataclass(frozen=True)
class EngineConnection:
    host: str
    port: int
    admin_user: str
    admin_password: str


class EngineConfigResolver:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def resolve(self, engine: DatabaseEngineType) -> EngineConnection:
        if engine == DatabaseEngineType.MYSQL:
            return EngineConnection(
                host=self._settings.mysql_host,
                port=self._settings.mysql_port,
                admin_user=self._settings.mysql_admin_user,
                admin_password=self._settings.mysql_admin_password,
            )
        if engine == DatabaseEngineType.MARIADB:
            return EngineConnection(
                host=self._settings.mariadb_host,
                port=self._settings.mariadb_port,
                admin_user=self._settings.mariadb_admin_user,
                admin_password=self._settings.mariadb_admin_password,
            )
        if engine == DatabaseEngineType.POSTGRESQL:
            return EngineConnection(
                host=self._settings.managed_postgres_host,
                port=self._settings.managed_postgres_port,
                admin_user=self._settings.managed_postgres_admin_user,
                admin_password=self._settings.managed_postgres_admin_password,
            )
        if engine == DatabaseEngineType.MSSQL:
            return EngineConnection(
                host=self._settings.mssql_host,
                port=self._settings.mssql_port,
                admin_user=self._settings.mssql_admin_user,
                admin_password=self._settings.mssql_admin_password,
            )
        raise ValueError(f"Unknown engine: {engine}")
