from datetime import datetime, time, timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


class ApiFootballError(Exception):
    pass


class RequestBudgetExceeded(ApiFootballError):
    pass


def _request_counter_key(category=None, today=None):
    key = f"api_requests_today:{(today or timezone.localdate()).isoformat()}"
    return f"{key}:{category}" if category else key


def _legacy_request_counter_key(today=None):
    return f"api_football_requests:{(today or timezone.localdate()).isoformat()}"


def _request_counter_timeout():
    now = timezone.localtime()
    next_midnight = timezone.make_aware(
        datetime.combine(now.date() + timedelta(days=1), time.min),
        timezone.get_current_timezone(),
    )
    return max(1, int((next_midnight - now).total_seconds()))


def _soft_request_limit():
    return max(0, settings.DAILY_REQUEST_BUDGET - settings.DAILY_REQUEST_HEADROOM)


def get_requests_used_today(category=None):
    try:
        value = cache.get(_request_counter_key(category), None)
        if value is None:
            value = cache.get(_legacy_request_counter_key(), 0) if category is None else 0
        return int(value)
    except Exception:
        return None


def can_make_request(cost=1):
    """Compatibility helper; API-Football enforces the real quota."""
    return cost >= 0


def get_live_poll_budget(active_league_count):
    """Compatibility helper; no application-side live budget is enforced."""
    return None


def _record_api_request(category):
    total_key = _request_counter_key()
    category_key = _request_counter_key(category)
    timeout = _request_counter_timeout()
    initial_total = get_requests_used_today()
    if initial_total is None:
        return False
    total_incremented = False
    try:
        cache.add(total_key, initial_total, timeout=timeout)
        cache.add(category_key, 0, timeout=timeout)
        cache.incr(total_key)
        total_incremented = True
        cache.incr(category_key)
    except Exception:
        # Cache failures should never prevent an API request.
        try:
            if total_incremented:
                cache.decr(total_key)
        except Exception:
            pass
    return True


def _request(endpoint, *, category="other", **params):
    if not settings.API_FOOTBALL_KEY:
        raise ApiFootballError("API_FOOTBALL_KEY is not configured")

    _record_api_request(category)
    if category == "live":
        try:
            cache.set(
                "api_live_last_request_at",
                timezone.now().timestamp(),
                timeout=_request_counter_timeout(),
            )
        except Exception:
            pass

    try:
        response = requests.get(
            f"{settings.API_FOOTBALL_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}",
            headers={"x-apisports-key": settings.API_FOOTBALL_KEY},
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ApiFootballError(str(exc)) from exc

    if payload.get("errors"):
        raise ApiFootballError(str(payload["errors"]))
    return payload.get("response", [])


def _datetime(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _status(short):
    if short == "HT":
        return "HALFTIME"
    if short in {"1H", "2H", "ET", "P", "BT", "INT"}:
        return "LIVE"
    if short in {"FT", "AET", "PEN"}:
        return "FINISHED"
    if short in {"PST", "CANC", "ABD", "AWD", "WO"}:
        return "POSTPONED"
    return "SCHEDULED"


def _fixture(item):
    fixture = item["fixture"]
    league = item["league"]
    teams = item["teams"]
    goals = item.get("goals") or {}
    status_data = fixture.get("status") or {}
    return {
        "external_id": fixture["id"],
        "kickoff_at": _datetime(fixture["date"]),
        "status": _status(status_data.get("short")),
        "minute": status_data.get("elapsed"),
        "home_score": goals.get("home"),
        "away_score": goals.get("away"),
        "matchday": league.get("round") or "",
        "league": {
            "external_id": league["id"],
            "name": league.get("name") or f"League {league['id']}",
            "country": league.get("country") or "",
            "logo_url": league.get("logo") or "",
        },
        "home_team": {
            "external_id": teams["home"]["id"],
            "name": teams["home"]["name"],
            "crest_url": teams["home"].get("logo") or "",
        },
        "away_team": {
            "external_id": teams["away"]["id"],
            "name": teams["away"]["name"],
            "crest_url": teams["away"].get("logo") or "",
        },
    }


def fetch_fixtures(league_id, match_date, season):
    response = _request(
        "fixtures",
        category="fixtures",
        league=league_id,
        season=season,
        date=match_date.isoformat(),
    )
    return [_fixture(item) for item in response]


def fetch_live_fixtures(league_ids):
    selected_leagues = sorted({int(league_id) for league_id in league_ids})
    if not selected_leagues:
        return []
    response = _request(
        "fixtures",
        category="live",
        live="-".join(str(league_id) for league_id in selected_leagues),
    )
    return [_fixture(item) for item in response]


def fetch_standings(league_id, season):
    response = _request("standings", category="standings", league=league_id, season=season)
    rows = []
    for group in response:
        league = group.get("league", {})
        for table in league.get("standings", []):
            for item in table:
                rows.append(
                    {
                        "league": {
                            "external_id": league["id"],
                            "name": league.get("name") or f"League {league['id']}",
                            "country": league.get("country") or "",
                            "logo_url": league.get("logo") or "",
                        },
                        "team": {
                            "external_id": item["team"]["id"],
                            "name": item["team"]["name"],
                            "crest_url": item["team"].get("logo") or "",
                        },
                        "position": item["rank"],
                        "played": item["all"]["played"],
                        "won": item["all"]["win"],
                        "drawn": item["all"]["draw"],
                        "lost": item["all"]["lose"],
                        "points": item["points"],
                        "goal_difference": item["goalsDiff"],
                        "season": str(season),
                    }
                )
    return rows