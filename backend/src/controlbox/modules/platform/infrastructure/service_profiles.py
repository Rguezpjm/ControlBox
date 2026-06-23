"""Optional Docker Compose profiles — read/apply from the panel."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from controlbox.config.settings import Settings
from controlbox.modules.databases.domain.entities import DatabaseEngineType
from controlbox.modules.databases.infrastructure.engine_adapters import MySqlMariaAdapter
from controlbox.modules.databases.infrastructure.engine_config import EngineConfigResolver
from controlbox.modules.ftp.infrastructure.service_manager import FtpServiceManager
from controlbox.shared.infrastructure.compose_overrides import compose_override_files
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env
from controlbox.shared.infrastructure.platform_env_file import patch_env_key, repair_celery_redis_urls

logger = logging.getLogger("controlbox.platform.services")

SERVICE_CATALOG: tuple[dict[str, object], ...] = (
    {
        "id": "databases",
        "profile": "databases",
        "name": "MySQL",
        "category": "lnmp",
        "description": "Motor MySQL para Websites, WordPress y bases de datos gestionadas.",
        "containers": ("controlbox-mysql",),
        "requires": (),
    },
    {
        "id": "backups",
        "profile": "backups",
        "name": "MinIO (Backups)",
        "category": "lnmp",
        "description": "Almacenamiento S3-compatible para backups de sitios y bases de datos.",
        "containers": ("controlbox-minio",),
        "requires": (),
    },
    {
        "id": "monitoring",
        "profile": "monitoring",
        "name": "Monitoring",
        "category": "platform",
        "description": "Prometheus, Grafana, Loki y Promtail para métricas y logs.",
        "containers": (
            "controlbox-prometheus",
            "controlbox-grafana",
            "controlbox-loki",
            "controlbox-promtail",
        ),
        "requires": (),
    },
    {
        "id": "ftp",
        "profile": "ftp",
        "name": "FTP / SFTP",
        "category": "platform",
        "description": "Pure-FTPd y SFTP para transferencia de archivos de sitios.",
        "containers": ("controlbox-pureftpd", "controlbox-sftp"),
        "requires": (),
    },
    {
        "id": "supabase",
        "profile": "supabase",
        "name": "Supabase",
        "category": "platform",
        "description": "Stack Supabase self-hosted (Auth, REST, Realtime, Storage). Requiere MinIO.",
        "containers": ("controlbox-supabase-db", "controlbox-supabase-kong"),
        "requires": ("backups",),
    },
)

PROFILE_CONTAINER_CHECKS: dict[str, tuple[str, ...]] = {
    "databases": ("controlbox-mysql",),
    "backups": ("controlbox-minio",),
    "supabase": ("controlbox-supabase-db",),
    "monitoring": ("controlbox-prometheus",),
    "ftp": ("controlbox-pureftpd",),
}

SUPABASE_COMPOSE_SERVICES: tuple[str, ...] = (
    "minio",
    "supabase-db",
    "supabase-meta",
    "supabase-kong",
    "supabase-auth",
    "supabase-rest",
    "supabase-realtime",
    "supabase-storage",
    "supabase-studio",
)


@dataclass(frozen=True)
class ServiceProfileView:
    id: str
    profile: str
    name: str
    category: str
    description: str
    enabled: bool
    running: bool
    requires: tuple[str, ...]


@dataclass(frozen=True)
class ServicesOverview:
    can_manage: bool
    enabled_profiles: list[str]
    services: list[ServiceProfileView]
    message: str = ""


class ServiceProfilesManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _install_dir(self) -> Path:
        raw = self._settings.controlbox_install_dir
        if raw.startswith("/host/"):
            return Path(raw)
        return Path("/host/opt/controlbox")

    def _config_dir(self) -> Path:
        raw = self._settings.platform_config_dir
        if raw.startswith("/host/"):
            return Path(raw)
        return Path("/host/etc/controlbox")

    def _host_data_dir(self) -> Path:
        """Data directory path on the Docker host (for compose bind mounts)."""
        env_file = self._env_file()
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("CONTROLBOX_DATA_DIR="):
                    raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if raw.startswith("/host/root"):
                        return Path(raw.removeprefix("/host/root") or "/")
                    if raw and not raw.startswith("/host/"):
                        return Path(raw)
        raw = (self._settings.controlbox_data_dir or "/var/lib/controlbox").strip()
        if raw.startswith("/host/root"):
            return Path(raw.removeprefix("/host/root") or "/")
        if raw.startswith("/host/"):
            return Path("/var/lib/controlbox")
        return Path(raw)

    def _env_file(self) -> Path:
        return self._config_dir() / "platform.env"

    def _compose_base_cmd(self) -> list[str]:
        install_dir = self._install_dir()
        env_file = self._env_file()
        cmd = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(install_dir / "docker-compose.yml"),
        ]
        for path in compose_override_files(self._settings):
            cmd.extend(["-f", str(path)])
        return cmd

    def _read_enabled_profiles(self) -> list[str]:
        raw = ""
        env_file = self._env_file()
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("CONTROLBOX_ENABLED_PROFILES="):
                    raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if not raw.strip():
            raw = self._settings.controlbox_enabled_profiles or ""
        return [p.strip() for p in raw.replace(" ", "").split(",") if p.strip()]

    def _normalize_profiles(self, selected: list[str]) -> list[str]:
        allowed = {str(item["id"]) for item in SERVICE_CATALOG}
        profiles: list[str] = []
        for item in selected:
            key = item.strip().lower()
            if key in allowed and key not in profiles:
                profiles.append(key)
        if "supabase" in profiles and "backups" not in profiles:
            profiles.append("backups")
        return profiles

    def _write_profiles_to_env(self, profiles: list[str]) -> None:
        env_file = self._env_file()
        if not env_file.is_file():
            raise FileNotFoundError("platform.env not found on host")
        repair_celery_redis_urls(env_file)
        joined = ",".join(profiles) if profiles else "databases"
        patch_env_key(env_file, "CONTROLBOX_ENABLED_PROFILES", joined)

    def _prepare_env_for_compose(self) -> None:
        try:
            repair_celery_redis_urls(self._env_file())
        except OSError as exc:
            logger.warning("Could not repair platform.env before compose: %s", exc)

    async def _running_containers(self) -> set[str]:
        cmd = self._compose_base_cmd() + ["ps", "--format", "json"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=docker_subprocess_env(self._settings),
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        running: set[str] = set()
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = row.get("Name") or row.get("Service") or ""
            state = str(row.get("State", "")).lower()
            if name and state in {"running", "up"}:
                running.add(name)
        return set(running)

    async def get_overview(self) -> ServicesOverview:
        compose = self._install_dir() / "docker-compose.yml"
        env_file = self._env_file()
        can_manage = compose.is_file() and env_file.is_file()
        enabled = self._read_enabled_profiles()
        running: set[str] = set()
        if can_manage:
            try:
                running = await self._running_containers()
            except Exception as exc:
                logger.warning("Could not list containers: %s", exc)

        services: list[ServiceProfileView] = []
        for item in SERVICE_CATALOG:
            sid = str(item["id"])
            containers = tuple(str(c) for c in item["containers"])  # type: ignore[arg-type]
            requires = tuple(str(r) for r in item["requires"])  # type: ignore[arg-type]
            is_enabled = sid in enabled
            is_running = is_enabled and any(c in running for c in containers)
            services.append(
                ServiceProfileView(
                    id=sid,
                    profile=str(item["profile"]),
                    name=str(item["name"]),
                    category=str(item["category"]),
                    description=str(item["description"]),
                    enabled=is_enabled,
                    running=is_running,
                    requires=requires,
                )
            )

        message = ""
        if not can_manage:
            message = "Gestión de servicios no disponible desde este entorno (requiere instalación en VPS)."

        return ServicesOverview(
            can_manage=can_manage,
            enabled_profiles=enabled,
            services=services,
            message=message,
        )

    def _ensure_supabase_config(self) -> None:
        config_supabase = self._config_dir() / "supabase"
        kong = config_supabase / "kong.yml"
        if kong.is_file():
            return
        templates = self._install_dir() / "templates" / "supabase"
        if not templates.is_dir():
            logger.warning("Supabase templates not found at %s", templates)
            return
        config_supabase.mkdir(parents=True, exist_ok=True)
        for item in templates.iterdir():
            dest = config_supabase / item.name
            if item.is_file() and not dest.exists():
                dest.write_bytes(item.read_bytes())
        if not kong.is_file():
            logger.error("Supabase kong.yml missing after template copy")

    async def _profiles_missing_containers(self, profiles: list[str]) -> bool:
        try:
            running = await self._running_containers()
        except Exception as exc:
            logger.warning("Could not list containers for profile check: %s", exc)
            return True
        for profile in profiles:
            expected = PROFILE_CONTAINER_CHECKS.get(profile)
            if expected and not any(name in running for name in expected):
                logger.info("Profile %s enabled but containers not running: %s", profile, expected)
                return True
        return False

    async def _ensure_supabase_stack(
        self,
        profiles: list[str],
        *,
        wait_seconds: float = 0,
    ) -> tuple[bool, str]:
        if "supabase" not in profiles:
            return True, ""

        self._prepare_env_for_compose()
        self._ensure_supabase_config()
        await self._ensure_supabase_runtime_dirs_async()

        kong = self._config_dir() / "supabase" / "kong.yml"
        if not kong.is_file():
            return False, (
                "Falta la configuración de Supabase (kong.yml). "
                "Ejecute controlbox repair en el VPS."
            )

        compose_profiles = list(dict.fromkeys(profiles))
        if "backups" not in compose_profiles:
            compose_profiles.append("backups")

        cmd = self._compose_base_cmd()
        for profile in compose_profiles:
            cmd.extend(["--profile", profile])
        cmd.extend(["up", "-d", "--remove-orphans", *SUPABASE_COMPOSE_SERVICES])

        code, output = await self._run_compose(cmd, timeout=120)
        if code not in (0, -1):
            logger.error("Supabase stack start failed: %s", output[-2000:])
            return False, f"Error al iniciar Supabase: {output[-300:]}"
        if code == -1:
            asyncio.create_task(self._run_compose(cmd, timeout=900))

        if wait_seconds <= 0:
            return True, "Supabase iniciándose en segundo plano (puede tardar 1-2 min)."

        polls = max(1, int(wait_seconds / 5))
        for _ in range(polls):
            try:
                running = await self._running_containers()
            except Exception:
                running = set()
            if "controlbox-supabase-db" in running:
                return True, "Supabase activado correctamente"
            await asyncio.sleep(5)

        return True, (
            "Supabase sigue iniciándose en segundo plano. "
            "Revise en unos minutos o ejecute: docker logs controlbox-supabase-db"
        )

    async def _run_docker(self, cmd: list[str], *, timeout: float = 120) -> tuple[int, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=docker_subprocess_env(self._settings),
            )
        except (FileNotFoundError, OSError) as exc:
            logger.error("Could not run docker: %s", exc)
            return 127, str(exc)
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, ""
        output = (stdout or b"").decode("utf-8", errors="replace")
        return proc.returncode or 0, output

    async def _ensure_supabase_runtime_dirs_async(self) -> None:
        host_data = self._host_data_dir()
        cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{host_data}:/data",
            "alpine:3.20",
            "sh",
            "-c",
            "mkdir -p /data/supabase/db && chmod 777 /data/supabase/db",
        ]
        code, output = await self._run_docker(cmd, timeout=120)
        if code not in (0, -1):
            logger.warning("Supabase data dir prep via docker returned %s: %s", code, output[-300:])

    def _compose_up_cmd(self, profiles: list[str], *, extra: list[str] | None = None) -> list[str]:
        cmd = self._compose_base_cmd()
        for profile in profiles:
            cmd.extend(["--profile", profile])
        cmd.extend(extra or ["up", "-d", "--remove-orphans"])
        return cmd

    async def _run_compose(self, cmd: list[str], *, timeout: float) -> tuple[int, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=docker_subprocess_env(self._settings),
            )
        except (FileNotFoundError, OSError) as exc:
            logger.error("Could not run docker compose: %s", exc)
            return 127, str(exc)
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return -1, ""
        output = (stdout or b"").decode("utf-8", errors="replace")
        return proc.returncode or 0, output

    async def _ensure_supabase_stack_background(self, profiles: list[str]) -> None:
        try:
            ok, msg = await self._ensure_supabase_stack(profiles, wait_seconds=0)
            if not ok:
                logger.error("Background Supabase start failed: %s", msg)
        except Exception as exc:
            logger.exception("Background Supabase start error: %s", exc)

    async def _ensure_mysql_remote_root(self) -> None:
        try:
            conn = EngineConfigResolver(self._settings).resolve(DatabaseEngineType.MYSQL)
            await MySqlMariaAdapter().ensure_admin_access(conn)
            logger.info("MySQL root@'%%' verified for panel provisioning")
        except Exception as exc:
            logger.warning("Could not verify MySQL root@'%%': %s", exc)

    async def _recreate_api_worker(self, profiles: list[str]) -> None:
        cmd = self._compose_up_cmd(profiles, extra=["up", "-d", "--force-recreate", "api", "worker"])
        try:
            await self._run_compose(cmd, timeout=300)
        except Exception as exc:
            logger.warning("Could not recreate api/worker after profile apply: %s", exc)

    async def apply_profiles(self, selected: list[str]) -> tuple[bool, str, list[str]]:
        profiles = self._normalize_profiles(selected)
        if not profiles:
            profiles = ["databases"]

        try:
            compose = self._install_dir() / "docker-compose.yml"
            if not compose.is_file():
                return False, "docker-compose.yml not found on host", profiles

            previous = set(self._read_enabled_profiles())
            profiles_set = set(profiles)

            try:
                self._write_profiles_to_env(profiles)
            except FileNotFoundError as exc:
                return False, str(exc), profiles
            except OSError as exc:
                return False, f"No se pudo actualizar platform.env: {exc}", profiles

            if "ftp" in profiles:
                try:
                    env_file = self._env_file()
                    patch_env_key(env_file, "PUREFTPD_ENABLED", "true")
                    patch_env_key(env_file, "CONTROLBOX_FEATURE_FTP", "true")
                except OSError as exc:
                    logger.warning("Could not enable FTP in platform.env: %s", exc)
                try:
                    FtpServiceManager(self._settings).ensure_compose_override_from_env()
                except OSError as exc:
                    logger.warning("Could not create docker-compose.ftp.yml: %s", exc)

            if "supabase" in profiles:
                self._ensure_supabase_config()
                await self._ensure_supabase_runtime_dirs_async()

            if "databases" in profiles:
                await self._ensure_mysql_remote_root()

            self._prepare_env_for_compose()

            profiles_changed = previous != profiles_set
            needs_compose = profiles_changed or await self._profiles_missing_containers(profiles)

            if not needs_compose:
                if "supabase" in profiles:
                    asyncio.create_task(self._ensure_supabase_stack_background(profiles))
                    return (
                        True,
                        "Servicios configurados correctamente. Supabase iniciándose en segundo plano.",
                        profiles,
                    )
                return True, "Servicios configurados correctamente", profiles

            cmd = self._compose_up_cmd(profiles)
            code, output = await self._run_compose(cmd, timeout=45)
            if code == -1:
                asyncio.create_task(self._run_compose(cmd, timeout=900))
            elif code not in (0, 127):
                logger.error("Profile apply failed: %s", output[-2000:])
                asyncio.create_task(self._run_compose(cmd, timeout=900))

            warnings: list[str] = []
            if "supabase" in profiles:
                asyncio.create_task(self._ensure_supabase_stack_background(profiles))
                warnings.append("Supabase iniciándose en segundo plano (puede tardar 1-2 min).")

            asyncio.create_task(self._recreate_api_worker(profiles))
            message = f"Servicios activados: {', '.join(profiles)}"
            if warnings:
                message = f"{message}. {' '.join(warnings)}"
            return True, message, profiles
        except Exception as exc:
            logger.exception("apply_profiles failed")
            return False, f"Error al aplicar servicios: {exc}", profiles
