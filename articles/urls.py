from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ArticleViewSet,
    CategoryViewSet,
    HealthCheckView,
    SearchView,
    VideoPostDetailView,
    VideoPostListView,
)

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("videos/", VideoPostListView.as_view(), name="video-list"),
    path("videos/<slug:slug>/", VideoPostDetailView.as_view(), name="video-detail"),
    path("search/", SearchView.as_view(), name="search"),
    path("", include(router.urls)),
]
