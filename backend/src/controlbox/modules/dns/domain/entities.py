from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from controlbox.shared.domain.base import Entity


class DnsRecordType(StrEnum):
    A = "A"
    AAAA = "AAAA"
    TXT = "TXT"
    CNAME = "CNAME"
    MX = "MX"
    CAA = "CAA"
    NS = "NS"
    SRV = "SRV"


SUPPORTED_RECORD_TYPES = list(DnsRecordType)


class DnsZoneStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    DELETING = "deleting"


@dataclass
class DnsZone(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    status: DnsZoneStatus = DnsZoneStatus.PENDING
    serial: int = 1
    soa_email: str = "hostmaster"
    default_ttl: int = 3600
    record_count: int = 0
    nameservers: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def mark_active(self, record_count: int = 0) -> None:
        self.status = DnsZoneStatus.ACTIVE
        self.record_count = record_count
        self.error_message = None
        self.touch()

    def mark_error(self, message: str) -> None:
        self.status = DnsZoneStatus.ERROR
        self.error_message = message
        self.touch()

    def bump_serial(self) -> None:
        today = datetime.now().strftime("%Y%m%d")
        base = int(f"{today}01")
        if self.serial >= base:
            self.serial += 1
        else:
            self.serial = base
        self.touch()


@dataclass
class DnsRecord:
    name: str
    type: DnsRecordType
    content: str
    ttl: int = 3600
    priority: int | None = None
    disabled: bool = False

    @property
    def record_id(self) -> str:
        return f"{self.name}:{self.type.value}"


@dataclass
class DnsApiKey(Entity):
    tenant_id: UUID | None = None
    name: str = ""
    key_prefix: str = ""
    key_hash: str = ""
    is_active: bool = True
    scopes: list[str] = field(default_factory=lambda: ["dns.read", "dns.manage"])
    last_used_at: datetime | None = None

    def deactivate(self) -> None:
        self.is_active = False
        self.touch()

    def mark_used(self) -> None:
        self.last_used_at = datetime.now()
        self.touch()
