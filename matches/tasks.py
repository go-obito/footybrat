import logging

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Fixture, League, Standing, Team
from .services import api_football

logger = logging.getLogger(__name__)


def _tracked_league_ids():
    return [int(value) for value in settings.TRACKED_LEAGUES if str(value).strip().isdigit()]


def _current_season():
    return timezone.now().year


def _upsert_league(data):
    league, _ = League.objects.update_or_create(
        external_id=data["external_id"],
        defaults={
            "name": data["name"],
            "country": data.get("country", ""),
            "logo_url": data.get("logo_url", ""),
        },
    )
    return league


def _upsert_team(data):
    team, _ = Team.objects.update_or_create(
        external_id=data["external_id"],
        defaults={"name": data["name"], "crest_url": data.get("crest_url", "")},
    )
    return team


def _upsert_fixture(data):
    league = _upsert_league(data["league"])
    home_team = _upsert_team(data["home_team"])
    away_team = _upsert_team(data["away_team"])
    return Fixture.objects.update_or_create(
        external_id=data["external_id"],
        defaults={
            "league": league,
            "home_team": home_team,
            "away_team": away_team,
            "kickoff_at": data["kickoff_at"],
            "status": data["status"],
            "minute": data.get("minute"),
            "home_score": data.get("home_score"),
            "away_score": data.get("away_score"),
            "matchday": data.get("matchday", ""),
        },
    )[0]


def _sync_fixtures(items):
    with transaction.atomic():
        for item in items:
            _upsert_fixture(item)
    return len(items)


@shared_task
def sync_fixtures_task():
    total = 0
    for league_id in _tracked_league_ids():
        try:
            total += _sync_fixtures(api_football.fetch_fixtures(league_id, _current_season()))
        except api_football.ApiFootballError as exc:
            logger.warning("Fixture sync failed for league %s: %s", league_id, exc)
    return total


@shared_task
def sync_live_scores_task():
    try:
        items = api_football.fetch_live_fixtures()
        total = 0
        for item in items:
            fixture, created = Fixture.objects.get_or_create(
                external_id=item["external_id"],
                defaults={
                    "league": _upsert_league(item["league"]),
                    "home_team": _upsert_team(item["home_team"]),
                    "away_team": _upsert_team(item["away_team"]),
                    "kickoff_at": item["kickoff_at"],
                },
            )
            fixture.status = item["status"]
            fixture.minute = item.get("minute")
            fixture.home_score = item.get("home_score")
            fixture.away_score = item.get("away_score")
            fixture.save(update_fields=["status", "minute", "home_score", "away_score", "updated_at"])
            total += 1
        return total
    except api_football.ApiFootballError as exc:
        logger.warning("Live score sync failed: %s", exc)
        return 0


@shared_task
def sync_standings_task():
    total = 0
    for league_id in _tracked_league_ids():
        try:
            rows = api_football.fetch_standings(league_id, _current_season())
            for row in rows:
                league = _upsert_league(row["league"])
                team = _upsert_team(row["team"])
                Standing.objects.update_or_create(
                    league=league,
                    team=team,
                    season=row["season"],
                    defaults={key: row[key] for key in (
                        "position", "played", "won", "drawn", "lost", "points", "goal_difference",
                    )},
                )
                total += 1
        except api_football.ApiFootballError as exc:
            logger.warning("Standing sync failed for league %s: %s", league_id, exc)
    return total
