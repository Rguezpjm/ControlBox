import asyncio
import json
import shutil
import tarfile
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from uuid import UUID

from controlbox.config.settings import Settings
from controlbox.modules.backups.domain.entities import BackupSourceType
from controlbox.modules.databases.domain.entities import BackupStatus, BackupType, DatabaseBackup
from controlbox.modules.databases.infrastructure.provisioner import DatabaseProvisioner
from controlbox.modules.dns.infrastructure.powerdns_client import PowerDnsClient
from controlbox.modules.dns.infrastructure.zone_file import export_zone_file
from controlbox.shared.domain.base import NotFoundError, ValidationError


class BackupExecutor(ABC):
    @abstractmethod
    async def backup(
        self,
        tenant_id: UUID,
        resource_id: UUID | None,
        work_dir: Path,
    ) -> tuple[Path, str, dict]:
        raise NotImplementedError

    @abstractmethod
    async def restore(
        self,
        tenant_id: UUID,
        resource_id: UUID | None,
        archive_path: Path,
    ) -> None:
        raise NotImplementedError


class WebsiteBackupExecutor(BackupExecutor):
    def __init__(self, settings: Settings, websites_repo) -> None:
        self._settings = settings
        self._websites = websites_repo

    async def backup(self, tenant_id: UUID, resource_id: UUID | None, work_dir: Path) -> tuple[Path, str, dict]:
        if not resource_id:
            raise ValidationError("Website resource_id is required")

        website = await self._websites.get_by_id_and_tenant(resource_id, tenant_id)
        if not website:
            raise NotFoundError("Website not found")

        site_path = Path(self._settings.sites_base_path) / str(tenant_id) / str(resource_id)
        if not site_path.exists():
            site_path.mkdir(parents=True, exist_ok=True)

        archive = work_dir / f"website-{resource_id}.tar.gz"
        manifest = {
            "source_type": BackupSourceType.WEBSITES.value,
            "resource_id": str(resource_id),
            "resource_name": website.name,
            "domain": website.domain,
            "created_at": datetime.utcnow().isoformat(),
        }
        (work_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        def _archive() -> None:
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(work_dir / "manifest.json", arcname="manifest.json")
                if site_path.exists():
                    tar.add(site_path, arcname="site")

        await asyncio.to_thread(_archive)
        return archive, website.name, manifest

    async def restore(self, tenant_id: UUID, resource_id: UUID | None, archive_path: Path) -> None:
        if not resource_id:
            raise ValidationError("Website resource_id is required")

        website = await self._websites.get_by_id_and_tenant(resource_id, tenant_id)
        if not website:
            raise NotFoundError("Website not found")

        site_path = Path(self._settings.sites_base_path) / str(tenant_id) / str(resource_id)

        def _extract() -> None:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(path=tmp_path)
                extracted = tmp_path / "site"
                if extracted.exists():
                    if site_path.exists():
                        shutil.rmtree(site_path)
                    shutil.move(str(extracted), str(site_path))

        await asyncio.to_thread(_extract)


class DatabaseBackupExecutor(BackupExecutor):
    def __init__(self, settings: Settings, databases_repo, database_backups_repo) -> None:
        self._settings = settings
        self._databases = databases_repo
        self._database_backups = database_backups_repo
        self._provisioner = DatabaseProvisioner(settings)

    async def backup(self, tenant_id: UUID, resource_id: UUID | None, work_dir: Path) -> tuple[Path, str, dict]:
        if not resource_id:
            raise ValidationError("Database resource_id is required")

        database = await self._databases.get_by_id_and_tenant(resource_id, tenant_id)
        if not database:
            raise NotFoundError("Database not found")

        backup = DatabaseBackup(
            database_id=database.id,
            tenant_id=tenant_id,
            name=f"cb-backup-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            backup_type=BackupType.MANUAL,
            status=BackupStatus.PENDING,
        )
        backup.file_path = str(
            self._provisioner.backup_path(tenant_id, database.id, backup.id, database.engine)
        )
        await self._provisioner.run_backup(database, backup)

        source = Path(backup.file_path)
        archive = work_dir / source.name
        await asyncio.to_thread(shutil.copy2, source, archive)
        if source.exists():
            await asyncio.to_thread(source.unlink)

        manifest = {
            "source_type": BackupSourceType.DATABASES.value,
            "resource_id": str(resource_id),
            "resource_name": database.name,
            "engine": database.engine.value,
            "database_name": database.database_name,
        }
        return archive, database.name, manifest

    async def restore(self, tenant_id: UUID, resource_id: UUID | None, archive_path: Path) -> None:
        if not resource_id:
            raise ValidationError("Database resource_id is required")

        database = await self._databases.get_by_id_and_tenant(resource_id, tenant_id)
        if not database:
            raise NotFoundError("Database not found")

        backup = DatabaseBackup(
            database_id=database.id,
            tenant_id=tenant_id,
            name="restore",
            backup_type=BackupType.MANUAL,
            status=BackupStatus.COMPLETED,
            file_path=str(archive_path),
        )
        await self._provisioner.run_restore(database, backup)


class DnsBackupExecutor(BackupExecutor):
    def __init__(self, settings: Settings, dns_zones_repo) -> None:
        self._settings = settings
        self._zones = dns_zones_repo
        self._client = PowerDnsClient(settings)

    async def backup(self, tenant_id: UUID, resource_id: UUID | None, work_dir: Path) -> tuple[Path, str, dict]:
        zones = await self._zones.list_by_tenant(tenant_id)
        if resource_id:
            zone = await self._zones.get_by_id_and_tenant(resource_id, tenant_id)
            if not zone:
                raise NotFoundError("DNS zone not found")
            zones = [zone]

        export_data: list[dict] = []
        for zone in zones:
            records = await self._client.list_records(zone.name)
            zone_file = export_zone_file(
                zone.name, zone.serial, zone.soa_email, zone.nameservers, records, zone.default_ttl
            )
            export_data.append({
                "zone": zone.name,
                "serial": zone.serial,
                "soa_email": zone.soa_email,
                "nameservers": zone.nameservers,
                "default_ttl": zone.default_ttl,
                "records": [
                    {
                        "name": r.name,
                        "type": r.type.value,
                        "content": r.content,
                        "ttl": r.ttl,
                        "priority": r.priority,
                    }
                    for r in records
                ],
                "zone_file": zone_file,
            })

        payload = {
            "source_type": BackupSourceType.DNS.value,
            "tenant_id": str(tenant_id),
            "zones": export_data,
            "created_at": datetime.utcnow().isoformat(),
        }
        json_path = work_dir / "dns-export.json"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        archive = work_dir / "dns-backup.tar.gz"

        def _archive() -> None:
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(json_path, arcname="dns-export.json")

        await asyncio.to_thread(_archive)
        name = zones[0].name if len(zones) == 1 else f"{len(zones)}-zones"
        return archive, name, {"zone_count": len(zones)}

    async def restore(self, tenant_id: UUID, resource_id: UUID | None, archive_path: Path) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            def _extract() -> Path:
                with tarfile.open(archive_path, "r:gz") as tar:
                    tar.extractall(path=tmp_path)
                return tmp_path / "dns-export.json"

            json_path = await asyncio.to_thread(_extract)
            data = json.loads(json_path.read_text(encoding="utf-8"))

            for zone_data in data.get("zones", []):
                zone_name = zone_data["zone"]
                zone = await self._zones.get_by_name(zone_name, tenant_id)
                if not zone:
                    continue
                from controlbox.modules.dns.domain.entities import DnsRecord, DnsRecordType

                records = [
                    DnsRecord(
                        name=r["name"],
                        type=DnsRecordType(r["type"]),
                        content=r["content"],
                        ttl=r.get("ttl", 3600),
                        priority=r.get("priority"),
                    )
                    for r in zone_data.get("records", [])
                ]
                await self._client.replace_records(zone.name, records)


class ConfigurationBackupExecutor(BackupExecutor):
    def __init__(
        self,
        settings: Settings,
        websites_repo,
        dns_zones_repo,
        ftp_accounts_repo,
        managed_databases_repo,
    ) -> None:
        self._settings = settings
        self._websites = websites_repo
        self._dns_zones = dns_zones_repo
        self._ftp_accounts = ftp_accounts_repo
        self._databases = managed_databases_repo

    async def backup(self, tenant_id: UUID, resource_id: UUID | None, work_dir: Path) -> tuple[Path, str, dict]:
        websites = await self._websites.list_by_tenant(tenant_id)
        zones = await self._dns_zones.list_by_tenant(tenant_id)
        ftp_accounts = await self._ftp_accounts.list_by_tenant(tenant_id)
        databases = await self._databases.list_by_tenant(tenant_id)

        payload = {
            "source_type": BackupSourceType.CONFIGURATIONS.value,
            "tenant_id": str(tenant_id),
            "created_at": datetime.utcnow().isoformat(),
            "websites": [
                {
                    "id": str(w.id),
                    "name": w.name,
                    "domain": w.domain,
                    "runtime": w.runtime.value,
                    "runtime_version": w.runtime_version,
                    "ssl_enabled": w.ssl_enabled,
                    "database_engine": w.database_engine.value,
                    "settings": w.settings,
                }
                for w in websites
            ],
            "dns_zones": [
                {
                    "id": str(z.id),
                    "name": z.name,
                    "soa_email": z.soa_email,
                    "default_ttl": z.default_ttl,
                    "nameservers": z.nameservers,
                }
                for z in zones
            ],
            "ftp_accounts": [
                {
                    "id": str(a.id),
                    "username": a.username,
                    "home_directory": a.home_directory,
                    "quota_mb": a.quota_mb,
                    "max_files": a.max_files,
                }
                for a in ftp_accounts
            ],
            "databases": [
                {
                    "id": str(d.id),
                    "name": d.name,
                    "engine": d.engine.value,
                    "database_name": d.database_name,
                }
                for d in databases
            ],
        }

        json_path = work_dir / "config-export.json"
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        archive = work_dir / "config-backup.tar.gz"

        def _archive() -> None:
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(json_path, arcname="config-export.json")

        await asyncio.to_thread(_archive)
        return archive, "tenant-config", {"item_count": len(websites) + len(zones) + len(ftp_accounts) + len(databases)}

    async def restore(self, tenant_id: UUID, resource_id: UUID | None, archive_path: Path) -> None:
        raise ValidationError("Configuration restore is export-only; review config-export.json manually")


class BackupExecutorFactory:
    def __init__(self, uow, settings: Settings) -> None:
        self._uow = uow
        self._settings = settings

    def get(self, source_type: BackupSourceType) -> BackupExecutor:
        if source_type == BackupSourceType.WEBSITES:
            return WebsiteBackupExecutor(self._settings, self._uow.websites)
        if source_type == BackupSourceType.DATABASES:
            return DatabaseBackupExecutor(self._settings, self._uow.managed_databases, self._uow.database_backups)
        if source_type == BackupSourceType.DNS:
            return DnsBackupExecutor(self._settings, self._uow.dns_zones)
        if source_type == BackupSourceType.CONFIGURATIONS:
            return ConfigurationBackupExecutor(
                self._settings,
                self._uow.websites,
                self._uow.dns_zones,
                self._uow.ftp_accounts,
                self._uow.managed_databases,
            )
        raise ValidationError(f"No executor for {source_type}")
