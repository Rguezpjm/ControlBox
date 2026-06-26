import json
import urllib.request
import urllib.parse
from typing import Any


class XtreamCodesClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        # Standardize URL
        if not base_url.startswith("http://") and not base_url.startswith("https://"):
            base_url = f"http://{base_url}"
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password

    def _build_url(self, action: str | None = None) -> str:
        params = {
            "username": self.username,
            "password": self.password,
        }
        if action:
            params["action"] = action
        query = urllib.parse.urlencode(params)
        return f"{self.base_url}/player_api.php?{query}"

    def _fetch_json(self, url: str) -> Any:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read().decode("utf-8", errors="ignore")
            return json.loads(data)

    def authenticate(self) -> dict[str, Any]:
        """Authenticate and get profile/server info."""
        url = self._build_url()
        return self._fetch_json(url)

    def get_categories(self) -> list[dict[str, Any]]:
        """Fetch live stream categories."""
        url = self._build_url("get_live_categories")
        res = self._fetch_json(url)
        return res if isinstance(res, list) else []

    def get_streams(self) -> list[dict[str, Any]]:
        """Fetch live stream listings."""
        url = self._build_url("get_live_streams")
        res = self._fetch_json(url)
        return res if isinstance(res, list) else []

    def get_stream_url(self, stream_id: int) -> str:
        """Construct the direct playback stream URL."""
        return f"{self.base_url}/live/{self.username}/{self.password}/{stream_id}.ts"

    def fetch_as_catalog(self) -> list[dict[str, Any]]:
        """Converts Xtream live streams into the uniform catalog format."""
        try:
            categories = {c["category_id"]: c["category_name"] for c in self.get_categories()}
        except Exception:
            categories = {}

        try:
            streams = self.get_streams()
        except Exception:
            return []

        catalog = []
        for s in streams:
            stream_id = s.get("stream_id")
            if not stream_id:
                continue

            category_id = s.get("category_id")
            category_name = categories.get(category_id, "Uncategorized")

            catalog.append({
                "name": s.get("name", f"Channel {stream_id}"),
                "stream_url": self.get_stream_url(stream_id),
                "logo_url": s.get("stream_icon"),
                "epg_id": s.get("epg_channel_id"),
                "stream_id": int(stream_id),
                "category_name": category_name,
            })

        return catalog
