from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0021_restore_pre_hierarchy_budget_codes")]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="financebudgetline",
                    name=f"m{i:02d}",
                    field=models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        default=0,
                        editable=False,
                        max_digits=16,
                        null=True,
                    ),
                )
                for i in range(1, 13)
            ],
        ),
    ]
