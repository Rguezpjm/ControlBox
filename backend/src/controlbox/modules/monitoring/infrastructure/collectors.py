import asyncio
import json
import re
import time
from datetime import datetime, timezone
from uuid import UUID

import psutil

from controlbox.config.settings import Settings
from controlbox.modules.monitoring.domain.entities import (
    DatabaseMetrics,
    DockerContainerMetrics,
    HostMetrics,
    SupabaseMetrics,
    WebsiteMetrics,
)
from controlbox.modules.monitoring.infrastructure.host_system_metrics import (
    network_rates_mbps,
    read_cpu_percent,
    read_disk_usage,
    read_memory_percent,
    read_uptime_seconds,
    resolve_disk_path,
    resolve_proc_path,
)
from controlbox.shared.application.unit_of_work import UnitOfWork
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env


class HostMetricsCollector:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings
        self._proc_path = resolve_proc_path(settings.host_proc_path if settings else "")
        self._disk_path = resolve_disk_path(
            settings.host_root_path if settings else "",
            settings.controlbox_data_dir if settings else "/var/lib/controlbox",
        )
        self._last_cpu: tuple[int, int, float] | None = None
        self._last_net: tuple[int, int, float] | None = None

    async def collect(self) -> HostMetrics:
        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> HostMetrics:
        if str(self._proc_path) != "/proc":
            return self._collect_from_proc()
        return self._collect_from_psutil()

    def _collect_from_proc(self) -> HostMetrics:
        cpu, self._last_cpu = read_cpu_percent(self._proc_path, self._last_cpu)
        mem_pct, mem_used_mb, mem_total_mb = read_memory_percent(self._proc_path)
        disk_pct, disk_used_gb, disk_total_gb = read_disk_usage(self._disk_path)
        in_mbps, out_mbps, self._last_net = network_rates_mbps(self._proc_path, self._last_net)
        uptime = read_uptime_seconds(self._proc_path)

        return HostMetrics(
            cpu_percent=round(cpu, 2),
            memory_percent=round(mem_pct, 2),
            memory_used_mb=round(mem_used_mb, 1),
            memory_total_mb=round(mem_total_mb, 1),
            disk_percent=round(disk_pct, 2),
            disk_used_gb=round(disk_used_gb, 2),
            disk_total_gb=round(disk_total_gb, 2),
            network_in_mbps=round(in_mbps, 2),
            network_out_mbps=round(out_mbps, 2),
            uptime_seconds=uptime,
        )

    def _collect_from_psutil(self) -> HostMetrics:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(self._disk_path)
        net = psutil.net_io_counters()

        in_mbps = 0.0
        out_mbps = 0.0
        now = time.time()
        if net and self._last_net:
            dt = max(now - self._last_net[2], 0.001)
            in_mbps = max(0.0, ((net.bytes_recv - self._last_net[0]) * 8) / (dt * 1_000_000))
            out_mbps = max(0.0, ((net.bytes_sent - self._last_net[1]) * 8) / (dt * 1_000_000))
        if net:
            self._last_net = (net.bytes_recv, net.bytes_sent, now)

        boot = psutil.boot_time()
        uptime = int(now - boot)

        return HostMetrics(
            cpu_percent=round(cpu, 2),
            memory_percent=round(mem.percent, 2),
            memory_used_mb=round(mem.used / (1024 * 1024), 1),
            memory_total_mb=round(mem.total / (1024 * 1024), 1),
            disk_percent=round(disk.percent, 2),
            disk_used_gb=round(disk.used / (1024 ** 3), 2),
            disk_total_gb=round(disk.total / (1024 ** 3), 2),
            network_in_mbps=round(in_mbps, 2),
            network_out_mbps=round(out_mbps, 2),
            uptime_seconds=uptime,
        )


class DockerMetricsCollector:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._use_docker = settings.monitoring_use_docker

    async def collect(self, name_filter: set[str] | None = None) -> list[DockerContainerMetrics]:
        if not self._use_docker:
            return []
        try:
            return await asyncio.to_thread(self._collect_sync, name_filter)
        except Exception:
            return []

    def _collect_sync(self, name_filter: set[str] | None) -> list[DockerContainerMetrics]:
        proc = __import__("subprocess").run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=15,
            env=docker_subprocess_env(self._settings),
        )
        if proc.returncode != 0:
            return []

        if name_filter is not None and not name_filter:
            return []

        containers: list[DockerContainerMetrics] = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue

            name = row.get("Name", "")
            if name_filter is not None and name not in name_filter:
                continue

            cpu = self._parse_percent(row.get("CPUPerc", "0%"))
            mem_used, mem_limit = self._parse_mem(row.get("MemUsage", "0B / 0B"))
            net_in, net_out = self._parse_net(row.get("NetIO", "0B / 0B"))
            mem_pct = (mem_used / mem_limit * 100) if mem_limit > 0 else 0

            containers.append(
                DockerContainerMetrics(
                    name=name,
                    container_id=row.get("ID", "")[:12],
                    status="running",
                    cpu_percent=round(cpu, 2),
                    memory_percent=round(mem_pct, 2),
                    memory_used_mb=round(mem_used, 1),
                    memory_limit_mb=round(mem_limit, 1),
                    network_in_mb=round(net_in, 2),
                    network_out_mb=round(net_out, 2),
                )
            )
        return containers

    def _parse_percent(self, value: str) -> float:
        return float(value.replace("%", "").strip() or 0)

    def _parse_mem(self, value: str) -> tuple[float, float]:
        parts = value.split("/")
        if len(parts) != 2:
            return 0.0, 0.0
        return self._to_mb(parts[0].strip()), self._to_mb(parts[1].strip())

    def _parse_net(self, value: str) -> tuple[float, float]:
        parts = value.split("/")
        if len(parts) != 2:
            return 0.0, 0.0
        return self._to_mb(parts[0].strip()), self._to_mb(parts[1].strip())

    def _to_mb(self, value: str) -> float:
        value = value.strip().upper()
        match = re.match(r"([\d.]+)\s*([KMGT]?i?B)", value)
        if not match:
            return 0.0
        num = float(match.group(1))
        unit = match.group(2)
        multipliers = {
            "B": 1 / (1024 * 1024),
            "KB": 1 / 1024,
            "KIB": 1 / 1024,
            "MB": 1,
            "MIB": 1,
            "GB": 1024,
            "GIB": 1024,
            "TB": 1024 * 1024,
            "TIB": 1024 * 1024,
        }
        return num * multipliers.get(unit, 1)


