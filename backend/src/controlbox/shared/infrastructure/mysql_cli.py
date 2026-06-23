"""Shared mysql/mysqldump CLI argument helpers."""

from __future__ import annotations

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Prefer TCP inside Docker; localhost uses a Unix socket with a separate auth entry.
_CONTAINER_EXEC_HOST = "127.0.0.1"


def mysql_exec_password_env(password: str) -> dict[str, str]:
    """Pass the password via env to avoid shell/CLI edge cases with -p."""
    return {"MYSQL_PWD": password}


def mysql_connection_args(
    host: str,
    port: int,
    user: str,
    password: str,
    *,
    password_via_env: bool = False,
) -> list[str]:
    """Build mysql client args compatible with MySQL 8+ and MariaDB CLIs."""
    args = [
        f"-h{host}",
        f"-P{port}",
        f"-u{user}",
    ]
    if not password_via_env:
        args.append(f"-p{password}")
    host_norm = host.strip().lower()
    if host_norm in _LOCAL_HOSTS:
        return args
    # MySQL 8+ rejects MariaDB's --skip-ssl; disable optional TLS on the Docker network.
    args.append("--ssl-mode=DISABLED")
    return args


def mysql_container_connection_args(
    port: int,
    user: str,
    password: str,
    *,
    password_via_env: bool = True,
) -> list[str]:
    """Connection args for mysql CLI executed inside the platform MySQL container."""
    return mysql_connection_args(
        _CONTAINER_EXEC_HOST,
        port,
        user,
        password,
        password_via_env=password_via_env,
    )
