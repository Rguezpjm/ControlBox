import os
import re

from controlbox.config.settings import Settings

_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


def docker_subprocess_env(settings: Settings | None = None) -> dict[str, str]:
    """Environment for docker CLI subprocess calls (uses socket proxy when configured)."""
    env = os.environ.copy()
    host = settings.docker_host if settings else os.environ.get("DOCKER_HOST", "")
    if host:
        env["DOCKER_HOST"] = host
    return env


def validate_container_name(name: str) -> str:
    if not _CONTAINER_NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid container name: {name!r}")
    return name
