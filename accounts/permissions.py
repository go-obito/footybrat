EDITOR_MODELS = (
    ("articles", "article"),
    ("articles", "category"),
    ("articles", "tag"),
    ("articles", "videopost"),
    ("ticker", "tickerentry"),
)


def ensure_account_groups():
    from django.contrib.auth.models import Group, Permission
    from django.db.models import Q

    editors, _ = Group.objects.get_or_create(name="Editors")
    editor_query = Q()
    for app_label, model in EDITOR_MODELS:
        editor_query |= Q(
            content_type__app_label=app_label,
            content_type__model=model,
            codename__in=["add_" + model, "change_" + model, "view_" + model],
        )
    editor_permissions = Permission.objects.filter(editor_query)
    editors.permissions.set(editor_permissions)

    admins, _ = Group.objects.get_or_create(name="Admins")
    admins.permissions.set(Permission.objects.all())
