from datetime import date

from django.conf import settings
from django.utils import timezone


def get_active_tracked_leagues(on_date: date | None = None) -> list[int]:
    today = on_date or timezone.localdate()
    active = []
    for value in settings.TRACKED_LEAGUES:
        try:
            league_id = int(value)
        except (TypeError, ValueError):
            continue
        windows = settings.SEASONAL_LEAGUES.get(league_id, ())
        if windows and not any(start <= today <= end for start, end in windows):
            continue
        if league_id not in active:
            active.append(league_id)
    return active