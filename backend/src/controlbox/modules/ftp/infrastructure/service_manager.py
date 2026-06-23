"""FTP / FTPS / SFTP service lifecycle via Docker Compose."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

from controlbox.config.settings import Settings
from controlbox.modules.ftp.domain.entities import FtpAccount, FtpAccountStatus
from controlbox.modules.ftp.infrastructure.platform_env import read_platform_env_value
from controlbox.modules.ftp.infrastructure.provisioner import PureFtpdProvisioner
from controlbox.shared.infrastructure.compose_overrides import (
    compose_override_files,
    ftp_override_write_path,
    write_ftp_override,
)
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env
from controlbox.shared.infrastructure.platform_env_file import patch_env_keys, repair_celery_redis_urls

logger = logging.getLogger("controlbox.ftp.service")

FTP_PROTOCOLS = frozenset({"ftp", "ftps", "sftp"})
SFTP_CHROOT_NAME = "files"


def _safe_int(raw: str, default: int) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class FtpServiceConfigView:
    enabled: bool
    protocol: str
    port: int
    passive_port_min: int
    passive_port_max: int
    public_host: str
    status: str
    host: str
    running: bool
    can_manage: bool
    message: str


class FtpServiceManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provisioner = PureFtpdProvisioner(settings)

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

    def _ftp_override_file(self) -> Path:
        return ftp_override_write_path(self._settings)

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

    def _read_env_value(self, key: str, default: str = "") -> str:
        return read_platform_env_value(self._settings, key, default)

    def _write_env_values(self, values: dict[str, str]) -> None:
        env_file = self._env_file()
        if not env_file.is_file():
            raise FileNotFoundError("platform.env not found on host")
        try:
            repair_celery_redis_urls(env_file)
            patch_env_keys(env_file, values)
        except OSError as exc:
            raise OSError(
                "No se pudo escribir platform.env. En el VPS ejecute: controlbox repair"
            ) from exc

    def _ensure_ftp_profile(self, enabled: bool) -> None:
        env_file = self._env_file()
        if not env_file.is_file():
            return
        raw = ""
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("CONTROLBOX_ENABLED_PROFILES="):
                raw = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        profiles = [p.strip() for p in raw.replace(" ", "").split(",") if p.strip()]
        if enabled and "ftp" not in profiles:
            profiles.append("ftp")
        if not enabled:
            profiles = [p for p in profiles if p != "ftp"]
        if not profiles:
            profiles = ["databases"]
        self._write_env_values({"CONTROLBOX_ENABLED_PROFILES": ",".join(profiles)})

    def _write_compose_override(self, protocol: str, port: int, passive_min: int, passive_max: int) -> None:
        if protocol == "sftp":
            content = f"""services:
  sftp:
    ports:
      - "{port}:22"
"""
        else:
            content = f"""services:
  pureftpd:
    ports:
      - "{port}:21"
      - "{passive_min}-{passive_max}:{passive_min}-{passive_max}"
