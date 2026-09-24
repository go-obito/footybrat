from django.urls import path

from .views import TickerEntryListView

urlpatterns = [
    path("ticker/", TickerEntryListView.as_view(), name="ticker-list"),
]