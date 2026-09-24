from django.contrib import admin

from .models import TickerEntry


@admin.register(TickerEntry)
class TickerEntryAdmin(admin.ModelAdmin):
    list_display = ("headline", "posted_at", "is_live")
    list_filter = ("is_live", "posted_at")
    search_fields = ("headline",)
    list_editable = ("posted_at", "is_live")
    ordering = ("-posted_at",)