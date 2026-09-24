import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group


class Command(BaseCommand):
    help = "Create an editor user with a temporary password."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("email")

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError("A user with that username already exists.")
        temporary_password = secrets.token_urlsafe(12)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=temporary_password,
        )
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        editors, _ = Group.objects.get_or_create(name="Editors")
        user.groups.add(editors)
        self.stdout.write(self.style.SUCCESS(f"Created editor {username}."))
        self.stdout.write(f"Temporary password: {temporary_password}")
