"""Cloudflare Tunnel lifecycle via Docker Compose."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from controlbox.config.settings import Settings
from controlbox.modules.cloudflare.infrastructure.settings_service import CloudflareSettingsService
from controlbox.modules.platform.domain.entities import TenantPlatformSettings

logger = logging.getLogger("controlbox.cloudflare.tunnel")

CLOUDFLARE_COMPOSE = """services:
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: controlbox-cloudflared
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
    networks:
      - controlbox
"""


@dataclass(frozen=True)
class TunnelStatus:
    enabled: bool
    running: bool
    tunnel_id: str
    hostname: str
    message: str


class CloudflareTunnelManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cf_settings = CloudflareSettingsService(settings)

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

    def _override_file(self) -> Path:
        return self._install_dir() / "docker-compose.cloudflare.yml"

    def _compose_cmd(self, *args: str) -> list[str]:
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
        for extra in (
            "docker-compose.override.yml",
            "docker-compose.ports.yml",
            "docker-compose.cloudflare.yml",
            "docker-compose.ftp.yml",
            "docker-compose.build.yml",
        ):
            path = install_dir / extra
            if path.exists():
                cmd.extend(["-f", str(path)])
        cmd.extend(args)
        return cmd

    async def _run(self, cmd: list[str], timeout: float = 120) -> tuple[int, str]:
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

    def _write_env_token(self, token: str) -> None:
        env_file = self._env_file()
        if not env_file.is_file():
            raise FileNotFoundError("platform.env not found on host")
        lines = env_file.read_text(encoding="utf-8").splitlines()
        key = "CLOUDFLARE_TUNNEL_TOKEN"
        found = False
        updated: list[str] = []
        for line in lines:
            if line.startswith(f"{key}="):
                updated.append(f'{key}="{token}"')
                found = True
            else:
                updated.append(line)
        if not found:
            updated.append(f'{key}="{token}"')
        env_file.write_text("\n".join(updated) + "\n", encoding="utf-8")

    def _remove_env_token(self) -> None:
        env_file = self._env_file()
        if not env_file.is_file():
            return
        key = "CLOUDFLARE_TUNNEL_TOKEN"
        lines = [line for line in env_file.read_text(encoding="utf-8").splitlines() if not line.startswith(f"{key}=")]
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _ensure_compose_file(self) -> None:
        self._override_file().write_text(CLOUDFLARE_COMPOSE, encoding="utf-8")

    async def _is_running(self) -> bool:
        code, output = await self._run(
            ["docker", "inspect", "-f", "{{.State.Running}}", "controlbox-cloudflared"],
            timeout=15,
        )
        return code == 0 and "true" in output.lower()

    def _panel_service_url(self) -> str:
        port = self._settings.panel_port or 8475
        return f"http://127.0.0.1:{port}"

    async def enable_tunnel(self, platform: TenantPlatformSettings) -> tuple[bool, str]:
        client = await self._cf_settings.client_for(platform)
        account_id = platform.cloudflare_account_id or await client.resolve_account_id()
        platform.cloudflare_account_id = account_id

        hostname = (platform.cloudflare_tunnel_hostname or "").strip()
        if not hostname:
            return False, "Tunnel hostname is required (e.g. panel.example.com)"

        tunnel_id = platform.cloudflare_tunnel_id
        if not tunnel_id:
            tunnel = await client.create_tunnel("controlbox-tunnel", account_id)
            tunnel_id = str(tunnel["id"])
            token = await client.get_tunnel_token(tunnel_id, account_id)
            self._cf_settings.store_tunnel_credentials(platform, tunnel_id=tunnel_id, tunnel_token=token)
        else:
            token = self._cf_settings.get_tunnel_token(platform)
            if not token:
                token = await client.get_tunnel_token(tunnel_id, account_id)
                self._cf_settings.store_tunnel_credentials(platform, tunnel_id=tunnel_id, tunnel_token=token)

        await client.configure_tunnel_ingress(
            tunnel_id,
            hostname,
            self._panel_service_url(),
            account_id,
        )

        self._write_env_token(token or "")
        self._ensure_compose_file()
        platform.cloudflare_tunnel_enabled = True

        code, output = await self._run(self._compose_cmd("up", "-d", "cloudflared"), timeout=180)
        if code != 0:
            logger.error("cloudflared start failed: %s", output)
            return False, f"Tunnel configured but container failed to start: {output[-500:]}"
        return True, f"Cloudflare Tunnel active for {hostname}"

    async def disable_tunnel(self, platform: TenantPlatformSettings) -> tuple[bool, str]:
        if self._override_file().exists():
            await self._run(self._compose_cmd("stop", "cloudflared"), timeout=60)
            await self._run(self._compose_cmd("rm", "-f", "cloudflared"), timeout=60)
        self._remove_env_token()
        platform.cloudflare_tunnel_enabled = False
        return True, "Cloudflare Tunnel stopped"

    async def status(self, platform: TenantPlatformSettings) -> TunnelStatus:
        running = await self._is_running() if platform.cloudflare_tunnel_enabled else False
        return TunnelStatus(
            enabled=platform.cloudflare_tunnel_enabled,
            running=running,
            tunnel_id=platform.cloudflare_tunnel_id or "",
            hostname=platform.cloudflare_tunnel_hostname or "",
            message="Running" if running else ("Stopped" if platform.cloudflare_tunnel_enabled else "Disabled"),
        )
