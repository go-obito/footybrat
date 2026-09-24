from math import ceil

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.text import slugify


class Author(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=150)
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.display_name


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Article(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    body = models.TextField(help_text="Markdown content")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="articles")
    tags = models.ManyToManyField(Tag, blank=True, related_name="articles")
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="articles")
    hero_image = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_breaking = models.BooleanField(default=False)
    is_top_story = models.BooleanField(default=False)
    top_story_order = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [GinIndex(fields=["search_vector"], name="article_search_gin")]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or "article"
            slug = base_slug
            suffix = 2
            while Article.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def read_time(self):
        word_count = len(self.body.split())
        return max(1, ceil(word_count / 200))


class ArticleView(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="views")
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    visitor_hash = models.CharField(max_length=64, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["article", "viewed_at"]),
            models.Index(fields=["article", "visitor_hash", "viewed_at"]),
        ]


class VideoPost(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    embed_url = models.URLField()
    thumbnail_url = models.URLField()
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="videos")
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [GinIndex(fields=["search_vector"], name="video_search_gin")]

    def __str__(self):
        return self.title
