from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from .leagues import get_active_tracked_leagues
from .models import Fixture, League, Standing, Team
from .realtime import LIVE_FIXTURES_CACHE_KEY
from .serializers import (
    FixtureSerializer,
    LeagueSerializer,
    StandingSerializer,
    TeamSerializer,
)

LIVE_CACHE_TIMEOUT = 10
STANDINGS_CACHE_TIMEOUT = 300


class FixtureViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public fixture data comes only from FootyBrat's database.

    This endpoint never calls API-Football; Celery is the only API-Football caller.
    """

    queryset = Fixture.objects.select_related("home_team", "away_team", "league").all()
    serializer_class = FixtureSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_value = self.request.query_params.get("status")
        league_slug = self.request.query_params.get("league")
        date_value = self.request.query_params.get("date")

        if status_value:
            queryset = queryset.filter(status__iexact=status_value)
        if league_slug:
            queryset = queryset.filter(league__slug=league_slug)

        if date_value and date_value.lower() == "today":
            queryset = queryset.filter(kickoff_at__date=timezone.localdate())
        elif date_value:
            parsed_date = parse_date(date_value)
            if parsed_date:
                queryset = queryset.filter(kickoff_at__date=parsed_date)

        return queryset


class LeagueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public league data comes only from FootyBrat's database.

    This endpoint never calls API-Football; Celery is the only API-Football caller.
    """

    queryset = League.objects.all()
    serializer_class = LeagueSerializer
    lookup_field = "slug"


class StandingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public standing data comes only from FootyBrat's database.

    This endpoint never calls API-Football; Celery is the only API-Football caller.
    """

    queryset = Standing.objects.select_related("league", "team").all()
    serializer_class = StandingSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        league_slug = self.request.query_params.get("league")
        season = self.request.query_params.get("season")

        if league_slug:
            queryset = queryset.filter(league__slug=league_slug)
        if season:
            queryset = queryset.filter(season=season)

        return queryset


class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public team data comes only from FootyBrat's database.

    This endpoint never calls API-Football; Celery is the only API-Football caller.
    """

    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    lookup_field = "slug"


class LiveFixturesView(ListAPIView):
    serializer_class = FixtureSerializer
    pagination_class = None

    def list(self, request, *args, **kwargs):
        try:
            cached = cache.get(LIVE_FIXTURES_CACHE_KEY)
        except Exception:
            cached = None
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        try:
            cache.set(LIVE_FIXTURES_CACHE_KEY, response.data, LIVE_CACHE_TIMEOUT)
        except Exception:
            pass
        return response

    def get_queryset(self):
        now = timezone.now()
        queryset = Fixture.objects.select_related(
            "league", "home_team", "away_team"
        ).filter(
            league__external_id__in=get_active_tracked_leagues(),
            status__in=[Fixture.Status.LIVE, Fixture.Status.HALFTIME],
            kickoff_at__gte=now - timedelta(hours=4),
            kickoff_at__lte=now + timedelta(minutes=15),
        )
        return queryset.order_by("kickoff_at")


class FixtureListView(ListAPIView):
    serializer_class = FixtureSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Fixture.objects.select_related(
            "league", "home_team", "away_team"
        ).filter(league__external_id__in=get_active_tracked_leagues())
        league_slug = self.request.query_params.get("league")
        date_value = self.request.query_params.get("date")
        if league_slug:
            queryset = queryset.filter(league__slug=league_slug)
        if date_value and date_value.lower() == "today":
            queryset = queryset.filter(kickoff_at__date=timezone.localdate())
        elif date_value:
            parsed_date = parse_date(date_value)
            if parsed_date:
                queryset = queryset.filter(kickoff_at__date=parsed_date)
        return queryset.order_by("kickoff_at")


class StandingListView(ListAPIView):
    serializer_class = StandingSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Standing.objects.select_related("league", "team").filter(
            league__external_id__in=get_active_tracked_leagues()
        )
        league_slug = self.request.query_params.get("league")
        if league_slug:
            queryset = queryset.filter(league__slug=league_slug)
        return queryset.order_by("position")

    def list(self, request, *args, **kwargs):
        league_slug = request.query_params.get("league", "all")
        cache_key = f"matches_standings:{league_slug}"
        try:
            cached = cache.get(cache_key)
        except Exception:
            cached = None
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        try:
            cache.set(cache_key, response.data, STANDINGS_CACHE_TIMEOUT)
        except Exception:
            pass
        return response
