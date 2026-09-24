import hashlib
from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.db.models import Count, Q
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.utils import timezone
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Article, ArticleView, Category, VideoPost
from .serializers import (
    ArticleHeadlineSerializer,
    ArticleSerializer,
    CategorySerializer,
    VideoPostSerializer,
)
from .tasks import TRENDING_CACHE_KEY, get_trending_payload

LATEST_CACHE_KEY = "articles_latest"
TOP_STORIES_CACHE_KEY = "articles_top_stories"
SEARCH_CACHE_TIMEOUT = 60


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ArticleSerializer
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Article.objects.select_related("category", "author").prefetch_related("tags").filter(
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )
        category_slug = self.request.query_params.get("category")
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset

    @action(detail=False, methods=["get"], url_path="latest", pagination_class=None)
    def latest(self, request):
        try:
            cached = cache.get(LATEST_CACHE_KEY)
        except Exception:
            cached = None
        if cached is None:
            articles = self.get_queryset().order_by("-published_at")[:10]
            cached = ArticleHeadlineSerializer(articles, many=True).data
            try:
                cache.set(LATEST_CACHE_KEY, cached, 60)
            except Exception:
                pass
        return Response(cached)

    @action(detail=False, methods=["get"], url_path="top-stories", pagination_class=None)
    def top_stories(self, request):
        try:
            cached = cache.get(TOP_STORIES_CACHE_KEY)
        except Exception:
            cached = None
        if cached is None:
            articles = self.get_queryset().filter(is_top_story=True).order_by(
                "top_story_order", "-published_at"
            )
            cached = self.get_serializer(articles, many=True).data
            try:
                cache.set(TOP_STORIES_CACHE_KEY, cached, 60)
            except Exception:
                pass
        return Response(cached)

    @action(detail=True, methods=["post"], url_path="view")
    def record_view(self, request, slug=None):
        article = self.get_object()
        visitor_data = f"{request.META.get('REMOTE_ADDR', '')}:{request.META.get('HTTP_USER_AGENT', '')}"
        visitor_hash = hashlib.sha256(visitor_data.encode()).hexdigest()
        viewed_since = timezone.now() - timedelta(minutes=30)

        if not ArticleView.objects.filter(
            article=article,
            visitor_hash=visitor_hash,
            viewed_at__gte=viewed_since,
        ).exists():
            ArticleView.objects.create(article=article, visitor_hash=visitor_hash)

        return Response(status=204)

    @action(detail=False, methods=["get"], url_path="trending", pagination_class=None)
    def trending(self, request):
        try:
            cached_articles = cache.get(TRENDING_CACHE_KEY)
        except Exception:
            cached_articles = None

        if cached_articles is None:
            cached_articles = get_trending_payload()

        return Response(cached_articles)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"


class VideoPostListView(generics.ListAPIView):
    serializer_class = VideoPostSerializer

    def get_queryset(self):
        return VideoPost.objects.select_related("category").filter(
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        ).order_by("-published_at", "-created_at")


class VideoPostDetailView(generics.RetrieveAPIView):
    serializer_class = VideoPostSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return VideoPost.objects.select_related("category").filter(
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )


class SearchView(generics.GenericAPIView):
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"detail": "The q query parameter is required."}, status=400)

        cache_key = f"search:{query.casefold()}"
        try:
            cached = cache.get(cache_key)
        except Exception:
            cached = None
        if cached is not None:
            return Response(cached)

        results = self._search(query)
        page = self.paginate_queryset(results)
        payload = [{"type": item["type"], **item["data"]} for item in page]
        response = self.get_paginated_response(payload)
        try:
            cache.set(cache_key, response.data, SEARCH_CACHE_TIMEOUT)
        except Exception:
            pass
        return response

    def _search(self, query):
        if connection.vendor == "postgresql":
            search_query = SearchQuery(query, config="simple", search_type="websearch")
            article_queryset = Article.objects.select_related("category").filter(
                published_at__isnull=False,
                published_at__lte=timezone.now(),
                search_vector=search_query,
            ).annotate(rank=SearchRank("search_vector", search_query))
            video_queryset = VideoPost.objects.select_related("category").filter(
                published_at__isnull=False,
                published_at__lte=timezone.now(),
                search_vector=search_query,
            ).annotate(rank=SearchRank("search_vector", search_query))
            article_items = [
                {"type": "article", "rank": float(item.rank), "data": ArticleHeadlineSerializer(item).data}
                for item in article_queryset
            ]
            video_items = [
                {"type": "video", "rank": float(item.rank), "data": VideoPostSerializer(item).data}
                for item in video_queryset
            ]
        else:
            terms = [term for term in query.casefold().split() if term]
            article_items = self._sqlite_results(
                Article.objects.select_related("category").filter(
                    published_at__isnull=False,
                    published_at__lte=timezone.now(),
                ),
                terms,
                ("title", "body"),
                ArticleHeadlineSerializer,
                "article",
            )
            video_items = self._sqlite_results(
                VideoPost.objects.select_related("category").filter(
                    published_at__isnull=False,
                    published_at__lte=timezone.now(),
                ),
                terms,
                ("title", "description"),
                VideoPostSerializer,
                "video",
            )

        return sorted(
            article_items + video_items,
            key=lambda item: (item["rank"], item["data"].get("published_at") or ""),
            reverse=True,
        )

    @staticmethod
    def _sqlite_results(queryset, terms, fields, serializer_class, result_type):
        matches = []
        for item in queryset:
            values = [getattr(item, field, "").casefold() for field in fields]
            rank = sum(
                value.count(term) * (2 if index == 0 else 1)
                for term in terms
                for index, value in enumerate(values)
            )
            if rank:
                matches.append({"type": result_type, "rank": rank, "data": serializer_class(item).data})
        return matches
