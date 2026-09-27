from datetime import date, datetime, time, timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Fixture, League, Standing, Team
from .leagues import get_active_tracked_leagues
from .services import api_football
from .tasks import (
    _current_season,
    get_today_match_window,
    sync_daily_fixtures_task,
    sync_live_scores_task,
)


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
            self.assertEqual(sync_daily_fixtures_task(), 1)
            self.assertEqual(sync_daily_fixtures_task(), 1)

        self.assertEqual(Fixture.objects.filter(external_id=100).count(), 1)

    def test_fixture_sync_filters_unselected_leagues(self):
        unselected = self.provider_fixture(external_id=200)
        unselected["league"]["external_id"] = 999
        with patch(
            "matches.tasks.api_football.fetch_fixtures",
            return_value=[self.provider_fixture(), unselected],
        ):
            self.assertEqual(sync_daily_fixtures_task(), 1)

        self.assertFalse(Fixture.objects.filter(external_id=200).exists())

    def test_live_sync_skips_api_when_no_fixture_is_nearby(self):
        with patch("matches.tasks.api_football.fetch_live_fixtures") as fetch_live:
            self.assertEqual(sync_live_scores_task(), 0)

        fetch_live.assert_not_called()

    def test_live_sync_persists_only_selected_leagues(self):
        Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=99,
            kickoff_at=timezone.now() + timedelta(minutes=5),
            status=Fixture.Status.SCHEDULED,
        )
        selected = self.provider_fixture(external_id=100)
        selected["kickoff_at"] = timezone.now() + timedelta(minutes=5)
        selected["status"] = Fixture.Status.LIVE
        unselected = self.provider_fixture(external_id=200)
        unselected["league"]["external_id"] = 999

        with patch(
            "matches.tasks.api_football.fetch_live_fixtures",
            return_value=[selected, unselected],
        ):
            self.assertEqual(sync_live_scores_task(), 1)

        self.assertEqual(Fixture.objects.get(external_id=100).status, Fixture.Status.LIVE)
        self.assertFalse(Fixture.objects.filter(external_id=200).exists())

    def test_live_sync_only_calls_inside_computed_window(self):
        kickoff = timezone.now() + timedelta(hours=1)
        Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=98,
            kickoff_at=kickoff,
            status=Fixture.Status.SCHEDULED,
        )
        window_start, window_end = get_today_match_window()
        self.assertEqual(window_start, kickoff - timedelta(minutes=15))
        self.assertEqual(window_end, kickoff + timedelta(hours=2, minutes=30))

        with patch("matches.tasks.timezone.now", return_value=window_start - timedelta(seconds=1)):
            with patch("matches.tasks.api_football.fetch_live_fixtures") as fetch_live:
                self.assertEqual(sync_live_scores_task(), 0)
        fetch_live.assert_not_called()

        with patch("matches.tasks.timezone.now", return_value=window_start + timedelta(seconds=1)):
            with patch("matches.tasks.api_football.fetch_live_fixtures", return_value=[]) as fetch_live:
                self.assertEqual(sync_live_scores_task(), 0)
        fetch_live.assert_called_once_with([39])

    def test_live_fixture_missing_from_bulk_response_is_finished(self):
        fixture = Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=97,
            kickoff_at=timezone.now() - timedelta(minutes=40),
            status=Fixture.Status.LIVE,
            minute=40,
            home_score=1,
            away_score=0,
        )

        with patch("matches.tasks.api_football.fetch_live_fixtures", return_value=[]):
            self.assertEqual(sync_live_scores_task(), 0)

        fixture.refresh_from_db()
        self.assertEqual(fixture.status, Fixture.Status.FINISHED)
        self.assertIsNone(fixture.minute)

    def test_match_window_includes_a_fixture_crossing_midnight(self):
        today = timezone.localdate()
        kickoff = timezone.make_aware(
            datetime.combine(today - timedelta(days=1), time(23, 30)),
            timezone.get_current_timezone(),
        )
        Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=96,
            kickoff_at=kickoff,
            status=Fixture.Status.LIVE,
        )

        window = get_today_match_window(today)

        self.assertEqual(window, (kickoff - timedelta(minutes=15), kickoff + timedelta(hours=2, minutes=30)))

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

    def test_fixtures_endpoint_returns_only_todays_active_league_fixtures(self):
        Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=104,
            kickoff_at=timezone.now() + timedelta(hours=1),
            status=Fixture.Status.SCHEDULED,
        )
        other_league = League.objects.create(name="Other League", slug="other-league", external_id=999)
        Fixture.objects.create(
            league=other_league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=105,
            kickoff_at=timezone.now() + timedelta(hours=2),
            status=Fixture.Status.SCHEDULED,
        )

        response = self.client.get(
            reverse("matches-fixtures"),
            {"date": "today"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["external_id"] for item in response.json()], [104])

    def test_daily_api_request_limit_blocks_the_next_request(self):
        response = Mock()
        response.json.return_value = {"response": []}
        with override_settings(
            API_FOOTBALL_KEY="test-key",
            DAILY_REQUEST_BUDGET=2,
            DAILY_REQUEST_HEADROOM=1,
        ):
            with patch("matches.services.api_football.requests.get", return_value=response) as request:
                api_football._request("fixtures")
                with self.assertRaises(api_football.RequestBudgetExceeded):
                    api_football._request("fixtures")

        self.assertEqual(request.call_count, 1)

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

    def test_admin_index_displays_request_budget(self):
        user = get_user_model().objects.create_superuser(
            username="quota-admin",
            email="quota@example.test",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "API-Football request budget")
        self.assertContains(response, "0 / 100")


