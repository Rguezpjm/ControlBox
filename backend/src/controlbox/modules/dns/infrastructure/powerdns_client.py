from dataclasses import dataclass
from typing import Any

import httpx

from controlbox.config.settings import Settings
from controlbox.modules.dns.domain.entities import DnsRecord, DnsRecordType, DnsZone


@dataclass
class PowerDnsRrset:
    name: str
    type: str
    ttl: int
    records: list[dict]


class PowerDnsClient:
    _shared_client: httpx.AsyncClient | None = None

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.powerdns_api_url.rstrip("/")
        self._server_id = settings.powerdns_server_id
        self._api_key = settings.powerdns_api_key
        self._default_ns = settings.powerdns_nameservers_list

    @classmethod
    def _client(cls) -> httpx.AsyncClient:
        if cls._shared_client is None or cls._shared_client.is_closed:
            cls._shared_client = httpx.AsyncClient(timeout=30)
        return cls._shared_client

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self._api_key,
            "Content-Type": "application/json",
        }

    def _zone_id(self, zone_name: str) -> str:
        return zone_name if zone_name.endswith(".") else f"{zone_name}."

    async def create_zone(self, zone: DnsZone) -> None:
        nameservers = zone.nameservers or self._default_ns
        ns_rrsets = [
            {
                "name": self._zone_id(zone.name),
                "type": "NS",
                "ttl": zone.default_ttl,
                "records": [{"content": ns if ns.endswith(".") else f"{ns}.", "disabled": False}],
            }
            for ns in nameservers
        ]
        payload = {
            "name": self._zone_id(zone.name),
            "kind": "Native",
            "nameservers": [ns if ns.endswith(".") else f"{ns}." for ns in nameservers],
            "rrsets": ns_rrsets,
        }
        client = self._client()
        response = await client.post(
            f"{self._base_url}/api/v1/servers/{self._server_id}/zones",
            headers=self._headers(),
            json=payload,
        )
        if response.status_code not in (200, 201, 409):
            raise RuntimeError(f"PowerDNS create zone failed: {response.text}")

    async def delete_zone(self, zone_name: str) -> None:
        client = self._client()
        response = await client.delete(
            f"{self._base_url}/api/v1/servers/{self._server_id}/zones/{self._zone_id(zone_name)}",
            headers=self._headers(),
        )
        if response.status_code not in (200, 204, 404):
            raise RuntimeError(f"PowerDNS delete zone failed: {response.text}")

    async def get_zone(self, zone_name: str) -> dict:
        client = self._client()
        response = await client.get(
            f"{self._base_url}/api/v1/servers/{self._server_id}/zones/{self._zone_id(zone_name)}",
            headers=self._headers(),
        )
        if response.status_code == 404:
            raise RuntimeError("Zone not found in PowerDNS")
        if response.status_code != 200:
            raise RuntimeError(f"PowerDNS get zone failed: {response.text}")
        return response.json()

    async def list_records(self, zone_name: str) -> list[DnsRecord]:
        data = await self.get_zone(zone_name)
        records: list[DnsRecord] = []
        zone_base = zone_name.rstrip(".")

        for rrset in data.get("rrsets", []):
            rtype = rrset.get("type", "")
            if rtype in ("SOA",) or rrset.get("type") == "NS" and rrset.get("name", "").rstrip(".") == zone_base:
                continue
            name = rrset.get("name", "").rstrip(".")
            ttl = rrset.get("ttl", 3600)
            for rec in rrset.get("records", []):
                if rec.get("disabled"):
                    continue
                content = rec.get("content", "")
                priority = None
                if rtype == "MX":
                    parts = content.split(" ", 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        priority = int(parts[0])
                        content = parts[1].rstrip(".")
                elif rtype == "SRV":
                    pass
                else:
                    content = content.rstrip(".")
                records.append(
                    DnsRecord(
                        name=name,
                        type=DnsRecordType(rtype),
                        content=content,
                        ttl=ttl,
                        priority=priority,
                    )
                )
        return records

    async def replace_records(self, zone_name: str, records: list[DnsRecord]) -> None:
        rrsets = self._records_to_rrsets(records)
        await self._patch_zone(zone_name, rrsets)

    async def upsert_record(self, zone_name: str, record: DnsRecord) -> None:
        rrset = self._record_to_rrset(record)
        await self._patch_zone(zone_name, [rrset])

    async def delete_record(self, zone_name: str, name: str, record_type: str) -> None:
        fqdn = name if name.endswith(".") else f"{name}."
        payload = {
            "rrsets": [
                {
                    "name": fqdn,
                    "type": record_type.upper(),
                    "changetype": "DELETE",
                }
            ]
        }
        await self._patch_zone_raw(zone_name, payload)

    async def import_records(self, zone_name: str, records: list[DnsRecord]) -> None:
        if records:
            await self.replace_records(zone_name, records)

    def _records_to_rrsets(self, records: list[DnsRecord]) -> list[dict]:
        grouped: dict[tuple[str, str], list[DnsRecord]] = {}
        for record in records:
            key = (record.name, record.type.value)
            grouped.setdefault(key, []).append(record)

        rrsets = []
        for (name, rtype), recs in grouped.items():
            rrsets.append(self._merge_rrset(name, rtype, recs))
        return rrsets

    def _record_to_rrset(self, record: DnsRecord) -> dict:
        return self._merge_rrset(record.name, record.type.value, [record])

    def _merge_rrset(self, name: str, rtype: str, records: list[DnsRecord]) -> dict:
        fqdn = name if name.endswith(".") else f"{name}."
        ttl = records[0].ttl
        pdns_records = []
        for rec in records:
            content = self._format_content(rec)
            pdns_records.append({"content": content, "disabled": rec.disabled})
        return {
            "name": fqdn,
            "type": rtype,
            "ttl": ttl,
            "changetype": "REPLACE",
            "records": pdns_records,
        }

    def _format_content(self, record: DnsRecord) -> str:
        content = record.content
        if record.type == DnsRecordType.MX:
            priority = record.priority or 10
            target = content if content.endswith(".") else f"{content}."
            return f"{priority} {target}"
        if record.type in (DnsRecordType.CNAME, DnsRecordType.NS):
            return content if content.endswith(".") else f"{content}."
        if record.type == DnsRecordType.SRV:
            if record.priority is not None and not content[0].isdigit():
                return f"{record.priority} {content}"
            return content
        if record.type == DnsRecordType.CAA:
            return content if content.startswith('"') else content
        return content

    async def _patch_zone(self, zone_name: str, rrsets: list[dict]) -> None:
        payload = {"rrsets": rrsets}
        await self._patch_zone_raw(zone_name, payload)

    async def _patch_zone_raw(self, zone_name: str, payload: dict) -> None:
        client = self._client()
        response = await client.patch(
            f"{self._base_url}/api/v1/servers/{self._server_id}/zones/{self._zone_id(zone_name)}",
            headers=self._headers(),
            json=payload,
        )
        if response.status_code not in (200, 204):
            raise RuntimeError(f"PowerDNS patch zone failed: {response.text}")

    async def health_check(self) -> bool:
        try:
            client = self._client()
            response = await client.get(
                f"{self._base_url}/api/v1/servers",
                headers=self._headers(),
                timeout=5,
            )
            return response.status_code == 200
        except Exception:
            return False
