"""Helpers to run database engine CLIs locally or via docker exec."""

from __future__ import annotations

import asyncio

from controlbox.config.settings import Settings, get_settings
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env, resolve_docker_host


async def spawn(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    input_data: bytes | None = None,
) -> tuple[int, bytes, bytes]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if input_data is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate(input=input_data)
        return proc.returncode or 0, stdout or b"", stderr or b""
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Ejecutable no encontrado: {cmd[0]!r}. "
            "Actualice el panel (controlbox update) o ejecute controlbox repair."
        ) from exc


def docker_enabled(settings: Settings | None = None) -> bool:
    return bool(resolve_docker_host(settings or get_settings()))


def docker_env(settings: Settings | None = None) -> dict[str, str]:
    return docker_subprocess_env(settings or get_settings())


async def docker_exec(
    container: str,
    cmd: list[str],
    *,
    settings: Settings | None = None,
    env: dict[str, str] | None = None,
    input_data: bytes | None = None,
) -> tuple[int, bytes, bytes]:
    full_cmd = ["docker", "exec", "-i"]
    if env:
        for key, value in env.items():
            full_cmd.extend(["-e", f"{key}={value}"])
    full_cmd.append(container)
    full_cmd.extend(cmd)
    merged_env = docker_env(settings)
    if env:
        merged_env = {**merged_env, **env}
    return await spawn(full_cmd, env=merged_env, input_data=input_data)
