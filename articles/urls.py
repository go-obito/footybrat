from django.urls import path

from .views import (
    HealthCheckView,
    SearchView,
    VideoPostDetailView,
    VideoPostListView,
)

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("videos/", VideoPostListView.as_view(), name="video-list"),
    path("videos/<slug:slug>/", VideoPostDetailView.as_view(), name="video-detail"),
    path("search/", SearchView.as_view(), name="search"),
]
