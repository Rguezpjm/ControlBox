"""Optional Docker Compose profiles — read/apply from the panel."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from controlbox.config.settings import Settings

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
        "id": "supabase",
        "profile": "supabase",
        "name": "Supabase",
        "category": "platform",
        "description": "Stack Supabase self-hosted (Auth, REST, Realtime, Storage). Requiere MinIO.",
        "containers": ("controlbox-supabase-db", "controlbox-supabase-kong"),
        "requires": ("backups",),
    },
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
        for extra in ("docker-compose.override.yml", "docker-compose.ports.yml", "docker-compose.build.yml"):
            path = install_dir / extra
            if path.exists():
                cmd.extend(["-f", str(path)])
        return cmd

    def _read_enabled_profiles(self) -> list[str]:
        raw = self._settings.controlbox_enabled_profiles or ""
        if not raw.strip() and self._env_file().is_file():
            for line in self._env_file().read_text(encoding="utf-8").splitlines():
                if line.startswith("CONTROLBOX_ENABLED_PROFILES="):
                    raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
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
        joined = ",".join(profiles) if profiles else "databases"
        lines = env_file.read_text(encoding="utf-8").splitlines()
        found = False
        updated: list[str] = []
        for line in lines:
            if line.startswith("CONTROLBOX_ENABLED_PROFILES="):
                updated.append(f"CONTROLBOX_ENABLED_PROFILES={joined}")
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f"CONTROLBOX_ENABLED_PROFILES={joined}")
        env_file.write_text("\n".join(updated) + "\n", encoding="utf-8")

    async def _running_containers(self) -> set[str]:
        cmd = self._compose_base_cmd() + ["ps", "--format", "json"]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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

    async def apply_profiles(self, selected: list[str]) -> tuple[bool, str, list[str]]:
        profiles = self._normalize_profiles(selected)
        if not profiles:
            profiles = ["databases"]

        compose = self._install_dir() / "docker-compose.yml"
        if not compose.is_file():
            return False, "docker-compose.yml not found on host", profiles

        try:
            self._write_profiles_to_env(profiles)
        except FileNotFoundError as exc:
            return False, str(exc), profiles

        cmd = self._compose_base_cmd()
        for profile in profiles:
            cmd.extend(["--profile", profile])
        cmd.extend(["up", "-d", "--remove-orphans"])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=900)
        except asyncio.TimeoutError:
            proc.kill()
            return True, "Instalación iniciada en segundo plano (puede tardar varios minutos)", profiles

        output = (stdout or b"").decode("utf-8", errors="replace")[-2000:]
        if proc.returncode != 0:
            logger.error("Profile apply failed: %s", output)
            return False, f"Error al instalar servicios: {output[-400:]}", profiles

        return True, f"Servicios activados: {', '.join(profiles)}", profiles
