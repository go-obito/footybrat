from django.conf import settings
from django.contrib.admin import AdminSite

from matches.services.api_football import get_requests_used_today


class FootybratAdminSite(AdminSite):
    index_template = "admin/index_with_api_usage.html"

    def index(self, request, extra_context=None):
        extra_context = dict(extra_context or {})
        extra_context.update(
            api_requests_used=get_requests_used_today(),
            api_request_budget=settings.DAILY_REQUEST_BUDGET,
            api_request_soft_limit=max(
                0,
                settings.DAILY_REQUEST_BUDGET - settings.DAILY_REQUEST_HEADROOM,
            ),
        )
        return super().index(request, extra_context=extra_context)