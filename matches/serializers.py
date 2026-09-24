from rest_framework import serializers

from .models import Fixture, League, Standing, Team


class LeagueSerializer(serializers.ModelSerializer):
    class Meta:
        model = League
        fields = ("name", "slug", "external_id", "country", "logo_url")


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ("name", "slug", "external_id", "crest_url")


class FixtureSerializer(serializers.ModelSerializer):
    league = LeagueSerializer(read_only=True)
    home_team = TeamSerializer(read_only=True)
    away_team = TeamSerializer(read_only=True)

    class Meta:
        model = Fixture
        fields = (
            "external_id", "league", "home_team", "away_team", "kickoff_at",
            "status", "minute", "home_score", "away_score", "matchday", "updated_at",
        )


class StandingSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)

    class Meta:
        model = Standing
        fields = (
            "position", "team", "played", "won", "drawn", "lost", "points",
            "goal_difference", "season", "updated_at",
        )
