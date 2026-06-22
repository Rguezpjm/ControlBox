"""Shared mysql/mysqldump CLI argument helpers."""

from __future__ import annotations


def mysql_connection_args(host: str, port: int, user: str, password: str) -> list[str]:
    """Build mysql client args with SSL disabled for local/docker MySQL."""
    return [
        f"-h{host}",
        f"-P{port}",
        f"-u{user}",
        f"-p{password}",
        "--ssl-mode=DISABLED",
    ]
