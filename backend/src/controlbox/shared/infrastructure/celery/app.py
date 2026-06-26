from celery import Celery

from controlbox.config.settings import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        "controlbox",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=[
            "controlbox.modules.wordpress.workers.tasks",
            "controlbox.modules.joomla.workers.tasks",
            "controlbox.modules.staging_sites.workers.tasks",
            "controlbox.modules.security.workers.tasks",
            "controlbox.modules.streaming.workers.tasks",
        ],
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
    )
    return app


celery_app = create_celery_app()
