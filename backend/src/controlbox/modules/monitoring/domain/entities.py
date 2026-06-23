from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MetricPoint:
    timestamp: datetime
    value: float


@dataclass
class HostMetrics:
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    disk_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    network_in_mbps: float = 0.0
    network_out_mbps: float = 0.0
    uptime_seconds: int = 0


@dataclass
class DockerContainerMetrics:
    name: str
    container_id: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_limit_mb: float
    network_in_mb: float
    network_out_mb: float


@dataclass
class DatabaseMetrics:
    id: str
    name: str
    engine: str
    status: str
    size_mb: int
    connections: int
    cpu_percent: float = 0.0


@dataclass
class SupabaseMetrics:
    id: str
    name: str
    status: str
    database_size_mb: int
    storage_used_mb: int
    requests_count: int


@dataclass
class WebsiteMetrics:
    id: str
    name: str
    domain: str
    status: str
    cpu_percent: float
    memory_percent: float
    disk_used_mb: int
    disk_limit_mb: int
    site_type: str = "website"
    created_at: datetime | None = None


@dataclass
class ServiceHealth:
    name: str
    status: str
    latency_ms: float | None = None


@dataclass
class MonitoringSnapshot:
    host: HostMetrics = field(default_factory=HostMetrics)
    docker: list[DockerContainerMetrics] = field(default_factory=list)
    databases: list[DatabaseMetrics] = field(default_factory=list)
    supabase: list[SupabaseMetrics] = field(default_factory=list)
    websites: list[WebsiteMetrics] = field(default_factory=list)
    services: list[ServiceHealth] = field(default_factory=list)
    collected_at: datetime | None = None
