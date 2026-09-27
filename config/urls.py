"""
URL configuration for the FootyBrat project.
"""
from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

from .api import router

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/", include("articles.urls")),
    path("api/", include("matches.urls")),
    path("api/", include("ticker.urls")),
    path("api/", include("newsletter.urls")),
    path("api/", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
