from django.urls import path

from .consumers import PublicUpdatesConsumer

websocket_urlpatterns = [
    path("ws/updates/", PublicUpdatesConsumer.as_asgi()),
]