class TrackedLeagueTests(SimpleTestCase):
    @override_settings(
        TRACKED_LEAGUES=["39", "6", "140"],
        SEASONAL_LEAGUES={6: [(date(2027, 6, 19), date(2027, 7, 17))]},
    )
    def test_afcon_is_excluded_outside_tournament_window(self):
        self.assertEqual(get_active_tracked_leagues(date(2027, 6, 18)), [39, 140])

    @override_settings(
        TRACKED_LEAGUES=["39", "6", "140"],
        SEASONAL_LEAGUES={6: [(date(2027, 6, 19), date(2027, 7, 17))]},
    )
    def test_afcon_is_included_during_tournament_window(self):
        self.assertEqual(get_active_tracked_leagues(date(2027, 7, 1)), [39, 6, 140])

    @override_settings(
        SEASONAL_LEAGUES={6: [(date(2025, 12, 21), date(2026, 1, 18))]},
    )
    def test_season_uses_tournament_and_european_season_start_years(self):
        self.assertEqual(_current_season(6, date(2026, 1, 10)), 2025)
        self.assertEqual(_current_season(39, date(2026, 1, 10)), 2025)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "api-budget-tests",
        }
    },
)
class ApiRequestBudgetTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_budget_counter_resets_on_new_day(self):
        today = date(2026, 9, 27)
        tomorrow = date(2026, 9, 28)
        with override_settings(DAILY_REQUEST_BUDGET=100, DAILY_REQUEST_HEADROOM=10):
            with patch("matches.services.api_football.timezone.localdate", return_value=today):
                cache.set(api_football._request_counter_key(), 90, timeout=3600)
                self.assertFalse(api_football.can_make_request())
            with patch("matches.services.api_football.timezone.localdate", return_value=tomorrow):
                self.assertTrue(api_football.can_make_request())

    def test_new_counter_migrates_known_same_day_usage(self):
        today = date(2026, 9, 27)
        with override_settings(DAILY_REQUEST_BUDGET=100, DAILY_REQUEST_HEADROOM=10):
            with patch("matches.services.api_football.timezone.localdate", return_value=today):
                cache.set(f"api_football_requests:{today.isoformat()}", 20, timeout=3600)
                self.assertEqual(api_football.get_requests_used_today(), 20)
                self.assertTrue(api_football._record_api_request("fixtures"))
                self.assertEqual(api_football.get_requests_used_today(), 21)

    def test_nine_leagues_reserve_only_seventy_two_live_requests(self):
        with override_settings(DAILY_REQUEST_BUDGET=100, DAILY_REQUEST_HEADROOM=10):
            self.assertEqual(api_football.get_live_poll_budget(9), 72)

    def test_bulk_live_request_uses_one_hyphen_separated_league_filter(self):
        with patch("matches.services.api_football._request", return_value=[]) as request:
            self.assertEqual(api_football.fetch_live_fixtures([39, 2, 6]), [])

        request.assert_called_once_with("fixtures", category="live", live="2-6-39")


    def test_public_fixture_api_supports_status_and_league_filters(self):
        live = Fixture.objects.create(
            league=self.league,
            home_team=self.home_team,
            away_team=self.away_team,
            external_id=300,
            kickoff_at=timezone.now(),
            status=Fixture.Status.LIVE,
            minute=64,
            home_score=2,
            away_score=1,
        )
        response = self.client.get("/api/fixtures/?status=live&league=premier-league")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["external_id"] for item in response.json()["results"]], [live.external_id])

    def test_public_standings_api_supports_league_filter(self):
        Standing.objects.create(
            league=self.league,
            team=self.home_team,
            position=1,
            season="2026",
            points=12,
        )
        response = self.client.get("/api/standings/?league=premier-league")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["league"]["slug"], "premier-league")
