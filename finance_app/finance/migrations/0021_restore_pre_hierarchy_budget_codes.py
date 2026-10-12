from django.db import migrations


def restore_legacy_codes(apps, schema_editor):
    FinanceBudgetLine = apps.get_model("finance", "FinanceBudgetLine")
    for line in FinanceBudgetLine.objects.order_by("pk"):
        legacy_code = f"LINE-{line.pk}"
        if line.code != legacy_code:
            line.code = legacy_code
            line.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [("finance", "0020_remove_budget_project_period_constraint")]

    operations = [migrations.RunPython(restore_legacy_codes, migrations.RunPython.noop)]
