from celery import Celery

from app.config import settings

celery_app = Celery(
    "ai_job_tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=2,
)

# Auto-discover tasks in ai_agent module
celery_app.autodiscover_tasks(["app.ai_agent"])
