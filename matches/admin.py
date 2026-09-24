from django.contrib import admin

from .models import Fixture, League, Standing, Team


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "external_id")
    search_fields = ("name", "country")
    readonly_fields = ("name", "slug", "external_id", "country", "logo_url")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "external_id")
    search_fields = ("name",)
    readonly_fields = ("name", "slug", "external_id", "crest_url")


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    list_display = ("kickoff_at", "home_team", "away_team", "status", "home_score", "away_score")
    list_filter = ("status", "league", "kickoff_at")
    search_fields = ("home_team__name", "away_team__name")
    readonly_fields = (
        "league", "home_team", "away_team", "external_id", "kickoff_at", "matchday", "updated_at",
    )
    fields = (
        "league", "home_team", "away_team", "external_id", "kickoff_at", "status", "minute",
        "home_score", "away_score", "matchday", "updated_at",
    )


@admin.register(Standing)
class StandingAdmin(admin.ModelAdmin):
    list_display = ("league", "season", "position", "team", "points", "goal_difference")
    list_filter = ("league", "season")
    search_fields = ("team__name",)
    readonly_fields = (
        "league", "team", "position", "played", "won", "drawn", "lost", "points",
        "goal_difference", "season", "updated_at",
    )
