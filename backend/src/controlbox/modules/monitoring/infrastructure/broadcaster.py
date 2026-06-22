from datetime import datetime, timezone
from uuid import UUID

from fastapi import WebSocket


class MonitoringBroadcaster:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = {}

    async def connect(self, tenant_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(tenant_id, set()).add(websocket)

    def disconnect(self, tenant_id: UUID, websocket: WebSocket) -> None:
        conns = self._connections.get(tenant_id)
        if conns:
            conns.discard(websocket)
            if not conns:
                del self._connections[tenant_id]

    def active_tenants(self) -> set[UUID]:
        return set(self._connections.keys())

    async def broadcast(self, tenant_id: UUID, payload: dict) -> None:
        conns = self._connections.get(tenant_id, set()).copy()
        dead: list[WebSocket] = []
        message = {
            "type": "metric",
            "resource": "monitoring",
            "resource_id": "snapshot",
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(tenant_id, ws)

    async def broadcast_alert(self, tenant_id: UUID, payload: dict) -> None:
        conns = self._connections.get(tenant_id, set()).copy()
        dead: list[WebSocket] = []
        message = {
            "type": "alert",
            "resource": "platform",
            "resource_id": payload.get("id", "resource"),
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(tenant_id, ws)
