"""Celery application for sync worker."""

from celery import Celery
from celery.schedules import crontab

from recommendation_service.config import get_settings

settings = get_settings()

# Create Celery app
app = Celery(
    "sync_worker",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "sync_worker.tasks.sync_products",
        "sync_worker.tasks.sync_orders",
        "sync_worker.tasks.update_embeddings",
    ],
)

# Celery configuration
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes
    task_soft_time_limit=540,  # 9 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="sync",
    task_routes={
        "sync_worker.tasks.*": {"queue": "sync"},
    },
)

# Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Sync products every hour
    "sync-products": {
        "task": "sync_worker.tasks.sync_products.sync_products_from_ecommerce",
        "schedule": crontab(minute=0),  # Every hour at :00
    },
    # Sync orders every 30 minutes
    "sync-orders": {
        "task": "sync_worker.tasks.sync_orders.sync_orders_from_ecommerce",
        "schedule": crontab(minute="*/30"),
    },
    # Update product embeddings every 4 hours
    "update-embeddings": {
        "task": "sync_worker.tasks.update_embeddings.update_stale_embeddings",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    # Update user preference vectors every 2 hours
    "update-user-preferences": {
        "task": "sync_worker.tasks.update_embeddings.update_user_preferences_batch",
        "schedule": crontab(minute=30, hour="*/2"),
    },
    # Refresh analytics materialized views daily at 2 AM
    "refresh-analytics": {
        "task": "sync_worker.tasks.update_embeddings.refresh_analytics_views",
        "schedule": crontab(minute=0, hour=2),
    },
}


def run() -> None:
    """Run the Celery worker."""
    app.worker_main(["worker", "--loglevel=info", "-Q", "sync"])


if __name__ == "__main__":
    run()
