from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Article
from .views import LATEST_CACHE_KEY, TOP_STORIES_CACHE_KEY


@receiver([post_save, post_delete], sender=Article)
def invalidate_article_list_caches(sender, **kwargs):
    try:
        cache.delete_many([LATEST_CACHE_KEY, TOP_STORIES_CACHE_KEY])
    except Exception:
        pass
