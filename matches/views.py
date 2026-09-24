from django.core.cache import cache
from django.utils.dateparse import parse_date
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from .models import Fixture, Standing
from .serializers import FixtureSerializer, StandingSerializer

LIVE_CACHE_KEY = "matches_live_fixtures"
LIVE_CACHE_TIMEOUT = 10
STANDINGS_CACHE_TIMEOUT = 300


class LiveFixturesView(ListAPIView):
    serializer_class = FixtureSerializer
    pagination_class = None

    def list(self, request, *args, **kwargs):
        try:
            cached = cache.get(LIVE_CACHE_KEY)
        except Exception:
            cached = None
        if cached is not None:
            from rest_framework.response import Response
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        try:
            cache.set(LIVE_CACHE_KEY, response.data, LIVE_CACHE_TIMEOUT)
        except Exception:
            pass
        return response

    def get_queryset(self):
        return Fixture.objects.select_related(
            "league", "home_team", "away_team"
        ).filter(status__in=[Fixture.Status.LIVE, Fixture.Status.HALFTIME]).order_by("kickoff_at")


class FixtureListView(ListAPIView):
    serializer_class = FixtureSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Fixture.objects.select_related(
            "league", "home_team", "away_team"
        ).all()
        league_slug = self.request.query_params.get("league")
        date_value = self.request.query_params.get("date")
        if league_slug:
            queryset = queryset.filter(league__slug=league_slug)
        if date_value:
            parsed_date = parse_date(date_value)
            if parsed_date:
                queryset = queryset.filter(kickoff_at__date=parsed_date)
        return queryset.order_by("kickoff_at")


class StandingListView(ListAPIView):
    serializer_class = StandingSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = Standing.objects.select_related("league", "team").all()
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
