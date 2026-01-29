"""Celery application for email worker."""

from celery import Celery
from celery.schedules import crontab

from recommendation_service.config import get_settings

settings = get_settings()

# Create Celery app
app = Celery(
    "email_worker",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "email_worker.tasks.cart_abandonment",
        "email_worker.tasks.new_products",
        "email_worker.tasks.weekly_digest",
        "email_worker.tasks.personalized_picks",
        "email_worker.tasks.back_in_stock",
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
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="email",
    task_routes={
        "email_worker.tasks.*": {"queue": "email"},
    },
)

# Beat schedule for periodic tasks
app.conf.beat_schedule = {
    # Check for abandoned carts every 15 minutes
    "check-abandoned-carts": {
        "task": "email_worker.tasks.cart_abandonment.check_abandoned_carts",
        "schedule": crontab(minute="*/15"),
    },
    # Send weekly digest on Sundays at 10 AM
    "send-weekly-digest": {
        "task": "email_worker.tasks.weekly_digest.send_weekly_digest_batch",
        "schedule": crontab(hour=10, minute=0, day_of_week=0),
    },
    # Check for new products daily at 10 AM
    "check-new-products": {
        "task": "email_worker.tasks.new_products.send_new_products_alerts",
        "schedule": crontab(hour=10, minute=0),
    },
    # Check for personalized picks opportunities every 6 hours
    "check-personalized-picks": {
        "task": "email_worker.tasks.personalized_picks.check_personalized_picks_opportunities",
        "schedule": crontab(minute=0, hour="*/6"),
    },
}


def run() -> None:
    """Run the Celery worker."""
    app.worker_main(["worker", "--loglevel=info", "-Q", "email"])


if __name__ == "__main__":
    run()
