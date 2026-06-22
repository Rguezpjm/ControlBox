import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, WebSocket, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from controlbox.config.settings import get_settings
from controlbox.modules.identity.api.dependencies import AppState, validate_csrf
from controlbox.modules.identity.api.router import router as identity_router
from controlbox.modules.websites.api.router import router as websites_router
from controlbox.modules.databases.api.router import router as databases_router
from controlbox.modules.supabase.api.router import router as supabase_router
from controlbox.modules.dns.api.router import router as dns_router
from controlbox.modules.dns.api.public_router import public_router as dns_public_router
from controlbox.modules.files.api.router import router as files_router
from controlbox.modules.ftp.api.router import router as ftp_router
from controlbox.modules.backups.api.router import router as backups_router
from controlbox.modules.backups.infrastructure.scheduler import BackupScheduler
from controlbox.modules.monitoring.api.router import monitoring_websocket, router as monitoring_router
from controlbox.modules.monitoring.infrastructure.broadcaster import MonitoringBroadcaster
from controlbox.modules.monitoring.infrastructure.service import MonitoringCollectorTask
from controlbox.modules.wordpress.api.router import router as wordpress_router
from controlbox.modules.team_members.api.router import router as team_router
from controlbox.modules.staging_sites.api.router import router as staging_router
from controlbox.modules.platform.api.router import router as platform_router
from controlbox.modules.security.api.router import router as security_router
from controlbox.modules.identity.api.schemas import ErrorResponseSchema, HealthResponseSchema
from controlbox.modules.identity.domain.services import TokenService
from controlbox.modules.identity.infrastructure.unit_of_work import Database
from controlbox.shared.domain.base import DomainException
from controlbox.shared.infrastructure.logging_config import setup_logging
from controlbox.shared.infrastructure.metrics import increment_errors, increment_requests, router as metrics_router
from controlbox.shared.infrastructure.redis.client import RedisClient, SessionCache
from controlbox.shared.infrastructure.security.middleware import SecurityMiddleware
from controlbox.version import __version__


logger = logging.getLogger("controlbox")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    database = Database(settings)
    redis_client = RedisClient(settings)
    session_cache = SessionCache(redis_client, settings)
    token_service = TokenService(settings)

    app.state.container = AppState(
        settings=settings,
        database=database,
        redis_client=redis_client,
        session_cache=session_cache,
        token_service=token_service,
    )

    scheduler = BackupScheduler(database, settings, redis_client)
    scheduler_task = asyncio.create_task(scheduler.run())

    monitoring_broadcaster = MonitoringBroadcaster()
    monitoring_collector = MonitoringCollectorTask(database, redis_client, settings, monitoring_broadcaster)
    monitoring_task = asyncio.create_task(monitoring_collector.run())
    app.state.monitoring_broadcaster = monitoring_broadcaster
    app.state.monitoring_collector = monitoring_collector

    logger.info("ControlBox API started", extra={"environment": settings.app_env})
    yield

    scheduler.stop()
    scheduler_task.cancel()
    monitoring_collector.stop()
    monitoring_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    try:
        await monitoring_task
    except asyncio.CancelledError:
        pass

    await database.dispose()
    await redis_client.close()
    logger.info("ControlBox API stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
        dependencies=[Depends(validate_csrf)],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "X-RateLimit-Remaining"],
    )

    app.add_middleware(SecurityMiddleware)

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        increment_requests()
        response = await call_next(request)
        if response.status_code >= 400:
            increment_errors()
        return response

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        status_map = {
            "not_found": status.HTTP_404_NOT_FOUND,
            "conflict": status.HTTP_409_CONFLICT,
            "unauthorized": status.HTTP_401_UNAUTHORIZED,
            "forbidden": status.HTTP_403_FORBIDDEN,
            "validation_error": status.HTTP_422_UNPROCESSABLE_ENTITY,
        }
        return JSONResponse(
            status_code=status_map.get(exc.code, status.HTTP_400_BAD_REQUEST),
            content=ErrorResponseSchema(error=exc.message, code=exc.code).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponseSchema(
                error="Validation failed",
                code="validation_error",
                detail=str(exc.errors()),
            ).model_dump(),
        )

    @app.get("/health", response_model=HealthResponseSchema, tags=["health"])
    async def health_check(request: Request) -> HealthResponseSchema:
        container: AppState = request.app.state.container
        postgres_status = "unhealthy"
        redis_status = "unhealthy"

        try:
            if await container.database.health_check():
                postgres_status = "healthy"
        except Exception:
            postgres_status = "unhealthy"

        try:
            if await container.redis_client.ping():
                redis_status = "healthy"
        except Exception:
            redis_status = "unhealthy"

        overall = "healthy" if postgres_status == "healthy" and redis_status == "healthy" else "degraded"

        return HealthResponseSchema(
            status=overall,
            app=container.settings.app_name,
            environment=container.settings.app_env,
            postgres=postgres_status,
            redis=redis_status,
        )

    app.include_router(metrics_router)
    app.include_router(identity_router, prefix=settings.app_api_prefix)
    app.include_router(websites_router, prefix=settings.app_api_prefix)
    app.include_router(databases_router, prefix=settings.app_api_prefix)
    app.include_router(supabase_router, prefix=settings.app_api_prefix)
    app.include_router(dns_router, prefix=settings.app_api_prefix)
    app.include_router(dns_public_router, prefix=settings.app_api_prefix)
    app.include_router(files_router, prefix=settings.app_api_prefix)
    app.include_router(ftp_router, prefix=settings.app_api_prefix)
    app.include_router(backups_router, prefix=settings.app_api_prefix)
    app.include_router(monitoring_router, prefix=settings.app_api_prefix)
    app.include_router(security_router, prefix=settings.app_api_prefix)
    app.include_router(wordpress_router, prefix=settings.app_api_prefix)
    app.include_router(team_router, prefix=settings.app_api_prefix)
    app.include_router(staging_router, prefix=settings.app_api_prefix)
    app.include_router(platform_router, prefix=settings.app_api_prefix)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, token: str | None = None):
        container: AppState = app.state.container
        await monitoring_websocket(
            websocket,
            token,
            container,
            app.state.monitoring_broadcaster,
            container.session_cache,
            container.token_service,
        )

    return app


app = create_app()
