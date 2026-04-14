from celery import Celery
from .config import settings

celery_app = Celery(
    "jrnys",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "mammoth.tasks.mammoth_tasks",
        "quest.tasks.quest_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Beat schedule – equivalent to PHP Scheduler / cron
    beat_schedule={
        "quest-collect-results-every-hour": {
            "task": "quest.tasks.quest_tasks.collect_results",
            "schedule": 3600.0,  # every hour
        },
    },
)
