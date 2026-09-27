from rest_framework.routers import DefaultRouter

from articles.views import ArticleViewSet, CategoryViewSet, VideoPostViewSet
from matches.views import FixtureViewSet, LeagueViewSet, StandingViewSet, TeamViewSet
from ticker.views import TickerEntryViewSet

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="article")
router.register("categories", CategoryViewSet, basename="category")
router.register("fixtures", FixtureViewSet, basename="fixture")
router.register("leagues", LeagueViewSet, basename="league")
router.register("standings", StandingViewSet, basename="standing")
router.register("teams", TeamViewSet, basename="team")
router.register("ticker", TickerEntryViewSet, basename="ticker")
router.register("video-posts", VideoPostViewSet, basename="video-post")
