from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import TickerEntry


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ticker-tests",
        }
    }
)
class TickerApiTests(TestCase):
    def setUp(self):
        cache.clear()
        now = timezone.now()
        self.old_entry = TickerEntry.objects.create(
            headline="Older deal update",
            posted_at=now - timedelta(minutes=5),
            is_live=True,
        )
        self.new_entry = TickerEntry.objects.create(
            headline="Newest deal update",
            posted_at=now,
            is_live=True,
        )
        TickerEntry.objects.create(
            headline="Retired rumor",
            posted_at=now + timedelta(minutes=1),
            is_live=False,
        )

    def test_only_live_entries_are_returned_newest_first(self):
        response = self.client.get(reverse("ticker-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [entry["id"] for entry in response.json()["results"]],
            [self.new_entry.id, self.old_entry.id],
        )
        self.assertNotIn("Retired rumor", response.content.decode())

    def test_second_request_uses_cache(self):
        url = reverse("ticker-list")
        self.client.get(url)
        cached_headline = self.new_entry.headline
        TickerEntry.objects.create(
            headline="New database row",
            posted_at=timezone.now() + timedelta(minutes=2),
            is_live=True,
        )

        with self.assertNumQueries(0):
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["headline"], cached_headline)
