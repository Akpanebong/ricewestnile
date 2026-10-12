import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0008_profile_forum_last_seen_at"),
        ("core", "0005_projectdocument"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("confirmed", models.BooleanField(default=False)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmed_project_activities", to=settings.AUTH_USER_MODEL)),
                ("workplan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="core.projectdocument")),
            ],
            options={"ordering": ("start_date", "name")},
        ),
        migrations.AddField(
            model_name="projectdocument",
            name="activity",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reports", to="core.projectactivity"),
        ),
    ]
