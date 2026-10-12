from django.db import migrations, models
import django.db.models.deletion


def seed_budget_line_codes(apps, schema_editor):
    FinanceBudgetLine = apps.get_model("finance", "FinanceBudgetLine")
    for line in FinanceBudgetLine.objects.filter(code__isnull=True).order_by("pk"):
        line.code = f"LINE-{line.pk}"
        line.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [("finance", "0015_alter_budgetperformance_options_and_more")]

    operations = [
        migrations.AddField(
            model_name="financebudgetline",
            name="code",
            field=models.CharField(max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="financebudgetline",
            name="description",
            field=models.TextField(default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="financebudgetline",
            name="unit",
            field=models.CharField(blank=True, default="", max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="financebudgetline",
            name="price_per_unit",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=16),
        ),
        migrations.AddField(
            model_name="financebudgetline",
            name="units",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="financebudgetline",
            name="frequency",
            field=models.DecimalField(decimal_places=2, default=1, max_digits=12),
        ),
        migrations.RunPython(seed_budget_line_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="financebudgetline",
            name="code",
            field=models.CharField(max_length=50),
        ),
        migrations.AddConstraint(
            model_name="financebudgetline",
            constraint=models.UniqueConstraint(fields=("budget", "code"), name="unique_budget_line_code"),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="financebudgetline",
                    name="unique_budget_line_category",
                ),
                migrations.RemoveField(model_name="financebudgetline", name="category"),
                *[
                    migrations.RemoveField(model_name="financebudgetline", name=f"m{i:02d}")
                    for i in range(1, 13)
                ],
                migrations.AlterModelOptions(
                    name="financebudgetline",
                    options={"ordering": ("code", "id")},
                ),
                migrations.AlterModelOptions(
                    name="budgetperformance",
                    options={"ordering": ("-period", "line__code")},
                ),
            ],
        ),
    ]
