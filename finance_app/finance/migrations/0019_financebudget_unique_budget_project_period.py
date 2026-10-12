from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0018_normalize_budget_hierarchy_codes")]

    operations = [
        migrations.AddConstraint(
            model_name="financebudget",
            constraint=models.UniqueConstraint(
                fields=("project", "period_start", "period_end"),
                name="unique_budget_project_period",
            ),
        ),
    ]