"""
        write_ftp_override(self._settings, content)

    def ensure_compose_override_from_env(self) -> None:
        """Ensure docker-compose.ftp.yml exists (host port mappings for Pure-FTPd/SFTP)."""
        if self._ftp_override_file().is_file():
            return
        protocol = self._read_env_value("PUREFTPD_PROTOCOL", "ftp").lower()
        if protocol not in FTP_PROTOCOLS:
            protocol = "ftp"
        port = _safe_int(
            self._read_env_value("PUREFTPD_PORT", "22" if protocol == "sftp" else "21"),
            22 if protocol == "sftp" else 21,
        )
        passive_min = _safe_int(self._read_env_value("PUREFTPD_PASSIVE_MIN", "30000"), 30000)
        passive_max = _safe_int(self._read_env_value("PUREFTPD_PASSIVE_MAX", "30009"), 30009)
        self._write_compose_override(protocol, port, passive_min, passive_max)

    def _sftp_passwd_file(self) -> Path:
        path = self._config_dir() / "ftp" / "sftp.passwd"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def store_sftp_password(self, system_username: str, password: str) -> None:
        path = self._sftp_passwd_file()
        lines = {}
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                if ":" in line:
                    user, pwd = line.split(":", 1)
                    lines[user] = pwd
        lines[system_username] = password
        path.write_text("\n".join(f"{u}:{p}" for u, p in sorted(lines.items())) + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass

    def remove_sftp_password(self, system_username: str) -> None:
        path = self._sftp_passwd_file()
        if not path.is_file():
            return
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{system_username}:"):
                continue
            lines.append(line)
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _read_sftp_passwords(self) -> dict[str, str]:
        path = self._sftp_passwd_file()
        if not path.is_file():
            return {}
        result: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                user, pwd = line.split(":", 1)
                result[user] = pwd
        return result

    def _write_sftp_compose(self, accounts: list[FtpAccount]) -> None:
        port = _safe_int(self._read_env_value("PUREFTPD_PORT", "22"), 22)
        passwords = self._read_sftp_passwords()
        uid = self._settings.pureftpd_virtual_uid
        gid = self._settings.pureftpd_virtual_gid

        command_parts: list[str] = []
        volume_lines: list[str] = ["      - ${CONTROLBOX_DATA_DIR}/sites:/var/lib/controlbox/sites"]

        for account in accounts:
            if account.status != FtpAccountStatus.ACTIVE:
                continue
            password = passwords.get(account.system_username)
            if not password:
                continue
            safe_pass = password.replace(":", "\\:")
            command_parts.append(
                f"{account.system_username}:{safe_pass}:{uid}:{gid}:{SFTP_CHROOT_NAME}"
            )
            home_rel = account.home_directory.strip("/")
            rel_path = f"${{CONTROLBOX_DATA_DIR}}/sites/{account.tenant_id}"
            if home_rel:
                rel_path += f"/{home_rel}"
            volume_lines.append(
                f"      - {rel_path}:/home/{account.system_username}/{SFTP_CHROOT_NAME}"
            )

        command = " ".join(command_parts) if command_parts else f"nobody:locked:{uid}:{gid}:."
        volumes_block = "\n".join(volume_lines)
        content = f"""services:
  sftp:
    ports:
      - "{port}:22"
    command: {command}
    volumes:
{volumes_block}
"""
        write_ftp_override(self._settings, content)

    async def _container_running(self, name: str) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            "-f",
            "{{.State.Running}}",
            name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip() == "true"

    async def get_config(self) -> FtpServiceConfigView:
        compose = self._install_dir() / "docker-compose.yml"
        env_file = self._env_file()
        can_manage = compose.is_file() and env_file.is_file()

        enabled = self._read_env_value("PUREFTPD_ENABLED", "false").lower() == "true"
        protocol = self._read_env_value("PUREFTPD_PROTOCOL", "ftp").lower()
        if protocol not in FTP_PROTOCOLS:
            protocol = "ftp"
        port = _safe_int(
            self._read_env_value("PUREFTPD_PORT", "21" if protocol != "sftp" else "22"),
            21 if protocol != "sftp" else 22,
        )
        passive_min = _safe_int(self._read_env_value("PUREFTPD_PASSIVE_MIN", "30000"), 30000)
        passive_max = _safe_int(self._read_env_value("PUREFTPD_PASSIVE_MAX", "30009"), 30009)
        public_host = self._read_env_value("PUREFTPD_PUBLIC_HOST", self._settings.pureftpd_host)

        status_raw = await self._provisioner.service_status()
        running = status_raw.get("status") == "running"
        if enabled and protocol == "sftp":
            running = await self._container_running("controlbox-sftp")

        message = ""
        if not can_manage:
            message = "Gestión FTP no disponible desde este entorno (requiere instalación en VPS)."
        elif not enabled:
            message = "Servicio FTP deshabilitado. Actívelo abajo para crear cuentas."
        elif not running:
            message = "Servicio detenido. Pulse Iniciar o guarde la configuración para levantarlo."

        return FtpServiceConfigView(
            enabled=enabled,
            protocol=protocol,
            port=port,
            passive_port_min=passive_min,
            passive_port_max=passive_max,
            public_host=public_host,
            status=str(status_raw.get("status", "stopped" if not running else "running")),
            host=self._read_env_value("PUREFTPD_HOST", "pureftpd"),
            running=running,
            can_manage=can_manage,
            message=message,
        )

    async def apply_config(
        self,
        *,
        enabled: bool,
        protocol: str,
        port: int,
        passive_port_min: int,
        passive_port_max: int,
        public_host: str,
        sftp_accounts: list[FtpAccount] | None = None,
    ) -> tuple[bool, str, FtpServiceConfigView]:
        try:
            return await self._apply_config_impl(
                enabled=enabled,
                protocol=protocol,
                port=port,
                passive_port_min=passive_port_min,
                passive_port_max=passive_port_max,
                public_host=public_host,
                sftp_accounts=sftp_accounts,
            )
        except FileNotFoundError as exc:
            logger.error("FTP apply_config: %s", exc)
            return False, str(exc), await self.get_config()
        except OSError as exc:
            logger.error("FTP apply_config I/O error: %s", exc)
            return False, str(exc), await self.get_config()
        except Exception as exc:
            logger.exception("FTP apply_config failed")
            return False, f"Error al configurar FTP: {exc}", await self.get_config()

    async def _apply_config_impl(
        self,
        *,
        enabled: bool,
        protocol: str,
        port: int,
        passive_port_min: int,
        passive_port_max: int,
        public_host: str,
        sftp_accounts: list[FtpAccount] | None = None,
    ) -> tuple[bool, str, FtpServiceConfigView]:
        protocol = protocol.lower()
        if protocol not in FTP_PROTOCOLS:
            return False, f"Protocolo no soportado: {protocol}", await self.get_config()

        if port < 1 or port > 65535:
            return False, "Puerto inválido", await self.get_config()
        if passive_port_min >= passive_port_max:
            return False, "Rango pasivo inválido", await self.get_config()

        compose = self._install_dir() / "docker-compose.yml"
        if not compose.is_file():
            return False, "docker-compose.yml not found on host", await self.get_config()

        tls = "1" if protocol == "ftps" else "0"
        self._write_env_values(
            {
                "PUREFTPD_ENABLED": "true" if enabled else "false",
                "PUREFTPD_PROTOCOL": protocol,
                "PUREFTPD_PORT": str(port),
                "PUREFTPD_PUBLIC_HOST": public_host.strip() or "localhost",
                "PUREFTPD_PASSIVE_MIN": str(passive_port_min),
                "PUREFTPD_PASSIVE_MAX": str(passive_port_max),
                "PUREFTPD_TLS": tls,
                "PUREFTPD_HOST": "pureftpd" if protocol != "sftp" else "sftp",
                "CONTROLBOX_FEATURE_FTP": "true" if enabled else "false",
            }
        )
        self._ensure_ftp_profile(enabled)

        if protocol == "sftp":
            self._write_sftp_compose(sftp_accounts or [])
        else:
            self._write_compose_override(protocol, port, passive_port_min, passive_port_max)

        if not enabled:
            await self._run_compose(["--profile", "ftp", "stop", "pureftpd", "sftp"], optional=True)
            return True, "Servicio FTP deshabilitado", await self.get_config()

        profile_cmd = self._compose_base_cmd() + ["--profile", "ftp"]
        if protocol == "sftp":
            await self._run_compose(["--profile", "ftp", "stop", "pureftpd"], optional=True)
            ok, msg = await self._run_compose(profile_cmd + ["up", "-d", "--remove-orphans", "sftp"])
        else:
            await self._run_compose(["--profile", "ftp", "stop", "sftp"], optional=True)
            ok, msg = await self._run_compose(profile_cmd + ["up", "-d", "--remove-orphans", "pureftpd"])

        if not ok:
            return False, msg, await self.get_config()
        return True, "Configuración FTP aplicada", await self.get_config()

    async def start(self) -> tuple[bool, str]:
        config = await self.get_config()
        if not config.enabled:
            return False, "Habilite el servicio FTP antes de iniciarlo"
        ok, message, _ = await self.apply_config(
            enabled=True,
            protocol=config.protocol,
            port=config.port,
            passive_port_min=config.passive_port_min,
            passive_port_max=config.passive_port_max,
            public_host=config.public_host,
        )
        return ok, message

    async def stop(self) -> tuple[bool, str]:
        ok, msg = await self._run_compose(["--profile", "ftp", "stop", "pureftpd", "sftp"], optional=True)
        return ok, "Servicio FTP detenido" if ok else msg

    async def rebuild_sftp(self, accounts: list[FtpAccount]) -> tuple[bool, str]:
        config = await self.get_config()
        if config.protocol != "sftp":
            return True, "skipped"
        self._write_sftp_compose(accounts)
        profile_cmd = self._compose_base_cmd() + ["--profile", "ftp"]
        return await self._run_compose(profile_cmd + ["up", "-d", "--force-recreate", "sftp"])

    async def sync_sftp_user(self, account: FtpAccount, plain_password: str, all_accounts: list[FtpAccount]) -> None:
        config = await self.get_config()
        if not config.enabled or config.protocol != "sftp":
            return
        self.store_sftp_password(account.system_username, plain_password)
        await self.rebuild_sftp(all_accounts)

    async def _run_compose(self, args: list[str], *, optional: bool = False) -> tuple[bool, str]:
        cmd = self._compose_base_cmd() + args
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=docker_subprocess_env(self._settings),
            )
        except (FileNotFoundError, OSError) as exc:
            logger.error("Could not run docker compose for FTP: %s", exc)
            return False, str(exc)
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return False, "Timeout al ejecutar docker compose"
        output = (stdout or b"").decode("utf-8", errors="replace")[-800:]
        if proc.returncode != 0:
            if optional:
                return True, output
            logger.error("FTP compose failed: %s", output)
            return False, f"Error Docker: {output[-300:]}"
        return True, output
