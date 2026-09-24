from django.db import models
from django.utils import timezone

from articles.models import Article


class TickerEntry(models.Model):
    headline = models.CharField(max_length=200)
    article = models.ForeignKey(
        Article,
        on_delete=models.SET_NULL,
        related_name="ticker_entries",
        null=True,
        blank=True,
    )
    link = models.URLField(blank=True)
    posted_at = models.DateTimeField(default=timezone.now)
    is_live = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-posted_at"]

    def __str__(self):
        return self.headline