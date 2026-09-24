from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Fixture, League, Standing, Team
from .tasks import sync_fixtures_task


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "matches-tests",
        }
    },
    TRACKED_LEAGUES=["39"],
)
class MatchesApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.league = League.objects.create(
            name="Premier League", slug="premier-league", external_id=39, country="England"
        )
        self.home_team = Team.objects.create(name="Home FC", slug="home-fc", external_id=1)
        self.away_team = Team.objects.create(name="Away FC", slug="away-fc", external_id=2)

    def provider_fixture(self, external_id=100):
        return {
            "external_id": external_id,
            "league": {
                "external_id": 39,
                "name": "Premier League",
                "country": "England",
                "logo_url": "",
            },
            "home_team": {"external_id": 1, "name": "Home FC", "crest_url": ""},
            "away_team": {"external_id": 2, "name": "Away FC", "crest_url": ""},
            "kickoff_at": timezone.now() + timedelta(hours=1),
            "status": "SCHEDULED",
            "minute": None,
            "home_score": None,
            "away_score": None,
            "matchday": "Regular Season - 1",
        }

    def test_repeated_fixture_sync_upserts_without_duplicates(self):
        with patch("matches.tasks.api_football.fetch_fixtures", return_value=[self.provider_fixture()]):
            self.assertEqual(sync_fixtures_task(), 1)
            self.assertEqual(sync_fixtures_task(), 1)

        self.assertEqual(Fixture.objects.filter(external_id=100).count(), 1)

    def test_live_endpoint_only_returns_live_and_halftime(self):
        Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=101,
            kickoff_at=timezone.now(),
            status=Fixture.Status.LIVE,
            minute=55,
            home_score=1,
            away_score=0,
        )
        Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=102,
            kickoff_at=timezone.now(),
            status=Fixture.Status.HALFTIME,
        )
        Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=103,
            kickoff_at=timezone.now(),
            status=Fixture.Status.FINISHED,
        )

        response = self.client.get(reverse("matches-live"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["external_id"] for item in response.json()}, {101, 102})

    def test_standings_are_ordered_by_position(self):
        Standing.objects.create(
            league=self.league, team=self.away_team, position=2, season="2026", points=10
        )
        Standing.objects.create(
            league=self.league, team=self.home_team, position=1, season="2026", points=12
        )

        response = self.client.get(reverse("matches-standings"), {"league": self.league.slug})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["position"] for item in response.json()], [1, 2])
