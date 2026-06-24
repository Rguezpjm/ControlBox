"""Host panel operations (restart, repair, update) via Docker Compose on the VPS."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from controlbox.config.settings import Settings
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env
from controlbox.shared.infrastructure.version_info import resolve_controlbox_version

logger = logging.getLogger("controlbox.platform")


@dataclass(frozen=True)
class OperationResult:
    success: bool
    message: str
    detail: str | None = None


@dataclass(frozen=True)
class UpdateCheckResult:
    current_version: str
    latest_version: str | None
    update_available: bool
    source: str
    release_url: str | None = None
    tarball_url: str | None = None


class PanelOperationsService:
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

    def _compose_cmd(self, *args: str) -> list[str]:
        install_dir = self._install_dir()
        env_file = self._config_dir() / "platform.env"
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
        cmd.extend(args)
        return cmd

    async def _run(self, cmd: list[str], timeout: float = 300) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=docker_subprocess_env(self._settings),
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return 1, "Operation timed out"
        output = (stdout or b"").decode("utf-8", errors="replace")[-4000:]
        return proc.returncode or 0, output

    async def restart_panel(self) -> OperationResult:
        # Restart the panel container directly via the Docker proxy. We avoid
        # `docker compose restart` because compose interpolates the *entire*
        # platform compose file and aborts if any optional service has an unset
        # `:?required` variable (e.g. MSSQL_ADMIN_PASSWORD on older installs).
        code, output = await self._run(["docker", "restart", "controlbox-panel"], timeout=120)
        if code == 0:
            return OperationResult(True, "Panel reiniciado correctamente")
        logger.error("Panel restart failed: %s", output)
        return OperationResult(False, "No se pudo reiniciar el panel", output)

    async def fix_stack(self) -> OperationResult:
        # IMPORTANT: the host repair.sh requires root and host-only paths
        # (e.g. /var/log/controlbox); it cannot run inside the api container.
        # From the panel we perform a container-safe recovery through the Docker
        # socket proxy: bring up the proxy and the panel/worker services. The api
        # container is intentionally not recreated so the request that triggered
        # this operation can complete.
        deeper = "Para una reparación completa ejecute 'controlbox repair' en el servidor."

        cmd = self._compose_cmd("up", "-d", "--remove-orphans", "docker-socket-proxy", "panel", "worker")
        code, output = await self._run(cmd, timeout=600)
        if code == 0:
            return OperationResult(True, "Servicios verificados y reiniciados", deeper)

        # Fallback: restart the known core containers directly (no compose
        # interpolation), which works even when platform.env is incomplete.
        code2, output2 = await self._run(
            ["docker", "restart", "controlbox-panel", "controlbox-worker"], timeout=180
        )
        if code2 == 0:
            return OperationResult(True, "Servicios reiniciados (recuperación básica)", deeper)

        detail = "\n".join(part for part in (output, output2) if part).strip()
        logger.error("Fix stack failed: %s", detail)
        return OperationResult(False, "No se pudo reparar el stack desde el panel", f"{detail}\n{deeper}".strip())

    async def _fetch_install_sh_version(self, client: httpx.AsyncClient) -> str | None:
        url = f"{self._settings.controlbox_install_url.rstrip('/')}/install.sh"
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            match = re.search(r'CONTROLBOX_VERSION="([^"]+)"', response.text)
            return match.group(1) if match else None
        except Exception:
            logger.debug("Could not fetch version from install.sh", exc_info=True)
            return None

    @staticmethod
    def _normalize_version_tag(raw: str) -> str:
        value = raw.strip().strip('"').strip("'")
        if value and value[0] in {"v", "V"}:
            value = value[1:]
        return value

    async def _fetch_github_release(self, client: httpx.AsyncClient) -> tuple[str | None, str | None, str | None]:
        repo = self._settings.controlbox_github_repo.strip()
        if not repo:
            return None, None, None
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ControlBox-Panel"}
        try:
            response = await client.get(url, headers=headers, follow_redirects=True)
            if response.status_code == 404:
                return None, None, None
            response.raise_for_status()
            data = response.json()
            tag = self._normalize_version_tag(str(data.get("tag_name", "")))
            html_url = data.get("html_url")
            tarball = None
            for asset in data.get("assets", []):
                name = str(asset.get("name", ""))
                if name.endswith(".tar.gz") and "controlbox-installer" in name.lower():
                    tarball = asset.get("browser_download_url")
                    break
            return tag or None, html_url, tarball
        except Exception:
            logger.debug("GitHub release check failed", exc_info=True)
            return None, None, None

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        normalized = PanelOperationsService._normalize_version_tag(version)
        parts: list[int] = []
        for piece in re.split(r"[.\-_]", normalized):
            if piece.isdigit():
                parts.append(int(piece))
        return tuple(parts) if parts else (0,)

    def _versions_equal(self, left: str, right: str) -> bool:
        return self._parse_version(left) == self._parse_version(right)

    async def check_updates(self) -> UpdateCheckResult:
        current = resolve_controlbox_version(self._settings)
        async with httpx.AsyncClient(timeout=20) as client:
            github_version, release_url, github_tarball = await self._fetch_github_release(client)
            cdn_version = None if github_version else await self._fetch_install_sh_version(client)

        if github_version:
            latest = github_version
            source = "github"
            tarball_url = github_tarball
        elif cdn_version:
            latest = cdn_version
            source = "cdn"
            tarball_url = f"{self._settings.controlbox_install_url.rstrip('/')}/controlbox-installer-{cdn_version}.tar.gz"
        else:
            latest = None
            source = "none"
            tarball_url = None

        update_available = bool(latest and not self._versions_equal(latest, current))
        return UpdateCheckResult(
            current_version=current,
            latest_version=latest,
            update_available=update_available,
            source=source,
            release_url=release_url,
            tarball_url=tarball_url,
        )

    async def apply_update(self) -> OperationResult:
        check = await self.check_updates()
        if not check.latest_version:
            return OperationResult(
                False,
                "Could not fetch latest release from GitHub",
                f"Repository: {self._settings.controlbox_github_repo}",
            )
        if not check.update_available:
            return OperationResult(
                True,
                f"Already on release v{check.current_version}",
            )

        update_script = self._install_dir() / "update.sh"
        env = {
            **dict(__import__("os").environ),
            "CONTROLBOX_VERSION": check.latest_version,
            "CONTROLBOX_INSTALL_URL": self._settings.controlbox_install_url,
            "CONTROLBOX_GITHUB_REPO": self._settings.controlbox_github_repo,
        }
        if check.tarball_url:
            env["CONTROLBOX_RELEASE_TARBALL"] = check.tarball_url

        if update_script.exists():
            proc = await asyncio.create_subprocess_exec(
                "bash",
                str(update_script),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=1200)
            except asyncio.TimeoutError:
                return OperationResult(
                    True,
                    f"Update to v{check.latest_version} started (running in background on server)",
                )
            output = (stdout or b"").decode("utf-8", errors="replace")[-4000:]
            if proc.returncode == 0:
                return OperationResult(True, f"Updated to v{check.latest_version}", output)
            return OperationResult(False, "Update failed", output)

        cmd = self._compose_cmd("pull", "panel", "api")
        code, output = await self._run(cmd, timeout=600)
        if code != 0:
            return OperationResult(False, "Could not pull updated images", output)
        cmd = self._compose_cmd("up", "-d", "--force-recreate", "panel", "api")
        code, output = await self._run(cmd, timeout=300)
        if code == 0:
            return OperationResult(True, f"Updated to v{check.latest_version}", output)
        return OperationResult(False, "Update deploy failed", output)
