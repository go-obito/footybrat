from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .permissions import ensure_account_groups


@receiver(post_migrate)
def configure_account_groups(sender, **kwargs):
    ensure_account_groups()
