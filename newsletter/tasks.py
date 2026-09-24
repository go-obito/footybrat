import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def sync_to_esp(subscriber_id=None):
    logger.info("ESP sync stub called for subscriber %s", subscriber_id or "all")
    return None
