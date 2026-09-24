from datetime import timedelta

from celery import shared_task
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

from .models import Article, ArticleView
from .serializers import ArticleHeadlineSerializer

TRENDING_CACHE_KEY = "trending_articles"


def get_trending_queryset():
    cutoff = timezone.now() - timedelta(days=7)
    return (
        Article.objects.select_related("category")
        .filter(published_at__isnull=False, published_at__lte=timezone.now())
        .annotate(view_count=Count("views", filter=Q(views__viewed_at__gte=cutoff)))
        .filter(view_count__gt=0)
        .order_by("-view_count", "-published_at", "-pk")[:10]
    )


def get_trending_payload():
    return ArticleHeadlineSerializer(get_trending_queryset(), many=True).data


@shared_task
def recompute_trending():
    payload = get_trending_payload()
    cache.set(TRENDING_CACHE_KEY, payload, timeout=60 * 60)
    return len(payload)


@shared_task
def cleanup_old_article_views():
    cutoff = timezone.now() - timedelta(days=30)
    deleted, _ = ArticleView.objects.filter(viewed_at__lt=cutoff).delete()
    return deleted