import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.files.infrastructure.filesystem_service import PathResolver
from controlbox.modules.ftp.domain.entities import FtpAccount, FtpLogEntry
from controlbox.modules.ftp.infrastructure.platform_env import is_ftp_service_enabled, read_platform_env_value
from controlbox.shared.domain.base import ValidationError
from controlbox.shared.infrastructure.docker.env import docker_subprocess_env, validate_container_name

LOG_PATTERNS = [
    re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\s+"
        r"(?P<user>\S+)\s+(?P<action>UPLOAD|DOWNLOAD|LOGIN|LOGOUT|DELETE|RENAME|MKDIR|RMDIR)\s+"
        r"(?P<path>\S+)?\s*(?P<bytes>\d+)?\s*(?P<ip>\d+\.\d+\.\d+\.\d+)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\[(?P<ts>\d{2}:\d{2}:\d{2})\]\s+\[FTP session \d+\]\s+"
        r"(?P<action>UPLOAD|DOWNLOAD|LOGIN|LOGOUT)\s+(?P<status>OK|FAIL):\s+"
        r"(?P<path>[^\s]+)?\s*\((?P<user>\S+)@(?P<ip>[^)]+)\)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
        r"(?P<host>\S+)\s+(?P<bytes>\d+)\s+(?P<path>\S+)\s+"
        r"(?P<type>\w+)\s+(?P<action>\w)\s+(?P<direction>\w)\s+"
        r"(?P<mode>\w)\s+(?P<user>\S+)",
        re.IGNORECASE,
    ),
]

XFERLOG_ACTIONS = {
    "a": "append",
    "b": "download",
    "d": "delete",
    "l": "login",
    "r": "rename",
    "s": "upload",
    "u": "upload",
}


class PureFtpdProvisioner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._resolver = PathResolver(settings)

    def resolve_home(self, tenant_id: UUID, relative_directory: str) -> Path:
        directory = self._resolver.resolve(tenant_id, relative_directory)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    async def create_user(self, account: FtpAccount, plain_password: str) -> None:
        home = str(self.resolve_home(account.tenant_id, account.home_directory))
        args = self._useradd_args(account.system_username, home, account)
        await self._run_pure_pw("useradd", args, plain_password)

    async def update_user(self, account: FtpAccount) -> None:
        home = str(self.resolve_home(account.tenant_id, account.home_directory))
        args = self._usermod_args(account.system_username, home, account)
        await self._run_pure_pw("usermod", args)

    async def change_password(self, account: FtpAccount, plain_password: str) -> None:
        await self._run_pure_pw("passwd", [account.system_username, "-m"], plain_password)

    async def delete_user(self, system_username: str) -> None:
        await self._run_pure_pw("userdel", [system_username, "-m"])

    async def user_exists(self, system_username: str) -> bool:
        try:
            output = await self._run_pure_pw("show", [system_username], capture=True)
            return bool(output.strip())
        except Exception:
            return False

    async def service_status(self) -> dict[str, str | bool]:
        if not is_ftp_service_enabled(self._settings):
            return {"enabled": False, "status": "disabled", "host": self._settings.pureftpd_host}
        if self._settings.pureftpd_use_docker:
            try:
                container = validate_container_name(self._settings.pureftpd_container)
                proc = await asyncio.create_subprocess_exec(
                    "docker", "inspect", "-f", "{{.State.Running}}", container,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=docker_subprocess_env(self._settings),
                )
                stdout, _ = await proc.communicate()
                running = stdout.decode().strip() == "true"
                return {
                    "enabled": True,
                    "status": "running" if running else "stopped",
                    "host": self._settings.pureftpd_host,
                    "port": self._settings.pureftpd_port,
                }
            except Exception:
                return {"enabled": True, "status": "unavailable", "host": self._settings.pureftpd_host}
        return {"enabled": True, "status": "configured", "host": self._settings.pureftpd_host}

    def _useradd_args(self, username: str, home: str, account: FtpAccount) -> list[str]:
        args = [
            username,
            "-u", str(account.uid),
            "-g", str(account.gid),
            "-d", home,
            "-m",
        ]
        args.extend(self._quota_args(account))
        return args

    def _usermod_args(self, username: str, home: str, account: FtpAccount) -> list[str]:
        args = [username, "-d", home, "-m"]
        args.extend(self._quota_args(account))
        return args

    def _quota_args(self, account: FtpAccount) -> list[str]:
        args: list[str] = []
        if account.quota_mb > 0:
            args.extend(["-N", str(account.quota_mb)])
        if account.max_files > 0:
            args.extend(["-n", str(account.max_files)])
        if account.upload_bandwidth_kbps > 0 or account.download_bandwidth_kbps > 0:
            up = account.upload_bandwidth_kbps or 1
            down = account.download_bandwidth_kbps or 1
            args.extend(["-t", f"{up}:{down}"])
        return args

    async def _run_pure_pw(
        self,
        action: str,
        args: list[str],
        password: str | None = None,
        capture: bool = False,
    ) -> str:
        if not is_ftp_service_enabled(self._settings):
            return ""

        base_cmd = self._build_command(action, args)
        proc = await asyncio.create_subprocess_exec(
            *base_cmd,
            stdin=asyncio.subprocess.PIPE if password else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=docker_subprocess_env(self._settings),
        )
        stdout, stderr = await proc.communicate(
            input=password.encode() if password else None
        )
        if proc.returncode != 0:
            message = stderr.decode().strip() or stdout.decode().strip() or f"pure-pw {action} failed"
            raise ValidationError(message)
        return stdout.decode()

    def _build_command(self, action: str, args: list[str]) -> list[str]:
        pure_pw_args = ["pure-pw", action, *args]
        if self._settings.pureftpd_use_docker:
            container = validate_container_name(self._settings.pureftpd_container)
            return ["docker", "exec", "-i", container, *pure_pw_args]
        if self._settings.pureftpd_passwd_file:
            pure_pw_args.extend(["-f", self._settings.pureftpd_passwd_file])
        return pure_pw_args


