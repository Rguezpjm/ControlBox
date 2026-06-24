from controlbox.shared.infrastructure.celery.app import celery_app


@celery_app.task(name="security.run_vulnerability_scan")
def run_vulnerability_scan(scan_id: str, tenant_id: str, target: str, tools: list[str], options: dict | None = None) -> None:
    from datetime import datetime, timezone

    from controlbox.config.settings import get_settings
    from controlbox.modules.security.infrastructure import scanner
    from controlbox.modules.security.infrastructure.scan_store import SyncScanStore

    settings = get_settings()
    store = SyncScanStore(settings)
    scan = store.get(tenant_id, scan_id) or {
        "id": scan_id,
        "tenant_id": tenant_id,
        "target": target,
        "tools": tools,
    }

    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    scan["status"] = "running"
    scan["started_at"] = now()
    store.save(tenant_id, scan)

    try:
        results = [scanner.run_tool(tool_id, target, options) for tool_id in tools]
        aggregated = scanner.aggregate(results)
        scan.update(aggregated)
        scan["status"] = "completed"
        scan["finished_at"] = now()
    except Exception as exc:  # noqa: BLE001
        scan["status"] = "failed"
        scan["error"] = str(exc)[:500]
        scan["finished_at"] = now()

    store.save(tenant_id, scan)