class TenantMetricsCollector:
    def __init__(self, settings: Settings) -> None:
        self._docker = DockerMetricsCollector(settings)

    @staticmethod
    def _runtime_status(stored_status: str, has_container: bool, container_running: bool) -> str:
        if stored_status == "error":
            return "error"
        if has_container:
            return "running" if container_running else "stopped"
        return stored_status

    @staticmethod
    def _combine_container_stats(
        docker_by_name: dict[str, DockerContainerMetrics],
        *names: str | None,
    ) -> DockerContainerMetrics | None:
        stats = [docker_by_name[name] for name in names if name and name in docker_by_name]
        if not stats:
            return None
        return DockerContainerMetrics(
            name=stats[0].name,
            container_id=stats[0].container_id,
            status=stats[0].status,
            cpu_percent=max(s.cpu_percent for s in stats),
            memory_percent=max(s.memory_percent for s in stats),
            memory_used_mb=max(s.memory_used_mb for s in stats),
            memory_limit_mb=max(s.memory_limit_mb for s in stats),
            network_in_mb=sum(s.network_in_mb for s in stats),
            network_out_mb=sum(s.network_out_mb for s in stats),
        )

    async def collect(self, uow: UnitOfWork, tenant_id: UUID) -> tuple[
        list[DatabaseMetrics],
        list[SupabaseMetrics],
        list[WebsiteMetrics],
        list[DockerContainerMetrics],
    ]:
        databases = await uow.managed_databases.list_by_tenant(tenant_id)
        projects = await uow.supabase_projects.list_by_tenant(tenant_id)
        websites = await uow.websites.list_by_tenant(tenant_id)
        wordpress_sites = await uow.wordpress_sites.list_by_tenant(tenant_id, 500, 0)

        db_metrics = [
            DatabaseMetrics(
                id=str(db.id),
                name=db.name,
                engine=db.engine.value,
                status=db.status.value,
                size_mb=db.size_mb,
                connections=min(db.max_connections, max(1, db.size_mb // 10)),
            )
            for db in databases
        ]

        supabase_metrics = [
            SupabaseMetrics(
                id=str(p.id),
                name=p.name,
                status=p.status.value,
                database_size_mb=p.database_size_mb,
                storage_used_mb=p.storage_used_mb,
                requests_count=p.requests_count,
            )
            for p in projects
        ]

        container_names: set[str] = set()
        for site in websites:
            if site.container_name:
                container_names.add(site.container_name)
        for wp in wordpress_sites:
            for name in (wp.nginx_container_name, wp.php_container_name):
                if name:
                    container_names.add(name)

        docker_all = await self._docker.collect(container_names)
        docker_by_name = {c.name: c for c in docker_all}

        website_metrics: list[WebsiteMetrics] = []
        for site in websites:
            docker_stat = docker_by_name.get(site.container_name or "")
            status = self._runtime_status(
                site.status.value,
                bool(site.container_name),
                bool(docker_stat),
            )
            website_metrics.append(
                WebsiteMetrics(
                    id=str(site.id),
                    name=site.name,
                    domain=site.domain,
                    status=status,
                    cpu_percent=docker_stat.cpu_percent if docker_stat else 0.0,
                    memory_percent=docker_stat.memory_percent if docker_stat else 0.0,
                    disk_used_mb=site.disk_used_mb,
                    disk_limit_mb=site.disk_limit_mb,
                    site_type="website",
                    created_at=site.created_at,
                )
            )

        for wp in wordpress_sites:
            docker_stat = self._combine_container_stats(
                docker_by_name,
                wp.nginx_container_name,
                wp.php_container_name,
            )
            has_container = bool(wp.nginx_container_name or wp.php_container_name)
            status = self._runtime_status(
                wp.status.value,
                has_container,
                bool(docker_stat),
            )
            website_metrics.append(
                WebsiteMetrics(
                    id=str(wp.id),
                    name=wp.name,
                    domain=wp.domain,
                    status=status,
                    cpu_percent=docker_stat.cpu_percent if docker_stat else 0.0,
                    memory_percent=docker_stat.memory_percent if docker_stat else 0.0,
                    disk_used_mb=wp.disk_used_mb,
                    disk_limit_mb=0,
                    site_type="wordpress",
                    created_at=wp.created_at,
                )
            )

        website_metrics.sort(
            key=lambda item: item.created_at or datetime.fromtimestamp(0, tz=timezone.utc),
            reverse=True,
        )

        return db_metrics, supabase_metrics, website_metrics, docker_all