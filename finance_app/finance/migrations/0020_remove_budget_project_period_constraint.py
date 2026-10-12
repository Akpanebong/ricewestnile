from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("finance", "0019_financebudget_unique_budget_project_period")]

    operations = [
        migrations.RemoveConstraint(
            model_name="financebudget",
            name="unique_budget_project_period",
        ),
    ]
