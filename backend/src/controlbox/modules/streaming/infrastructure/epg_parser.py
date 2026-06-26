import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import urllib.request
from typing import Any


class EpgParser:
    @staticmethod
    def parse_xmltv_time(time_str: str) -> datetime:
        # Example format: "20260624180000 +0000" or "20260624180000"
        parts = time_str.split()
        raw_dt = parts[0]
        tz_offset = parts[1] if len(parts) > 1 else "+0000"

        # Parse basic ISO-like format
        dt = datetime.strptime(raw_dt[:14], "%Y%m%d%H%M%S")

        # Parse timezone offset
        try:
            sign = 1 if tz_offset[0] == "+" else -1
            hours = int(tz_offset[1:3])
            minutes = int(tz_offset[3:5])
            tz = timezone(offset=timezone.utc.tzname(None) if sign * (hours * 60 + minutes) == 0 else None)
            # Actually, standard timezone creation:
            from datetime import timedelta
            tz = timezone(timedelta(hours=sign * hours, minutes=sign * minutes))
            return dt.replace(tzinfo=tz)
        except Exception:
            return dt.replace(tzinfo=timezone.utc)

    @classmethod
    def parse_xmltv_content(cls, content: bytes) -> list[dict[str, Any]]:
        # Parse XML tree
        root = ET.fromstring(content)
        programs = []

        for program_node in root.findall("programme"):
            channel_id = program_node.get("channel")
            start_str = program_node.get("start")
            stop_str = program_node.get("stop")

            if not channel_id or not start_str or not stop_str:
                continue

            title_node = program_node.find("title")
            title = title_node.text if title_node is not None else "No Title"

            desc_node = program_node.find("desc")
            desc = desc_node.text if desc_node is not None else ""

            start_time = cls.parse_xmltv_time(start_str)
            end_time = cls.parse_xmltv_time(stop_str)

            programs.append({
                "channel_epg_id": channel_id,
                "title": title,
                "description": desc,
                "start_time": start_time,
                "end_time": end_time,
            })

        return programs

    @classmethod
    def parse_from_url(cls, url: str) -> list[dict[str, Any]]:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read()

        # Check if gzipped
        if url.endswith(".gz") or content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)

        return cls.parse_xmltv_content(content)
