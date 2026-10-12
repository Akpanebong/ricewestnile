import re

from django.db import migrations


CODE_RE = re.compile(r"^\d+(?:\.\d+){3}$")


def normalize_codes(apps, schema_editor):
    FinanceBudgetLine = apps.get_model("finance", "FinanceBudgetLine")
    for budget in apps.get_model("finance", "FinanceBudget").objects.all().iterator():
        used = set()
        next_item = 1
        lines = FinanceBudgetLine.objects.filter(budget_id=budget.pk).order_by("pk")
        for line in lines:
            code = (line.code or "").strip()
            if CODE_RE.fullmatch(code) and code not in used:
                used.add(code)
                continue
            while f"1.1.1.{next_item}" in used:
                next_item += 1
            line.code = f"1.1.1.{next_item}"
            line.save(update_fields=["code"])
            used.add(line.code)
            next_item += 1


class Migration(migrations.Migration):
    dependencies = [("finance", "0017_preserve_budget_line_totals")]

    operations = [migrations.RunPython(normalize_codes, migrations.RunPython.noop)]
