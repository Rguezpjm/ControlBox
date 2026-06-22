import time

from fastapi import APIRouter, Response

router = APIRouter(tags=["metrics"])

_start_time = time.time()
_request_count = 0
_error_count = 0


def increment_requests() -> None:
    global _request_count
    _request_count += 1


def increment_errors() -> None:
    global _error_count
    _error_count += 1


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    uptime = int(time.time() - _start_time)
    body = "\n".join(
        [
            "# HELP controlbox_uptime_seconds Uptime in seconds",
            "# TYPE controlbox_uptime_seconds gauge",
            f"controlbox_uptime_seconds {uptime}",
            "# HELP controlbox_http_requests_total Total HTTP requests",
            "# TYPE controlbox_http_requests_total counter",
            f"controlbox_http_requests_total {_request_count}",
            "# HELP controlbox_http_errors_total Total HTTP errors",
            "# TYPE controlbox_http_errors_total counter",
            f"controlbox_http_errors_total {_error_count}",
        ]
    )
    return Response(content=body + "\n", media_type="text/plain; version=0.0.4")
