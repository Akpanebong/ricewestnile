from decimal import Decimal

from django.db import migrations


def preserve_monthly_totals(apps, schema_editor):
    FinanceBudgetLine = apps.get_model("finance", "FinanceBudgetLine")
    table = schema_editor.quote_name(FinanceBudgetLine._meta.db_table)
    columns = ", ".join(schema_editor.quote_name(f"m{i:02d}") for i in range(1, 13))
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"SELECT id, {columns} FROM {table}")
        rows = cursor.fetchall()
        for row in rows:
            total = sum((value or Decimal("0.00") for value in row[1:]), Decimal("0.00"))
            cursor.execute(
                f"UPDATE {table} SET price_per_unit = %s, units = %s, frequency = %s WHERE id = %s",
                [total, Decimal("1.00"), Decimal("1.00"), row[0]],
            )


class Migration(migrations.Migration):
    dependencies = [("finance", "0016_restore_legacy_budget_lines")]

    operations = [migrations.RunPython(preserve_monthly_totals, migrations.RunPython.noop)]
