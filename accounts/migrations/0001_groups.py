from django.db import migrations


EDITOR_MODELS = (
    ("articles", "article"),
    ("articles", "category"),
    ("articles", "tag"),
    ("articles", "videopost"),
    ("ticker", "tickerentry"),
)


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    editors, _ = Group.objects.get_or_create(name="Editors")
    editor_permissions = Permission.objects.none()
    for app_label, model in EDITOR_MODELS:
        editor_permissions = editor_permissions | Permission.objects.filter(
            content_type__app_label=app_label,
            content_type__model=model,
            codename__in=["add_" + model, "change_" + model, "view_" + model],
        )
    editors.permissions.set(editor_permissions)

    admins, _ = Group.objects.get_or_create(name="Admins")
    admins.permissions.set(Permission.objects.all())


def remove_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Editors", "Admins"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("articles", "0004_article_search_vector_videopost_search_vector_and_more"),
        ("newsletter", "0001_initial"),
        ("ticker", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
