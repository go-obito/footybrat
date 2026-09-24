from django.urls import path

from .views import FixtureListView, LiveFixturesView, StandingListView

urlpatterns = [
    path("matches/live/", LiveFixturesView.as_view(), name="matches-live"),
    path("matches/fixtures/", FixtureListView.as_view(), name="matches-fixtures"),
    path("standings/", StandingListView.as_view(), name="matches-standings"),
]
