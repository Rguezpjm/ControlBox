from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity


class WebsiteRuntime(StrEnum):
    HTML = "html"
    PHP = "php"
    NODEJS = "nodejs"
    PYTHON = "python"
    FLUTTER = "flutter"


class WebsiteStatus(StrEnum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DELETING = "deleting"


class SslStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    FAILED = "failed"


class DatabaseEngine(StrEnum):
    NONE = "none"
    MYSQL = "mysql"
    SUPABASE = "supabase"
    MSSQL = "mssql"


RUNTIME_VERSIONS: dict[WebsiteRuntime, list[str]] = {
    WebsiteRuntime.HTML: [],
    WebsiteRuntime.PHP: ["8.2", "8.3"],
    WebsiteRuntime.NODEJS: ["22"],
    WebsiteRuntime.PYTHON: ["3.13"],
    WebsiteRuntime.FLUTTER: ["3.44.2"],
}

DEFAULT_RUNTIME_VERSIONS: dict[WebsiteRuntime, str] = {
    WebsiteRuntime.HTML: "",
    WebsiteRuntime.PHP: "8.3",
    WebsiteRuntime.NODEJS: "22",
    WebsiteRuntime.PYTHON: "3.13",
    WebsiteRuntime.FLUTTER: "3.44.2",
}

RUNTIME_PORTS: dict[str, int] = {
    "html": 80,
    "php": 80,
    "nodejs": 3000,
    "python": 8000,
    "flutter": 80,
}


@dataclass
class Website(Entity):
    tenant_id: UUID | None = None
    owner_user_id: UUID | None = None
    name: str = ""
    domain: str = ""
    runtime: WebsiteRuntime = WebsiteRuntime.HTML
    runtime_version: str = ""
    status: WebsiteStatus = WebsiteStatus.PENDING
    container_id: str | None = None
    container_name: str | None = None
    document_root: str = ""
    ssl_enabled: bool = True
    ssl_status: SslStatus = SslStatus.PENDING
    database_engine: DatabaseEngine = DatabaseEngine.NONE
    database_config: dict[str, Any] = field(default_factory=dict)
    monitoring_enabled: bool = True
    logs_enabled: bool = True
    logs_path: str | None = None
    traefik_router: str | None = None
    port: int = 80
    disk_used_mb: int = 0
    disk_limit_mb: int = 5120
    settings: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def mark_provisioning(self) -> None:
        self.status = WebsiteStatus.PROVISIONING
        self.touch()

    def mark_running(self, container_id: str, container_name: str) -> None:
        self.status = WebsiteStatus.RUNNING
        self.container_id = container_id
        self.container_name = container_name
        self.error_message = None
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = WebsiteStatus.ERROR
        self.error_message = message
        self.touch()

    def mark_stopped(self) -> None:
        self.status = WebsiteStatus.STOPPED
        self.touch()

    def activate_ssl(self) -> None:
        self.ssl_status = SslStatus.ACTIVE
        self.ssl_enabled = True
        self.touch()
