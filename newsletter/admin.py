from django.contrib import admin

from .models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "subscribed_at", "is_confirmed", "is_active")
    list_filter = ("is_confirmed", "is_active", "subscribed_at")
    search_fields = ("email",)
    list_editable = ("is_active",)
    readonly_fields = ("email", "subscribed_at", "is_confirmed")
