from django.core.cache import cache
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from .models import TickerEntry
from .serializers import TickerEntrySerializer

TICKER_CACHE_KEY = "ticker_entries_page_1"
TICKER_CACHE_TIMEOUT = 25


class TickerEntryListView(ListAPIView):
    serializer_class = TickerEntrySerializer

    def get_queryset(self):
        return TickerEntry.objects.select_related("article").filter(is_live=True).order_by(
            "-posted_at"
        )[:20]

    def list(self, request, *args, **kwargs):
        try:
            cached = cache.get(TICKER_CACHE_KEY)
        except Exception:
            cached = None
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        try:
            cache.set(TICKER_CACHE_KEY, response.data, TICKER_CACHE_TIMEOUT)
        except Exception:
            pass
        return response