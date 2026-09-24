from django.urls import reverse
from rest_framework import serializers

from .models import TickerEntry


class TickerEntrySerializer(serializers.ModelSerializer):
    link = serializers.SerializerMethodField()

    class Meta:
        model = TickerEntry
        fields = ("id", "headline", "link", "posted_at")

    def get_link(self, obj):
        if obj.article_id:
            return reverse("article-detail", kwargs={"slug": obj.article.slug})
        return obj.link or None