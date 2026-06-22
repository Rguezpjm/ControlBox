"""Read and parse site access logs with IP geolocation."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx

from controlbox.config.settings import Settings
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env

logger = logging.getLogger("controlbox.site_logs")

ACCESS_LOG_RE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
    r'"(?P<method>\S+) (?P<path>\S+) (?P<protocol>[^"]+)" '
    r'(?P<status>\d+) (?P<bytes>\S+) "(?P<referer>[^"]*)" "(?P<ua>[^"]*)"'
)

CONTAINER_LOG_PATHS = (
    "/var/log/nginx/access.log",
    "/var/log/apache2/access.log",
    "/var/log/app/access.log",
    "/var/log/httpd/access_log",
)

ERROR_LOG_PATHS = (
    "/var/log/nginx/error.log",
    "/var/log/apache2/error.log",
    "/var/log/app/error.log",
    "/var/log/httpd/error_log",
)


@dataclass(frozen=True)
class AccessLogEntry:
    raw: str
    ip: str
    timestamp: str
    method: str
    path: str
    protocol: str
    status: int
    bytes: str
    user_agent: str
    ip_location: str | None = None


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return not (addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local)
    except ValueError:
        return False


@lru_cache(maxsize=4096)
def _lookup_ip_location_sync(ip: str) -> str | None:
    if not _is_public_ip(ip):
        return "Local / private"
    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,city,regionName,isp"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("status") != "success":
                return None
            city = data.get("city") or ""
            region = data.get("regionName") or ""
            country = data.get("country") or ""
            parts = [p for p in (city, region, country) if p]
            location = ", ".join(dict.fromkeys(parts))
            isp = data.get("isp")
            if isp and location:
                return f"{location} ({isp})"
            return location or isp
    except Exception:
        logger.debug("IP lookup failed for %s", ip, exc_info=True)
        return None


async def resolve_ip_locations(entries: list[AccessLogEntry]) -> list[AccessLogEntry]:
    unique_ips = {e.ip for e in entries}
    locations: dict[str, str | None] = {}
    for ip in unique_ips:
        locations[ip] = await asyncio.to_thread(_lookup_ip_location_sync, ip)
    return [
        AccessLogEntry(
            raw=e.raw,
            ip=e.ip,
            timestamp=e.timestamp,
            method=e.method,
            path=e.path,
            protocol=e.protocol,
            status=e.status,
            bytes=e.bytes,
            user_agent=e.user_agent,
            ip_location=locations.get(e.ip),
        )
        for e in entries
    ]


def parse_access_log_lines(lines: list[str]) -> list[AccessLogEntry]:
    entries: list[AccessLogEntry] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = ACCESS_LOG_RE.match(line)
        if not match:
            entries.append(
                AccessLogEntry(
                    raw=line,
                    ip="",
                    timestamp="",
                    method="",
                    path="",
                    protocol="",
                    status=0,
                    bytes="",
                    user_agent=line,
                )
            )
            continue
        entries.append(
            AccessLogEntry(
                raw=line,
                ip=match.group("ip"),
                timestamp=match.group("time"),
                method=match.group("method"),
                path=match.group("path"),
                protocol=match.group("protocol"),
                status=int(match.group("status")),
                bytes=match.group("bytes"),
                user_agent=match.group("ua"),
            )
        )
    return entries


def _tail_file(path: Path, limit: int) -> list[str]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-limit:] if limit > 0 else lines
    except OSError:
        return []


class SiteLogReader:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _docker_tail(self, container_name: str, log_path: str, limit: int) -> str:
        cmd = ["docker", "exec", container_name, "sh", "-c", f"tail -n {limit} {log_path} 2>/dev/null"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=docker_subprocess_env(self._settings),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        if proc.returncode != 0:
            return ""
        return stdout.decode("utf-8", errors="replace")

    async def read_access_logs(
        self,
        *,
        site_path: Path,
        container_name: str | None,
        limit: int = 100,
        with_geo: bool = True,
    ) -> tuple[str, list[AccessLogEntry]]:
        host_log = site_path / "logs" / "access.log"
        if host_log.is_file():
            lines = _tail_file(host_log, limit)
            if lines:
                entries = parse_access_log_lines(lines)
                if with_geo:
                    entries = await resolve_ip_locations(entries)
                return str(host_log), entries

        if container_name:
            for log_path in CONTAINER_LOG_PATHS:
                text = await self._docker_tail(container_name, log_path, limit)
                if text.strip():
                    entries = parse_access_log_lines(text.splitlines())
                    if with_geo:
                        entries = await resolve_ip_locations(entries)
                    return log_path, entries

        return "", []

    async def read_error_log(
        self,
        *,
        site_path: Path,
        container_name: str | None,
        limit: int = 100,
    ) -> tuple[str, str]:
        host_log = site_path / "logs" / "error.log"
        if host_log.is_file():
            lines = _tail_file(host_log, limit)
            if lines:
                return str(host_log), "\n".join(lines)

        if container_name:
            for log_path in ERROR_LOG_PATHS:
                text = await self._docker_tail(container_name, log_path, limit)
                if text.strip():
                    return log_path, text.strip()

        return "", ""
