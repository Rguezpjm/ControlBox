"""Host panel operations (restart, repair, update) via Docker Compose on the VPS."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

from controlbox.config.settings import Settings

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
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return 1, "Operation timed out"
        output = (stdout or b"").decode("utf-8", errors="replace")[-4000:]
        return proc.returncode or 0, output

    async def restart_panel(self) -> OperationResult:
        cmd = self._compose_cmd("restart", "panel")
        code, output = await self._run(cmd, timeout=120)
        if code == 0:
            return OperationResult(True, "Panel restarted successfully")
        logger.error("Panel restart failed: %s", output)
        return OperationResult(False, "Failed to restart panel", output)

    async def fix_stack(self) -> OperationResult:
        repair_script = self._install_dir() / "repair.sh"
        if not repair_script.exists():
            cmd = self._compose_cmd("up", "-d", "--remove-orphans", "panel", "api")
            code, output = await self._run(cmd, timeout=600)
            if code == 0:
                return OperationResult(True, "Services restarted")
            return OperationResult(False, "Repair failed", output)

        proc = await asyncio.create_subprocess_exec(
            "bash",
            str(repair_script),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=900)
        except asyncio.TimeoutError:
            proc.kill()
            return OperationResult(False, "Repair timed out (still running on server)")

        output = (stdout or b"").decode("utf-8", errors="replace")[-4000:]
        if proc.returncode == 0:
            return OperationResult(True, "Repair completed successfully")
        return OperationResult(False, "Repair failed", output)

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
            tag = str(data.get("tag_name", "")).lstrip("v")
            html_url = data.get("html_url")
            tarball = None
            for asset in data.get("assets", []):
                name = str(asset.get("name", ""))
                if name.endswith(".tar.gz") and "controlbox-installer" in name:
                    tarball = asset.get("browser_download_url")
                    break
            return tag or None, html_url, tarball
        except Exception:
            logger.debug("GitHub release check failed", exc_info=True)
            return None, None, None

    @staticmethod
    def _parse_version(version: str) -> tuple[int, ...]:
        parts: list[int] = []
        for piece in re.split(r"[.\-]", version):
            if piece.isdigit():
                parts.append(int(piece))
        return tuple(parts) if parts else (0,)

    def _is_newer(self, latest: str, current: str) -> bool:
        return self._parse_version(latest) > self._parse_version(current)

    async def check_updates(self) -> UpdateCheckResult:
        current = self._settings.controlbox_version
        async with httpx.AsyncClient(timeout=20) as client:
            github_version, release_url, github_tarball = await self._fetch_github_release(client)
            cdn_version = await self._fetch_install_sh_version(client)

        latest = github_version or cdn_version
        source = "github" if github_version else "cdn"
        tarball_url = github_tarball
        if cdn_version and (not latest or self._is_newer(cdn_version, latest)):
            latest = cdn_version
            source = "cdn"
            tarball_url = f"{self._settings.controlbox_install_url.rstrip('/')}/controlbox-installer-{cdn_version}.tar.gz"

        update_available = bool(latest and self._is_newer(latest, current))
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
        if not check.update_available or not check.latest_version:
            return OperationResult(True, f"Already on latest version ({check.current_version})")

        update_script = self._install_dir() / "update.sh"
        env = {
            **dict(__import__("os").environ),
            "CONTROLBOX_VERSION": check.latest_version,
            "CONTROLBOX_INSTALL_URL": self._settings.controlbox_install_url,
        }

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
