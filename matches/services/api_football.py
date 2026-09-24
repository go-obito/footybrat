from datetime import date, datetime, timedelta

import requests
from django.conf import settings


class ApiFootballError(Exception):
    pass


def _request(endpoint, **params):
    if not settings.API_FOOTBALL_KEY:
        raise ApiFootballError("API_FOOTBALL_KEY is not configured")

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


def fetch_fixtures(league_id, season):
    today = date.today()
    response = _request(
        "fixtures",
        league=league_id,
        season=season,
        **{
            "from": (today - timedelta(days=30)).isoformat(),
            "to": (today + timedelta(days=60)).isoformat(),
        },
    )
    return [_fixture(item) for item in response]


def fetch_live_fixtures():
    return [_fixture(item) for item in _request("fixtures", live="all")]


def fetch_standings(league_id, season):
    response = _request("standings", league=league_id, season=season)
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