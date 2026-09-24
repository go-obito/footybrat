from django.urls import path

from .views import SubscribeView

urlpatterns = [
    path("newsletter/subscribe/", SubscribeView.as_view(), name="newsletter-subscribe"),
]
