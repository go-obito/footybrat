from rest_framework import serializers

from .models import Article, Author, Category, Tag, VideoPost


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("name", "slug")


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("name",)


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ("display_name", "bio")


class ArticleSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    author = AuthorSerializer(read_only=True)
    read_time = serializers.ReadOnlyField()

    class Meta:
        model = Article
        fields = (
            "title", "slug", "body", "category", "tags", "author", "hero_image",
            "published_at", "is_breaking", "is_top_story", "top_story_order",
            "created_at", "updated_at", "read_time",
        )


class ArticleHeadlineSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    read_time = serializers.ReadOnlyField()

    class Meta:
        model = Article
        fields = ("title", "slug", "category", "hero_image", "published_at", "is_breaking", "read_time")


class VideoPostSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)

    class Meta:
        model = VideoPost
        fields = (
            "title", "slug", "description", "embed_url", "thumbnail_url",
            "duration_seconds", "category", "published_at", "created_at",
        )
