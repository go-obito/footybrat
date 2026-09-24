from django.contrib import admin

from .models import Article, ArticleView, Author, Category, Tag, VideoPost


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user")
    search_fields = ("display_name", "user__username")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "published_at", "is_breaking", "is_top_story")
    list_filter = ("category", "is_breaking", "is_top_story", "published_at")
    search_fields = ("title",)
    list_editable = ("published_at", "is_breaking")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tags",)


@admin.register(ArticleView)
class ArticleViewAdmin(admin.ModelAdmin):
    list_display = ("article", "viewed_at")
    list_filter = ("viewed_at",)
    search_fields = ("article__title",)
    readonly_fields = ("article", "viewed_at", "visitor_hash")


@admin.register(VideoPost)
class VideoPostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "published_at")
    list_filter = ("category", "published_at")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("published_at",)
