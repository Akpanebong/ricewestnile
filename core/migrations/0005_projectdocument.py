import django.core.validators
import django.db.models.deletion
import core.project_models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0008_profile_forum_last_seen_at"),
        ("core", "0004_project_program_area"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_type", models.CharField(choices=[("workplan", "Workplan"), ("report", "Report")], max_length=20)),
                ("file", models.FileField(upload_to=core.project_models.project_document_upload_to, validators=[django.core.validators.FileExtensionValidator(allowed_extensions=["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx"])])),
                ("workplan_period", models.CharField(blank=True, choices=[("monthly", "Monthly"), ("quarterly", "Quarterly"), ("annual", "Annual")], max_length=20)),
                ("activities_count", models.PositiveIntegerField(blank=True, null=True)),
                ("report_type", models.CharField(blank=True, choices=[("activity_report", "Activity Report"), ("monthly_report", "Monthly Report"), ("quarterly_report", "Quarterly Report"), ("annual_report", "Annual Report")], max_length=30)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="core.project")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_project_documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-uploaded_at",)},
        ),
    ]
