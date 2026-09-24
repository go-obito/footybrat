from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Article, ArticleView, Author, Category, VideoPost
from .tasks import TRENDING_CACHE_KEY


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "articles-tests",
        }
    }
)
class PublicApiTests(TestCase):
    def setUp(self):
        cache.clear()
        user = get_user_model().objects.create_user(username="editor", password="password")
        self.author = Author.objects.create(user=user, display_name="Editor")
        self.category = Category.objects.create(name="Premier League", slug="premier-league")

    def create_article(self, title, **kwargs):
        defaults = {
            "body": "A short match report.",
            "category": self.category,
            "author": self.author,
            "published_at": timezone.now(),
        }
        defaults.update(kwargs)
        return Article.objects.create(title=title, **defaults)

    def test_unpublished_articles_are_not_public(self):
        published = self.create_article("Published")
        draft = self.create_article("Draft", published_at=None)
        future = self.create_article("Future", published_at=timezone.now() + timedelta(hours=1))

        response = self.client.get(reverse("article-list"))

        self.assertEqual(response.status_code, 200)
        returned_slugs = [article["slug"] for article in response.json()["results"]]
        self.assertIn(published.slug, returned_slugs)
        self.assertNotIn(draft.slug, returned_slugs)
        self.assertNotIn(future.slug, returned_slugs)

    def test_top_stories_respect_story_order(self):
        second = self.create_article("Second", is_top_story=True, top_story_order=2)
        first = self.create_article("First", is_top_story=True, top_story_order=1)
        self.create_article("Not top")

        response = self.client.get(reverse("article-top-stories"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["slug"] for item in response.json()], [first.slug, second.slug])

    def test_health_check(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_article_view_is_deduplicated_within_30_minutes(self):
        article = self.create_article("Viewed article")

        first_response = self.client.post(reverse("article-record-view", kwargs={"slug": article.slug}))
        second_response = self.client.post(reverse("article-record-view", kwargs={"slug": article.slug}))

        self.assertEqual(first_response.status_code, 204)
        self.assertEqual(second_response.status_code, 204)
        self.assertEqual(ArticleView.objects.filter(article=article).count(), 1)

    def test_trending_orders_articles_by_recent_view_count(self):
        most_viewed = self.create_article("Most viewed")
        next_most_viewed = self.create_article("Next most viewed")
        least_viewed = self.create_article("Least viewed")
        ArticleView.objects.bulk_create(
            [
                ArticleView(article=most_viewed, visitor_hash=f"most-{index}")
                for index in range(3)
            ]
            + [
                ArticleView(article=next_most_viewed, visitor_hash="next-1"),
                ArticleView(article=next_most_viewed, visitor_hash="next-2"),
                ArticleView(article=least_viewed, visitor_hash="least-1"),
            ]
        )

        response = self.client.get(reverse("article-trending"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["slug"] for item in response.json()],
            [most_viewed.slug, next_most_viewed.slug, least_viewed.slug],
        )

    def test_trending_uses_populated_cache(self):
        cached_payload = [{"title": "Cached", "slug": "cached"}]
        cache.set(TRENDING_CACHE_KEY, cached_payload)

        response = self.client.get(reverse("article-trending"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), cached_payload)

    def test_unpublished_videos_are_not_public(self):
        VideoPost.objects.create(
            title="Published highlights",
            slug="published-highlights",
            embed_url="https://www.youtube.com/embed/published",
            thumbnail_url="https://example.com/published.jpg",
            category=self.category,
            published_at=timezone.now(),
        )
        VideoPost.objects.create(
            title="Draft highlights",
            slug="draft-highlights",
            embed_url="https://www.youtube.com/embed/draft",
            thumbnail_url="https://example.com/draft.jpg",
            category=self.category,
        )

        response = self.client.get(reverse("video-list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["slug"] for item in response.json()["results"]], ["published-highlights"])

    def test_search_ranks_title_matches_and_excludes_unpublished_content(self):
        title_match = self.create_article("Transfer target confirmed", body="A short update.")
        body_match = self.create_article("Club update", body="Transfer discussions continue.")
        self.create_article("Unpublished transfer", body="Transfer", published_at=None)
        VideoPost.objects.create(
            title="Deal wire video",
            slug="transfer-video",
            description="Latest transfer footage",
            embed_url="https://www.youtube.com/embed/transfer",
            thumbnail_url="https://example.com/transfer.jpg",
            category=self.category,
            published_at=timezone.now(),
        )

        response = self.client.get(reverse("search"), {"q": "transfer"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["slug"], title_match.slug)
        self.assertEqual(response.json()["results"][0]["type"], "article")
        returned_slugs = {item["slug"] for item in response.json()["results"]}
        self.assertIn(body_match.slug, returned_slugs)
        self.assertIn("transfer-video", returned_slugs)
        self.assertNotIn("unpublished-transfer", returned_slugs)

    def test_empty_search_query_is_rejected(self):
        response = self.client.get(reverse("search"), {"q": " "})

        self.assertEqual(response.status_code, 400)

    def test_article_save_invalidates_latest_cache(self):
        self.client.get(reverse("article-latest"))
        newer = self.create_article("New latest article", published_at=timezone.now())

        response = self.client.get(reverse("article-latest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["slug"], newer.slug)
