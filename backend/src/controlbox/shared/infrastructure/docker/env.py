import os
import re
import socket
from functools import lru_cache

from controlbox.config.settings import Settings

_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")
_TCP_DOCKER_HOST_RE = re.compile(r"^tcp://([^:/]+):(\d+)$")

_PROXY_HOST_FALLBACKS: dict[str, tuple[str, ...]] = {
    "docker-socket-proxy": ("docker-socket-proxy", "controlbox-docker-proxy"),
    "controlbox-docker-proxy": ("controlbox-docker-proxy", "docker-socket-proxy"),
}


def _host_resolves(hostname: str, port: int, timeout: float = 1.0) -> bool:
    try:
        socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        return True
    except OSError:
        return False


def _resolve_tcp_docker_host(host: str) -> str:
    match = _TCP_DOCKER_HOST_RE.match(host.strip())
    if not match:
        return host

    hostname, port_str = match.group(1), match.group(2)
    port = int(port_str)
    candidates = _PROXY_HOST_FALLBACKS.get(hostname, (hostname,))

    for candidate in candidates:
        if _host_resolves(candidate, port):
            return f"tcp://{candidate}:{port_str}"

    return host


@lru_cache(maxsize=1)
def _cached_resolved_docker_host(configured: str) -> str:
    if not configured:
        return ""
    if configured.startswith("tcp://"):
        return _resolve_tcp_docker_host(configured)
    return configured


def resolve_docker_host(settings: Settings | None = None) -> str:
    configured = settings.docker_host if settings else os.environ.get("DOCKER_HOST", "")
    if not configured:
        return ""
    return _cached_resolved_docker_host(configured)


def docker_subprocess_env(settings: Settings | None = None) -> dict[str, str]:
    """Environment for docker CLI subprocess calls (uses socket proxy when configured)."""
    env = os.environ.copy()
    host = resolve_docker_host(settings)
    if host:
        env["DOCKER_HOST"] = host
    return env


def docker_connectivity_hint(settings: Settings | None = None) -> str:
    configured = settings.docker_host if settings else os.environ.get("DOCKER_HOST", "")
    if not configured:
        return "Compruebe que Docker está en ejecución en el servidor."

    if "docker-socket-proxy" in configured or "controlbox-docker-proxy" in configured:
        return (
            "El proxy Docker del panel no está accesible. En el VPS ejecute: "
            "controlbox repair  (o: docker compose up -d docker-socket-proxy api worker)"
        )
    return f"No se pudo conectar a Docker en {configured}."


def validate_container_name(name: str) -> str:
    if not _CONTAINER_NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid container name: {name!r}")
    return name
