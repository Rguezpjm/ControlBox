import asyncio
import logging
import re
from pathlib import Path

from controlbox.config.settings import Settings

logger = logging.getLogger("controlbox.platform")


class PanelConfigService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_config(self) -> dict:
        base_path = self._settings.panel_base_path or ""
        if base_path and not base_path.startswith("/"):
            base_path = f"/{base_path}"
        url_suffix = f":{self._settings.panel_port}{base_path}" if base_path else f":{self._settings.panel_port}"
        return {
            "panel_port": self._settings.panel_port,
            "panel_base_path": base_path or "/",
            "panel_url_hint": url_suffix,
            "config_dir": self._settings.platform_config_dir,
            "install_dir": self._settings.controlbox_install_dir,
            "can_apply_changes": Path(self._settings.platform_config_dir).exists(),
        }

    async def update_config(self, *, panel_port: int | None, panel_base_path: str | None) -> dict:
        config_dir = Path(self._settings.platform_config_dir)
        env_file = config_dir / "platform.env"
        if not env_file.exists():
            return {
                "applied": False,
                "requires_manual_step": True,
                "message": "Configuración del host no accesible desde el contenedor API. Use: controlbox repair --apply-panel",
            }

        content = env_file.read_text(encoding="utf-8")
        path_changed = False
        port_changed = False

        if panel_port is not None:
            if panel_port < 1024 or panel_port > 65535:
                raise ValueError("Puerto inválido")
            content, replaced = self._replace_env_value(content, "PANEL_PORT", str(panel_port))
            port_changed = replaced or f"PANEL_PORT={panel_port}" in content
            if not replaced:
                content += f"\nPANEL_PORT={panel_port}\n"

        if panel_base_path is not None:
            normalized = panel_base_path.strip()
            if not normalized.startswith("/"):
                normalized = f"/{normalized}"
            if not re.fullmatch(r"/[A-Za-z0-9_/-]+", normalized):
                raise ValueError("Ruta del panel inválida")
            content, replaced = self._replace_env_value(content, "PANEL_BASE_PATH", normalized)
            path_changed = True
            if not replaced:
                content += f"\nPANEL_BASE_PATH={normalized}\n"

        env_file.write_text(content, encoding="utf-8")
        install_env = Path(self._settings.controlbox_install_dir) / ".env"
        if install_env.exists():
            install_env.write_text(content, encoding="utf-8")

        result = {
            "applied": True,
            "port_changed": port_changed,
            "path_changed": path_changed,
            "requires_panel_rebuild": path_changed,
            "requires_restart": port_changed or path_changed,
            "message": "",
        }

        if path_changed:
            result["message"] = (
                "Ruta del panel guardada. Ejecute en el servidor: "
                "sudo controlbox repair --apply-panel para reconstruir y reiniciar el panel."
            )
        elif port_changed:
            restarted = await self._restart_panel_service()
            result["applied"] = restarted
            result["message"] = (
                "Puerto del panel actualizado y servicio reiniciado."
                if restarted
                else "Puerto guardado. Reinicie el panel: sudo controlbox repair --apply-panel"
            )
        return result

    def _replace_env_value(self, content: str, key: str, value: str) -> tuple[str, bool]:
        pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
        if pattern.search(content):
            return pattern.sub(f"{key}={value}", content), True
        return content, False

    async def _restart_panel_service(self) -> bool:
        install_dir = self._settings.controlbox_install_dir
        env_file = f"{self._settings.platform_config_dir}/platform.env"
        compose = f"{install_dir}/docker-compose.yml"
        override = f"{install_dir}/docker-compose.override.yml"
        panel_build = f"{install_dir}/docker-compose.panel-build.yml"
        if not Path(compose).exists():
            return False
        cmd = ["docker", "compose", "--env-file", env_file, "-f", compose]
        if Path(override).exists():
            cmd.extend(["-f", override])
        if Path(panel_build).exists():
            cmd.extend(["-f", panel_build])
        cmd.extend(["up", "-d", "--force-recreate", "panel"])
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            logger.exception("Failed to restart panel service")
            return False
