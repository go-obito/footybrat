import logging
from math import ceil
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


def _live_poll_interval(now, window_end, active_league_count):
    remaining_calls = api_football.get_live_poll_budget(active_league_count)
    if remaining_calls <= 0:
        return None
    remaining_seconds = max(0, (window_end - now).total_seconds())
    interval_for_remaining_calls = ceil(remaining_seconds / max(1, remaining_calls - 1))
    return max(300, interval_for_remaining_calls)


@shared_task
def sync_daily_fixtures_task():
    league_ids = get_active_tracked_leagues()
    if not league_ids:
        return 0

    if not api_football.can_make_request(cost=len(league_ids)):
        logger.warning(
            "Skipping daily fixture sync: need %s requests, budget usage is %s/%s",
            len(league_ids),
            api_football.get_requests_used_today(),
            max(0, settings.DAILY_REQUEST_BUDGET - settings.DAILY_REQUEST_HEADROOM),
        )
        return 0

    items = []
    today = timezone.localdate()
    for league_id in league_ids:
        if not api_football.can_make_request():
            logger.warning("Skipping remaining daily fixture sync calls: daily budget exhausted")
            return 0
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
            logger.warning("Daily fixture sync failed for league %s: %s", league_id, exc)
            return 0

    total = _sync_fixtures(items)
    if total:
        invalidate_and_publish_after_commit("fixtures", [LIVE_FIXTURES_CACHE_KEY])
    return total


@shared_task
def sync_live_scores_task():
    league_ids = get_active_tracked_leagues()
    if not league_ids:
        return 0

    window = get_today_match_window()
    if window is None:
        return 0
    window_start, window_end = window
    now = timezone.now()
    if not window_start <= now <= window_end:
        return 0

    interval = _live_poll_interval(now, window_end, len(league_ids))
    if interval is None or not api_football.can_make_request():
        logger.warning("skipped live sync: daily budget exhausted")
        return 0

    try:
        if not cache.add("api_live_sync_lock", True, timeout=60):
            return 0
    except Exception:
        logger.warning("skipped live sync: unable to acquire Redis lock")
        return 0

    try:
        last_request_at = cache.get("api_live_last_request_at")
        if last_request_at is not None and now.timestamp() - float(last_request_at) < interval:
            return 0
        if not api_football.can_make_request():
            logger.warning("skipped live sync: daily budget exhausted")
            return 0

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
    finally:
        try:
            cache.delete("api_live_sync_lock")
        except Exception:
            logger.warning("Unable to release live sync lock")


@shared_task
def sync_standings_task():
    total = 0
    changed_cache_keys = {"matches_standings:all"}
    league_ids = get_active_tracked_leagues()
    if not league_ids:
        return 0
    if not api_football.can_make_request(cost=len(league_ids)):
        logger.warning(
            "Skipping daily standings sync: need %s requests, budget usage is %s/%s",
            len(league_ids),
            api_football.get_requests_used_today(),
            max(0, settings.DAILY_REQUEST_BUDGET - settings.DAILY_REQUEST_HEADROOM),
        )
        return 0

    for league_id in league_ids:
        if not api_football.can_make_request():
            logger.warning("Skipping remaining standings sync calls: daily budget exhausted")
            return 0
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
