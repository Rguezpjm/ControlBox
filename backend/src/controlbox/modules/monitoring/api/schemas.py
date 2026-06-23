from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MetricPointSchema(BaseModel):
    timestamp: datetime
    value: float


class HostMetricsSchema(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    network_in_mbps: float
    network_out_mbps: float
    uptime_seconds: int


class DockerContainerSchema(BaseModel):
    name: str
    container_id: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_limit_mb: float
    network_in_mb: float
    network_out_mb: float


class DatabaseMetricSchema(BaseModel):
    id: str
    name: str
    engine: str
    status: str
    size_mb: int
    connections: int
    cpu_percent: float = 0


class SupabaseMetricSchema(BaseModel):
    id: str
    name: str
    status: str
    database_size_mb: int
    storage_used_mb: int
    requests_count: int


class WebsiteMetricSchema(BaseModel):
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


class ServiceHealthSchema(BaseModel):
    name: str
    status: str
    latency_ms: float | None = None


class MonitoringOverviewSchema(BaseModel):
    host: HostMetricsSchema
    docker: list[DockerContainerSchema]
    databases: list[DatabaseMetricSchema]
    supabase: list[SupabaseMetricSchema]
    websites: list[WebsiteMetricSchema]
    services: list[ServiceHealthSchema]
    collected_at: datetime | None


class MetricHistorySchema(BaseModel):
    metric: str
    points: list[MetricPointSchema]


class MonitoringHistorySchema(BaseModel):
    cpu: list[MetricPointSchema]
    memory: list[MetricPointSchema]
    disk: list[MetricPointSchema]
    network_in: list[MetricPointSchema]
    network_out: list[MetricPointSchema]
