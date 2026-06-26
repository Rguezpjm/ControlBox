import re
import urllib.request
import unicodedata
from typing import Any


class M3uParser:
    @staticmethod
    def parse_m3u_content(content: str) -> list[dict[str, Any]]:
        channels = []
        current_channel: dict[str, Any] = {}

        def is_live_tv(url: str, name: str, category: str) -> bool:
            clean_url = url.split("?")[0].lower()
            vod_extensions = ('.mp4', '.mkv', '.avi', '.m4v', '.mov', '.flv', '.mpg', '.mpeg', '.wmv', '.3gp', '.webm')
            if clean_url.endswith(vod_extensions):
                return False
                
            vod_patterns = ('/movie/', '/movies/', '/series/', '/vod/')
            if any(pat in clean_url for pat in vod_patterns):
                return False
                
            def remove_accents(input_str: str) -> str:
                nfkd_form = unicodedata.normalize('NFKD', input_str)
                return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

            cat_lower = remove_accents(category.lower())
            vod_categories = (
                'movie', 'pelicula', 'cine', 'vod', 'series', 'temporada', 'season', 
                'episod', 'shows', 'show', 'estrenos', 'films', 'cinema', 'novela',
                'documental', 'documentales'
            )
            if any(pat in cat_lower for pat in vod_categories):
                # Fox Series, HBO Series, etc. are Live TV channels
                name_lower = remove_accents(name.lower())
                if any(live_word in name_lower for live_word in ('live', 'en vivo', 'envivo', 'directo', 'tv', 'hbo', 'fox')):
                    return True
                return False
            return True

        # Regex patterns to parse standard EXTINF attributes
        tvg_id_pat = re.compile(r'tvg-id="([^"]*)"', re.IGNORECASE)
        tvg_logo_pat = re.compile(r'tvg-logo="([^"]*)"', re.IGNORECASE)
        group_title_pat = re.compile(r'group-title="([^"]*)"', re.IGNORECASE)

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                # Parse metadata
                current_channel = {
                    "name": "",
                    "stream_url": "",
                    "logo_url": None,
                    "epg_id": None,
                    "category_name": "Uncategorized",
                }

                # Find commas, which separates attributes from channel name
                comma_idx = line.find(",")
                if comma_idx != -1:
                    current_channel["name"] = line[comma_idx + 1:].strip()
                    attrs_part = line[:comma_idx]
                else:
                    attrs_part = line

                # Match EPG ID
                m_id = tvg_id_pat.search(attrs_part)
                if m_id:
                    current_channel["epg_id"] = m_id.group(1)

                # Match logo
                m_logo = tvg_logo_pat.search(attrs_part)
                if m_logo:
                    current_channel["logo_url"] = m_logo.group(1)

                # Match group
                m_group = group_title_pat.search(attrs_part)
                if m_group:
                    current_channel["category_name"] = m_group.group(1)

            elif line.startswith("#"):
                # Other M3U tags (like #EXTGRP)
                if line.startswith("#EXTGRP:") and current_channel:
                    current_channel["category_name"] = line[8:].strip()
            else:
                # This line contains the stream URL
                if current_channel and current_channel.get("name"):
                    current_channel["stream_url"] = line
                    if is_live_tv(line, current_channel["name"], current_channel.get("category_name", "")):
                        channels.append(current_channel)
                    current_channel = {}
                elif not current_channel or not current_channel.get("name"):
                    # URL without preceding #EXTINF metadata — add as unnamed channel
                    name = line.rsplit("/", 1)[-1].split("?")[0] or "unknown"
                    if is_live_tv(line, name, "Uncategorized"):
                        channels.append({
                            "name": name,
                            "stream_url": line,
                            "logo_url": None,
                            "epg_id": None,
                            "category_name": "Uncategorized",
                        })
                    current_channel = {}

        return channels

    @classmethod
    def parse_from_url(cls, url: str) -> list[dict[str, Any]]:
        # Fetch M3U over HTTP
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode("utf-8", errors="ignore")
        return cls.parse_m3u_content(content)
