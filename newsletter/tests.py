from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Subscriber


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "newsletter-tests",
        }
    }
)
class NewsletterApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("newsletter-subscribe")

    def test_duplicate_signup_is_idempotent_and_reactivates(self):
        subscriber = Subscriber.objects.create(email="fan@example.com", is_active=False)

        first = self.client.post(self.url, {"email": "FAN@example.com"}, format="json")
        second = self.client.post(self.url, {"email": "fan@example.com"}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)
        self.assertEqual(Subscriber.objects.count(), 1)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(self.url, {"email": "not-an-email"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Subscriber.objects.count(), 0)

    def test_subscription_is_rate_limited(self):
        responses = [
            self.client.post(self.url, {"email": f"fan{index}@example.com"}, format="json")
            for index in range(6)
        ]

        self.assertEqual([response.status_code for response in responses[:5]], [200] * 5)
        self.assertEqual(responses[5].status_code, 429)