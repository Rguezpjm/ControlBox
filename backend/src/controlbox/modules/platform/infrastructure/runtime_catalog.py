"""Runtime language versions (PHP, Python, Node.js, etc.) enabled on the panel host."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from controlbox.config.settings import Settings
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env

logger = logging.getLogger("controlbox.platform.runtimes")

DEFAULT_ENABLED_RUNTIMES = (
    "php:8.2",
    "php:8.3",
    "nodejs:22",
    "python:3.13",
    "flutter:3.44.2",
)

RUNTIME_CATALOG: tuple[dict[str, str], ...] = (
    {"id": "php-8.1", "runtime": "php", "version": "8.1", "name": "PHP 8.1", "category": "php", "image": "php:8.1-apache"},
    {"id": "php-8.2", "runtime": "php", "version": "8.2", "name": "PHP 8.2", "category": "php", "image": "php:8.2-apache"},
    {"id": "php-8.3", "runtime": "php", "version": "8.3", "name": "PHP 8.3", "category": "php", "image": "php:8.3-apache"},
    {"id": "php-8.4", "runtime": "php", "version": "8.4", "name": "PHP 8.4", "category": "php", "image": "php:8.4-apache"},
    {"id": "nodejs-20", "runtime": "nodejs", "version": "20", "name": "Node.js 20", "category": "nodejs", "image": "node:20-alpine"},
    {"id": "nodejs-22", "runtime": "nodejs", "version": "22", "name": "Node.js 22", "category": "nodejs", "image": "node:22-alpine"},
    {"id": "python-3.12", "runtime": "python", "version": "3.12", "name": "Python 3.12", "category": "python", "image": "python:3.12-slim"},
    {"id": "python-3.13", "runtime": "python", "version": "3.13", "name": "Python 3.13", "category": "python", "image": "python:3.13-slim"},
    {"id": "flutter-3.44.2", "runtime": "flutter", "version": "3.44.2", "name": "Flutter Web 3.44.2", "category": "flutter", "image": "nginx:1.27-alpine"},
)

RUNTIME_IMAGE_MAP: dict[tuple[str, str], str] = {
    (item["runtime"], item["version"]): item["image"] for item in RUNTIME_CATALOG
}
RUNTIME_IMAGE_MAP[("html", "")] = "nginx:1.27-alpine"


@dataclass(frozen=True)
class RuntimeVersionView:
    id: str
    runtime: str
    version: str
    name: str
    category: str
    image: str
    enabled: bool
    installed: bool


@dataclass(frozen=True)
class RuntimesOverview:
    can_manage: bool
    enabled_runtimes: list[str]
    runtimes: list[RuntimeVersionView]
    message: str = ""


def _parse_runtime_key(raw: str) -> tuple[str, str] | None:
    raw = raw.strip().lower()
    if ":" not in raw:
        return None
    runtime, version = raw.split(":", 1)
    if not runtime or not version:
        return None
    return runtime, version


class RuntimeCatalogManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _config_dir(self) -> Path:
        raw = self._settings.platform_config_dir
        if raw.startswith("/host/"):
            return Path(raw)
        return Path("/host/etc/controlbox") if raw == "/etc/controlbox" else Path(raw)

    def _env_file(self) -> Path:
        return self._config_dir() / "platform.env"

    def _read_enabled_keys(self) -> list[str]:
        raw = ""
        env_file = self._env_file()
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("CONTROLBOX_ENABLED_RUNTIMES="):
                    raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
        if not raw.strip():
            raw = getattr(self._settings, "controlbox_enabled_runtimes", "") or ""
        keys = [p.strip() for p in raw.replace(" ", "").split(",") if p.strip()]
        return keys if keys else list(DEFAULT_ENABLED_RUNTIMES)

    def _normalize_selected(self, selected: list[str]) -> list[str]:
        id_to_key = {item["id"]: f"{item['runtime']}:{item['version']}" for item in RUNTIME_CATALOG}
        valid_keys = set(id_to_key.values())
        keys: list[str] = []
        for item in selected:
            token = item.strip().lower()
            if token in id_to_key:
                key = id_to_key[token]
            elif _parse_runtime_key(token):
                runtime, version = _parse_runtime_key(token)
                key = f"{runtime}:{version}"
            else:
                continue
            if key in valid_keys and key not in keys:
                keys.append(key)
        return keys

    def _write_enabled_to_env(self, keys: list[str]) -> None:
        env_file = self._env_file()
        if not env_file.is_file():
            raise FileNotFoundError("platform.env not found on host")
        joined = ",".join(keys) if keys else ",".join(DEFAULT_ENABLED_RUNTIMES)
        lines = env_file.read_text(encoding="utf-8").splitlines()
        found = False
        updated: list[str] = []
        for line in lines:
            if line.startswith("CONTROLBOX_ENABLED_RUNTIMES="):
                updated.append(f"CONTROLBOX_ENABLED_RUNTIMES={joined}")
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f"CONTROLBOX_ENABLED_RUNTIMES={joined}")
        env_file.write_text("\n".join(updated) + "\n", encoding="utf-8")

    async def _image_installed(self, image: str) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "image",
            "inspect",
            image,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=docker_subprocess_env(self._settings),
        )
        await proc.wait()
        return proc.returncode == 0

    def get_enabled_by_runtime(self) -> dict[str, list[str]]:
        enabled_keys = set(self._read_enabled_keys())
        result: dict[str, list[str]] = {}
        for item in RUNTIME_CATALOG:
            key = f"{item['runtime']}:{item['version']}"
            if key in enabled_keys:
                result.setdefault(item["runtime"], []).append(item["version"])
        for runtime in result:
            result[runtime].sort(key=lambda v: [int(p) if p.isdigit() else p for p in re.split(r"[.\-]", v)])
        return result

    def get_php_versions(self) -> list[str]:
        return self.get_enabled_by_runtime().get("php", ["8.2", "8.3"])

    def get_default_version(self, runtime: str) -> str:
        versions = self.get_enabled_by_runtime().get(runtime, [])
        return versions[-1] if versions else ""

    def is_version_enabled(self, runtime: str, version: str) -> bool:
        if runtime == "html":
            return True
        return version in self.get_enabled_by_runtime().get(runtime, [])

    async def get_overview(self) -> RuntimesOverview:
        env_file = self._env_file()
        can_manage = env_file.is_file()
        enabled_keys = set(self._read_enabled_keys())
        runtimes: list[RuntimeVersionView] = []

        for item in RUNTIME_CATALOG:
            key = f"{item['runtime']}:{item['version']}"
            installed = False
            if can_manage:
                try:
                    installed = await self._image_installed(item["image"])
                except Exception as exc:
                    logger.debug("Could not inspect image %s: %s", item["image"], exc)
            runtimes.append(
                RuntimeVersionView(
                    id=item["id"],
                    runtime=item["runtime"],
                    version=item["version"],
                    name=item["name"],
                    category=item["category"],
                    image=item["image"],
                    enabled=key in enabled_keys,
                    installed=installed,
                )
            )

        message = ""
        if not can_manage:
            message = "Gestión de runtimes no disponible desde este entorno (requiere instalación en VPS)."

        return RuntimesOverview(
            can_manage=can_manage,
            enabled_runtimes=sorted(enabled_keys),
            runtimes=runtimes,
            message=message,
        )

    async def apply_runtimes(self, selected: list[str]) -> tuple[bool, str, list[str]]:
        keys = self._normalize_selected(selected)
        if not keys:
            keys = list(DEFAULT_ENABLED_RUNTIMES)

        previous = set(self._read_enabled_keys())
        keys_set = set(keys)

        images = []
        for item in RUNTIME_CATALOG:
            key = f"{item['runtime']}:{item['version']}"
            if key in keys:
                images.append(item["image"])
                if item["runtime"] == "php":
                    images.append(f"wordpress:php{item['version']}-fpm")

        try:
            self._write_enabled_to_env(keys)
        except FileNotFoundError as exc:
            return False, str(exc), keys

        if previous == keys_set:
            return True, "Runtimes configurados correctamente", keys

        unique_images = list(dict.fromkeys(images))
        pull_task = asyncio.create_task(self._pull_images(unique_images))
        try:
            pulled, failed = await asyncio.wait_for(asyncio.shield(pull_task), timeout=45)
        except asyncio.TimeoutError:
            return True, "Runtimes guardados. Descarga de imágenes en segundo plano.", keys

        if failed and not pulled:
            return True, f"Runtimes guardados. Imágenes pendientes: {', '.join(failed)}", keys
        if failed:
            return True, f"Runtimes guardados. Algunas imágenes pendientes: {', '.join(failed)}", keys
        return True, f"Runtimes activados: {', '.join(keys)}", keys

    async def _pull_images(self, images: list[str]) -> tuple[list[str], list[str]]:
        pulled: list[str] = []
        failed: list[str] = []
        for image in images:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "pull",
                image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=docker_subprocess_env(self._settings),
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=600)
            except asyncio.TimeoutError:
                proc.kill()
                failed.append(image)
                continue
            if proc.returncode == 0:
                pulled.append(image)
            else:
                logger.warning("Failed to pull %s: %s", image, (stderr or b"").decode()[-200:])
                failed.append(image)
        return pulled, failed
