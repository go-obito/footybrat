import logging
from datetime import datetime, time, timedelta

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max, Min
from django.utils import timezone

from .models import Fixture, League, Standing, Team
from .leagues import get_active_tracked_leagues
from .realtime import (
    LIVE_FIXTURES_CACHE_KEY,
    invalidate_and_publish_after_commit,
)
from .services import api_football

logger = logging.getLogger(__name__)


def _current_season(league_id=None, on_date=None):
    today = on_date or timezone.localdate()
    for start, end in settings.SEASONAL_LEAGUES.get(league_id, ()):
        if start <= today <= end:
            return start.year
    return today.year if today.month >= 7 else today.year - 1


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


def get_today_match_window(today=None):
    today = today or timezone.localdate()
    league_ids = get_active_tracked_leagues(today)
    if not league_ids:
        return None

    midnight = timezone.make_aware(
        datetime.combine(today, time.min),
        timezone.get_current_timezone(),
    )
    kickoffs = Fixture.objects.filter(
        league__external_id__in=league_ids,
        kickoff_at__gte=midnight - timedelta(hours=2, minutes=30),
        kickoff_at__lt=midnight + timedelta(days=1),
    ).aggregate(first=Min("kickoff_at"), last=Max("kickoff_at"))
    if not kickoffs["first"] or not kickoffs["last"]:
        return None
    return (
        kickoffs["first"] - timedelta(minutes=15),
        kickoffs["last"] + timedelta(hours=2, minutes=30),
    )


@shared_task
def sync_daily_fixtures_task():
    league_ids = get_active_tracked_leagues()
    if not league_ids:
        return 0

    items = []
    today = timezone.localdate()
    for league_id in league_ids:
        try:
            items.extend(
                item
                for item in api_football.fetch_fixtures(
                    league_id,
                    today,
                    season=_current_season(league_id, today),
                )
                if int(item["league"]["external_id"]) == league_id
            )
        except api_football.ApiFootballError as exc:
            # Do not discard successful fixture results for other leagues.
            logger.warning(
                "Daily fixture sync failed for league %s: %s",
                league_id,
                exc,
            )
            continue

    total = _sync_fixtures(items)
    if total:
        invalidate_and_publish_after_commit("fixtures", [LIVE_FIXTURES_CACHE_KEY])
    return total


@shared_task
def sync_live_scores_task():
    league_ids = get_active_tracked_leagues()
    if not league_ids:
        return 0

    now = timezone.now()

    try:
        items = [
            item
            for item in api_football.fetch_live_fixtures(league_ids)
            if int(item["league"]["external_id"]) in league_ids
        ]
        active_fixture_ids = []
        with transaction.atomic():
            for item in items:
                fixture = _upsert_fixture(item)
                active_fixture_ids.append(fixture.external_id)

            finished_count = Fixture.objects.filter(
                league__external_id__in=league_ids,
                kickoff_at__date__in=[timezone.localdate(), timezone.localdate() - timedelta(days=1)],
                status__in=[Fixture.Status.LIVE, Fixture.Status.HALFTIME],
            ).exclude(external_id__in=active_fixture_ids).update(
                status=Fixture.Status.FINISHED,
                minute=None,
                updated_at=now,
            )
            if active_fixture_ids or finished_count:
                invalidate_and_publish_after_commit("live_scores", [LIVE_FIXTURES_CACHE_KEY])
        return len(active_fixture_ids)
    except api_football.ApiFootballError as exc:
        logger.warning("Live score sync failed: %s", exc)
        return 0
    except Exception:
        logger.exception("Live score sync failed unexpectedly")
        return 0


@shared_task
def sync_standings_task():
    total = 0
    changed_cache_keys = {"matches_standings:all"}
    league_ids = get_active_tracked_leagues()
    if not league_ids:
        return 0
    for league_id in league_ids:
        try:
            rows = api_football.fetch_standings(league_id, _current_season(league_id))
            if not rows:
                logger.info("No standings available for league %s", league_id)
                continue
            with transaction.atomic():
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
                    changed_cache_keys.add(f"matches_standings:{league.slug}")
                    total += 1
        except api_football.ApiFootballError as exc:
            logger.warning("Standing sync failed for league %s: %s", league_id, exc)
    if total:
        invalidate_and_publish_after_commit("standings", sorted(changed_cache_keys))
    return total


sync_fixtures_task = sync_daily_fixtures_task