class FtpLogReader:
    def __init__(self, settings: Settings) -> None:
        self._log_path = Path(settings.pureftpd_log_path)

    def read_logs(
        self,
        system_usernames: set[str],
        username_map: dict[str, str],
        limit: int = 100,
        account_filter: str | None = None,
    ) -> list[FtpLogEntry]:
        if not self._log_path.exists():
            return []

        entries: list[FtpLogEntry] = []
        try:
            lines = self._log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

        for line in reversed(lines):
            entry = self._parse_line(line.strip())
            if not entry:
                continue
            if entry.username not in system_usernames:
                continue
            if account_filter and entry.username != account_filter:
                continue
            entry.username = username_map.get(entry.username, entry.username)
            entries.append(entry)
            if len(entries) >= limit:
                break

        return list(reversed(entries))

    def _parse_line(self, line: str) -> FtpLogEntry | None:
        if not line:
            return None

        for pattern in LOG_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            groups = match.groupdict()
            return self._build_entry(groups, line)

        if " FTP command:" in line and "USER " in line:
            user_match = re.search(r'USER\s+(\S+)', line)
            ip_match = re.search(r'Client\s+"([^"]+)"', line)
            if user_match:
                return FtpLogEntry(
                    timestamp=datetime.now(timezone.utc),
                    username=user_match.group(1),
                    action="login",
                    path=None,
                    bytes_transferred=0,
                    ip_address=ip_match.group(1) if ip_match else None,
                    status="ok",
                )
        return None

    def _build_entry(self, groups: dict[str, str | None], line: str) -> FtpLogEntry | None:
        username = groups.get("user")
        if not username:
            return None

        action = (groups.get("action") or "unknown").lower()
        if len(action) == 1 and action in XFERLOG_ACTIONS:
            action = XFERLOG_ACTIONS[action]

        ts = self._parse_timestamp(groups)
        bytes_val = int(groups["bytes"]) if groups.get("bytes") and groups["bytes"].isdigit() else 0

        return FtpLogEntry(
            timestamp=ts,
            username=username,
            action=action,
            path=groups.get("path"),
            bytes_transferred=bytes_val,
            ip_address=groups.get("ip"),
            status=(groups.get("status") or "ok").lower(),
        )

    def _parse_timestamp(self, groups: dict[str, str | None]) -> datetime:
        if groups.get("ts"):
            raw = groups["ts"]
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%H:%M:%S"):
                try:
                    parsed = datetime.strptime(raw, fmt)
                    if fmt == "%H:%M:%S":
                        now = datetime.now()
                        parsed = parsed.replace(year=now.year, month=now.month, day=now.day)
                    return parsed.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        if groups.get("month") and groups.get("day") and groups.get("time"):
            try:
                raw = f"{groups['month']} {groups['day']} {groups['time']} {datetime.now().year}"
                parsed = datetime.strptime(raw, "%b %d %H:%M:%S %Y")
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)
