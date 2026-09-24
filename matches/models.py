from django.db import models
from django.utils.text import slugify


class League(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    external_id = models.PositiveIntegerField(unique=True)
    country = models.CharField(max_length=100, blank=True)
    logo_url = models.URLField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or f"league-{self.external_id}"
        super().save(*args, **kwargs)


class Team(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    external_id = models.PositiveIntegerField(unique=True)
    crest_url = models.URLField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or f"team-{self.external_id}"
        super().save(*args, **kwargs)


class Fixture(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        LIVE = "LIVE", "Live"
        HALFTIME = "HALFTIME", "Halftime"
        FINISHED = "FINISHED", "Finished"
        POSTPONED = "POSTPONED", "Postponed"

    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name="fixtures")
    home_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_fixtures")
    away_team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_fixtures")
    external_id = models.PositiveIntegerField(unique=True)
    kickoff_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    minute = models.PositiveSmallIntegerField(null=True, blank=True)
    home_score = models.PositiveSmallIntegerField(null=True, blank=True)
    away_score = models.PositiveSmallIntegerField(null=True, blank=True)
    matchday = models.CharField(max_length=150, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kickoff_at"]
        indexes = [
            models.Index(fields=["status", "kickoff_at"]),
            models.Index(fields=["league", "kickoff_at"]),
        ]

    def __str__(self):
        return f"{self.home_team} v {self.away_team}"


class Standing(models.Model):
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name="standings")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="standings")
    position = models.PositiveSmallIntegerField()
    played = models.PositiveSmallIntegerField(default=0)
    won = models.PositiveSmallIntegerField(default=0)
    drawn = models.PositiveSmallIntegerField(default=0)
    lost = models.PositiveSmallIntegerField(default=0)
    points = models.IntegerField(default=0)
    goal_difference = models.IntegerField(default=0)
    season = models.CharField(max_length=10)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["league", "team", "season"],
                name="unique_standing_league_team_season",
            ),
        ]

    def __str__(self):
        return f"{self.league} - {self.team} ({self.season})"