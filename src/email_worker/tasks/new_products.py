"""New products alert email tasks."""

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_new_products_alerts(self) -> dict:
    """
    Send new product alerts to users based on their interests.

    This task runs daily to:
    1. Find products added in the last 24 hours
    2. Match new products to user preferences
    3. Send personalized new product alerts

    Returns:
        dict: Summary of sent alerts
    """
    logger.info("Checking for new products to alert users about")

    # TODO: Implement actual logic

    return {
        "new_products_count": 0,
        "users_notified": 0,
        "emails_sent": 0,
    }
