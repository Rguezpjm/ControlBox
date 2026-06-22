from dataclasses import dataclass

from controlbox.modules.dns.domain.entities import DnsRecord, DnsRecordType


@dataclass
class ParsedZone:
    origin: str
    ttl: int
    records: list[DnsRecord]
    soa_email: str = "hostmaster"


def parse_zone_file(content: str, default_origin: str | None = None) -> ParsedZone:
    origin = default_origin or ""
    ttl = 3600
    records: list[DnsRecord] = []
    soa_email = "hostmaster"

    for raw_line in content.splitlines():
        line = raw_line.split(";")[0].strip()
        if not line:
            continue
        if line.startswith("$ORIGIN"):
            origin = line.split()[1].rstrip(".").lower()
            continue
        if line.startswith("$TTL"):
            ttl = int(line.split()[1])
            continue

        parts = line.split()
        if len(parts) < 3:
            continue

        idx = 0
        if parts[0].isdigit():
            ttl = int(parts[0])
            idx = 1
        if idx < len(parts) and parts[idx].upper() in ("IN",):
            idx += 1

        name = parts[idx]
        idx += 1
        if idx < len(parts) and parts[idx].upper() in ("IN",):
            idx += 1
        if idx >= len(parts):
            continue

        rtype = parts[idx].upper()
        idx += 1
        if idx >= len(parts):
            continue

        if rtype == "SOA":
            if len(parts) > idx + 6:
                soa_email = parts[idx + 1].rstrip(".").replace(".", "@", 1)
            continue

        if rtype not in {t.value for t in DnsRecordType}:
            continue

        content_parts = parts[idx:]
        priority = None
        if rtype == "MX" and content_parts[0].isdigit():
            priority = int(content_parts[0])
            content_parts = content_parts[1:]
        elif rtype == "SRV" and len(content_parts) >= 4:
            priority = int(content_parts[0])
            content_parts = content_parts

        content = " ".join(content_parts).rstrip(".")
        if rtype in ("CNAME", "MX", "NS", "SRV") and " " not in content and not content.endswith("."):
            content = f"{content}."

        record_name = name.rstrip(".")
        if record_name == "@":
            record_name = origin
        elif not record_name.endswith(origin) and "." not in record_name:
            record_name = f"{record_name}.{origin}"

        records.append(
            DnsRecord(
                name=record_name,
                type=DnsRecordType(rtype),
                content=content,
                ttl=ttl,
                priority=priority,
            )
        )

    if not origin:
        raise ValueError("Zone file must contain $ORIGIN or provide default origin")

    return ParsedZone(origin=origin, ttl=ttl, records=records, soa_email=soa_email)


def export_zone_file(zone_name: str, serial: int, soa_email: str, nameservers: list[str], records: list[DnsRecord], default_ttl: int = 3600) -> str:
    lines = [
        f"$ORIGIN {zone_name}.",
        f"$TTL {default_ttl}",
        "",
        f"@  IN  SOA {nameservers[0] if nameservers else f'ns1.{zone_name}.'} {soa_email}.{zone_name}. (",
        f"    {serial} ; serial",
        "    3600       ; refresh",
        "    1800       ; retry",
        "    1209600    ; expire",
        "    3600 )     ; minimum",
        "",
    ]

    for ns in nameservers:
        lines.append(f"@  IN  NS  {ns if ns.endswith('.') else ns + '.'}")

    lines.append("")

    for record in sorted(records, key=lambda r: (r.type.value, r.name)):
        rel_name = _relative_name(record.name, zone_name)
        content = record.content
        if record.type in (DnsRecordType.CNAME, DnsRecordType.MX, DnsRecordType.NS):
            if not content.endswith("."):
                content = f"{content}."
        if record.type == DnsRecordType.MX and record.priority is not None:
            content = f"{record.priority} {content}"
        if record.type == DnsRecordType.SRV:
            content = record.content

        lines.append(f"{rel_name:<20} {record.ttl}  IN  {record.type.value:<6} {content}")

    return "\n".join(lines) + "\n"


def _relative_name(name: str, zone: str) -> str:
    name = name.rstrip(".")
    zone = zone.rstrip(".")
    if name == zone:
        return "@"
    if name.endswith(f".{zone}"):
        return name[: -(len(zone) + 1)]
    return name
