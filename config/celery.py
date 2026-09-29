import os

from celery import Celery
from celery.signals import worker_ready

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_ready.connect
def sync_matches_when_worker_is_ready(sender=None, **kwargs):
    """Refresh today's fixtures whenever a worker comes online."""
    if sender is not None:
        sender.app.send_task("matches.tasks.sync_daily_fixtures_task")
