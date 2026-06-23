"""Read/write /etc/controlbox/platform.env with Docker Compose–safe quoting."""

from __future__ import annotations

import re
from pathlib import Path

_ORPHAN_REDIS_LINE = re.compile(r"^[^=]*@redis:6379/\d+\s*$")


def format_env_line(key: str, value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", "")
        .replace("\n", "\\n")
    )
    return f'{key}="{escaped}"'


def parse_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        inner = value[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")
    return value


def read_env_key(env_file: Path, key: str) -> str | None:
    if not env_file.is_file():
        return None
    prefix = f"{key}="
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return parse_env_value(line[len(prefix) :])
    return None


def patch_env_key(env_file: Path, key: str, value: str) -> None:
    if not env_file.is_file():
        raise FileNotFoundError(f"platform.env not found: {env_file}")
    lines = env_file.read_text(encoding="utf-8").splitlines()
    new_line = format_env_line(key, value)
    found = False
    updated: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            if not found:
                updated.append(new_line)
                found = True
            continue
        updated.append(line)
    if not found:
        updated.append(new_line)
    env_file.write_text("\n".join(updated) + "\n", encoding="utf-8")


def repair_celery_redis_urls(env_file: Path) -> bool:
    """Fix broken CELERY_* lines and orphan fragments from unquoted Redis passwords."""
    if not env_file.is_file():
        return False

    lines = env_file.read_text(encoding="utf-8").splitlines()
    filtered = [line for line in lines if not _ORPHAN_REDIS_LINE.match(line.strip())]
    changed = len(filtered) != len(lines)

    if filtered != lines:
        env_file.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="utf-8")

    redis_pass = read_env_key(env_file, "REDIS_PASSWORD")
    if not redis_pass:
        return changed

    broker = f"redis://:{redis_pass}@redis:6379/1"
    backend = f"redis://:{redis_pass}@redis:6379/2"
    current_broker = read_env_key(env_file, "CELERY_BROKER_URL")
    current_backend = read_env_key(env_file, "CELERY_RESULT_BACKEND")

    if current_broker != broker or current_backend != backend:
        patch_env_key(env_file, "CELERY_BROKER_URL", broker)
        patch_env_key(env_file, "CELERY_RESULT_BACKEND", backend)
        changed = True

    return changed


def patch_env_keys(env_file: Path, values: dict[str, str]) -> None:
    for key, value in values.items():
        patch_env_key(env_file, key, value)
