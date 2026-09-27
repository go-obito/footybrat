import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

PUBLIC_CONTENT_GROUP = "public_content_updates"
LIVE_FIXTURES_CACHE_KEY = "matches_live_fixtures"


def publish_content_update(resource):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        async_to_sync(channel_layer.group_send)(
            PUBLIC_CONTENT_GROUP,
            {
                "type": "content_update",
                "resource": resource,
                "updated_at": timezone.now().isoformat(),
            },
        )
    except Exception:
        logger.exception("Failed to publish %s content update", resource)


def invalidate_and_publish_after_commit(resource, cache_keys):
    def invalidate_and_publish():
        try:
            cache.delete_many(cache_keys)
        except Exception:
            logger.exception("Failed to invalidate cache before %s update", resource)
            return
        publish_content_update(resource)

    transaction.on_commit(invalidate_and_publish, robust=True)