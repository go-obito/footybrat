from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from django.test import TestCase
from django.urls import reverse

from articles.models import Article, Author, Category


class AccountsApiTests(TestCase):
    def test_registration_login_and_me(self):
        register_response = self.client.post(
            reverse("account-register"),
            {
                "username": "supporter",
                "email": "supporter@example.com",
                "password": "A-long-valid-password-123!",
            },
            format="json",
        )

        self.assertEqual(register_response.status_code, 201)
        self.assertTrue(get_user_model().objects.filter(username="supporter").exists())
        registration_tokens = register_response.json()
        self.assertIn("access", registration_tokens)
        self.assertIn("refresh", registration_tokens)

        login_response = self.client.post(
            reverse("account-login"),
            {"username": "supporter", "password": "A-long-valid-password-123!"},
            format="json",
        )

        self.assertEqual(login_response.status_code, 200)
        access_token = login_response.json()["access"]

        me_without_auth = self.client.get(reverse("account-me"))
        me_with_auth = self.client.get(
            reverse("account-me"),
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

        self.assertEqual(me_without_auth.status_code, 401)
        self.assertEqual(me_with_auth.status_code, 200)
        self.assertEqual(me_with_auth.json()["username"], "supporter")

    def test_editor_can_publish_articles_but_cannot_manage_subscribers_or_users(self):
        editor = get_user_model().objects.create_user(
            username="editor",
            email="editor@example.com",
            password="A-long-valid-password-123!",
            is_staff=True,
        )
        editor.groups.add(Group.objects.get(name="Editors"))
        category = Category.objects.create(name="Transfers", slug="transfers")
        author = Author.objects.create(user=editor, display_name="Editor")
        self.client.force_login(editor)

        self.assertTrue(editor.has_perm("articles.add_article"))
        response = self.client.post(
            "/admin/articles/article/add/",
            {
                "title": "Admin published article",
                "slug": "admin-published-article",
                "body": "A published report.",
                "category": category.pk,
                "author": author.pk,
                "hero_image": "",
                "published_at_0": "2026-09-24",
                "published_at_1": "12:00:00",
                "is_breaking": "0",
                "is_top_story": "0",
                "top_story_order": "",
                "tags": [],
            },
            HTTP_HOST="localhost",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Article.objects.filter(slug="admin-published-article", published_at__isnull=False).exists(),
        )
        self.assertNotEqual(self.client.get("/admin/newsletter/subscriber/", HTTP_HOST="localhost").status_code, 200)
        self.assertNotEqual(self.client.get("/admin/auth/user/", HTTP_HOST="localhost").status_code, 200)